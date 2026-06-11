#!/usr/bin/env python3
"""SEO smoke checks for rendered Flask routes."""

import os
import json
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

db_file = tempfile.NamedTemporaryFile(prefix="tsa-seo-smoke-", suffix=".db", delete=False)
db_file.close()

os.environ["DB_PATH"] = db_file.name
os.environ["ENABLE_POLLER"] = "false"
os.environ["ENABLE_INTERNAL_GRAPH"] = "true"
os.environ.setdefault("SITE_URL", "https://tsatracker.com")

import app as site  # noqa: E402


site.ENABLE_POLLER = False
site.ENABLE_INTERNAL_GRAPH = True
site.init_db()
site._db_initialized = True

failures = []


def record_failure(message: str) -> None:
    failures.append(message)


def tags_named(html: str, tag_name: str) -> list[str]:
    return re.findall(rf"<{tag_name}\b[^>]*>", html, flags=re.IGNORECASE)


def attr_value(tag: str, name: str) -> str:
    match = re.search(rf"\b{name}\s*=\s*([\"'])(.*?)\1", tag, flags=re.IGNORECASE)
    return match.group(2) if match else ""


def canonical_hrefs(html: str) -> list[str]:
    hrefs = []
    for tag in tags_named(html, "link"):
        if attr_value(tag, "rel").lower() == "canonical":
            hrefs.append(attr_value(tag, "href"))
    return hrefs


def robots_contents(html: str) -> list[str]:
    contents = []
    for tag in tags_named(html, "meta"):
        if attr_value(tag, "name").lower() == "robots":
            contents.append(attr_value(tag, "content"))
    return contents


def visible_word_count(html: str) -> int:
    text = re.sub(r"<script\b.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'/-]*", text))


def assert_status(client, path: str, expected: int):
    response = client.get(path, follow_redirects=False)
    if response.status_code != expected:
        record_failure(f"{path}: expected {expected}, got {response.status_code}")
    return response


def assert_canonical(client, path: str) -> str:
    response = assert_status(client, path, 200)
    html = response.get_data(as_text=True)
    expected = f"{site.SITE_URL}{path}"
    hrefs = canonical_hrefs(html)
    if hrefs != [expected]:
        record_failure(f"{path}: expected one canonical {expected}, got {hrefs}")
    return html


with site.app.test_client() as client:
    canonical_paths = [
        "/",
        "/airports",
        "/airport-security-wait-times",
        "/best-time-to-get-to-the-airport",
        "/about",
        "/privacy",
        "/terms",
        "/contact",
        "/when-should-i-leave",
        "/guide/tsa-wait-times",
        "/guide/tsa-precheck-clear",
        "/methodology",
        "/link-graph",
        "/wide-link-graph",
    ]
    rendered = {path: assert_canonical(client, path) for path in canonical_paths}

    for path, target in {
        "/tsa-wait-times-by-airport": "/airports",
        "/how-early-should-i-arrive-for-tsa": "/best-time-to-get-to-the-airport",
    }.items():
        response = assert_status(client, path, 301)
        location = response.headers.get("Location", "")
        if urlparse(location).path != target:
            record_failure(f"{path}: expected redirect to {target}, got {location}")

    for path in ("/link-graph", "/wide-link-graph"):
        robots = robots_contents(rendered[path])
        if robots != ["noindex"]:
            record_failure(f"{path}: expected robots noindex, got {robots}")

    ad_loader = "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js"
    for path in ("/privacy", "/terms", "/contact"):
        if ad_loader in rendered[path]:
            record_failure(f"{path}: AdSense loader still present")

    redirected_hrefs = (
        'href="/how-early-should-i-arrive-for-tsa',
        "href='/how-early-should-i-arrive-for-tsa",
        'href="/tsa-wait-times-by-airport',
        "href='/tsa-wait-times-by-airport",
    )
    for path, html in rendered.items():
        if path in ("/link-graph", "/wide-link-graph"):
            continue
        for href in redirected_hrefs:
            if href in html:
                record_failure(f"{path}: contains redirected internal link {href}")

    for code in site.LIVE_AIRPORTS:
        path = site.airport_seo_slug(code)
        html = assert_canonical(client, path)
        count = visible_word_count(html)
        if count < 300:
            record_failure(f"{path}: expected at least 300 visible words, got {count}")

    graph_nodes = {node["id"] for node in json.loads(site.link_graph_context()["nodes_json"])}
    for old_path in ("/how-early-should-i-arrive-for-tsa", "/tsa-wait-times-by-airport"):
        if old_path in graph_nodes:
            record_failure(f"link graph still contains redirected node {old_path}")

if failures:
    print("SEO smoke check failed:")
    for failure in failures:
        print(f"- {failure}")
    sys.exit(1)

print("SEO smoke check passed.")
