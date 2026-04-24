#!/usr/bin/env python3
"""Minimal Google Search Console automation.

Supports:
- submitting a sitemap
- inspecting index status for one or more URLs

Auth model:
- Google service account JSON file
- service account must be granted access to the Search Console property
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

import requests

SEARCH_CONSOLE_SCOPE = "https://www.googleapis.com/auth/webmasters"
SITEMAP_SUBMIT_ENDPOINT = "https://www.googleapis.com/webmasters/v3/sites/{site}/sitemaps/{feed}"
INSPECTION_ENDPOINT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"


def _load_google_auth():
    try:
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2 import service_account
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: google-auth. Run `pip install -r requirements.txt`."
        ) from exc
    return GoogleRequest, service_account


def env_default(name: str, fallback: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value else fallback


def required_env_or_arg(value: str | None, name: str) -> str:
    if value:
        return value
    raise SystemExit(f"Missing required value: {name}")


def get_access_token(credentials_path: str) -> str:
    google_request_cls, service_account = _load_google_auth()
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=[SEARCH_CONSOLE_SCOPE],
    )
    credentials.refresh(google_request_cls())
    token = credentials.token
    if not token:
        raise SystemExit("Failed to obtain Google access token from service account.")
    return token


def build_headers(credentials_path: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_access_token(credentials_path)}",
        "Content-Type": "application/json",
    }


def submit_sitemap(property_uri: str, sitemap_url: str, credentials_path: str) -> None:
    endpoint = SITEMAP_SUBMIT_ENDPOINT.format(
        site=quote(property_uri, safe=""),
        feed=quote(sitemap_url, safe=""),
    )
    response = requests.put(endpoint, headers=build_headers(credentials_path), timeout=30)
    if response.status_code >= 400:
        raise SystemExit(
            f"Sitemap submit failed ({response.status_code}): {response.text.strip()}"
        )
    print(f"Submitted sitemap: {sitemap_url}")


def inspect_url(
    property_uri: str,
    inspection_url: str,
    credentials_path: str,
    language_code: str | None = None,
) -> dict:
    payload = {
        "siteUrl": property_uri,
        "inspectionUrl": inspection_url,
    }
    if language_code:
        payload["languageCode"] = language_code
    response = requests.post(
        INSPECTION_ENDPOINT,
        headers=build_headers(credentials_path),
        data=json.dumps(payload),
        timeout=30,
    )
    if response.status_code >= 400:
        raise SystemExit(
            f"Inspection failed for {inspection_url} ({response.status_code}): "
            f"{response.text.strip()}"
        )
    return response.json()


def load_urls(args_urls: list[str], urls_file: str | None) -> list[str]:
    urls = list(args_urls)
    if urls_file:
        lines = Path(urls_file).read_text().splitlines()
        urls.extend(line.strip() for line in lines if line.strip())
    unique_urls: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            unique_urls.append(url)
            seen.add(url)
    if not unique_urls:
        raise SystemExit("No URLs provided. Use --url or --urls-file.")
    return unique_urls


def summarize_inspection_result(url: str, payload: dict) -> dict[str, str]:
    result = payload.get("inspectionResult", {}).get("indexStatusResult", {})
    return {
        "url": url,
        "coverage": result.get("coverageState", "UNKNOWN"),
        "indexing": result.get("indexingState", "UNKNOWN"),
        "robots": result.get("robotsTxtState", "UNKNOWN"),
        "fetch": result.get("pageFetchState", "UNKNOWN"),
        "canonical": result.get("googleCanonical", "") or result.get("userCanonical", ""),
        "verdict": payload.get("inspectionResult", {}).get("inspectionResultLink", ""),
    }


def print_human_results(rows: Iterable[dict[str, str]]) -> None:
    for row in rows:
        print(f"URL: {row['url']}")
        print(f"  coverage: {row['coverage']}")
        print(f"  indexing: {row['indexing']}")
        print(f"  robots:   {row['robots']}")
        print(f"  fetch:    {row['fetch']}")
        if row["canonical"]:
            print(f"  canonical:{row['canonical']}")
        print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minimal Google Search Console automation for sitemap submit and URL inspection.",
    )
    parser.add_argument(
        "--property",
        dest="property_uri",
        default=env_default("GSC_PROPERTY"),
        help="Search Console property URL, e.g. https://tsatracker.com/ or sc-domain:tsatracker.com",
    )
    parser.add_argument(
        "--credentials",
        default=env_default("GSC_SERVICE_ACCOUNT_FILE"),
        help="Path to Google service account JSON credentials.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    submit_parser = subparsers.add_parser("submit-sitemap", help="Submit a sitemap URL.")
    submit_parser.add_argument(
        "--sitemap-url",
        default=env_default("GSC_SITEMAP_URL"),
        help="Absolute sitemap URL. Defaults to GSC_SITEMAP_URL.",
    )

    inspect_parser = subparsers.add_parser("inspect", help="Inspect one or more URLs.")
    inspect_parser.add_argument(
        "--url",
        action="append",
        default=[],
        help="URL to inspect. Pass multiple times for multiple URLs.",
    )
    inspect_parser.add_argument(
        "--urls-file",
        help="Path to a newline-delimited file of URLs to inspect.",
    )
    inspect_parser.add_argument(
        "--language-code",
        default=env_default("GSC_LANGUAGE_CODE"),
        help="Optional language code, e.g. en-US.",
    )
    inspect_parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON instead of a human summary.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    property_uri = required_env_or_arg(args.property_uri, "--property or GSC_PROPERTY")
    credentials_path = required_env_or_arg(
        args.credentials, "--credentials or GSC_SERVICE_ACCOUNT_FILE"
    )

    if args.command == "submit-sitemap":
        sitemap_url = required_env_or_arg(
            args.sitemap_url, "--sitemap-url or GSC_SITEMAP_URL"
        )
        submit_sitemap(property_uri, sitemap_url, credentials_path)
        return 0

    if args.command == "inspect":
        urls = load_urls(args.url, args.urls_file)
        results = [
            inspect_url(property_uri, url, credentials_path, args.language_code) for url in urls
        ]
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print_human_results(
                summarize_inspection_result(url, payload)
                for url, payload in zip(urls, results, strict=True)
            )
        return 0

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
