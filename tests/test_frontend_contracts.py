import importlib
import json
import os
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


CORE_ROUTES = (
    "/",
    "/airports",
    "/airport-security-wait-times",
    "/best-time-to-get-to-the-airport",
    "/when-should-i-leave",
    "/about",
    "/methodology",
    "/contact",
    "/privacy",
    "/terms",
    "/guide/tsa-wait-times",
    "/guide/tsa-precheck-clear",
)

AIRPORT_INDEX_ROUTES = (
    "/",
    "/airports",
    "/airport-security-wait-times",
)

PLACEHOLDER_HREFS = {
    "",
    "#",
    "javascript:;",
    "javascript:void(0)",
    "javascript:void(0);",
}


class ParsedDocument(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical_hrefs = []
        self.description = None
        self.elements = []
        self.hrefs = []
        self.h1_count = 0
        self.h1_parts = []
        self.json_ld = []
        self.script_blocks = {}
        self._in_title = False
        self._in_h1 = False
        self._in_json_ld = False
        self._script_id = None
        self._title_parts = []
        self._json_ld_parts = []
        self._script_parts = []

    @property
    def title(self):
        return "".join(self._title_parts).strip()

    @property
    def h1(self):
        return " ".join("".join(self.h1_parts).split())

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.elements.append((tag, attributes))
        if tag == "a" and "href" in attributes:
            self.hrefs.append(attributes["href"])
        elif tag == "link":
            rel = set((attributes.get("rel") or "").lower().split())
            if "canonical" in rel and attributes.get("href"):
                self.canonical_hrefs.append(attributes["href"])
        elif tag == "meta" and (attributes.get("name") or "").lower() == "description":
            self.description = (attributes.get("content") or "").strip()
        elif tag == "title":
            self._in_title = True
        elif tag == "h1":
            self.h1_count += 1
            self._in_h1 = True
        elif tag == "script" and attributes.get("type", "").lower() == "application/ld+json":
            self._in_json_ld = True
            self._json_ld_parts = []
        if tag == "script" and attributes.get("id"):
            self._script_id = attributes["id"]
            self._script_parts = []

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "script":
            if self._in_json_ld:
                raw = "".join(self._json_ld_parts).strip()
                if raw:
                    self.json_ld.append(json.loads(raw))
                self._in_json_ld = False
                self._json_ld_parts = []
            if self._script_id:
                self.script_blocks[self._script_id] = "".join(self._script_parts).strip()
                self._script_id = None
                self._script_parts = []

    def handle_data(self, data):
        if self._in_title:
            self._title_parts.append(data)
        if self._in_h1:
            self.h1_parts.append(data)
        if self._in_json_ld:
            self._json_ld_parts.append(data)
        if self._script_id:
            self._script_parts.append(data)


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tempdir = tempfile.TemporaryDirectory(prefix="tsa-frontend-tests-")
        cls._original_environment = {
            key: os.environ.get(key)
            for key in (
                "DB_PATH",
                "ENABLE_POLLER",
                "SITE_URL",
                "SUPABASE_URL",
                "SUPABASE_SERVICE_ROLE_KEY",
                "ENABLE_ADSENSE",
                "ENABLE_ANALYTICS",
                "GA_MEASUREMENT_ID",
                "ADSENSE_CLIENT",
                "ADSENSE_SLOT_DISPLAY",
                "ADSENSE_SLOT_MULTIPLEX",
                "SKIMLINKS_SCRIPT_URL",
                "ENABLE_INTERNAL_GRAPH",
                "AIRPORT_ARRIVAL_MODE_CODES",
            )
        }
        os.environ.update(
            {
                "DB_PATH": os.path.join(cls._tempdir.name, "test.db"),
                "ENABLE_POLLER": "false",
                "SITE_URL": "https://tsa-tracker.test",
                "SUPABASE_URL": "",
                "SUPABASE_SERVICE_ROLE_KEY": "",
                "ENABLE_ADSENSE": "false",
                "ENABLE_ANALYTICS": "false",
                "GA_MEASUREMENT_ID": "",
                "ADSENSE_CLIENT": "",
                "ADSENSE_SLOT_DISPLAY": "",
                "ADSENSE_SLOT_MULTIPLEX": "",
                "SKIMLINKS_SCRIPT_URL": "",
                "ENABLE_INTERNAL_GRAPH": "false",
                "AIRPORT_ARRIVAL_MODE_CODES": "LAS",
            }
        )

        cls.app_module = importlib.import_module("app")
        cls.app_module.app.config.update(TESTING=True)

        # Keep contract tests local and deterministic.
        cls.app_module.get_lite_brain_insights = lambda: []
        cls.app_module.supabase_history_rows = lambda *args, **kwargs: None
        cls.app_module.supabase_historical_24h_average = lambda *args, **kwargs: None
        cls.app_module.supabase_checkpoint_24h_average = lambda *args, **kwargs: None

        cls.client = cls.app_module.app.test_client()
        cls.airport_routes = {
            code: cls.app_module.airport_seo_slug(code)
            for code in cls.app_module.LIVE_AIRPORTS
        }

    @classmethod
    def tearDownClass(cls):
        cls._tempdir.cleanup()
        for key, value in cls._original_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def get_html(self, route):
        response = self.client.get(route)
        self.assertEqual(response.status_code, 200, route)
        self.assertTrue(response.content_type.startswith("text/html"), route)
        html = response.get_data(as_text=True)
        document = ParsedDocument()
        document.feed(html)
        return html, document

    def test_core_routes_render(self):
        for route in CORE_ROUTES:
            with self.subTest(route=route):
                self.get_html(route)

    def test_all_canonical_airport_pages_render(self):
        for code, route in self.airport_routes.items():
            with self.subTest(code=code, route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.content_type.startswith("text/html"))

    def test_airport_indexes_use_generated_canonical_hrefs(self):
        expected_hrefs = set(self.airport_routes.values())
        for route in AIRPORT_INDEX_ROUTES:
            with self.subTest(route=route):
                _, document = self.get_html(route)
                rendered_hrefs = {
                    href
                    for href in document.hrefs
                    if href.startswith("/airports/")
                }
                self.assertEqual(rendered_hrefs, expected_hrefs)

    def test_home_map_coordinates_cover_live_airports(self):
        locations = self.app_module.AIRPORT_MAP_COORDINATES
        self.assertEqual(set(locations), set(self.app_module.LIVE_AIRPORTS))

        coordinate_pairs = set()
        for code, location in locations.items():
            with self.subTest(code=code):
                lat = float(location["lat"])
                lng = float(location["lng"])
                self.assertGreaterEqual(lat, 24)
                self.assertLessEqual(lat, 50)
                self.assertGreaterEqual(lng, -125)
                self.assertLessEqual(lng, -66)
                coordinate_pairs.add((lat, lng))

        self.assertEqual(len(coordinate_pairs), len(locations))

    def test_home_map_payload_and_server_rendered_markers_match(self):
        _, document = self.get_html("/")
        expected_codes = set(self.app_module.LIVE_AIRPORTS)

        raw_payload = document.script_blocks["airport-map-data"]
        self.assertNotIn("NaN", raw_payload)
        self.assertNotIn("Infinity", raw_payload)
        payload = json.loads(raw_payload)
        payload_by_code = {item["code"]: item for item in payload}
        self.assertEqual(set(payload_by_code), expected_codes)

        required = {
            "code",
            "name",
            "city",
            "href",
            "map_lat",
            "map_lng",
            "current_wait",
            "tier",
            "is_live",
            "source_label",
            "trend",
            "trend_arrow",
            "updated_at",
        }
        for code, item in payload_by_code.items():
            with self.subTest(code=code):
                self.assertTrue(required.issubset(item))
                self.assertEqual(item["href"], self.airport_routes[code])
                self.assertAlmostEqual(
                    float(item["map_lat"]),
                    float(self.app_module.AIRPORT_MAP_COORDINATES[code]["lat"]),
                )
                self.assertAlmostEqual(
                    float(item["map_lng"]),
                    float(self.app_module.AIRPORT_MAP_COORDINATES[code]["lng"]),
                )
                self.assertGreaterEqual(float(item["current_wait"]), 0)
                self.assertIn(item["tier"], {"low", "med", "high", "crit"})
                self.assertIs(type(item["is_live"]), bool)
                self.assertTrue(item["source_label"])

        markers = [
            attrs
            for tag, attrs in document.elements
            if tag == "a"
            and "airport-map-marker" in (attrs.get("class") or "").split()
        ]
        self.assertEqual(len(markers), len(expected_codes))
        self.assertEqual({attrs["data-map-code"] for attrs in markers}, expected_codes)

        for attrs in markers:
            code = attrs["data-map-code"]
            item = payload_by_code[code]
            with self.subTest(code=code):
                self.assertIn("data-map-airport-link", attrs)
                self.assertEqual(attrs["href"], self.airport_routes[code])
                self.assertAlmostEqual(float(attrs["data-lat"]), float(item["map_lat"]))
                self.assertAlmostEqual(float(attrs["data-lng"]), float(item["map_lng"]))
                self.assertAlmostEqual(float(attrs["data-wait"]), float(item["current_wait"]))
                self.assertEqual(attrs["data-tier"], item["tier"])
                self.assertEqual(attrs["data-live"], str(item["is_live"]).lower())
                self.assertIn(code, attrs.get("aria-label", ""))
                self.assertIn(item["city"], attrs.get("aria-label", ""))

    def test_home_map_accessibility_and_enhancement_asset_contract(self):
        html, document = self.get_html("/")
        expected_codes = set(self.app_module.LIVE_AIRPORTS)
        by_id = {
            attrs["id"]: (tag, attrs)
            for tag, attrs in document.elements
            if attrs.get("id")
        }

        map_tag, map_attrs = by_id["airport-network-map"]
        self.assertEqual(map_tag, "section")
        self.assertEqual(map_attrs.get("aria-labelledby"), "home-title")
        interactive_map_tag, interactive_map_attrs = by_id["airport-map"]
        self.assertEqual(interactive_map_tag, "div")
        self.assertEqual(interactive_map_attrs.get("role"), "region")
        self.assertEqual(interactive_map_attrs.get("tabindex"), "0")
        self.assertEqual(
            interactive_map_attrs.get("aria-describedby"), "airport-map-help"
        )
        self.assertIn(
            "Interactive satellite map", interactive_map_attrs.get("aria-label", "")
        )
        self.assertIn("airport-map-help", by_id)
        self.assertIn("airport-map-preview", by_id)
        _, status_attrs = by_id["airport-map-status"]
        self.assertEqual(status_attrs.get("role"), "status")
        self.assertEqual(status_attrs.get("aria-live"), "polite")

        zoom_control_groups = [
            attrs
            for tag, attrs in document.elements
            if tag == "div" and "data-map-zoom-controls" in attrs
        ]
        self.assertEqual(len(zoom_control_groups), 1)
        self.assertEqual(zoom_control_groups[0].get("role"), "group")
        self.assertEqual(
            zoom_control_groups[0].get("aria-label"), "Map zoom controls"
        )
        zoom_buttons = [
            attrs
            for tag, attrs in document.elements
            if tag == "button"
            and ("data-map-zoom-in" in attrs or "data-map-zoom-out" in attrs)
        ]
        self.assertEqual(len(zoom_buttons), 2)
        self.assertEqual(
            {attrs.get("aria-label") for attrs in zoom_buttons},
            {"Zoom map in", "Zoom map out"},
        )
        for attrs in zoom_buttons:
            self.assertEqual(attrs.get("aria-controls"), "airport-map")

        expand_controls = [
            attrs
            for tag, attrs in document.elements
            if tag == "button" and "data-map-expand" in attrs
        ]
        exit_controls = [
            attrs
            for tag, attrs in document.elements
            if tag == "button" and "data-map-exit" in attrs
        ]
        self.assertEqual(len(expand_controls), 1)
        self.assertEqual(len(exit_controls), 1)
        self.assertEqual(expand_controls[0].get("type"), "button")
        self.assertEqual(expand_controls[0].get("aria-controls"), "airport-map")
        self.assertEqual(expand_controls[0].get("aria-expanded"), "false")
        self.assertIn("hidden", expand_controls[0])
        self.assertEqual(exit_controls[0].get("type"), "button")
        self.assertEqual(exit_controls[0].get("aria-controls"), "airport-map")
        self.assertEqual(exit_controls[0].get("aria-label"), "Exit expanded map")
        self.assertIn("hidden", exit_controls[0])

        fly_in_links = [
            attrs
            for tag, attrs in document.elements
            if tag == "a" and "data-map-preview-fly-in" in attrs
        ]
        self.assertEqual(len(fly_in_links), 1)
        self.assertIn("data-map-preview-link", fly_in_links[0])
        self.assertIn("data-map-airport-link", fly_in_links[0])
        self.assertEqual(fly_in_links[0].get("href"), "/airports/jfk-tsa-wait-times")

        board_rows = [
            attrs
            for tag, attrs in document.elements
            if tag == "a"
            and "airport-row" in (attrs.get("class") or "").split()
        ]
        self.assertEqual(len(board_rows), len(expected_codes))
        self.assertEqual({attrs["data-code"] for attrs in board_rows}, expected_codes)
        for attrs in board_rows:
            self.assertEqual(attrs["href"], self.airport_routes[attrs["data-code"]])

        script_assets = [
            attrs
            for tag, attrs in document.elements
            if tag == "script" and attrs.get("src")
        ]
        map_scripts = [
            attrs
            for attrs in script_assets
            if attrs["src"].split("?", 1)[0] == "/static/home-map.js"
        ]
        self.assertEqual(len(map_scripts), 1)
        self.assertIn("defer", map_scripts[0])
        self.assertNotIn('/static/app.js', html)

        response = self.client.get(map_scripts[0]["src"])
        self.assertEqual(response.status_code, 200)
        source = response.get_data(as_text=True)
        response.close()
        for token in (
            '.airport-map-marker[data-map-airport-link]',
            '#airport-map-preview',
            'airport-map-status',
            '(prefers-reduced-motion: reduce)',
            'USGSImageryOnly/MapServer/tile/{z}/{y}/{x}',
            'window.location.assign',
            'map.flyTo(',
            'boxZoom: true',
            'doubleClickZoom: true',
            'dragging: true',
            'keyboard: true',
            'maxBoundsViscosity: 0.82',
            'scrollWheelZoom: true',
            'touchZoom: true',
            'map.zoomIn(',
            'map.zoomOut(',
            'captureOverviewView',
            'AIRPORT_REVEAL_ZOOM = 13',
            'AIRPORT_REVEAL_DURATION = 1.25',
            'AIRPORT_REVEAL_HOLD_MS = 1500',
            'AIRPORT_REVEAL_FALLBACK_MS = 5000',
            'imagery.isLoading()',
            'stage.dataset.revealCode',
            '[data-map-expand]',
            '[data-map-exit]',
            'setMapExpanded',
            'map.invalidateSize',
            'is-mobile-embedded',
        ):
            self.assertIn(token, source)
        self.assertRegex(source, r'addEventListener\(\s*["\']pointerenter["\']')
        self.assertRegex(source, r'addEventListener\(\s*["\']focus["\']')
        self.assertRegex(source, r'addEventListener\(\s*["\']click["\']')

    def test_homepage_airport_handoff_contract_is_versioned_and_storage_safe(self):
        html, document = self.get_html("/")
        map_script = next(
            attrs["src"]
            for tag, attrs in document.elements
            if tag == "script"
            and attrs.get("src", "").split("?", 1)[0] == "/static/home-map.js"
        )
        response = self.client.get(map_script)
        self.assertEqual(response.status_code, 200)
        source = response.get_data(as_text=True)
        response.close()

        self.assertNotIn("tsaAirportHandoffV1", html)
        for token in (
            'AIRPORT_HANDOFF_KEY = "tsaAirportHandoffV1"',
            "window.sessionStorage.setItem(AIRPORT_HANDOFF_KEY",
            "version: 1",
            "code: airport.code",
            "center: [airport.lat, airport.lng]",
            "zoom: zoom",
            "startedAt: Date.now()",
            'source: "home-map"',
            "storeAirportHandoff(airport, targetZoom)",
        ):
            self.assertIn(token, source)
        self.assertRegex(
            source,
            r"function storeAirportHandoff\([^)]*\)\s*\{[\s\S]*?try\s*\{[\s\S]*?sessionStorage\.setItem[\s\S]*?catch\s*\(",
        )
        self.assertLess(
            source.index("storeAirportHandoff(airport, targetZoom)"),
            source.index("map.flyTo([airport.lat, airport.lng], targetZoom"),
        )

    def test_airport_pages_reference_matching_history_apis(self):
        for code, route in self.airport_routes.items():
            with self.subTest(code=code, route=route):
                html, _ = self.get_html(route)
                history_url = f"/api/history-24h-average?airport={code}&days=30"
                checkpoint_url = (
                    f"/api/checkpoint-history-24h-average?airport={code}&days=30"
                )
                self.assertIn(history_url, html)
                self.assertIn(checkpoint_url, html)

                history_response = self.client.get(history_url)
                self.assertEqual(history_response.status_code, 200)
                history_payload = history_response.get_json()
                self.assertEqual(history_payload["airport"], code)
                self.assertIn("rows", history_payload)

                checkpoint_response = self.client.get(checkpoint_url)
                self.assertEqual(checkpoint_response.status_code, 200)
                checkpoint_payload = checkpoint_response.get_json()
                self.assertEqual(checkpoint_payload["airport"], code)
                self.assertIn("groups", checkpoint_payload)

    def test_production_pages_have_seo_and_exact_canonicals(self):
        routes = list(CORE_ROUTES) + list(self.airport_routes.values())
        for route in routes:
            with self.subTest(route=route):
                _, document = self.get_html(route)
                self.assertTrue(document.title, "missing <title>")
                self.assertTrue(document.description, "missing meta description")
                self.assertEqual(
                    document.canonical_hrefs,
                    [f"{self.app_module.SITE_URL}{route}"],
                )

    def test_production_pages_have_no_placeholder_hrefs(self):
        routes = list(CORE_ROUTES) + list(self.airport_routes.values())
        for route in routes:
            with self.subTest(route=route):
                _, document = self.get_html(route)
                placeholders = [
                    href
                    for href in document.hrefs
                    if href.strip().lower() in PLACEHOLDER_HREFS
                ]
                self.assertEqual(placeholders, [])

    def test_airport_h1_metadata_and_structured_data(self):
        for code, route in self.airport_routes.items():
            with self.subTest(code=code):
                _, document = self.get_html(route)
                self.assertIn(code, document.h1)
                self.assertIn("TSA wait times", document.h1)
                self.assertLessEqual(len(document.description), 160)
                schema_types = {item.get("@type") for item in document.json_ld}
                self.assertIn("BreadcrumbList", schema_types)
                self.assertIn("WebPage", schema_types)
                web_page = next(item for item in document.json_ld if item.get("@type") == "WebPage")
                self.assertEqual(web_page["mainEntity"]["@type"], "Airport")
                self.assertEqual(web_page["mainEntity"]["iataCode"], code)

    def test_calculator_is_discoverable_and_substantive(self):
        html, document = self.get_html("/when-should-i-leave")
        text = re.sub(r"<script\b.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'/-]*", text)
        self.assertGreaterEqual(len(words), 300)
        schema_types = {item.get("@type") for item in document.json_ld}
        self.assertIn("BreadcrumbList", schema_types)
        self.assertIn("WebApplication", schema_types)

        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        root = ET.fromstring(sitemap.get_data(as_text=True))
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locations = {node.text for node in root.findall("sm:url/sm:loc", namespace)}
        expected = {
            f"{self.app_module.SITE_URL}{route}"
            for route in list(CORE_ROUTES) + list(self.airport_routes.values())
        }
        self.assertTrue(expected.issubset(locations))

        graph = self.app_module.link_graph_context()
        nodes = {node["id"] for node in json.loads(graph["nodes_json"])}
        edges = json.loads(graph["edges_json"])
        inbound = [edge for edge in edges if edge["to"] == "/when-should-i-leave"]
        self.assertIn("/when-should-i-leave", nodes)
        self.assertGreaterEqual(len(inbound), 4)

    def test_calculator_deep_link_validates_checkpoint_and_lane_context(self):
        def selection_for(query):
            html, _ = self.get_html(f"/when-should-i-leave?{query}")
            match = re.search(
                r"var CALCULATOR_SELECTION = (\{.*?\});", html, re.DOTALL
            )
            self.assertIsNotNone(match)
            return json.loads(match.group(1)), html

        valid, valid_html = selection_for(
            "airport=las&checkpoint=las-t1-ab&lane=standard"
        )
        self.assertEqual(
            valid,
            {
                "airport": "LAS",
                "checkpoint": "las-t1-ab",
                "lane": "STANDARD",
            },
        )
        checkpoint_payload = re.search(
            r"var CALCULATOR_CHECKPOINTS = (\{.*?\});\s*var hourlyCache",
            valid_html,
            re.DOTALL,
        )
        self.assertIsNotNone(checkpoint_payload)
        calculator_model = json.loads(checkpoint_payload.group(1))
        self.assertEqual(calculator_model["schema_version"], 1)
        self.assertEqual(calculator_model["code"], "LAS")
        self.assertEqual(
            {
                checkpoint["id"]
                for terminal in calculator_model["terminals"]
                for checkpoint in terminal["checkpoints"]
            },
            {
                "las-t1-ab",
                "las-t1-c",
                "las-t1-cd",
                "las-t3-de",
                "las-t3-innovation",
            },
        )

        invalid_checkpoint, _ = selection_for(
            "airport=LAS&checkpoint=not-configured&lane=PRECHECK"
        )
        self.assertEqual(
            invalid_checkpoint,
            {"airport": "LAS", "checkpoint": "", "lane": ""},
        )
        mismatched_airport, _ = selection_for(
            "airport=PHL&checkpoint=las-t1-ab&lane=STANDARD"
        )
        self.assertEqual(
            mismatched_airport,
            {"airport": "PHL", "checkpoint": "", "lane": ""},
        )
        invalid_airport, _ = selection_for(
            "airport=XYZ&checkpoint=las-t1-ab&lane=STANDARD"
        )
        self.assertEqual(
            invalid_airport,
            {"airport": "", "checkpoint": "", "lane": ""},
        )
        invalid_airport_lane, _ = selection_for("airport=XYZ&lane=PRECHECK")
        self.assertEqual(
            invalid_airport_lane,
            {"airport": "", "checkpoint": "", "lane": ""},
        )
        invalid_lane, invalid_lane_html = selection_for(
            "airport=LAS&checkpoint=las-t1-ab&lane=CLEAR"
        )
        self.assertEqual(
            invalid_lane,
            {"airport": "LAS", "checkpoint": "", "lane": ""},
        )

        for token in (
            "activeCheckpointSelection",
            'reading.freshness==="live" || reading.freshness==="aging"',
            "fallback.fallbackReason=reading.freshness",
            "checkpointLabel(source.checkpoint)",
            "reconcileCheckpointSelection()",
            "if(code!==activeCheckpointSelection.airport)",
            "if(lane!==activeCheckpointSelection.lane)",
        ):
            self.assertIn(token, valid_html)
        self.assertNotIn('"lane": "CLEAR"', invalid_lane_html)

    def test_calculator_checkpoint_model_uses_html_safe_json(self):
        malicious = "</script><script>window.__arrival_xss__=true</script>"
        model = {
            "schema_version": 1,
            "code": "LAS",
            "terminals": [],
            "unmatched_readings": [{"checkpoint": malicious}],
        }
        with patch.object(
            self.app_module, "build_airport_arrival_mode", return_value=model
        ), patch.object(self.app_module, "history_for_airport", return_value=[]):
            html, _ = self.get_html("/when-should-i-leave?airport=LAS")

        self.assertNotIn(malicious, html)
        self.assertNotIn("window.__arrival_xss__=true</script>", html)
        self.assertIn(r"\u003c/script\u003e", html)

    def test_sitemap_keeps_editorial_dates_stable(self):
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        def lastmods():
            response = self.client.get("/sitemap.xml")
            self.assertEqual(response.status_code, 200)
            root = ET.fromstring(response.get_data(as_text=True))
            result = {}
            for url in root.findall("sm:url", namespace):
                location = url.findtext("sm:loc", namespaces=namespace)
                lastmod = url.findtext("sm:lastmod", namespaces=namespace)
                result[location] = lastmod
            return result

        static_paths = (
            "/about",
            "/methodology",
            "/privacy",
            "/terms",
            "/guide/tsa-wait-times",
            "/guide/tsa-precheck-clear",
            "/best-time-to-get-to-the-airport",
        )
        before = lastmods()
        original_utc_now = self.app_module.utc_now
        try:
            self.app_module.utc_now = lambda: datetime(2035, 1, 2, tzinfo=timezone.utc)
            after = lastmods()
        finally:
            self.app_module.utc_now = original_utc_now

        for path in static_paths:
            with self.subTest(path=path):
                location = f"{self.app_module.SITE_URL}{path}"
                self.assertEqual(before[location], self.app_module.EDITORIAL_REVIEW_DATES[path])
                self.assertEqual(after[location], before[location])
        self.assertIsNone(after[f"{self.app_module.SITE_URL}/contact"])
        self.assertEqual(after[f"{self.app_module.SITE_URL}/"], "2035-01-02")

    def test_fallback_airport_never_uses_live_only_claims(self):
        html, _ = self.get_html(self.airport_routes["LAS"])
        self.assertIn("Estimated fallback", html)
        self.assertIn("Planning estimate while the live airport source is unavailable", html)
        self.assertNotIn("Official airport reading captured", html)

    def test_las_decision_map_preserves_zero_and_unmatched_rows(self):
        rows = [
            {
                "checkpoint": "T1 - A/B Gates",
                "lane_type": "STANDARD",
                "wait_minutes": 0,
                "captured_at": "2026-07-10T22:16:00+00:00",
            },
            {
                "checkpoint": "Terminal 3 – D/E Gates",
                "lane_type": "PRECHECK",
                "wait_minutes": 4,
                "captured_at": "2026-07-10T22:16:00+00:00",
            },
            {
                "checkpoint": "Unmapped checkpoint",
                "lane_type": "STANDARD",
                "wait_minutes": 7,
                "captured_at": "2026-07-10T22:16:00+00:00",
            },
        ]
        decision_map = self.app_module.build_airport_decision_map("LAS", rows)
        nodes = {
            checkpoint["id"]: checkpoint
            for terminal in decision_map["terminals"]
            for checkpoint in terminal["checkpoints"]
        }
        self.assertEqual(nodes["las-t1-ab"]["standard_wait"], 0)
        self.assertEqual(nodes["las-t1-ab"]["status"], "reporting")
        self.assertEqual(nodes["las-t3-de"]["precheck_wait"], 4)
        self.assertEqual(nodes["las-t3-innovation"]["status"], "not_reporting")
        self.assertEqual([row["checkpoint"] for row in decision_map["unmatched_rows"]], ["Unmapped checkpoint"])

    def test_las_arrival_mode_model_schema_freshness_and_location_contract(self):
        now = datetime(2026, 7, 10, 20, 0, tzinfo=timezone.utc)

        def captured(minutes=0, seconds=0):
            return (now - timedelta(minutes=minutes, seconds=seconds)).isoformat()

        rows = [
            {
                "checkpoint": "T1 - A/B Gates",
                "lane_type": "STANDARD",
                "wait_minutes": 0,
                "captured_at": captured(minutes=5),
                "source": "https://source.test/las",
            },
            {
                "checkpoint": "Terminal 1 - C Gates",
                "lane_type": "STANDARD",
                "wait_minutes": 9,
                "captured_at": captured(minutes=6),
            },
            {
                "checkpoint": "T1 - C/D Gates",
                "lane_type": "STANDARD",
                "wait_minutes": 15,
                "captured_at": captured(minutes=15),
            },
            {
                "checkpoint": "T3 - D/E Gates",
                "lane_type": "STANDARD",
                "wait_minutes": 42,
                "captured_at": captured(minutes=15, seconds=1),
            },
            {
                "checkpoint": "Unmapped checkpoint",
                "lane_type": "STANDARD",
                "wait_minutes": 7,
                "captured_at": captured(),
            },
        ]
        model = self.app_module.build_airport_arrival_mode(
            "las", rows=rows, history_rows=[], now=now
        )

        self.assertEqual(model["schema_version"], 1)
        self.assertEqual(model["refresh_seconds"], 120)
        self.assertEqual(model["airport"]["code"], "LAS")
        self.assertEqual(model["code"], "LAS")
        self.assertEqual(model["generated_at"], now.isoformat())
        self.assertEqual(model["lane_types"], ["STANDARD", "PRECHECK"])
        self.assertEqual(model["source_status"], "live")
        self.assertEqual(model["source"]["verified_on"], "2026-07-10")

        map_config = model["map"]
        self.assertEqual(len(map_config["center"]), 2)
        self.assertEqual(len(map_config["bounds"]), 2)
        self.assertTrue(all(len(corner) == 2 for corner in map_config["bounds"]))
        self.assertGreater(map_config["detail_zoom"], map_config["overview_zoom"])
        self.assertEqual(map_config["location_accuracy"], "airport_overview")
        self.assertIn("USGSImageryOnly", map_config["tile_url"])

        self.assertEqual(len(model["terminals"]), 2)
        self.assertEqual({terminal["id"] for terminal in model["terminals"]}, {"t1", "t3"})
        for terminal in model["terminals"]:
            with self.subTest(terminal=terminal["id"]):
                self.assertEqual(len(terminal["anchor"]), 2)
                self.assertEqual(
                    terminal["location_accuracy"], "terminal_curb_anchor"
                )

        checkpoints = {
            checkpoint["id"]: checkpoint
            for terminal in model["terminals"]
            for checkpoint in terminal["checkpoints"]
        }
        self.assertEqual(
            set(checkpoints),
            {
                "las-t1-ab",
                "las-t1-c",
                "las-t1-cd",
                "las-t3-de",
                "las-t3-innovation",
            },
        )
        for checkpoint in checkpoints.values():
            self.assertTrue(checkpoint["hours"])
            self.assertNotIn("anchor", checkpoint)
            self.assertNotIn("is_open", checkpoint)
            self.assertNotIn("closed", checkpoint)

        lanes = {
            (checkpoint_id, lane["lane_type"]): lane
            for checkpoint_id, checkpoint in checkpoints.items()
            for lane in checkpoint["lanes"]
        }
        self.assertEqual(lanes[("las-t1-ab", "STANDARD")]["freshness_status"], "live")
        self.assertEqual(lanes[("las-t1-ab", "STANDARD")]["wait_minutes"], 0)
        self.assertEqual(
            lanes[("las-t1-ab", "PRECHECK")]["freshness_status"],
            "no_current_reading",
        )
        self.assertIsNone(lanes[("las-t1-ab", "PRECHECK")]["wait_minutes"])
        self.assertEqual(lanes[("las-t1-c", "STANDARD")]["freshness_status"], "aging")
        self.assertEqual(lanes[("las-t1-cd", "STANDARD")]["freshness_status"], "aging")
        self.assertEqual(lanes[("las-t3-de", "STANDARD")]["freshness_status"], "stale")
        self.assertIsNone(lanes[("las-t3-de", "STANDARD")]["wait_minutes"])
        for lane_type in ("STANDARD", "PRECHECK"):
            self.assertEqual(
                lanes[("las-t3-innovation", lane_type)]["freshness_status"],
                "published_only",
            )
            self.assertIsNone(
                lanes[("las-t3-innovation", lane_type)]["wait_minutes"]
            )

        module = self.app_module
        with patch.object(module, "latest_for_code", return_value=rows), patch.object(
            module, "history_for_airport", return_value=[]
        ):
            html, _ = self.get_html(self.airport_routes["LAS"])
        self.assertIn("Stale — no number", html)

        self.assertEqual(model["fastest_fresh_reading"]["checkpoint_id"], "las-t1-ab")
        self.assertEqual(model["fastest_fresh_reading"]["wait_minutes"], 0)
        self.assertEqual(
            [row["checkpoint"] for row in model["unmatched_readings"]],
            ["Unmapped checkpoint"],
        )
        self.assertEqual(model["unmatched_rows"], model["unmatched_readings"])

    def test_generic_arrival_mode_normalizes_checkpoint_first_airports(self):
        now = datetime(2026, 7, 10, 20, 0, tzinfo=timezone.utc)
        rows = [
            {
                "checkpoint": "Terminal 4 General",
                "lane_type": "STANDARD",
                "wait_minutes": 0,
                "captured_at": (now - timedelta(minutes=2)).isoformat(),
            },
            {
                "checkpoint": "Terminal 4 TSA PreCheck",
                "lane_type": "STANDARD",
                "wait_minutes": 4,
                "captured_at": (now - timedelta(minutes=3)).isoformat(),
            },
            {
                "checkpoint": "Estimated Wait",
                "lane_type": "STANDARD",
                "wait_minutes": 12,
                "captured_at": now.isoformat(),
            },
        ]
        module = self.app_module
        with patch.dict(module.AIRPORT_DECISION_MAPS, {"JFK": None}, clear=False):
            model = module.build_airport_arrival_mode(
                "JFK", rows=rows, history_rows=rows, now=now
            )
        self.assertIsNotNone(model)

        self.assertEqual(model["decision_mode"], "checkpoint_only")
        self.assertFalse(model["has_published_hours"])
        self.assertEqual(model["map"]["location_accuracy"], "airport_overview")
        self.assertEqual(len(model["terminals"]), 1)
        self.assertEqual(model["terminals"][0]["id"], "airport")
        self.assertEqual(
            model["terminals"][0]["location_accuracy"],
            "airport_overview_anchor",
        )
        checkpoints = model["terminals"][0]["checkpoints"]
        self.assertEqual([checkpoint["id"] for checkpoint in checkpoints], ["jfk-terminal-4"])
        lanes = {lane["lane_type"]: lane for lane in checkpoints[0]["lanes"]}
        self.assertEqual(lanes["STANDARD"]["wait_minutes"], 0)
        self.assertEqual(lanes["PRECHECK"]["wait_minutes"], 4)
        self.assertEqual(
            {row["checkpoint"] for row in model["unmatched_readings"]},
            {"Estimated Wait"},
        )

    def test_atl_arrival_mode_maps_five_reviewed_checkpoint_areas(self):
        now = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)
        rows = [
            {
                "checkpoint": label,
                "lane_type": "STANDARD",
                "wait_minutes": index,
                "captured_at": (now - timedelta(minutes=2)).isoformat(),
            }
            for index, label in enumerate(
                (
                    "Main Checkpoint",
                    "North Checkpoint",
                    "Lower North Checkpoint",
                    "South Checkpoint",
                    "International Main Checkpoint",
                )
            )
        ]
        model = self.app_module.build_airport_arrival_mode(
            "ATL", rows=rows, history_rows=rows, now=now
        )

        self.assertEqual(model["decision_mode"], "terminal_checkpoint")
        self.assertTrue(model["has_published_hours"])
        self.assertTrue(model["all_checkpoints_reach_all_gates"])
        self.assertIn("All concourses and aircraft gates are accessible", model["routing_note"])
        self.assertEqual(model["map"]["location_accuracy"], "checkpoint_area_overview")
        self.assertEqual(
            [terminal["id"] for terminal in model["terminals"]],
            ["main", "north", "lower-north", "south", "international-main"],
        )
        self.assertEqual(
            {terminal["id"]: terminal["anchor"] for terminal in model["terminals"]},
            {
                "main": [33.6409, -84.4440],
                "north": [33.64105, -84.4449],
                "lower-north": [33.64075, -84.44485],
                "south": [33.6405, -84.4439],
                "international-main": [33.64037, -84.41821],
            },
        )
        self.assertTrue(
            all(
                terminal["location_accuracy"] == "checkpoint_area_anchor"
                for terminal in model["terminals"]
            )
        )
        checkpoints = [
            checkpoint
            for terminal in model["terminals"]
            for checkpoint in terminal["checkpoints"]
        ]
        self.assertEqual(
            [checkpoint["id"] for checkpoint in checkpoints],
            [
                "atl-main",
                "atl-north",
                "atl-lower-north",
                "atl-south",
                "atl-international-main",
            ],
        )
        self.assertEqual(checkpoints[0]["hours"], "24 hours")
        self.assertEqual(model["fastest_fresh_reading"]["checkpoint_id"], "atl-main")
        self.assertEqual(model["unmatched_readings"], [])

    def test_clt_arrival_mode_maps_three_reviewed_checkpoint_areas(self):
        now = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)
        rows = [
            {
                "checkpoint": "Checkpoint 1 (Standard)",
                "lane_type": "STANDARD",
                "wait_minutes": 5,
                "captured_at": (now - timedelta(minutes=2)).isoformat(),
            },
            {
                "checkpoint": "Checkpoint 2 (Standard)",
                "lane_type": "STANDARD",
                "wait_minutes": 4,
                "captured_at": (now - timedelta(minutes=2)).isoformat(),
            },
            {
                "checkpoint": "Checkpoint 2 (PreCheck)",
                "lane_type": "PRECHECK",
                "wait_minutes": 1,
                "captured_at": (now - timedelta(minutes=2)).isoformat(),
            },
            {
                "checkpoint": "Checkpoint 3 (Standard)",
                "lane_type": "STANDARD",
                "wait_minutes": 7,
                "captured_at": (now - timedelta(minutes=2)).isoformat(),
            },
        ]
        model = self.app_module.build_airport_arrival_mode(
            "CLT", rows=rows, history_rows=rows, now=now
        )

        self.assertEqual(model["decision_mode"], "terminal_checkpoint")
        self.assertTrue(model["has_published_hours"])
        self.assertTrue(model["all_checkpoints_reach_all_gates"])
        self.assertIn("All concourses and aircraft gates are accessible", model["routing_note"])
        self.assertEqual(model["map"]["location_accuracy"], "checkpoint_area_overview")
        self.assertEqual(
            [terminal["id"] for terminal in model["terminals"]],
            ["checkpoint-1", "checkpoint-2", "checkpoint-3"],
        )
        self.assertEqual(
            {terminal["id"]: terminal["anchor"] for terminal in model["terminals"]},
            {
                "checkpoint-1": [35.2206, -80.9448],
                "checkpoint-2": [35.2206, -80.9433],
                "checkpoint-3": [35.2206, -80.9418],
            },
        )
        checkpoints = {
            checkpoint["id"]: checkpoint
            for terminal in model["terminals"]
            for checkpoint in terminal["checkpoints"]
        }
        self.assertEqual(
            set(checkpoints),
            {"clt-checkpoint-1", "clt-checkpoint-2", "clt-checkpoint-3"},
        )
        self.assertEqual(checkpoints["clt-checkpoint-1"]["hours"], "3:45 a.m. - 8 p.m.")
        self.assertIn("Main PreCheck", checkpoints["clt-checkpoint-2"]["hours"])
        self.assertEqual(checkpoints["clt-checkpoint-2"]["lane_waits"], {"STANDARD": 4.0, "PRECHECK": 1.0})
        self.assertEqual(model["fastest_fresh_reading"]["checkpoint_id"], "clt-checkpoint-2")
        self.assertEqual(model["unmatched_readings"], [])

    def test_jax_arrival_mode_uses_the_main_terminal_checkpoint_anchor(self):
        now = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)
        rows = [
            {
                "checkpoint": "Main Checkpoint",
                "lane_type": "STANDARD",
                "wait_minutes": 4,
                "captured_at": (now - timedelta(minutes=2)).isoformat(),
            }
        ]
        model = self.app_module.build_airport_arrival_mode(
            "JAX", rows=rows, history_rows=rows, now=now
        )

        self.assertEqual(model["map"]["location_accuracy"], "checkpoint_area_overview")
        self.assertEqual(len(model["terminals"]), 1)
        self.assertEqual(model["terminals"][0]["id"], "main")
        self.assertEqual(model["terminals"][0]["anchor"], [30.4915, -81.6846])
        self.assertEqual(model["terminals"][0]["location_accuracy"], "checkpoint_area_anchor")

    def test_jfk_arrival_mode_uses_the_reviewed_terminal_anchors(self):
        now = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)
        rows = [
            {
                "checkpoint": "Terminal 4",
                "lane_type": "STANDARD",
                "wait_minutes": 4,
                "captured_at": (now - timedelta(minutes=2)).isoformat(),
            }
        ]
        model = self.app_module.build_airport_arrival_mode(
            "JFK", rows=rows, history_rows=rows, now=now
        )

        self.assertEqual(
            {terminal["id"]: terminal["anchor"] for terminal in model["terminals"]},
            {
                "terminal-1": [40.6428, -73.7914],
                "terminal-4": [40.6441, -73.7828],
                "terminal-5": [40.6456, -73.7779],
                "terminal-7": [40.6485, -73.7832],
                "terminal-8": [40.6471, -73.7900],
            },
        )

    def test_dca_arrival_mode_maps_three_reviewed_checkpoint_areas(self):
        now = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)
        rows = [
            {
                "checkpoint": "Terminal 1 (A Gates)",
                "lane_type": "STANDARD",
                "wait_minutes": 0,
                "captured_at": (now - timedelta(minutes=2)).isoformat(),
            },
            {
                "checkpoint": "Terminal 2 South (B, C, D, E Gates)",
                "lane_type": "PRECHECK",
                "wait_minutes": 4,
                "captured_at": (now - timedelta(minutes=3)).isoformat(),
            },
            {
                "checkpoint": "Terminal 2 North (B, C, D, E Gates)",
                "lane_type": "STANDARD",
                "wait_minutes": 7,
                "captured_at": (now - timedelta(minutes=4)).isoformat(),
            },
        ]
        model = self.app_module.build_airport_arrival_mode(
            "DCA", rows=rows, history_rows=rows, now=now
        )

        self.assertEqual(model["decision_mode"], "terminal_checkpoint")
        self.assertFalse(model["has_published_hours"])
        self.assertFalse(model["all_checkpoints_reach_all_gates"])
        self.assertIn("Terminal 1 serves A gates", model["routing_note"])
        self.assertEqual(model["map"]["location_accuracy"], "checkpoint_area_overview")
        self.assertEqual(
            [terminal["id"] for terminal in model["terminals"]],
            ["t1", "t2-south", "t2-north"],
        )
        self.assertTrue(
            all(
                terminal["location_accuracy"] == "checkpoint_area_anchor"
                for terminal in model["terminals"]
            )
        )
        checkpoints = {
            checkpoint["id"]: checkpoint
            for terminal in model["terminals"]
            for checkpoint in terminal["checkpoints"]
        }
        self.assertEqual(
            set(checkpoints), {"dca-t1", "dca-t2-south", "dca-t2-north"}
        )
        self.assertEqual(checkpoints["dca-t1"]["standard_wait"], 0)
        self.assertEqual(checkpoints["dca-t2-south"]["precheck_wait"], 4)
        self.assertEqual(checkpoints["dca-t2-north"]["standard_wait"], 7)
        self.assertEqual(model["fastest_fresh_reading"]["checkpoint_id"], "dca-t1")
        self.assertEqual(model["unmatched_readings"], [])

    def test_sfo_arrival_mode_groups_six_checkpoints_under_five_terminals(self):
        now = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)
        labels = (
            "Checkpoint A · International Terminal A",
            "Checkpoint B · Harvey Milk Terminal 1",
            "Checkpoint B - Mezzanine Level · Harvey Milk Terminal 1",
            "Checkpoint D · Terminal 2",
            "Checkpoint F · Terminal 3",
            "Checkpoint G · International Terminal G",
        )
        rows = [
            {
                "checkpoint": label,
                "lane_type": "STANDARD",
                "wait_minutes": index,
                "captured_at": (now - timedelta(minutes=2)).isoformat(),
            }
            for index, label in enumerate(labels)
        ]
        rows.append(
            {
                "checkpoint": "Estimated Wait",
                "lane_type": "STANDARD",
                "wait_minutes": 15,
                "captured_at": now.isoformat(),
            }
        )
        model = self.app_module.build_airport_arrival_mode(
            "SFO", rows=rows, history_rows=rows, now=now
        )

        self.assertEqual(model["decision_mode"], "terminal_checkpoint")
        self.assertTrue(model["all_checkpoints_reach_all_gates"])
        self.assertIn("every gate is accessible", model["routing_note"])
        self.assertEqual(model["map"]["location_accuracy"], "terminal_building_overview")
        self.assertEqual(len(model["terminals"]), 5)
        self.assertEqual(
            [terminal["id"] for terminal in model["terminals"]],
            ["intl-a", "t1", "t2", "t3", "intl-g"],
        )
        self.assertTrue(
            all(
                terminal["location_accuracy"] == "terminal_building_centroid"
                for terminal in model["terminals"]
            )
        )
        checkpoints = [
            checkpoint
            for terminal in model["terminals"]
            for checkpoint in terminal["checkpoints"]
        ]
        self.assertEqual(len(checkpoints), 6)
        terminal_one = next(
            terminal for terminal in model["terminals"] if terminal["id"] == "t1"
        )
        self.assertEqual(
            [checkpoint["id"] for checkpoint in terminal_one["checkpoints"]],
            ["sfo-checkpoint-b", "sfo-checkpoint-b-mezzanine"],
        )
        self.assertEqual(
            [row["checkpoint"] for row in model["unmatched_readings"]],
            ["Estimated Wait"],
        )

    def test_ewr_and_lga_arrival_modes_preserve_terminal_checkpoint_ids(self):
        now = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)
        rows_by_code = {
            "EWR": [
                {
                    "checkpoint": label,
                    "lane_type": "STANDARD",
                    "wait_minutes": index,
                    "captured_at": (now - timedelta(minutes=2)).isoformat(),
                }
                for index, label in enumerate(
                    (
                        "Terminal A",
                        "Terminal B (40-49)",
                        "Terminal B (51-57)",
                        "Terminal B (60-68)",
                        "Terminal C",
                    )
                )
            ],
            "LGA": [
                {
                    "checkpoint": label,
                    "lane_type": "STANDARD",
                    "wait_minutes": index,
                    "captured_at": (now - timedelta(minutes=2)).isoformat(),
                }
                for index, label in enumerate(("Terminal B", "Terminal C"))
            ],
        }
        expected = {
            "EWR": {
                "terminal_ids": ["terminal-a", "terminal-b", "terminal-c"],
                "checkpoint_ids": [
                    "ewr-terminal-a",
                    "ewr-terminal-b-40-49",
                    "ewr-terminal-b-51-57",
                    "ewr-terminal-b-60-68",
                    "ewr-terminal-c",
                ],
            },
            "LGA": {
                "terminal_ids": ["terminal-b", "terminal-c"],
                "checkpoint_ids": ["lga-terminal-b", "lga-terminal-c"],
            },
        }

        for code in ("EWR", "LGA"):
            with self.subTest(code=code):
                model = self.app_module.build_airport_arrival_mode(
                    code,
                    rows=rows_by_code[code],
                    history_rows=rows_by_code[code],
                    now=now,
                )
                self.assertEqual(model["decision_mode"], "terminal_checkpoint")
                self.assertFalse(model["has_published_hours"])
                self.assertEqual(
                    model["map"]["location_accuracy"],
                    "terminal_building_overview",
                )
                self.assertEqual(
                    [terminal["id"] for terminal in model["terminals"]],
                    expected[code]["terminal_ids"],
                )
                self.assertTrue(
                    all(
                        terminal["location_accuracy"]
                        == "terminal_building_centroid"
                        for terminal in model["terminals"]
                    )
                )
                checkpoints = [
                    checkpoint
                    for terminal in model["terminals"]
                    for checkpoint in terminal["checkpoints"]
                ]
                self.assertEqual(
                    [checkpoint["id"] for checkpoint in checkpoints],
                    expected[code]["checkpoint_ids"],
                )
                self.assertEqual(model["unmatched_readings"], [])

        ewr = self.app_module.build_airport_arrival_mode(
            "EWR", rows=rows_by_code["EWR"], history_rows=[], now=now
        )
        terminal_b = next(
            terminal
            for terminal in ewr["terminals"]
            if terminal["id"] == "terminal-b"
        )
        self.assertEqual(len(terminal_b["checkpoints"]), 3)

    def test_bos_and_ord_arrival_modes_preserve_terminal_checkpoint_ids(self):
        now = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)
        rows_by_code = {
            "BOS": [
                {
                    "checkpoint": label,
                    "lane_type": "PRECHECK" if "PreCheck" in label else "STANDARD",
                    "wait_minutes": index,
                    "captured_at": (now - timedelta(minutes=2)).isoformat(),
                }
                for index, label in enumerate(
                    (
                        "Checkpoint 1: A Gates",
                        "Checkpoint 2: A Gates PreCheck Only",
                        "Checkpoint 3: Gates B1 - B22",
                        "Checkpoint 4: Gates B23 - 40",
                        "Checkpoint 5: Terminal C",
                        "Checkpoint 6: All E Gates",
                        "Checkpoint 7: All E Gates",
                    )
                )
            ],
            "ORD": [
                {
                    "checkpoint": label,
                    "lane_type": "STANDARD",
                    "wait_minutes": index,
                    "captured_at": (now - timedelta(minutes=2)).isoformat(),
                }
                for index, label in enumerate(
                    (
                        "Terminal 1 — Economy",
                        "Terminal 2 — Checkpoint 5 General",
                        "Terminal 3 — Checkpoint 6",
                        "Terminal 3 — Checkpoint 7 General",
                        "Terminal 3 — Checkpoint 7A",
                        "Terminal 3 — Checkpoint 8 General",
                        "Terminal 3 — Checkpoint 9",
                        "Terminal 5 — Checkpoint 10",
                    )
                )
            ],
        }
        expected = {
            "BOS": {
                "terminal_ids": [
                    "terminal-a",
                    "terminal-b",
                    "terminal-c",
                    "terminal-e",
                ],
                "checkpoint_ids": [
                    "bos-checkpoint-1-a-gates",
                    "bos-checkpoint-2-a-gates-precheck-only",
                    "bos-checkpoint-3-gates-b1-b22",
                    "bos-checkpoint-4-gates-b23-40",
                    "bos-checkpoint-5-terminal-c",
                    "bos-checkpoint-6-all-e-gates",
                    "bos-checkpoint-7-all-e-gates",
                ],
            },
            "ORD": {
                "terminal_ids": [
                    "terminal-1",
                    "terminal-2",
                    "terminal-3",
                    "terminal-5",
                ],
                "checkpoint_ids": [
                    "ord-terminal-1",
                    "ord-terminal-2-checkpoint-5",
                    "ord-terminal-3-checkpoint-6",
                    "ord-terminal-3-checkpoint-7",
                    "ord-terminal-3-checkpoint-7a",
                    "ord-terminal-3-checkpoint-8",
                    "ord-terminal-3-checkpoint-9",
                    "ord-terminal-5-checkpoint-10",
                ],
            },
        }

        for code in ("BOS", "ORD"):
            with self.subTest(code=code):
                model = self.app_module.build_airport_arrival_mode(
                    code,
                    rows=rows_by_code[code],
                    history_rows=rows_by_code[code],
                    now=now,
                )
                self.assertEqual(model["decision_mode"], "terminal_checkpoint")
                self.assertFalse(model["has_published_hours"])
                self.assertEqual(
                    model["map"]["location_accuracy"],
                    "terminal_building_overview",
                )
                self.assertEqual(
                    [terminal["id"] for terminal in model["terminals"]],
                    expected[code]["terminal_ids"],
                )
                self.assertTrue(
                    all(
                        terminal["location_accuracy"]
                        in {
                            "terminal_building_centroid",
                            "terminal_building_overview_anchor",
                        }
                        for terminal in model["terminals"]
                    )
                )
                checkpoints = [
                    checkpoint
                    for terminal in model["terminals"]
                    for checkpoint in terminal["checkpoints"]
                ]
                self.assertEqual(
                    [checkpoint["id"] for checkpoint in checkpoints],
                    expected[code]["checkpoint_ids"],
                )
                self.assertEqual(model["unmatched_readings"], [])

        ord_model = self.app_module.build_airport_arrival_mode(
            "ORD",
            rows=[
                {
                    "checkpoint": "Terminal 2 — Checkpoint 5 General",
                    "wait_minutes": 4,
                    "captured_at": (now - timedelta(minutes=2)).isoformat(),
                },
                {
                    "checkpoint": "Terminal 2 — Checkpoint 5 TSA PreCheck",
                    "wait_minutes": 1,
                    "captured_at": (now - timedelta(minutes=2)).isoformat(),
                },
            ],
            history_rows=[],
            now=now,
        )
        checkpoint_five = next(
            checkpoint
            for terminal in ord_model["terminals"]
            for checkpoint in terminal["checkpoints"]
            if checkpoint["id"] == "ord-terminal-2-checkpoint-5"
        )
        self.assertEqual(checkpoint_five["lane_waits"], {"STANDARD": 4.0, "PRECHECK": 1.0})

    def test_dfw_and_phl_arrival_modes_preserve_terminal_checkpoint_ids(self):
        now = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)
        rows_by_code = {
            "DFW": [
                {
                    "checkpoint": f"{checkpoint} ({lane})",
                    "lane_type": "PRECHECK" if lane == "TSA Pre" else "STANDARD",
                    "wait_minutes": index,
                    "captured_at": (now - timedelta(minutes=2)).isoformat(),
                }
                for index, (checkpoint, lane) in enumerate(
                    (
                        ("A12", "General"), ("A21", "TSA Pre"),
                        ("A35", "General"), ("B9", "General"),
                        ("B30", "TSA Pre"), ("C10", "General"),
                        ("C11", "TSA Pre"), ("C20", "General"),
                        ("D18", "General"), ("D22", "General"),
                        ("D30", "TSA Pre"), ("E8", "General"),
                        ("E16", "TSA Pre"), ("E18", "General"),
                        ("E33", "General"),
                    )
                )
            ],
            "PHL": [
                {
                    "checkpoint": checkpoint,
                    "lane_type": "PRECHECK" if checkpoint == "C" else "STANDARD",
                    "wait_minutes": index,
                    "captured_at": (now - timedelta(minutes=2)).isoformat(),
                }
                for index, checkpoint in enumerate(
                    ("A-West", "A-East", "B", "C", "D/E", "F")
                )
            ],
        }
        expected = {
            "DFW": {
                "terminal_ids": [
                    "terminal-a", "terminal-b", "terminal-c", "terminal-d", "terminal-e"
                ],
                "checkpoint_ids": [
                    "dfw-a12", "dfw-a21", "dfw-a35", "dfw-b9", "dfw-b30",
                    "dfw-c10", "dfw-c11", "dfw-c20", "dfw-d18", "dfw-d22",
                    "dfw-d30", "dfw-e8", "dfw-e16", "dfw-e18", "dfw-e33",
                ],
            },
            "PHL": {
                "terminal_ids": ["a-west", "a-east", "b", "c", "d-e", "f"],
                "checkpoint_ids": [
                    "phl-a-west", "phl-a-east", "phl-b", "phl-c", "phl-d-e", "phl-f"
                ],
            },
        }

        for code in ("DFW", "PHL"):
            with self.subTest(code=code):
                model = self.app_module.build_airport_arrival_mode(
                    code, rows=rows_by_code[code], history_rows=rows_by_code[code], now=now
                )
                self.assertEqual(model["decision_mode"], "terminal_checkpoint")
                self.assertFalse(model["has_published_hours"])
                self.assertEqual(
                    [terminal["id"] for terminal in model["terminals"]],
                    expected[code]["terminal_ids"],
                )
                checkpoints = [
                    checkpoint
                    for terminal in model["terminals"]
                    for checkpoint in terminal["checkpoints"]
                ]
                self.assertEqual(
                    [checkpoint["id"] for checkpoint in checkpoints],
                    expected[code]["checkpoint_ids"],
                )
                self.assertEqual(model["unmatched_readings"], [])

        phl_c = next(
            checkpoint
            for terminal in self.app_module.build_airport_arrival_mode(
                "PHL", rows=rows_by_code["PHL"], history_rows=[], now=now
            )["terminals"]
            for checkpoint in terminal["checkpoints"]
            if checkpoint["id"] == "phl-c"
        )
        self.assertEqual(phl_c["lane_waits"], {"STANDARD": None, "PRECHECK": 3.0})

    def test_phl_and_dfw_collectors_preserve_lane_and_missing_wait_semantics(self):
        module = self.app_module

        class Response:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self.payload

        phl_payload = {
            "content": {"rows": [["5052", 4], ["4386", 6], ["3971", 8]]}
        }
        with patch.object(module.requests, "get", return_value=Response(phl_payload)):
            phl_rows = module.fetch_phl_rows()
        self.assertEqual(
            [(row["checkpoint"], row["lane_type"]) for row in phl_rows],
            [("C", "PRECHECK"), ("A-East", "PRECHECK"), ("D/E", "STANDARD")],
        )

        dfw_payload = {
            "data": {"wait_times": [
                {"isDisplayable": True, "name": "A12", "lane": "General", "waitSeconds": 0},
                {"isDisplayable": True, "name": "A21", "lane": "TSA Pre", "waitSeconds": 120},
                {"isDisplayable": True, "name": "A35", "lane": "General", "waitSeconds": None},
            ]}
        }
        with patch.object(module.requests, "get", return_value=Response(dfw_payload)):
            dfw_rows = module.fetch_dfw_rows()
        self.assertEqual(
            [(row["checkpoint"], row["lane_type"], row["wait_minutes"]) for row in dfw_rows],
            [("A12 (General)", "STANDARD", 0.0), ("A21 (TSA Pre)", "PRECHECK", 2.0)],
        )

    def test_jfk_collector_uses_public_graphql_endpoint_and_compressed_payload(self):
        module = self.app_module
        from lzstring import LZString

        class Response:
            def __init__(self, payload):
                self.payload = payload
                self.status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return self.payload

        payload = {
            "data": {
                "securityWaitTimes": [
                    {
                        "title": "Terminal 1",
                        "terminal": "1",
                        "gate": "All Gates",
                        "checkPoint": "Main ChekPoint",
                        "queueType": "Reg",
                        "isOpen": True,
                        "waitTime": 7,
                        "isWaitTimeAvailable": True,
                        "status": "Open",
                        "lastUpdated": "1:15 AM",
                    },
                    {
                        "title": "Terminal 1",
                        "terminal": "1",
                        "gate": "All Gates",
                        "checkPoint": "Main ChekPoint",
                        "queueType": "TSAPre",
                        "isOpen": True,
                        "waitTime": 2,
                        "isWaitTimeAvailable": True,
                        "status": "Open",
                        "lastUpdated": "1:15 AM",
                    },
                ]
            }
        }
        captured = {}

        def fake_post(url, data=None, headers=None, timeout=None):
            captured["url"] = url
            captured["data"] = data
            captured["headers"] = headers
            captured["timeout"] = timeout
            return Response(payload)

        with patch.object(module.requests, "post", side_effect=fake_post):
            rows = module.fetch_jfk_rows()

        self.assertEqual(captured["url"], "https://www.jfkairport.com/api/graphql")
        self.assertEqual(captured["headers"]["Content-Type"], "text/plain")
        self.assertEqual(captured["headers"]["Origin"], "https://www.jfkairport.com")
        decoded = json.loads(LZString().decompressFromEncodedURIComponent(captured["data"]))
        self.assertEqual(decoded["operationName"], "GetSecurityWaitTimes")
        self.assertEqual(decoded["variables"], {"airportCode": "JFK"})
        self.assertEqual([row["lane_type"] for row in rows], ["STANDARD", "PRECHECK"])
        self.assertEqual([row["wait_minutes"] for row in rows], [7.0, 2.0])

    def test_dtw_collector_uses_public_json_proxy(self):
        module = self.app_module

        class Response:
            def __init__(self, payload):
                self.payload = payload
                self.status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return self.payload

        payload = [
            {"Name": "McNamara", "WaitTime": 6},
            {"Name": "Evans", "WaitTime": 7},
        ]
        captured = {}

        def fake_get(url, headers=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["timeout"] = timeout
            return Response(payload)

        with patch.object(module.requests, "get", side_effect=fake_get):
            rows = module.fetch_dtw_rows()

        self.assertEqual(captured["url"], "https://proxy.metroairport.com/SkyFiiTSAProxy.ashx")
        self.assertEqual(captured["headers"]["Accept"], "application/json")
        self.assertEqual([row["checkpoint"] for row in rows], ["McNamara Terminal", "Evans Terminal"])
        self.assertEqual([row["wait_minutes"] for row in rows], [6.0, 7.0])
        self.assertTrue(all(row["lane_type"] == "STANDARD" for row in rows))

    def test_bwi_collector_uses_live_homepage_widget(self):
        module = self.app_module

        class Response:
            def __init__(self, html):
                self.content = html.encode("utf-8")
                self.status_code = 200

            def raise_for_status(self):
                return None

        html = """
        <div class="hud_item hud_item_3 hud_item_security js-security" data-file="/themes/custom/bwi/cache/wait-times.json">
          <header class="hud_header">
            <h2 class="hud_title">Security Wait Times</h2>
            <h3 class="hud_time hud_time_lg">as of <time class="js-security-update">1:36 am</time></h3>
          </header>
          <table class="hud_security_table">
            <tbody>
              <tr class="hud_security_table_row_A">
                <td>Checkpoint A</td><td>9 min</td><td>4 min</td><td>Closed</td><td>Closed</td>
              </tr>
              <tr class="hud_security_table_row_B">
                <td>Checkpoint B</td><td>1 min</td><td>1 min</td><td>4 min</td><td>1 min</td>
              </tr>
            </tbody>
          </table>
        </div>
        """
        captured = {}

        def fake_get(url, headers=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["timeout"] = timeout
            return Response(html)

        with patch.object(module.requests, "get", side_effect=fake_get):
            rows = module.fetch_bwi_rows()

        self.assertEqual(captured["url"], "https://bwiairport.com/")
        self.assertEqual(captured["headers"]["Accept-Encoding"], "br")
        self.assertEqual(
            [(row["checkpoint"], row["lane_type"], row["wait_minutes"]) for row in rows],
            [
                ("Checkpoint A", "STANDARD", 9.0),
                ("Checkpoint A", "PRIORITY", 4.0),
                ("Checkpoint B", "STANDARD", 1.0),
                ("Checkpoint B", "PRIORITY", 1.0),
                ("Checkpoint B", "PRECHECK", 4.0),
                ("Checkpoint B", "CLEAR", 1.0),
            ],
        )

    def test_mia_and_lax_arrival_modes_distinguish_live_and_published_context(self):
        now = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)
        rows_by_code = {
            "MIA": [
                {
                    "checkpoint": label,
                    "wait_minutes": index + 1,
                    "captured_at": (now - timedelta(minutes=2)).isoformat(),
                }
                for index, label in enumerate(
                    ("2 General", "2 Priority", "9 Clear", "9 General", "9 Priority")
                )
            ],
            "LAX": [
                {
                    "checkpoint": "TBIT",
                    "lane_type": lane,
                    "wait_minutes": wait,
                    "captured_at": (now - timedelta(minutes=2)).isoformat(),
                }
                for lane, wait in (("STANDARD", 4), ("PRECHECK", 1))
            ],
        }
        expected = {
            "MIA": {
                "terminal_ids": ["north-terminal-d", "central-terminal", "south-terminal"],
                "checkpoint_ids": [
                    "mia-1", "mia-2", "mia-3", "mia-4", "mia-dfis",
                    "mia-5", "mia-6", "mia-7", "mia-8", "mia-9", "mia-10",
                ],
                "published_only": 9,
            },
            "LAX": {
                "terminal_ids": [
                    "terminal-1", "terminal-2", "terminal-3", "terminal-b",
                    "terminal-4", "terminal-5", "terminal-6", "terminal-7-8",
                ],
                "checkpoint_ids": [
                    "lax-terminal-1", "lax-terminal-2", "lax-terminal-3", "lax-tbit",
                    "lax-terminal-4", "lax-terminal-5", "lax-terminal-6", "lax-terminal-7-8",
                ],
                "published_only": 7,
            },
        }

        for code in ("MIA", "LAX"):
            with self.subTest(code=code):
                model = self.app_module.build_airport_arrival_mode(
                    code, rows=rows_by_code[code], history_rows=rows_by_code[code], now=now
                )
                checkpoints = [
                    checkpoint
                    for terminal in model["terminals"]
                    for checkpoint in terminal["checkpoints"]
                ]
                self.assertEqual(model["decision_mode"], "terminal_checkpoint")
                self.assertEqual(
                    [terminal["id"] for terminal in model["terminals"]],
                    expected[code]["terminal_ids"],
                )
                self.assertEqual(
                    [checkpoint["id"] for checkpoint in checkpoints],
                    expected[code]["checkpoint_ids"],
                )
                self.assertEqual(
                    sum(checkpoint["published_only"] for checkpoint in checkpoints),
                    expected[code]["published_only"],
                )
                self.assertEqual(model["unmatched_readings"], [])

        mia = self.app_module.build_airport_arrival_mode(
            "MIA", rows=rows_by_code["MIA"], history_rows=[], now=now
        )
        mia_two = next(
            checkpoint for terminal in mia["terminals"]
            for checkpoint in terminal["checkpoints"] if checkpoint["id"] == "mia-2"
        )
        self.assertEqual(mia_two["lane_waits"]["STANDARD"], 1.0)

        lax = self.app_module.build_airport_arrival_mode(
            "LAX", rows=rows_by_code["LAX"], history_rows=[], now=now
        )
        tbit = next(
            checkpoint for terminal in lax["terminals"]
            for checkpoint in terminal["checkpoints"] if checkpoint["id"] == "lax-tbit"
        )
        self.assertEqual(tbit["lane_waits"], {"STANDARD": 4.0, "PRECHECK": 1.0})

    def test_lax_collector_does_not_convert_missing_wait_to_zero(self):
        module = self.app_module

        class Response:
            text = """
                <table>
                  <tr><th>Terminal</th><th>Boarding Type</th><th>Wait Time</th></tr>
                  <tr><td>TBIT</td><td>General Boarding</td><td>0 minutes</td></tr>
                  <tr><td>Terminal 1</td><td>General Boarding</td><td>Unavailable</td></tr>
                </table>
            """

            def raise_for_status(self):
                return None

        with patch.object(module.requests, "get", return_value=Response()):
            rows = module.fetch_lax_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["checkpoint"], "TBIT")
        self.assertEqual(rows[0]["wait_minutes"], 0.0)

    def test_den_security_anchors_are_in_jeppesen_terminal(self):
        model = self.app_module.build_airport_arrival_mode(
            "DEN", rows=[], history_rows=[], now=datetime.now(timezone.utc)
        )

        self.assertEqual(model["map"]["center"], [39.8535, -104.6737])
        self.assertEqual(model["map"]["bounds"][0], [39.8472, -104.6804])
        self.assertEqual(
            {terminal["id"]: terminal["anchor"] for terminal in model["terminals"]},
            {
                "west": [39.8512, -104.67455],
                "east": [39.8512, -104.67305],
            },
        )

    def test_terminal_checkpoint_airports_render_without_las_gate_controls(self):
        now = datetime.now(timezone.utc)
        rows_by_code = {
            "DCA": [
                {
                    "checkpoint": "Terminal 1 (A Gates)",
                    "lane_type": "STANDARD",
                    "wait_minutes": 5,
                    "captured_at": now.isoformat(),
                }
            ],
            "SFO": [
                {
                    "checkpoint": "Checkpoint B · Harvey Milk Terminal 1",
                    "lane_type": "STANDARD",
                    "wait_minutes": 6,
                    "captured_at": now.isoformat(),
                }
            ],
            "EWR": [
                {
                    "checkpoint": "Terminal B (40-49)",
                    "lane_type": "STANDARD",
                    "wait_minutes": 4,
                    "captured_at": now.isoformat(),
                }
            ],
            "LGA": [
                {
                    "checkpoint": "Terminal C",
                    "lane_type": "STANDARD",
                    "wait_minutes": 3,
                    "captured_at": now.isoformat(),
                }
            ],
            "BOS": [
                {
                    "checkpoint": "Checkpoint 4: Gates B23 - 40",
                    "lane_type": "STANDARD",
                    "wait_minutes": 5,
                    "captured_at": now.isoformat(),
                }
            ],
            "ORD": [
                {
                    "checkpoint": "Terminal 3 — Checkpoint 7A",
                    "lane_type": "STANDARD",
                    "wait_minutes": 7,
                    "captured_at": now.isoformat(),
                }
            ],
            "DFW": [
                {
                    "checkpoint": "C20 (General)",
                    "lane_type": "STANDARD",
                    "wait_minutes": 6,
                    "captured_at": now.isoformat(),
                }
            ],
            "BWI": [
                {
                    "checkpoint": "Checkpoint A",
                    "lane_type": "STANDARD",
                    "wait_minutes": 9,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint B",
                    "lane_type": "PRIORITY",
                    "wait_minutes": 1,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint C",
                    "lane_type": "PRECHECK",
                    "wait_minutes": 4,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint D/E",
                    "lane_type": "CLEAR",
                    "wait_minutes": 7,
                    "captured_at": now.isoformat(),
                },
            ],
            "DTW": [
                {
                    "checkpoint": "McNamara Terminal",
                    "lane_type": "STANDARD",
                    "wait_minutes": 6,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Evans Terminal",
                    "lane_type": "STANDARD",
                    "wait_minutes": 7,
                    "captured_at": now.isoformat(),
                },
            ],
            "DEN": [
                {
                    "checkpoint": "West Security",
                    "lane_type": "STANDARD",
                    "wait_minutes": 6,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "East Security",
                    "lane_type": "PRECHECK",
                    "wait_minutes": 4,
                    "captured_at": now.isoformat(),
                },
            ],
            "IAD": [
                {
                    "checkpoint": "East Checkpoint",
                    "lane_type": "STANDARD",
                    "wait_minutes": 8,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "West Checkpoint",
                    "lane_type": "STANDARD",
                    "wait_minutes": 7,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "TSA PreCheck",
                    "lane_type": "PRECHECK",
                    "wait_minutes": 3,
                    "captured_at": now.isoformat(),
                },
            ],
            "IAH": [
                {
                    "checkpoint": "Terminal A North",
                    "lane_type": "STANDARD",
                    "wait_minutes": 5,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Terminal A South",
                    "lane_type": "STANDARD",
                    "wait_minutes": 6,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Terminal B",
                    "lane_type": "STANDARD",
                    "wait_minutes": 0,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Terminal C North",
                    "lane_type": "STANDARD",
                    "wait_minutes": 4,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Terminal C South",
                    "lane_type": "STANDARD",
                    "wait_minutes": 5,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Terminal D",
                    "lane_type": "STANDARD",
                    "wait_minutes": 7,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Terminal E",
                    "lane_type": "STANDARD",
                    "wait_minutes": 6,
                    "captured_at": now.isoformat(),
                },
            ],
            "PHL": [
                {
                    "checkpoint": "D/E",
                    "lane_type": "STANDARD",
                    "wait_minutes": 5,
                    "captured_at": now.isoformat(),
                }
            ],
            "MIA": [
                {
                    "checkpoint": "2 General",
                    "lane_type": "STANDARD",
                    "wait_minutes": 4,
                    "captured_at": now.isoformat(),
                }
            ],
            "LAX": [
                {
                    "checkpoint": "TBIT",
                    "lane_type": "STANDARD",
                    "wait_minutes": 4,
                    "captured_at": now.isoformat(),
                }
            ],
            "JFK": [
                {
                    "checkpoint": "Terminal 1",
                    "lane_type": "STANDARD",
                    "wait_minutes": 9,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Terminal 4",
                    "lane_type": "STANDARD",
                    "wait_minutes": 7,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Terminal 5",
                    "lane_type": "STANDARD",
                    "wait_minutes": 8,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Terminal 7",
                    "lane_type": "STANDARD",
                    "wait_minutes": 6,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Terminal 8",
                    "lane_type": "STANDARD",
                    "wait_minutes": 5,
                    "captured_at": now.isoformat(),
                },
            ],
            "MCO": [
                {
                    "checkpoint": "West Standard",
                    "lane_type": "STANDARD",
                    "wait_minutes": 4,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "West PreCheck",
                    "lane_type": "PRECHECK",
                    "wait_minutes": 1,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "South Standard",
                    "lane_type": "STANDARD",
                    "wait_minutes": 3,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "South PreCheck",
                    "lane_type": "PRECHECK",
                    "wait_minutes": 1,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "East Standard",
                    "lane_type": "STANDARD",
                    "wait_minutes": 5,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "East PreCheck",
                    "lane_type": "PRECHECK",
                    "wait_minutes": 2,
                    "captured_at": now.isoformat(),
                },
            ],
            "JAX": [
                {
                    "checkpoint": "Main Checkpoint",
                    "lane_type": "STANDARD",
                    "wait_minutes": 4,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Main Checkpoint",
                    "lane_type": "PRECHECK",
                    "wait_minutes": 1,
                    "captured_at": now.isoformat(),
                },
            ],
            "SEA": [
                {
                    "checkpoint": "Checkpoint 1",
                    "lane_type": "STANDARD",
                    "wait_minutes": 7,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint 2",
                    "lane_type": "STANDARD",
                    "wait_minutes": 6,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint 3",
                    "lane_type": "STANDARD",
                    "wait_minutes": 15,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint 4",
                    "lane_type": "STANDARD",
                    "wait_minutes": 4,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint 5",
                    "lane_type": "STANDARD",
                    "wait_minutes": 9,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint 6",
                    "lane_type": "STANDARD",
                    "wait_minutes": 11,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint 6",
                    "lane_type": "PRECHECK",
                    "wait_minutes": 2,
                    "captured_at": now.isoformat(),
                },
            ],
        }
        module = self.app_module
        original_codes = module.AIRPORT_ARRIVAL_MODE_CODES
        try:
            module.AIRPORT_ARRIVAL_MODE_CODES = {
                "DCA",
                "SFO",
                "EWR",
                "LGA",
                "BOS",
                "ORD",
                "DFW",
                "DEN",
                "BWI",
                "DTW",
                "IAD",
                "IAH",
                "PHL",
                "MIA",
                "LAX",
                "JFK",
                "MCO",
                "JAX",
                "SEA",
            }
            for code, marker_count, checkpoint_count, checkpoint_id in (
                ("DCA", 3, 3, "dca-t1"),
                ("SFO", 5, 6, "sfo-checkpoint-b"),
                ("EWR", 3, 5, "ewr-terminal-b-40-49"),
                ("LGA", 2, 2, "lga-terminal-c"),
                ("BOS", 4, 7, "bos-checkpoint-4-gates-b23-40"),
                ("ORD", 4, 8, "ord-terminal-3-checkpoint-7a"),
                ("DFW", 5, 15, "dfw-c20"),
                ("DEN", 2, 2, "den-west"),
                ("BWI", 4, 4, "bwi-b"),
                ("DTW", 2, 2, "dtw-mcnamara"),
                ("IAD", 3, 3, "iad-east"),
                ("IAH", 5, 7, "iah-terminal-a-north"),
                ("PHL", 6, 6, "phl-d-e"),
                ("MIA", 3, 11, "mia-2"),
                ("LAX", 8, 8, "lax-tbit"),
                ("JFK", 5, 5, "jfk-terminal-4"),
                ("MCO", 3, 3, "mco-west"),
                ("JAX", 1, 1, "jax-main"),
                ("SEA", 6, 6, "sea-checkpoint-6"),
            ):
                with self.subTest(code=code), patch.object(
                    module, "latest_for_code", return_value=rows_by_code[code]
                ), patch.object(
                    module, "history_for_airport", return_value=rows_by_code[code]
                ):
                    html, document = self.get_html(self.airport_routes[code])
                    api_response = self.client.get(
                        f"/api/airport-arrival-mode?airport={code}"
                    )
                    calculator_html, _ = self.get_html(
                        f"/when-should-i-leave?airport={code}"
                        f"&checkpoint={checkpoint_id}&lane=STANDARD"
                    )

                markers = [
                    attrs
                    for tag, attrs in document.elements
                    if tag == "button" and "data-arrival-terminal-marker" in attrs
                ]
                checkpoint_buttons = [
                    attrs
                    for tag, attrs in document.elements
                    if tag == "button" and "data-arrival-checkpoint-choice" in attrs
                ]
                self.assertEqual(len(markers), marker_count)
                self.assertEqual(len(checkpoint_buttons), checkpoint_count)
                self.assertIn("Terminal or checkpoint area", html)
                self.assertNotIn("Gate on your boarding pass", html)
                self.assertIn("data-location-accuracy", html)
                self.assertEqual(api_response.status_code, 200)
                self.assertEqual(
                    api_response.get_json()["decision_mode"], "terminal_checkpoint"
                )
                selection_match = re.search(
                    r"var CALCULATOR_SELECTION = (\{.*?\});",
                    calculator_html,
                    re.DOTALL,
                )
                self.assertIsNotNone(selection_match)
                self.assertEqual(
                    json.loads(selection_match.group(1)),
                    {
                        "airport": code,
                        "checkpoint": checkpoint_id,
                        "lane": "STANDARD",
                    },
                )
        finally:
            module.AIRPORT_ARRIVAL_MODE_CODES = original_codes

    def test_generic_arrival_mode_keeps_label_encoded_lane_trends_separate(self):
        now = datetime(2026, 7, 10, 20, 0, tzinfo=timezone.utc)
        history_rows = [
            {"checkpoint": "Terminal 4 General", "lane_type": "STANDARD", "wait_minutes": 5, "captured_at": (now - timedelta(minutes=30)).isoformat()},
            {"checkpoint": "Terminal 4 General", "lane_type": "STANDARD", "wait_minutes": 12, "captured_at": (now - timedelta(minutes=20)).isoformat()},
            {"checkpoint": "Terminal 4 TSA PreCheck", "lane_type": "STANDARD", "wait_minutes": 9, "captured_at": (now - timedelta(minutes=30)).isoformat()},
            {"checkpoint": "Terminal 4 TSA PreCheck", "lane_type": "STANDARD", "wait_minutes": 3, "captured_at": (now - timedelta(minutes=20)).isoformat()},
        ]
        rows = [
            {"checkpoint": "Terminal 4 General", "lane_type": "STANDARD", "wait_minutes": 12, "captured_at": (now - timedelta(minutes=2)).isoformat()},
            {"checkpoint": "Terminal 4 TSA PreCheck", "lane_type": "STANDARD", "wait_minutes": 3, "captured_at": (now - timedelta(minutes=2)).isoformat()},
        ]
        module = self.app_module
        with patch.dict(module.AIRPORT_DECISION_MAPS, {"JFK": None}, clear=False):
            model = module.build_airport_arrival_mode(
                "JFK", rows=rows, history_rows=history_rows, now=now
            )
        self.assertIsNotNone(model)
        lanes = {
            lane["lane_type"]: lane
            for lane in model["terminals"][0]["checkpoints"][0]["lanes"]
        }
        self.assertEqual(lanes["STANDARD"]["trend"], "rising")
        self.assertEqual(lanes["PRECHECK"]["trend"], "falling")

    def test_las_arrival_mode_trends_remain_checkpoint_and_lane_separated(self):
        now = datetime(2026, 7, 10, 20, 0, tzinfo=timezone.utc)
        rows = [
            {
                "checkpoint": "T1 - A/B Gates",
                "lane_type": "STANDARD",
                "wait_minutes": 12,
                "captured_at": (now - timedelta(minutes=2)).isoformat(),
            },
            {
                "checkpoint": "T1 - A/B Gates",
                "lane_type": "PRECHECK",
                "wait_minutes": 3,
                "captured_at": (now - timedelta(minutes=2)).isoformat(),
            },
        ]
        history_rows = [
            {
                "checkpoint": "Terminal 1 - A/B Gates",
                "lane_type": "STANDARD",
                "wait_minutes": 5,
                "captured_at": (now - timedelta(minutes=30)).isoformat(),
            },
            {
                "checkpoint": "T1 - A/B Gates",
                "lane_type": "STANDARD",
                "wait_minutes": 12,
                "captured_at": (now - timedelta(minutes=20)).isoformat(),
            },
            {
                "checkpoint": "Terminal 1 - A/B Gates",
                "lane_type": "PRECHECK",
                "wait_minutes": 10,
                "captured_at": (now - timedelta(minutes=30)).isoformat(),
            },
            {
                "checkpoint": "T1 - A/B Gates",
                "lane_type": "PRECHECK",
                "wait_minutes": 3,
                "captured_at": (now - timedelta(minutes=20)).isoformat(),
            },
        ]
        model = self.app_module.build_airport_arrival_mode(
            "LAS", rows=rows, history_rows=history_rows, now=now
        )
        checkpoint = next(
            checkpoint
            for terminal in model["terminals"]
            for checkpoint in terminal["checkpoints"]
            if checkpoint["id"] == "las-t1-ab"
        )
        lanes = {lane["lane_type"]: lane for lane in checkpoint["lanes"]}
        self.assertEqual(lanes["STANDARD"]["wait_minutes"], 12)
        self.assertEqual(lanes["STANDARD"]["trend"], "rising")
        self.assertEqual(lanes["STANDARD"]["trend_delta"], 7)
        self.assertEqual(lanes["PRECHECK"]["wait_minutes"], 3)
        self.assertEqual(lanes["PRECHECK"]["trend"], "falling")
        self.assertEqual(lanes["PRECHECK"]["trend_delta"], -7)

    def test_supabase_history_contract_retains_and_groups_lane_type(self):
        supabase_module = importlib.import_module("supabase_integration")
        captured_at = "2026-07-10T12:00:00+00:00"
        raw_rows = [
            {
                "checkpoint": "T1 - A/B Gates",
                "lane_type": "STANDARD",
                "wait_minutes": 20,
                "captured_at": captured_at,
            },
            {
                "checkpoint": "T1 - A/B Gates",
                "lane_type": "PRECHECK",
                "wait_minutes": 4,
                "captured_at": captured_at,
            },
        ]
        aggregate_rows = [
            {
                "checkpoint": "T1 - A/B Gates",
                "lane_type": "STANDARD",
                "wait_sum": 40,
                "sample_count": 2,
                "hour_bucket": captured_at,
            },
            {
                "checkpoint": "T1 - A/B Gates",
                "lane_type": "PRECHECK",
                "wait_sum": 8,
                "sample_count": 2,
                "hour_bucket": captured_at,
            },
        ]
        with patch.object(
            supabase_module, "init_supabase", return_value=object()
        ), patch.object(
            supabase_module, "_select_historical_samples", return_value=raw_rows
        ) as raw_select, patch.object(
            supabase_module,
            "_select_historical_hourly_aggregates",
            return_value=aggregate_rows,
        ):
            history_rows = supabase_module.supabase_history_rows("LAS")
            self.assertEqual(history_rows, raw_rows)
            self.assertIn("lane_type", raw_select.call_args.kwargs["columns"])

            groups = supabase_module.supabase_checkpoint_24h_average(
                "LAS", time_zone_name="UTC"
            )

        by_lane = {group["lane_type"]: group for group in groups}
        self.assertEqual(set(by_lane), {"STANDARD", "PRECHECK"})
        standard_noon = by_lane["STANDARD"]["rows"][12]
        precheck_noon = by_lane["PRECHECK"]["rows"][12]
        self.assertEqual(standard_noon["avg_wait"], 20)
        self.assertEqual(standard_noon["samples"], 3)
        self.assertEqual(precheck_noon["avg_wait"], 4)
        self.assertEqual(precheck_noon["samples"], 3)
        self.assertIn("lane_type", raw_select.call_args.kwargs["columns"])

    def test_las_collector_skips_missing_waits_but_preserves_numeric_zero(self):
        timestamp_ms = 1783713600000
        init_payload = [
            {
                "result": {
                    "data": {
                        "journeys": {
                            "journey-one": {"name": "T1 - A/B Gates"}
                        }
                    }
                }
            }
        ]
        update_payload = [
            {
                "result": {
                    "data": {
                        "paths": {
                            "standard": {
                                "open": True,
                                "waitTime": {
                                    "value": 0,
                                    "timestamp": timestamp_ms,
                                },
                            },
                            "precheck": {
                                "open": True,
                                "waitTime": {
                                    "value": None,
                                    "timestamp": timestamp_ms,
                                },
                            },
                            "missing": {"open": True, "waitTime": {}},
                        }
                    }
                }
            }
        ]

        class Response:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self.payload

        with patch.object(
            self.app_module.requests,
            "get",
            side_effect=[Response(init_payload), Response(update_payload)],
        ):
            rows = self.app_module.fetch_las_rows()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["checkpoint"], "T1 - A/B Gates")
        self.assertEqual(rows[0]["lane_type"], "STANDARD")
        self.assertEqual(rows[0]["wait_minutes"], 0)

    def test_las_arrival_api_validates_airports_and_feature_allowlist(self):
        now = self.app_module.utc_now()
        rows = [
            {
                "checkpoint": "T1 - A/B Gates",
                "lane_type": "STANDARD",
                "wait_minutes": 3,
                "captured_at": now.isoformat(),
            }
        ]
        module = self.app_module
        original_codes = module.AIRPORT_ARRIVAL_MODE_CODES
        try:
            module.AIRPORT_ARRIVAL_MODE_CODES = {"LAS"}
            with patch.object(module, "latest_for_code", return_value=rows), patch.object(
                module, "history_for_airport", return_value=rows
            ):
                response = self.client.get("/api/airport-arrival-mode?airport=las")
                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                self.assertEqual(payload["schema_version"], 1)
                self.assertEqual(payload["airport"]["code"], "LAS")
                self.assertEqual(payload["refresh_seconds"], 120)

            self.assertEqual(
                self.client.get("/api/airport-arrival-mode").status_code, 400
            )
            self.assertEqual(
                self.client.get("/api/airport-arrival-mode?airport=XYZ").status_code,
                400,
            )
            self.assertEqual(
                self.client.get("/api/airport-arrival-mode?airport=PHL").status_code,
                404,
            )

            module.AIRPORT_ARRIVAL_MODE_CODES = set()
            self.assertEqual(
                self.client.get("/api/airport-arrival-mode?airport=LAS").status_code,
                404,
            )
        finally:
            module.AIRPORT_ARRIVAL_MODE_CODES = original_codes

    def test_arrival_mode_survives_history_dependency_failure(self):
        module = self.app_module
        original_codes = module.AIRPORT_ARRIVAL_MODE_CODES
        try:
            module.AIRPORT_ARRIVAL_MODE_CODES = {"LAS"}
            with patch.object(
                module,
                "history_for_airport",
                side_effect=RuntimeError("history unavailable"),
            ):
                html, _ = self.get_html(self.airport_routes["LAS"])
                self.assertIn("data-airport-arrival-mode", html)
                self.assertNotIn("data-decision-map", html)

                api_response = self.client.get(
                    "/api/airport-arrival-mode?airport=LAS"
                )
                self.assertEqual(api_response.status_code, 200)
                self.assertEqual(api_response.get_json()["schema_version"], 1)

                calculator_html, _ = self.get_html(
                    "/when-should-i-leave?airport=LAS&checkpoint=las-t1-ab&lane=STANDARD"
                )
                self.assertIn("var CALCULATOR_CHECKPOINTS", calculator_html)
        finally:
            module.AIRPORT_ARRIVAL_MODE_CODES = original_codes

    def test_arrival_mode_renders_once_for_las_and_preserves_page_contracts(self):
        now = self.app_module.utc_now()
        rows = [
            {
                "checkpoint": "T1 - A/B Gates",
                "lane_type": "STANDARD",
                "wait_minutes": 0,
                "captured_at": now.isoformat(),
                "source": "https://source.test/las",
            }
        ]
        module = self.app_module
        original_codes = module.AIRPORT_ARRIVAL_MODE_CODES
        try:
            module.AIRPORT_ARRIVAL_MODE_CODES = {"LAS"}
            with patch.object(module, "latest_for_code", return_value=rows), patch.object(
                module, "history_for_airport", return_value=rows
            ):
                las_html, las_document = self.get_html(self.airport_routes["LAS"])

            arrivals = [
                attrs
                for tag, attrs in las_document.elements
                if tag == "section" and "data-airport-arrival-mode" in attrs
            ]
            self.assertEqual(len(arrivals), 1)
            self.assertEqual(arrivals[0].get("data-airport-code"), "LAS")
            self.assertEqual(las_document.h1_count, 1)
            self.assertIn("LAS TSA wait times", las_document.h1)
            self.assertEqual(
                las_document.canonical_hrefs,
                [f"{module.SITE_URL}{self.airport_routes['LAS']}"],
            )
            schema_types = {item.get("@type") for item in las_document.json_ld}
            self.assertIn("BreadcrumbList", schema_types)
            self.assertIn("WebPage", schema_types)
            self.assertIn("Raw checkpoint readings", las_html)
            self.assertIn("data-arrival-raw-feed", las_html)
            self.assertIn("T1 - A/B Gates", las_html)
            self.assertIn(
                "/api/history-24h-average?airport=LAS&days=30", las_html
            )
            self.assertIn(
                "/api/checkpoint-history-24h-average?airport=LAS&days=30",
                las_html,
            )
            self.assertIn("airport-arrival-mode-data", las_html)
            self.assertEqual(
                len(
                    re.findall(
                        r'<script[^>]+src="/static/airport-decision-map\.js\?v=[^"]+"',
                        las_html,
                    )
                ),
                1,
            )
            self.assertEqual(
                len(
                    re.findall(
                        r'<link[^>]+href="/static/tracker\.css\?v=[^"]+"',
                        las_html,
                    )
                ),
                1,
            )
            self.assertIn("Satellite airport view", las_html)
            self.assertIn("Hours are published reference windows", las_html)
            self.assertIn("not an “open now” calculation", las_html)

            phl_html, phl_document = self.get_html(self.airport_routes["PHL"])
            self.assertEqual(phl_document.h1_count, 1)
            self.assertNotIn("data-airport-arrival-mode", phl_html)
            self.assertNotIn("airport-arrival-mode-data", phl_html)
            self.assertNotIn("airport-decision-map.js", phl_html)
            self.assertNotIn("leaflet.css", phl_html)
            self.assertNotRegex(phl_html, r"/static/tracker\.css\?v=")
        finally:
            module.AIRPORT_ARRIVAL_MODE_CODES = original_codes

    def test_arrival_mode_rollout_renders_generic_pages_api_and_calculator_links(self):
        now = self.app_module.utc_now()
        rows_by_code = {
            "ATL": [
                {
                    "checkpoint": "Main Checkpoint",
                    "lane_type": "STANDARD",
                    "wait_minutes": 7,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "North Checkpoint",
                    "lane_type": "STANDARD",
                    "wait_minutes": 3,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Lower North Checkpoint",
                    "lane_type": "STANDARD",
                    "wait_minutes": 5,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "South Checkpoint",
                    "lane_type": "STANDARD",
                    "wait_minutes": 4,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "International Main Checkpoint",
                    "lane_type": "STANDARD",
                    "wait_minutes": 6,
                    "captured_at": now.isoformat(),
                },
            ],
            "CLT": [
                {
                    "checkpoint": "Checkpoint 1 (Standard)",
                    "lane_type": "STANDARD",
                    "wait_minutes": 6,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint 2 (Standard)",
                    "lane_type": "STANDARD",
                    "wait_minutes": 8,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint 2 (PreCheck)",
                    "lane_type": "PRECHECK",
                    "wait_minutes": 2,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint 3 (Standard)",
                    "lane_type": "STANDARD",
                    "wait_minutes": 9,
                    "captured_at": now.isoformat(),
                },
            ],
            "JFK": [
                {
                    "checkpoint": "Terminal 1",
                    "lane_type": "STANDARD",
                    "wait_minutes": 9,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Terminal 4",
                    "lane_type": "STANDARD",
                    "wait_minutes": 7,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Terminal 5",
                    "lane_type": "STANDARD",
                    "wait_minutes": 8,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Terminal 7",
                    "lane_type": "STANDARD",
                    "wait_minutes": 6,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Terminal 8",
                    "lane_type": "STANDARD",
                    "wait_minutes": 5,
                    "captured_at": now.isoformat(),
                },
            ],
            "MCO": [
                {
                    "checkpoint": "West Standard",
                    "lane_type": "STANDARD",
                    "wait_minutes": 4,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "West PreCheck",
                    "lane_type": "PRECHECK",
                    "wait_minutes": 1,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "South Standard",
                    "lane_type": "STANDARD",
                    "wait_minutes": 3,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "South PreCheck",
                    "lane_type": "PRECHECK",
                    "wait_minutes": 1,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "East Standard",
                    "lane_type": "STANDARD",
                    "wait_minutes": 5,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "East PreCheck",
                    "lane_type": "PRECHECK",
                    "wait_minutes": 2,
                    "captured_at": now.isoformat(),
                },
            ],
            "JAX": [
                {
                    "checkpoint": "Main Checkpoint",
                    "lane_type": "STANDARD",
                    "wait_minutes": 4,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Main Checkpoint",
                    "lane_type": "PRECHECK",
                    "wait_minutes": 1,
                    "captured_at": now.isoformat(),
                },
            ],
            "SEA": [
                {
                    "checkpoint": "Checkpoint 1",
                    "lane_type": "STANDARD",
                    "wait_minutes": 7,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint 2",
                    "lane_type": "STANDARD",
                    "wait_minutes": 6,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint 3",
                    "lane_type": "STANDARD",
                    "wait_minutes": 15,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint 4",
                    "lane_type": "STANDARD",
                    "wait_minutes": 4,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint 5",
                    "lane_type": "STANDARD",
                    "wait_minutes": 9,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint 6",
                    "lane_type": "STANDARD",
                    "wait_minutes": 11,
                    "captured_at": now.isoformat(),
                },
                {
                    "checkpoint": "Checkpoint 6",
                    "lane_type": "PRECHECK",
                    "wait_minutes": 2,
                    "captured_at": now.isoformat(),
                },
            ],
        }
        expectations = {
            "ATL": {
                "checkpoint_id": "atl-main",
                "marker_count": 5,
                "checkpoint_count": 5,
                "lane": "STANDARD",
            },
            "CLT": {
                "checkpoint_id": "clt-checkpoint-2",
                "marker_count": 3,
                "checkpoint_count": 3,
                "lane": "PRECHECK",
            },
            "JFK": {
                "checkpoint_id": "jfk-terminal-4",
                "marker_count": 5,
                "checkpoint_count": 5,
                "lane": "STANDARD",
            },
            "MCO": {
                "checkpoint_id": "mco-west",
                "marker_count": 3,
                "checkpoint_count": 3,
                "lane": "STANDARD",
            },
            "JAX": {
                "checkpoint_id": "jax-main",
                "marker_count": 1,
                "checkpoint_count": 1,
                "lane": "PRECHECK",
            },
            "SEA": {
                "checkpoint_id": "sea-checkpoint-6",
                "marker_count": 6,
                "checkpoint_count": 6,
                "lane": "PRECHECK",
            },
        }
        module = self.app_module
        original_codes = module.AIRPORT_ARRIVAL_MODE_CODES
        try:
            module.AIRPORT_ARRIVAL_MODE_CODES = set(module.LIVE_AIRPORTS)
            for code, expectation in expectations.items():
                with self.subTest(code=code), patch.object(
                    module, "latest_for_code", return_value=rows_by_code[code]
                ), patch.object(
                    module, "history_for_airport", return_value=rows_by_code[code]
                ):
                    html, document = self.get_html(self.airport_routes[code])
                    api_response = self.client.get(
                        f"/api/airport-arrival-mode?airport={code}"
                    )
                    calculator_html, _ = self.get_html(
                        f"/when-should-i-leave?airport={code}"
                        f"&checkpoint={expectation['checkpoint_id']}&lane={expectation['lane']}"
                    )

                arrivals = [
                    attrs for tag, attrs in document.elements
                    if tag == "section" and "data-airport-arrival-mode" in attrs
                ]
                self.assertEqual(len(arrivals), 1)
                self.assertEqual(arrivals[0].get("data-airport-code"), code)
                self.assertEqual(document.h1_count, 1)
                self.assertIn("Satellite airport view", html)
                self.assertIn("Choose a terminal area and screening lane.", html)
                self.assertNotIn("Check-in terminal", html)
                self.assertNotIn("Gate on your boarding pass", html)
                self.assertIn("Screening lane", html)
                self.assertIn("tracker.css?v=20260713-5", html)
                self.assertIn("airport-decision-map.js?v=20260713-5", html)

                marker_buttons = [
                    attrs
                    for tag, attrs in document.elements
                    if tag == "button" and "data-arrival-terminal-marker" in attrs
                ]
                checkpoint_buttons = [
                    attrs
                    for tag, attrs in document.elements
                    if tag == "button" and "data-arrival-checkpoint-choice" in attrs
                ]
                self.assertEqual(len(marker_buttons), expectation["marker_count"])
                self.assertEqual(len(checkpoint_buttons), expectation["checkpoint_count"])

                self.assertEqual(api_response.status_code, 200)
                payload = api_response.get_json()
                self.assertEqual(payload["airport"]["code"], code)
                self.assertEqual(payload["decision_mode"], "terminal_checkpoint")

                match = re.search(
                    r"var CALCULATOR_SELECTION = (\{.*?\});", calculator_html, re.DOTALL
                )
                self.assertIsNotNone(match)
                self.assertEqual(
                    json.loads(match.group(1)),
                    {"airport": code, "checkpoint": expectation["checkpoint_id"], "lane": expectation["lane"]},
                )
        finally:
            module.AIRPORT_ARRIVAL_MODE_CODES = original_codes

    def test_default_arrival_mode_rollout_matches_every_tracked_airport(self):
        configured = {
            code.strip()
            for code in self.app_module.DEFAULT_AIRPORT_ARRIVAL_MODE_CODES.split(",")
            if code.strip()
        }
        self.assertEqual(configured, set(self.app_module.LIVE_AIRPORTS))

    def test_arrival_mode_controls_and_assets_have_accessible_fallback_contracts(self):
        html, document = self.get_html(self.airport_routes["LAS"])

        marker_buttons = [
            attrs
            for tag, attrs in document.elements
            if tag == "button" and "data-arrival-terminal-marker" in attrs
        ]
        checkpoint_buttons = [
            attrs
            for tag, attrs in document.elements
            if tag == "button" and "data-arrival-checkpoint-choice" in attrs
        ]
        self.assertEqual(len(marker_buttons), 2)
        self.assertEqual(len(checkpoint_buttons), 5)
        for attrs in marker_buttons + checkpoint_buttons:
            self.assertEqual(attrs.get("type"), "button")
            self.assertTrue(attrs.get("aria-label"))
            self.assertEqual(attrs.get("aria-pressed"), "false")

        by_attribute = {
            key: attrs
            for tag, attrs in document.elements
            for key in (
                "data-arrival-map-expand",
                "data-arrival-map-done",
                "data-arrival-sheet-toggle",
            )
            if tag == "button" and key in attrs
        }
        self.assertEqual(
            set(by_attribute),
            {
                "data-arrival-map-expand",
                "data-arrival-map-done",
                "data-arrival-sheet-toggle",
            },
        )
        self.assertEqual(
            by_attribute["data-arrival-map-expand"].get("aria-expanded"),
            "false",
        )
        self.assertEqual(
            by_attribute["data-arrival-sheet-toggle"].get("aria-expanded"),
            "false",
        )
        self.assertTrue(
            by_attribute["data-arrival-map-done"].get("aria-label")
        )

        status = next(
            attrs
            for tag, attrs in document.elements
            if attrs.get("id") == "arrival-map-status"
        )
        self.assertEqual(status.get("role"), "status")
        self.assertEqual(status.get("aria-live"), "polite")
        self.assertIn("data-arrival-map-fallback", html)
        self.assertIn("<noscript>", html)
        self.assertIn("Satellite view requires JavaScript.", html)
        self.assertIn("data-arrival-calculator-link", html)

        script_src = next(
            attrs["src"]
            for tag, attrs in document.elements
            if tag == "script"
            and attrs.get("src", "").split("?", 1)[0]
            == "/static/airport-decision-map.js"
        )
        response = self.client.get(script_src)
        self.assertEqual(response.status_code, 200)
        source = response.get_data(as_text=True)
        response.close()
        for token in (
            '[data-airport-arrival-mode]',
            '[data-decision-map]',
            'HANDOFF_KEY = "tsaAirportHandoffV1"',
            "HANDOFF_MAX_AGE_MS = 10000",
            "window.sessionStorage.getItem(HANDOFF_KEY)",
            "window.sessionStorage.removeItem(HANDOFF_KEY)",
            'source !== "home-map"',
            '(prefers-reduced-motion: reduce)',
            'event.key !== "Escape"',
            'document.body.classList.toggle("arrival-map-is-expanded"',
            'setBackgroundInert(',
            'focusTarget.focus()',
            'setSheetDetailed(false)',
            'showMapFallback(',
            'mapUnavailable = true',
            'expandButton.hidden = mapUnavailable',
            'imagery.on("tileerror"',
            'map.setView(handoff.center',
            'map.flyTo(anchor, detailZoom()',
            'button.setAttribute("aria-pressed"',
            'waitTier(wait)',
            'currentWait.className = "arrival-current-wait"',
            '/api/airport-arrival-mode?airport=',
            'startRefreshTimer()',
        ):
            self.assertIn(token, source)

        stylesheet_src = next(
            attrs["href"]
            for tag, attrs in document.elements
            if tag == "link"
            and attrs.get("href", "").split("?", 1)[0] == "/static/tracker.css"
        )
        response = self.client.get(stylesheet_src)
        self.assertEqual(response.status_code, 200)
        css = response.get_data(as_text=True)
        response.close()
        for pattern in (
            r"\.arrival-terminal-marker\s*\{[^}]*min-height:\s*(?:4[4-9]|[5-9]\d)px",
            r"\.arrival-checkpoint-choice\s*\{[^}]*min-height:\s*(?:4[4-9]|[5-9]\d)px",
            r"\.arrival-map-zoom button\s*\{[^}]*min-width:\s*44px[^}]*min-height:\s*44px",
            r"\.arrival-map-expand,\s*\.arrival-map-done\s*\{[^}]*min-height:\s*44px",
            r"body\.arrival-map-is-expanded\s*\{[^}]*overflow:\s*hidden",
            r"\.airport-arrival-mode\.is-mobile-embedded \.arrival-map-canvas\s*\{[^}]*touch-action:\s*pan-y",
        ):
            self.assertRegex(css, pattern)

    def test_empty_arrival_allowlist_restores_legacy_las_experience(self):
        module = self.app_module
        original_codes = module.AIRPORT_ARRIVAL_MODE_CODES
        try:
            module.AIRPORT_ARRIVAL_MODE_CODES = set()
            html, document = self.get_html(self.airport_routes["LAS"])
            self.assertEqual(document.h1_count, 1)
            self.assertNotIn("data-airport-arrival-mode", html)
            self.assertNotIn("airport-arrival-mode-data", html)
            self.assertIn("data-decision-map", html)
            self.assertIn("LAS TSA checkpoint map", html)
            self.assertIn("airport-decision-map.js", html)
            script_src = next(
                attrs["src"]
                for tag, attrs in document.elements
                if tag == "script"
                and attrs.get("src", "").split("?", 1)[0]
                == "/static/airport-decision-map.js"
            )
            response = self.client.get(script_src)
            source = response.get_data(as_text=True)
            response.close()
            self.assertIn('document.querySelector("[data-decision-map]")', source)
            self.assertIn('form.addEventListener("change", update)', source)
        finally:
            module.AIRPORT_ARRIVAL_MODE_CODES = original_codes

    def test_default_routes_have_no_monetization_code(self):
        routes = list(CORE_ROUTES) + list(self.airport_routes.values())
        for route in routes:
            with self.subTest(route=route):
                html, _ = self.get_html(route)
                self.assertNotIn("pagead2.googlesyndication.com", html)
                self.assertNotIn("adsbygoogle", html)
                self.assertNotIn("skimresources.com", html)
                self.assertNotIn("googletagmanager.com/gtag/js", html)

    def test_analytics_is_opt_in(self):
        module = self.app_module
        original_enabled = module.ENABLE_ANALYTICS
        original_measurement_id = module.GA_MEASUREMENT_ID
        try:
            module.ENABLE_ANALYTICS = True
            module.GA_MEASUREMENT_ID = "G-TEST123"
            html, _ = self.get_html("/")
            self.assertIn("googletagmanager.com/gtag/js?id=G-TEST123", html)
            self.assertIn('gtag("config", "G-TEST123")', html)
        finally:
            module.ENABLE_ANALYTICS = original_enabled
            module.GA_MEASUREMENT_ID = original_measurement_id

    def test_monetization_is_opt_in_and_route_scoped(self):
        module = self.app_module
        original = {
            key: getattr(module, key)
            for key in (
                "ENABLE_ADSENSE",
                "ADSENSE_CLIENT",
                "ADSENSE_SLOT_DISPLAY",
                "ADSENSE_SLOT_MULTIPLEX",
                "SKIMLINKS_SCRIPT_URL",
            )
        }
        try:
            module.ENABLE_ADSENSE = True
            module.ADSENSE_CLIENT = "ca-pub-test"
            module.ADSENSE_SLOT_DISPLAY = "display-slot"
            module.ADSENSE_SLOT_MULTIPLEX = "multiplex-slot"
            module.SKIMLINKS_SCRIPT_URL = "https://example.test/skimlinks.js"

            home_html, _ = self.get_html("/")
            self.assertEqual(home_html.count('class="adsbygoogle"'), 1)
            self.assertIn('data-ad-slot="display-slot"', home_html)
            self.assertIn('data-ad-format="auto"', home_html)
            self.assertNotIn("multiplex-slot", home_html)

            airport_html, _ = self.get_html(self.airport_routes["LAS"])
            self.assertEqual(airport_html.count('class="adsbygoogle"'), 1)
            self.assertIn('data-ad-slot="display-slot"', airport_html)

            guide_html, _ = self.get_html("/guide/tsa-precheck-clear")
            self.assertEqual(guide_html.count('class="adsbygoogle"'), 1)
            self.assertIn('data-ad-slot="multiplex-slot"', guide_html)
            self.assertIn('data-ad-format="autorelaxed"', guide_html)
            self.assertIn("Advertisements", guide_html)
            self.assertNotIn(">Sponsored<", guide_html)
            self.assertIn("https://example.test/skimlinks.js", guide_html)
            self.assertLess(guide_html.index("Disclosure:"), guide_html.index('rel="sponsored noopener noreferrer"'))

            for route in ("/airports", "/when-should-i-leave", "/about", "/methodology"):
                html, _ = self.get_html(route)
                self.assertNotIn("pagead2.googlesyndication.com", html)
                self.assertNotIn("adsbygoogle", html)
                self.assertNotIn("skimlinks.js", html)
        finally:
            for key, value in original.items():
                setattr(module, key, value)

    def test_internal_graph_is_disabled_and_never_monetized(self):
        module = self.app_module
        original_graph = module.ENABLE_INTERNAL_GRAPH
        original_ads = module.ENABLE_ADSENSE
        original_client = module.ADSENSE_CLIENT
        try:
            module.ENABLE_INTERNAL_GRAPH = False
            self.assertEqual(self.client.get("/link-graph").status_code, 404)
            self.assertEqual(self.client.get("/wide-link-graph").status_code, 404)

            module.ENABLE_INTERNAL_GRAPH = True
            module.ENABLE_ADSENSE = True
            module.ADSENSE_CLIENT = "ca-pub-test"
            for route in ("/link-graph", "/wide-link-graph"):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers.get("X-Robots-Tag"), "noindex, nofollow")
                html = response.get_data(as_text=True)
                self.assertNotIn("pagead2.googlesyndication.com", html)
                self.assertNotIn("adsbygoogle", html)
        finally:
            module.ENABLE_INTERNAL_GRAPH = original_graph
            module.ENABLE_ADSENSE = original_ads
            module.ADSENSE_CLIENT = original_client


if __name__ == "__main__":
    unittest.main()
