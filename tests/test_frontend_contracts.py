import importlib
import json
import os
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


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
        self.assertIn("airport-map", by_id)
        self.assertIn("airport-map-preview", by_id)
        _, status_attrs = by_id["airport-map-status"]
        self.assertEqual(status_attrs.get("role"), "status")
        self.assertEqual(status_attrs.get("aria-live"), "polite")

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
        ):
            self.assertIn(token, source)
        self.assertRegex(source, r'addEventListener\(\s*["\']pointerenter["\']')
        self.assertRegex(source, r'addEventListener\(\s*["\']focus["\']')
        self.assertRegex(source, r'addEventListener\(\s*["\']click["\']')

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

    def test_decision_map_renders_only_for_las(self):
        las_html, _ = self.get_html(self.airport_routes["LAS"])
        self.assertIn("data-decision-map", las_html)
        self.assertIn("LAS TSA checkpoint map", las_html)
        self.assertIn("Published checkpoint; no separate reading", las_html)
        self.assertIn("airport-decision-map.js", las_html)

        other_html, _ = self.get_html(self.airport_routes["PHL"])
        self.assertNotIn("data-decision-map", other_html)
        self.assertNotIn("airport-decision-map.js", other_html)

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
