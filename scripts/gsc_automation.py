#!/usr/bin/env python3
"""Google Search Console and site reporting automation.

Supports:
- submitting a sitemap
- inspecting index status for one or more URLs
- pulling Search Console performance data
- pulling Google Analytics daily views when GA4 access is configured

Auth models:
- Google service account JSON file
- Google OAuth desktop-client JSON file with cached refresh token
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote
from zoneinfo import ZoneInfo

import sqlite3

import requests

SEARCH_CONSOLE_SCOPE = "https://www.googleapis.com/auth/webmasters"
ANALYTICS_READONLY_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
SITEMAP_SUBMIT_ENDPOINT = "https://www.googleapis.com/webmasters/v3/sites/{site}/sitemaps/{feed}"
INSPECTION_ENDPOINT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
SEARCH_ANALYTICS_ENDPOINT = "https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
GA4_ACCOUNT_SUMMARIES_ENDPOINT = "https://analyticsadmin.googleapis.com/v1beta/accountSummaries"
GA4_PROPERTIES_ENDPOINT = "https://analyticsadmin.googleapis.com/v1beta/properties"
GA4_RUN_REPORT_ENDPOINT = "https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"


def _load_google_auth():
    try:
        import google.auth
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2 import service_account
    except ImportError as exc:
        raise ImportError("Missing dependency: google-auth. Run `pip install -r requirements.txt`.") from exc
    return google.auth, GoogleRequest, service_account


def _load_google_oauth():
    try:
        from google.oauth2.credentials import Credentials as UserCredentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise ImportError("Missing dependency: google-auth-oauthlib. Run `pip install -r requirements.txt`.") from exc
    return UserCredentials, InstalledAppFlow


def env_default(name: str, fallback: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value else fallback


DEFAULT_QUOTA_PROJECT = env_default("GSC_QUOTA_PROJECT", env_default("GOOGLE_CLOUD_QUOTA_PROJECT"))
DEFAULT_GA4_PROPERTY_ID = env_default("GA4_PROPERTY_ID")
DEFAULT_GA4_CREDENTIALS = env_default("GA4_SERVICE_ACCOUNT_FILE", env_default("GA4_CREDENTIALS"))
DEFAULT_DB_PATH = env_default("DB_PATH", "data.db")


def required_env_or_arg(value: str | None, name: str) -> str:
    if value:
        return value
    raise SystemExit(f"Missing required value: {name}")


def _ensure_parent_dir(path: str) -> None:
    Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)


def _get_gcloud_adc_access_token(scopes: list[str]) -> str:
    scope_arg = ",".join(scopes)
    result = subprocess.run(
        [
            "gcloud",
            "auth",
            "application-default",
            "print-access-token",
            f"--scopes={scope_arg}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise SystemExit(
            "Failed to obtain a Google access token from application default credentials.\n"
            "If this is a new scope, rerun:\n"
            f"  gcloud auth application-default login --scopes={scope_arg}\n"
            + (f"\nDetails: {stderr}" if stderr else "")
        )
    token = result.stdout.strip()
    if not token:
        raise SystemExit("gcloud returned an empty application default access token.")
    return token


def get_service_account_access_token(credentials_path: str, scopes: list[str]) -> str:
    try:
        _, google_request_cls, service_account = _load_google_auth()
    except ImportError as exc:
        raise SystemExit(str(exc)) from exc
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=scopes,
    )
    credentials.refresh(google_request_cls())
    token = credentials.token
    if not token:
        raise SystemExit("Failed to obtain Google access token from service account.")
    return token


def get_oauth_access_token(
    client_secret_path: str,
    token_path: str,
    oauth_port: int,
    scopes: list[str],
) -> str:
    try:
        _, google_request_cls, _ = _load_google_auth()
        user_credentials_cls, installed_app_flow_cls = _load_google_oauth()
    except ImportError as exc:
        raise SystemExit(str(exc)) from exc

    token_file = Path(token_path).expanduser()
    credentials = None
    if token_file.exists():
        credentials = user_credentials_cls.from_authorized_user_file(
            str(token_file),
            scopes=scopes,
        )

    if credentials and credentials.valid:
        return credentials.token

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(google_request_cls())
    else:
        flow = installed_app_flow_cls.from_client_secrets_file(
            client_secret_path,
            scopes=scopes,
        )
        credentials = flow.run_local_server(
            host="localhost",
            port=oauth_port,
            redirect_uri_trailing_slash=False,
            prompt="select_account",
        )

    if not credentials or not credentials.token:
        raise SystemExit("Failed to obtain Google access token from OAuth flow.")

    _ensure_parent_dir(str(token_file))
    token_file.write_text(credentials.to_json())
    return credentials.token


def get_adc_access_token(scopes: list[str]) -> str:
    try:
        google_auth, google_request_cls, _ = _load_google_auth()
    except ImportError:
        return _get_gcloud_adc_access_token(scopes)

    credentials, _ = google_auth.default(scopes=scopes)
    credentials.refresh(google_request_cls())
    token = credentials.token
    if not token:
        raise SystemExit("Failed to obtain Google access token from application default credentials.")
    return token


def get_adc_quota_project() -> str | None:
    """Return the quota project attached to local ADC, when one is configured."""
    try:
        google_auth, _, _ = _load_google_auth()
        credentials, _ = google_auth.default()
        quota_project = getattr(credentials, "quota_project_id", None)
        return str(quota_project) if quota_project else None
    except Exception:
        return None


def resolve_auth_mode(
    auth_mode: str,
    service_account_file: str | None,
    oauth_client_file: str | None,
) -> str:
    if auth_mode != "auto":
        return auth_mode
    if oauth_client_file:
        return "oauth"
    if service_account_file:
        return "service-account"
    return "adc"


def get_access_token(
    auth_mode: str,
    service_account_file: str | None,
    oauth_client_file: str | None,
    oauth_token_file: str | None,
    oauth_port: int,
    scopes: list[str],
) -> str:
    resolved_mode = resolve_auth_mode(auth_mode, service_account_file, oauth_client_file)
    if resolved_mode == "adc":
        return get_adc_access_token(scopes)
    if resolved_mode == "service-account":
        return get_service_account_access_token(
            required_env_or_arg(
                service_account_file,
                "--credentials or GSC_SERVICE_ACCOUNT_FILE",
            ),
            scopes,
        )
    return get_oauth_access_token(
        required_env_or_arg(
            oauth_client_file,
            "--oauth-client-secret or GSC_OAUTH_CLIENT_SECRET_FILE",
        ),
        required_env_or_arg(
            oauth_token_file,
            "--token-file or GSC_OAUTH_TOKEN_FILE",
        ),
        oauth_port,
        scopes,
    )


def build_headers(
    auth_mode: str,
    service_account_file: str | None,
    oauth_client_file: str | None,
    oauth_token_file: str | None,
    oauth_port: int,
    quota_project: str | None,
    scopes: list[str],
) -> dict[str, str]:
    resolved_mode = resolve_auth_mode(auth_mode, service_account_file, oauth_client_file)
    resolved_quota_project = quota_project
    if not resolved_quota_project and resolved_mode == "adc":
        resolved_quota_project = get_adc_quota_project()
    headers = {
        "Authorization": (
            f"Bearer {get_access_token(auth_mode, service_account_file, oauth_client_file, oauth_token_file, oauth_port, scopes)}"
        ),
        "Content-Type": "application/json",
    }
    if resolved_quota_project:
        headers["X-Goog-User-Project"] = resolved_quota_project
    return headers


def submit_sitemap(
    property_uri: str,
    sitemap_url: str,
    auth_mode: str,
    service_account_file: str | None,
    oauth_client_file: str | None,
    oauth_token_file: str | None,
    oauth_port: int,
    quota_project: str | None,
) -> None:
    endpoint = SITEMAP_SUBMIT_ENDPOINT.format(
        site=quote(property_uri, safe=""),
        feed=quote(sitemap_url, safe=""),
    )
    response = requests.put(
        endpoint,
        headers=build_headers(
            auth_mode,
            service_account_file,
            oauth_client_file,
            oauth_token_file,
            oauth_port,
            quota_project,
            [SEARCH_CONSOLE_SCOPE],
        ),
        timeout=30,
    )
    if response.status_code >= 400:
        raise SystemExit(
            f"Sitemap submit failed ({response.status_code}): {response.text.strip()}"
        )
    print(f"Submitted sitemap: {sitemap_url}")


def inspect_url(
    property_uri: str,
    inspection_url: str,
    auth_mode: str,
    service_account_file: str | None,
    oauth_client_file: str | None,
    oauth_token_file: str | None,
    oauth_port: int,
    quota_project: str | None,
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
        headers=build_headers(
            auth_mode,
            service_account_file,
            oauth_client_file,
            oauth_token_file,
            oauth_port,
            quota_project,
            [SEARCH_CONSOLE_SCOPE],
        ),
        data=json.dumps(payload),
        timeout=30,
    )
    if response.status_code >= 400:
        raise SystemExit(
            f"Inspection failed for {inspection_url} ({response.status_code}): "
            f"{response.text.strip()}"
    )
    return response.json()


def _float_or_zero(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except Exception:
        return 0.0


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def fetch_internal_views_report(db_path: str, start_date: str, end_date: str) -> dict:
    if not db_path:
        return {"summary": {"views": 0.0}, "daily": []}

    path = Path(db_path)
    if not path.exists():
        return {"summary": {"views": 0.0}, "daily": []}

    tz = ZoneInfo("America/New_York")
    start_local = datetime.fromisoformat(f"{start_date}T00:00:00").replace(tzinfo=tz)
    end_local = datetime.fromisoformat(f"{end_date}T23:59:59.999999").replace(tzinfo=tz)
    start_utc = start_local.astimezone(timezone.utc).isoformat()
    end_utc = end_local.astimezone(timezone.utc).isoformat()

    conn = sqlite3.connect(str(path))
    try:
        cur = conn.cursor()
        try:
            rows = cur.execute(
                """
                SELECT captured_at
                FROM page_views
                WHERE captured_at BETWEEN ? AND ?
                ORDER BY captured_at
                """,
                (start_utc, end_utc),
            ).fetchall()
        except sqlite3.Error:
            return {"summary": {"views": 0.0}, "daily": []}
    finally:
        conn.close()

    counts: dict[str, float] = {}
    for (captured_at,) in rows:
        try:
            day = datetime.fromisoformat(captured_at).astimezone(tz).date().isoformat()
        except Exception:
            continue
        counts[day] = counts.get(day, 0.0) + 1.0

    daily_rows = [{"date": day, "views": counts[day]} for day in sorted(counts)]
    return {"summary": {"views": float(sum(counts.values()))}, "daily": daily_rows}


def search_console_query(
    property_uri: str,
    start_date: str,
    end_date: str,
    auth_mode: str,
    service_account_file: str | None,
    oauth_client_file: str | None,
    oauth_token_file: str | None,
    oauth_port: int,
    quota_project: str | None,
    dimensions: list[str] | None = None,
    row_limit: int = 25000,
) -> dict:
    endpoint = SEARCH_ANALYTICS_ENDPOINT.format(site=quote(property_uri, safe=""))
    payload: dict[str, object] = {
        "startDate": start_date,
        "endDate": end_date,
        "rowLimit": row_limit,
    }
    if dimensions:
        payload["dimensions"] = dimensions
    response = requests.post(
        endpoint,
        headers=build_headers(
            auth_mode,
            service_account_file,
            oauth_client_file,
            oauth_token_file,
            oauth_port,
            quota_project,
            [SEARCH_CONSOLE_SCOPE],
        ),
        data=json.dumps(payload),
        timeout=30,
    )
    if response.status_code >= 400:
        raise SystemExit(
            f"Search Console query failed ({response.status_code}): {response.text.strip()}"
        )
    return response.json()


def fetch_search_console_report(
    property_uri: str,
    start_date: str,
    end_date: str,
    auth_mode: str,
    service_account_file: str | None,
    oauth_client_file: str | None,
    oauth_token_file: str | None,
    oauth_port: int,
    quota_project: str | None,
) -> dict:
    summary_payload = search_console_query(
        property_uri,
        start_date,
        end_date,
        auth_mode,
        service_account_file,
        oauth_client_file,
        oauth_token_file,
        oauth_port,
        quota_project,
        dimensions=None,
        row_limit=1,
    )
    daily_payload = search_console_query(
        property_uri,
        start_date,
        end_date,
        auth_mode,
        service_account_file,
        oauth_client_file,
        oauth_token_file,
        oauth_port,
        quota_project,
        dimensions=["date"],
        row_limit=25000,
    )

    summary_row = (summary_payload.get("rows") or [{}])[0]
    daily_rows = []
    total_clicks = 0.0
    total_impressions = 0.0
    weighted_position = 0.0
    for row in daily_payload.get("rows", []) or []:
        keys = row.get("keys", [])
        day = str(keys[0]) if keys else ""
        clicks = _float_or_zero(row.get("clicks"))
        impressions = _float_or_zero(row.get("impressions"))
        position = _float_or_zero(row.get("position"))
        total_clicks += clicks
        total_impressions += impressions
        weighted_position += position * impressions
        daily_rows.append(
            {
                "date": day,
                "clicks": clicks,
                "impressions": impressions,
                "ctr": _float_or_zero(row.get("ctr")),
                "position": position,
            }
        )

    summary = {
        "clicks": _float_or_zero(summary_row.get("clicks")) or total_clicks,
        "impressions": _float_or_zero(summary_row.get("impressions")) or total_impressions,
        "ctr": _float_or_zero(summary_row.get("ctr"))
        if summary_row
        else (total_clicks / total_impressions if total_impressions else 0.0),
        "position": _float_or_zero(summary_row.get("position"))
        if summary_row
        else (weighted_position / total_impressions if total_impressions else 0.0),
    }

    if not summary["ctr"] and summary["impressions"]:
        summary["ctr"] = summary["clicks"] / summary["impressions"]
    if not summary["position"] and total_impressions:
        summary["position"] = weighted_position / total_impressions

    return {"summary": summary, "daily": daily_rows}


def normalize_ga4_property_id(property_id: str) -> str:
    value = property_id.strip()
    if value.startswith("properties/"):
        value = value.split("/", 1)[1]
    return value


def list_ga4_properties(
    auth_mode: str,
    service_account_file: str | None,
    oauth_client_file: str | None,
    oauth_token_file: str | None,
    oauth_port: int,
    quota_project: str | None,
) -> list[dict]:
    headers = build_headers(
        auth_mode,
        service_account_file,
        oauth_client_file,
        oauth_token_file,
        oauth_port,
        quota_project,
        [ANALYTICS_READONLY_SCOPE],
    )
    properties: list[dict] = []
    page_token: str | None = None
    while True:
        params: dict[str, object] = {"pageSize": 200}
        if page_token:
            params["pageToken"] = page_token
        response = requests.get(
            GA4_ACCOUNT_SUMMARIES_ENDPOINT,
            headers=headers,
            params=params,
            timeout=30,
        )
        if response.status_code >= 400:
            raise SystemExit(
                f"GA4 property listing failed ({response.status_code}): {response.text.strip()}"
            )
        payload = response.json()
        for summary in payload.get("accountSummaries", []) or []:
            account_name = summary.get("account", "")
            account_display_name = summary.get("displayName", "")
            for prop in summary.get("propertySummaries", []) or []:
                entry = dict(prop)
                entry["account"] = account_name
                entry["accountDisplayName"] = account_display_name
                properties.append(entry)
        page_token = payload.get("nextPageToken") or None
        if not page_token:
            break
    return properties


def ga4_run_report(
    property_id: str,
    start_date: str,
    end_date: str,
    auth_mode: str,
    service_account_file: str | None,
    oauth_client_file: str | None,
    oauth_token_file: str | None,
    oauth_port: int,
    quota_project: str | None,
    dimensions: list[str] | None = None,
) -> dict:
    payload: dict[str, object] = {
        "dateRanges": [{"startDate": start_date, "endDate": end_date}],
        "metrics": [
            {"name": "screenPageViews"},
            {"name": "sessions"},
            {"name": "activeUsers"},
        ],
        "limit": 100000,
    }
    if dimensions:
        payload["dimensions"] = [{"name": name} for name in dimensions]
    response = requests.post(
        GA4_RUN_REPORT_ENDPOINT.format(property_id=normalize_ga4_property_id(property_id)),
        headers=build_headers(
            auth_mode,
            service_account_file,
            oauth_client_file,
            oauth_token_file,
            oauth_port,
            quota_project,
            [ANALYTICS_READONLY_SCOPE],
        ),
        data=json.dumps(payload),
        timeout=30,
    )
    if response.status_code >= 400:
        raise SystemExit(f"GA4 report failed ({response.status_code}): {response.text.strip()}")
    return response.json()


def fetch_ga4_report(
    property_id: str,
    start_date: str,
    end_date: str,
    auth_mode: str,
    service_account_file: str | None,
    oauth_client_file: str | None,
    oauth_token_file: str | None,
    oauth_port: int,
    quota_project: str | None,
) -> dict:
    summary_payload = ga4_run_report(
        property_id,
        start_date,
        end_date,
        auth_mode,
        service_account_file,
        oauth_client_file,
        oauth_token_file,
        oauth_port,
        quota_project,
        dimensions=None,
    )
    daily_payload = ga4_run_report(
        property_id,
        start_date,
        end_date,
        auth_mode,
        service_account_file,
        oauth_client_file,
        oauth_token_file,
        oauth_port,
        quota_project,
        dimensions=["date"],
    )

    summary_row = (summary_payload.get("rows") or [{}])[0]
    summary_metrics = summary_row.get("metricValues", []) if isinstance(summary_row, dict) else []
    summary = {
        "screenPageViews": _float_or_zero(summary_metrics[0].get("value")) if len(summary_metrics) > 0 else 0.0,
        "sessions": _float_or_zero(summary_metrics[1].get("value")) if len(summary_metrics) > 1 else 0.0,
        "activeUsers": _float_or_zero(summary_metrics[2].get("value")) if len(summary_metrics) > 2 else 0.0,
    }

    daily_rows = []
    for row in daily_payload.get("rows", []) or []:
        dimensions_data = row.get("dimensionValues", []) or []
        metric_values = row.get("metricValues", []) or []
        day = ""
        if dimensions_data:
            raw_day = dimensions_data[0].get("value", "")
            if raw_day and len(raw_day) == 8 and raw_day.isdigit():
                day = f"{raw_day[0:4]}-{raw_day[4:6]}-{raw_day[6:8]}"
            else:
                day = str(raw_day)
        daily_rows.append(
            {
                "date": day,
                "screenPageViews": _float_or_zero(metric_values[0].get("value")) if len(metric_values) > 0 else 0.0,
                "sessions": _float_or_zero(metric_values[1].get("value")) if len(metric_values) > 1 else 0.0,
                "activeUsers": _float_or_zero(metric_values[2].get("value")) if len(metric_values) > 2 else 0.0,
            }
        )

    return {"summary": summary, "daily": daily_rows}


def _merge_daily_series(
    view_daily: list[dict],
    sc_daily: list[dict],
    start_date: str | None = None,
    end_date: str | None = None,
    view_key: str = "views",
) -> list[dict]:
    merged: dict[str, dict] = {}
    for row in view_daily:
        merged[row["date"]] = {
            "date": row["date"],
            "views": _float_or_zero(row.get(view_key)),
            "clicks": 0.0,
            "impressions": 0.0,
            "ctr": 0.0,
            "position": 0.0,
        }
    for row in sc_daily:
        bucket = merged.setdefault(
            row["date"],
            {
                "date": row["date"],
                "views": 0.0,
                "clicks": 0.0,
                "impressions": 0.0,
                "ctr": 0.0,
                "position": 0.0,
            },
        )
        bucket["clicks"] = row["clicks"]
        bucket["impressions"] = row["impressions"]
        bucket["ctr"] = row["ctr"]
        bucket["position"] = row["position"]
    rows = [merged[key] for key in sorted(merged)]
    if not start_date or not end_date:
        return rows

    start = datetime.fromisoformat(start_date).date()
    end = datetime.fromisoformat(end_date).date()
    filled: list[dict] = []
    current = start
    by_date = {row["date"]: row for row in rows}
    while current <= end:
        key = current.isoformat()
        filled.append(
            by_date.get(
                key,
                {
                    "date": key,
                    "views": 0.0,
                    "clicks": 0.0,
                    "impressions": 0.0,
                    "ctr": 0.0,
                    "position": 0.0,
                },
            )
        )
        current += timedelta(days=1)
    return filled


def print_report(
    start_date: str,
    end_date: str,
    property_uri: str,
    internal_report: dict,
    sc_report: dict,
    ga4_property_id: str | None,
    ga4_report: dict | None,
) -> None:
    internal_summary = internal_report["summary"]
    sc_summary = sc_report["summary"]
    print(f"Local page views (stale DB): {internal_summary['views']:.0f}")
    print(f"Search Console: {property_uri}")
    print(
        f"  clicks={sc_summary['clicks']:.0f} impressions={sc_summary['impressions']:.0f} "
        f"ctr={_format_percent(sc_summary['ctr'])} avg_position={sc_summary['position']:.2f}"
    )
    if ga4_property_id and ga4_report:
        ga4_summary = ga4_report["summary"]
        print(f"GA4: properties/{normalize_ga4_property_id(ga4_property_id)}")
        print(
            f"  views={ga4_summary['screenPageViews']:.0f} sessions={ga4_summary['sessions']:.0f} "
            f"active_users={ga4_summary['activeUsers']:.0f}"
        )
    else:
        print("GA4: unavailable")
    print()
    print("Daily:")
    header = (
        f"{'date':<12} {'views':>9} {'clicks':>9} {'impr':>10} {'ctr':>8} {'pos':>7}"
    )
    print(header)
    print("-" * len(header))
    merged = _merge_daily_series(
        ga4_report["daily"] if ga4_report else internal_report["daily"],
        sc_report["daily"],
        start_date,
        end_date,
        view_key="screenPageViews" if ga4_report else "views",
    )
    for row in merged:
        print(
            f"{row['date']:<12} "
            f"{row['views']:>9.0f} "
            f"{row['clicks']:>9.0f} "
            f"{row['impressions']:>10.0f} "
            f"{_format_percent(row['ctr']):>8} "
            f"{row['position']:>7.2f}"
        )


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


def report_date_range(days: int) -> tuple[str, str]:
    if days < 1:
        raise SystemExit("--days must be at least 1.")
    end_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    start_date = end_date - timedelta(days=days - 1)
    return start_date.isoformat(), end_date.isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Google Search Console and site reporting automation for sitemap submit, URL inspection, and daily performance views.",
    )
    parser.add_argument(
        "--auth-mode",
        choices=["auto", "service-account", "oauth", "adc"],
        default=env_default("GSC_AUTH_MODE", "auto"),
        help="Authentication mode. Defaults to auto, which prefers OAuth, then service account, then ADC.",
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
    parser.add_argument(
        "--oauth-client-secret",
        default=env_default("GSC_OAUTH_CLIENT_SECRET_FILE"),
        help="Path to Google OAuth desktop client JSON credentials.",
    )
    parser.add_argument(
        "--token-file",
        default=env_default(
            "GSC_OAUTH_TOKEN_FILE",
            str(Path.home() / ".config" / "tsa-tracker" / "gsc-oauth-token.json"),
        ),
        help="Path to the cached Google OAuth token JSON.",
    )
    parser.add_argument(
        "--oauth-port",
        type=int,
        default=int(env_default("GSC_OAUTH_PORT", "3033")),
        help="Localhost port used for the OAuth callback. Must match the configured redirect URI.",
    )
    parser.add_argument(
        "--quota-project",
        default=DEFAULT_QUOTA_PROJECT,
        help="Optional Google Cloud project ID to send as X-Goog-User-Project.",
    )
    parser.add_argument(
        "--ga4-property-id",
        default=DEFAULT_GA4_PROPERTY_ID,
        help="Numeric GA4 property ID, or properties/<id>. Required for GA4 reporting commands.",
    )
    parser.add_argument(
        "--ga4-auth-mode",
        choices=["auto", "service-account", "oauth", "adc"],
        default=env_default("GA4_AUTH_MODE"),
        help="Authentication mode for GA4 commands. Defaults to the main auth mode unless GA4 credentials are provided.",
    )
    parser.add_argument(
        "--ga4-credentials",
        default=DEFAULT_GA4_CREDENTIALS,
        help="Path to GA4 Google service account JSON credentials.",
    )
    parser.add_argument(
        "--ga4-oauth-client-secret",
        default=env_default("GA4_OAUTH_CLIENT_SECRET_FILE"),
        help="Path to GA4 Google OAuth desktop client JSON credentials.",
    )
    parser.add_argument(
        "--ga4-token-file",
        default=env_default(
            "GA4_OAUTH_TOKEN_FILE",
            str(Path.home() / ".config" / "tsa-tracker" / "ga4-oauth-token.json"),
        ),
        help="Path to the cached GA4 Google OAuth token JSON.",
    )
    parser.add_argument(
        "--ga4-oauth-port",
        type=int,
        default=int(env_default("GA4_OAUTH_PORT", "3034")),
        help="Localhost port used for the GA4 OAuth callback. Must match the configured redirect URI.",
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

    report_parser = subparsers.add_parser("report", help="Print Search Console and GA4 daily performance.")
    report_parser.add_argument(
        "--days",
        type=int,
        default=int(env_default("REPORT_DAYS", "7")),
        help="How many completed days to include in report output.",
    )
    report_parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON instead of a human summary.",
    )

    subparsers.add_parser("list-ga4-properties", help="List GA4 properties visible to the current Google auth.")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ga4_auth_mode = args.ga4_auth_mode or ("service-account" if args.ga4_credentials else args.auth_mode)
    ga4_service_account_file = args.ga4_credentials or args.credentials
    ga4_oauth_client_file = args.ga4_oauth_client_secret or args.oauth_client_secret
    ga4_oauth_token_file = args.ga4_token_file or args.token_file
    ga4_oauth_port = args.ga4_oauth_port or args.oauth_port
    ga4_quota_project = env_default("GA4_QUOTA_PROJECT") if ga4_auth_mode == "service-account" else args.quota_project

    if args.command == "list-ga4-properties":
        properties = list_ga4_properties(
            ga4_auth_mode,
            ga4_service_account_file,
            ga4_oauth_client_file,
            ga4_oauth_token_file,
            ga4_oauth_port,
            ga4_quota_project,
        )
        if not properties:
            print("No accessible GA4 properties found for the current Google auth.")
            return 0
        for prop in properties:
            name = prop.get("property") or prop.get("name", "")
            display_name = prop.get("displayName", "")
            property_type = prop.get("propertyType", "")
            account_display_name = prop.get("accountDisplayName", "")
            account_name = prop.get("account", "")
            print(
                f"{name} | {display_name} | {property_type} | {account_name} | {account_display_name}"
            )
        return 0

    property_uri = required_env_or_arg(args.property_uri, "--property or GSC_PROPERTY")

    if args.command == "submit-sitemap":
        sitemap_url = required_env_or_arg(
            args.sitemap_url, "--sitemap-url or GSC_SITEMAP_URL"
        )
        submit_sitemap(
            property_uri,
            sitemap_url,
            args.auth_mode,
            args.credentials,
            args.oauth_client_secret,
            args.token_file,
            args.oauth_port,
            args.quota_project,
        )
        return 0

    if args.command == "inspect":
        urls = load_urls(args.url, args.urls_file)
        results = [
            inspect_url(
                property_uri,
                url,
                args.auth_mode,
                args.credentials,
                args.oauth_client_secret,
                args.token_file,
                args.oauth_port,
                args.quota_project,
                args.language_code,
            )
            for url in urls
        ]
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print_human_results(
                summarize_inspection_result(url, payload)
                for url, payload in zip(urls, results, strict=True)
            )
        return 0

    if args.command == "report":
        start_date, end_date = report_date_range(args.days)
        internal_report = fetch_internal_views_report(DEFAULT_DB_PATH, start_date, end_date)
        sc_report = fetch_search_console_report(
            property_uri,
            start_date,
            end_date,
            args.auth_mode,
            args.credentials,
            args.oauth_client_secret,
            args.token_file,
            args.oauth_port,
            args.quota_project,
        )

        ga4_report = None
        if args.ga4_property_id:
            try:
                ga4_report = fetch_ga4_report(
                    args.ga4_property_id,
                    start_date,
                    end_date,
                    ga4_auth_mode,
                    ga4_service_account_file,
                    ga4_oauth_client_file,
                    ga4_oauth_token_file,
                    ga4_oauth_port,
                    ga4_quota_project,
                )
            except SystemExit as exc:
                print(f"GA4 report unavailable: {exc}", file=sys.stderr)

        if args.json:
            payload = {
                "property_uri": property_uri,
                "ga4_property_id": args.ga4_property_id,
                "start_date": start_date,
                "end_date": end_date,
                "internal_views": internal_report,
                "search_console": sc_report,
                "ga4": ga4_report,
            }
            print(json.dumps(payload, indent=2))
        else:
            print_report(
                start_date,
                end_date,
                property_uri,
                internal_report,
                sc_report,
                args.ga4_property_id if ga4_report else None,
                ga4_report,
            )
        return 0

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
