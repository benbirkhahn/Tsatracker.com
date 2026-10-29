"""Regression checks for screening lane, freshness, and historical integrity."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class DataCorrectnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A separate module prevents its configuration from leaking into the
        # existing frontend suite, or depending on test discovery order.
        name = "tsa_data_correctness_app"
        spec = importlib.util.spec_from_file_location(name, ROOT / "app.py")
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[name] = cls.module
        with patch.dict(os.environ, {"ENABLE_POLLER": "false", "SUPABASE_URL": "", "SUPABASE_SERVICE_ROLE_KEY": ""}):
            spec.loader.exec_module(cls.module)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tsa-data-tests-")
        self.addCleanup(self.temp.cleanup)
        self.now = datetime(2026, 10, 2, 16, 0, tzinfo=timezone.utc)
        self.m = self.module
        for name, value in {
            "DB_PATH": str(Path(self.temp.name) / "test.db"),
            "ENABLE_POLLER": False,
            "SUPABASE_ENABLED": False,
            "_db_initialized": True,
        }.items():
            patcher = patch.object(self.m, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        archive = patch.object(self.m, "recovered_airport_history", return_value=[])
        archive.start()
        self.addCleanup(archive.stop)
        clock = patch.object(self.m, "utc_now", return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)
        collector = patch.object(self.m, "collect_once", return_value={"ok": [{"airport": "PHL", "rows": 1}], "errors": []})
        self.collector = collector.start()
        self.addCleanup(collector.stop)
        self.m.init_db()
        self.m.app.config["TESTING"] = True
        self.client = self.m.app.test_client()

    def sample(self, wait=30, lane="STANDARD", code="PHL", checkpoint="A", age=0):
        return {"airport_code": code, "checkpoint": checkpoint, "wait_minutes": wait,
                "lane_type": lane, "source": "https://airport.example/waits",
                "captured_at": (self.now - timedelta(minutes=age)).isoformat()}

    def store(self, *rows):
        self.m.db_insert_rows(list(rows))

    def test_archive_fills_missing_days_without_overlapping_or_becoming_live(self):
        self.store(self.sample(10, code="DFW", age=1440), self.sample(10, code="DFW", age=1439), self.sample(10, code="DFW", age=1438))
        hour = self.now.astimezone(self.m.ZoneInfo("America/Chicago")).hour
        def bucket(days, value, lane="STANDARD", bucket_hour=hour):
            return {"airport": "DFW", "date": (self.now-timedelta(days=days)).date().isoformat(),
                    "hour": bucket_hour, "lane": lane, "mean": value, "samples": 60}
        archive = [bucket(1, 100), bucket(2, 30), bucket(3, 0), bucket(31, 180), bucket(0, 180), bucket(2, 180, bucket_hour=(hour+1)%24)]
        with patch.object(self.m, "recovered_airport_history", return_value=archive):
            result = self.m.historical_outage_estimates("DFW", [])
            lane = result["lanes"]["STANDARD"]
            self.assertEqual(lane["days"], 3)
            self.assertEqual(lane["archiveDays"], 2)
            self.assertEqual(lane["minutes"], 13.3)
            self.assertEqual(lane["samples"], 123)
            self.assertFalse(result["isLive"])
            recovered = [self.sample(4, code="DFW"), self.sample(2, code="DFW", lane="PRECHECK")]
            self.assertIsNone(self.m.historical_outage_estimates("DFW", recovered))
        with sqlite3.connect(self.m.DB_PATH) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0], 3)

    def test_historical_outage_fallback_and_automatic_recovery(self):
        for code in ("DFW", "IAH", "MCO"):
            with self.subTest(code=code):
                self.store(self.sample(0, code=code, age=1440),
                           self.sample(20, code=code, age=2880),
                           self.sample(20, code=code, age=2881),
                           self.sample(4, code=code, lane="PRECHECK", age=1440),
                           self.sample(8, code=code, lane="PRECHECK", age=2880),
                           self.sample(8, code=code, lane="PRECHECK", age=2881),
                           self.sample(100, code=code, lane="PRIORITY", age=1440))
                # Use the same local hour: minute -1 above crosses the hour.
                with sqlite3.connect(self.m.DB_PATH) as conn:
                    conn.execute("UPDATE samples SET captured_at = ? WHERE airport_code = ? AND captured_at = ?",
                                 ((self.now - timedelta(minutes=2879)).isoformat(), code,
                                  (self.now - timedelta(minutes=2881)).isoformat()))
                with patch.object(self.m, "community_wait_for_code", return_value=None):
                    payload = self.m.normalized_current_wait_for_code(code, rows=[])
                    self.assertEqual(payload["sourceReason"], "historical_outage_estimate")
                    self.assertEqual(payload["currentWait"]["standard"], 10)
                    self.assertIsNone(payload["currentWait"]["observedAt"])
                    estimates = payload["historicalEstimate"]["lanes"]
                    self.assertEqual(estimates["PRECHECK"]["minutes"], 6)
                    self.assertEqual(estimates["STANDARD"]["days"], 2)
                    recovered = [self.sample(0, code=code), self.sample(2, code=code, lane="PRECHECK")]
                    self.assertIsNone(self.m.historical_outage_estimates(code, recovered))
                    self.assertEqual(self.m.normalized_current_wait_for_code(code, recovered)["sourceType"], "live_direct")
                    partial = self.m.historical_outage_estimates(code, recovered[:1])
                    self.assertEqual(list(partial["lanes"]), ["PRECHECK"])
                    stale = [dict(r, captured_at=(self.now-timedelta(minutes=16)).isoformat()) for r in recovered]
                    self.assertIsNotNone(self.m.historical_outage_estimates(code, stale))

    def test_historical_fallback_requires_recent_samples_and_matching_hour(self):
        self.store(self.sample(40, code="DFW", age=1440),
                   self.sample(40, code="DFW", age=1439),
                   self.sample(80, code="DFW", age=2880+60),
                   self.sample(80, code="DFW", age=31*1440),
                   self.sample(80, code="DFW", age=-1440))
        with sqlite3.connect(self.m.DB_PATH) as conn:
            before = conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
        result = self.m.historical_outage_estimates("DFW", [])
        self.assertIsNone(result["lanes"]["STANDARD"]["minutes"])
        self.assertEqual(result["lanes"]["STANDARD"]["days"], 1)
        self.assertIsNone(result["lanes"]["PRECHECK"]["minutes"])
        self.assertIsNone(self.m.historical_outage_estimates("PHL", []))
        with sqlite3.connect(self.m.DB_PATH) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0], before)
        self.store(self.sample(40, code="DFW", age=1438))
        sparse = self.m.historical_outage_estimates("DFW", [])["lanes"]["STANDARD"]
        self.assertEqual(sparse["minutes"], 40)
        self.assertEqual(sparse["days"], 1)

    def test_standard_mean_excludes_other_lanes_and_retains_zero(self):
        self.store(self.sample(30), self.sample(0, checkpoint="B"),
                   self.sample(2, lane="PRECHECK"), self.sample(1, lane="CLEAR"))
        current = self.m.normalized_current_wait_for_code("PHL")
        self.assertEqual(current["currentWait"]["standard"], 15)
        self.assertEqual(current["currentWait"]["precheckWait"], 2)
        self.assertEqual(current["sourceType"], "live_direct")
        self.assertEqual(current["currentWait"]["observedAt"], self.now.isoformat())

    def test_iah_customs_and_premier_never_lower_standard_departure_wait(self):
        self.store(self.sample(20, code="IAH", checkpoint="IAH Terminal A North"),
                   self.sample(1, code="IAH", checkpoint="Int'l Arrivals Customs Checkpoint"),
                   self.sample(2, code="IAH", checkpoint="IAH Terminal C North Premier"))
        payload = self.m.normalized_current_wait_for_code("IAH")
        self.assertEqual(payload["currentWait"]["standard"], 20)
        self.assertEqual({r["lane_type"] for r in self.m.latest_for_code("IAH")},
                         {"STANDARD", "ARRIVALS_CUSTOMS", "PRIORITY"})

    def test_precheck_only_is_never_presented_as_live_standard(self):
        self.store(self.sample(0, lane="PRECHECK"))
        payload = self.m.normalized_current_wait_for_code("PHL")
        self.assertEqual(payload["sourceType"], "estimated_fallback")
        self.assertEqual(payload["sourceReason"], "standard_lane_unavailable")
        self.assertEqual(payload["currentWait"]["precheckWait"], 0)
        self.assertIsNone(payload["currentWait"]["observedAt"])

    def test_snapshot_preserves_source_and_recovers_lane_from_legacy_label(self):
        self.store(self.sample(3, checkpoint="Terminal A TSA PreCheck"), self.sample(20))
        snapshot = self.m.latest_for_code("PHL")
        self.assertEqual({row["lane_type"] for row in snapshot}, {"STANDARD", "PRECHECK"})
        self.assertTrue(all(row["source"] == "https://airport.example/waits" for row in snapshot))
        self.assertEqual(self.m.normalized_current_wait_for_code("PHL")["currentWait"]["standard"], 20)

    def test_live_network_rankings_exclude_estimates_and_community(self):
        self.store(self.sample(0, code="PHL"), self.sample(30, code="MIA"),
                   self.sample(2, lane="PRECHECK", code="LAX"))
        with sqlite3.connect(self.m.DB_PATH) as conn:
            conn.executemany("INSERT INTO user_reports (airport_code, level, current_wait, reported_at) VALUES (?, ?, ?, ?)",
                             [("BOS", "low", 1, self.now.isoformat())] * 2)
        overview = self.m.build_airport_overview_context()
        self.assertEqual(overview["live_count"], 2)
        self.assertEqual(overview["community_count"], 1)
        self.assertEqual(overview["estimated_count"], len(self.m.LIVE_AIRPORTS) - 3)
        self.assertEqual(overview["overall_average"], 15)
        self.assertEqual(overview["fastest_airport"]["code"], "PHL")
        self.assertEqual(overview["slowest_airport"]["code"], "MIA")
        bos = next(row for row in overview["airport_summaries"] if row["code"] == "BOS")
        self.assertFalse(bos["is_live"])
        self.assertIn("lane unspecified", bos["source_label"])

    def test_no_live_network_returns_unknown_not_zero(self):
        result = self.m.build_airport_overview_context()
        self.assertIsNone(result["overall_average"])
        self.assertIsNone(result["fastest_airport"])
        self.assertIsNone(result["slowest_airport"])

    def test_fallback_uses_airport_local_hour(self):
        # 16:00 UTC is 09:00 at LAX, which has a different modeled baseline.
        result = self.m.normalized_current_wait_for_code("LAX")
        expected = self.m.estimated_wait_for_hour(9, self.m.AIRPORT_FACTORS["LAX"])
        self.assertEqual(result["currentWait"]["standard"], round(expected, 1))
        self.assertEqual(result["timezone"], "America/Los_Angeles")
        self.assertEqual(self.m.format_airport_timestamp("JFK", "2026-10-02T19:10:00+00:00"), "Oct 2, 3:10 PM EDT")
        self.assertEqual(self.m.format_airport_timestamp("LAX", "2026-10-02T19:10:00+00:00"), "Oct 2, 12:10 PM PDT")

    def test_forecast_now_aggregates_latest_standard_per_checkpoint(self):
        self.store(self.sample(60, age=10), self.sample(30, age=2),
                   self.sample(0, checkpoint="B", age=1), self.sample(2, lane="PRECHECK"),
                   self.sample(1, lane="PRIORITY"))
        payload = self.client.get("/api/forecast-data?airport=PHL").get_json()
        self.assertEqual(payload["now"]["standard"], 15)
        self.assertEqual(payload["now"]["timestamp"], (self.now - timedelta(minutes=1)).isoformat())
        self.assertEqual(payload["now"]["sourceType"], "live_direct")
        self.assertEqual(payload["coverage"]["standardSamples"], 3)
        self.assertEqual(payload["coverage"]["precheckSamples"], 1)

    def test_stale_history_does_not_become_now(self):
        self.store(self.sample(42, age=60))
        payload = self.client.get("/api/forecast-data?airport=PHL").get_json()
        self.assertIsNone(payload["now"]["standard"])
        self.assertIsNone(payload["now"]["timestamp"])
        self.assertEqual(payload["hours"][11]["standard"], 42)
        self.assertEqual(payload["coverage"]["daysWithSamples"], 1)

    def test_empty_forecast_and_invalid_values_stay_null(self):
        # SQLite accepts Infinity; it must never serialize as a chart reading.
        self.store(self.sample(float("inf")), self.sample(-3, checkpoint="B"),
                   self.sample(20, checkpoint="C", age=-10))
        response = self.client.get("/api/forecast-data?airport=PHL")
        payload = response.get_json()
        self.assertIsNone(payload["now"]["standard"])
        self.assertTrue(all(row["standard"] is None for row in payload["hours"]))
        self.assertEqual(payload["coverage"]["standardSamples"], 0)
        self.assertNotIn("Infinity", response.get_data(as_text=True))
        self.assertTrue(all(row["avg_wait"] is None for row in self.m.historical_24h_average_for_airport("PHL")))

    def test_trend_uses_standard_and_preserves_reported_zero(self):
        self.store(self.sample(30, age=30), self.sample(0),
                   self.sample(0, lane="PRECHECK", age=30), self.sample(90, lane="PRECHECK"),
                   self.sample(0, checkpoint="B TSA PreCheck", age=30),
                   self.sample(100, checkpoint="B TSA PreCheck"))
        self.assertEqual(self.m.compute_airport_trends()["PHL"], {"direction": "falling", "delta": -30})

    def test_historical_apis_share_standard_only_definition(self):
        self.store(self.sample(0), self.sample(80, lane="PRECHECK"))
        average = self.client.get("/api/historical-average?airport=PHL&hour=12").get_json()
        self.assertEqual(average["avg_wait"], 0)
        self.assertEqual(average["description"], "under 1 minute")
        self.assertEqual(average["lane_type"], "STANDARD")
        peaks = self.client.get("/api/peak-hours?airport=PHL").get_json()
        self.assertEqual(len(peaks["peak_hours"]), 1)
        self.assertEqual(peaks["peak_hours"][0]["avg_wait"], 0)

    def test_calculator_payload_exposes_timezone_and_source(self):
        self.store(self.sample(10))
        with self.m.app.test_request_context("/when-should-i-leave"), patch.object(self.m, "render_template", return_value="rendered") as render:
            self.m.when_should_i_leave_page()
        airports = json.loads(render.call_args.kwargs["calc_airports_json"])
        self.assertEqual(airports["PHL"]["timezone"], "America/New_York")
        self.assertEqual(airports["PHL"]["sourceType"], "live_direct")
        self.assertEqual(airports["PHL"]["updatedAt"], self.now.isoformat())

    def test_standard_aggregate_migration_is_idempotent_and_preserves_legacy(self):
        with sqlite3.connect(self.m.DB_PATH) as conn:
            conn.execute("INSERT INTO hourly_wait_aggregates VALUES (?, ?, ?, ?, ?, ?)",
                         ("PHL", "2026-10-01", 12, 999, 9, self.now.isoformat()))
        self.store(self.sample(30), self.sample(0, checkpoint="B"),
                   self.sample(2, lane="PRECHECK"), self.sample(1, lane="CLEAR"),
                   self.sample(4, checkpoint="Terminal A TSA PreCheck"))
        for _ in range(2):
            noon = self.m.historical_24h_average_for_airport("PHL")[12]
            self.assertEqual((noon["avg_wait"], noon["samples"]), (15, 2))
        # Pruned raw data must not destroy a safely accumulated bucket.
        with sqlite3.connect(self.m.DB_PATH) as conn:
            conn.execute("DELETE FROM samples")
        self.m.refresh_hourly_aggregates_from_local_samples("PHL")
        self.assertEqual(self.m.historical_24h_average_for_airport("PHL")[12]["samples"], 2)
        self.store(self.sample(60, checkpoint="C"))
        noon = self.m.historical_24h_average_for_airport("PHL")[12]
        self.assertEqual((noon["avg_wait"], noon["samples"]), (30, 3))
        with sqlite3.connect(self.m.DB_PATH) as conn:
            legacy = conn.execute("SELECT wait_sum, sample_count FROM hourly_wait_aggregates").fetchall()
        self.assertEqual(legacy, [(999, 9)])

    def test_mixed_legacy_history_without_raw_samples_is_not_relabelled_standard(self):
        with sqlite3.connect(self.m.DB_PATH) as conn:
            conn.execute("INSERT INTO hourly_wait_aggregates VALUES (?, ?, ?, ?, ?, ?)",
                         ("PHL", "2026-10-01", 12, 999, 9, self.now.isoformat()))
        self.assertTrue(all(row["avg_wait"] is None for row in self.m.historical_24h_average_for_airport("PHL")))

    def test_backfill_is_bounded_reports_pending_and_finishes_without_skipping(self):
        rows = [self.sample(wait, checkpoint=str(wait)) for wait in [10, 20, 30, 40, 50]]
        with patch.object(self.m, "STANDARD_AGGREGATE_BATCH_SIZE", 2):
            self.store(*rows)
            self.assertTrue(self.m.standard_history_backfill_pending("PHL"))
            self.assertEqual(self.m.read_hourly_aggregate_rows("PHL")[12]["samples"], 2)
            partial = self.client.get("/api/history-24h-average?airport=PHL").get_json()
            self.assertTrue(partial["history_backfill_pending"])
            self.assertEqual(partial["rows"][12]["samples"], 4)
            # The collection path uses the same cursor, including on retry.
            self.m.update_hourly_aggregates_for_rows(rows)
            complete = self.client.get("/api/history-24h-average?airport=PHL").get_json()
            self.assertFalse(complete["history_backfill_pending"])
            self.assertEqual(complete["rows"][12]["samples"], 5)
            self.assertEqual(complete["rows"][12]["avg_wait"], 30)
        with sqlite3.connect(self.m.DB_PATH) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0], 5)

    def test_collect_now_requires_configured_token(self):
        with patch.object(self.m, "COLLECT_NOW_TOKEN", None):
            self.assertEqual(self.client.post("/api/collect-now").status_code, 503)
        with patch.object(self.m, "COLLECT_NOW_TOKEN", "test-only-token"):
            self.assertEqual(self.client.post("/api/collect-now").status_code, 401)
            self.assertEqual(self.client.post("/api/collect-now", headers={"x-collect-token": "wrong"}).status_code, 401)
            self.collector.assert_not_called()
            self.assertEqual(self.client.post("/api/collect-now", headers={"x-collect-token": "test-only-token"}).status_code, 200)
            self.collector.assert_called_once()
    def test_collect_now_returns_failure_status_only_when_no_airport_succeeds(self):
        results = [
            ({"ok": [{"airport": "PHL", "rows": 2}], "errors": []}, 200),
            ({"ok": [{"airport": "PHL", "rows": 2}], "errors": [{"airport": "BOS", "error": "offline"}]}, 200),
            ({"ok": [], "errors": [{"airport": "PHL", "error": "offline"}]}, 502),
        ]
        with patch.object(self.m, "COLLECT_NOW_TOKEN", "test-only-token"):
            for result, expected_status in results:
                with self.subTest(expected_status=expected_status, result=result), patch.object(
                    self.m, "collect_once", return_value=result
                ):
                    response = self.client.post(
                        "/api/collect-now",
                        headers={"x-collect-token": "test-only-token"},
                    )
                    self.assertEqual(response.status_code, expected_status)
                    self.assertEqual(response.get_json(), result)

    def test_wsgi_import_starts_runtime_and_runtime_start_is_idempotent(self):
        import importlib

        previous_wsgi = sys.modules.pop("wsgi", None)
        try:
            with patch.dict(sys.modules, {"app": self.m}), patch.object(
                self.m, "start_web_runtime_once"
            ) as start_runtime:
                module = importlib.import_module("wsgi")
                self.assertIs(module.app, self.m.app)
                start_runtime.assert_called_once_with()
        finally:
            sys.modules.pop("wsgi", None)
            if previous_wsgi is not None:
                sys.modules["wsgi"] = previous_wsgi

        with patch.object(self.m, "_db_initialized", False), patch.object(
            self.m, "_poller_started", False
        ), patch.object(self.m, "ENABLE_POLLER", True), patch.object(
            self.m, "init_db"
        ) as init_db, patch.object(self.m.threading, "Thread") as thread:
            self.m.start_web_runtime_once()
            self.m.start_web_runtime_once()
            init_db.assert_called_once_with()
            thread.assert_called_once()
            thread.return_value.start.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
