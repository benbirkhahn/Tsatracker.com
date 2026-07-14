#!/usr/bin/env python3
import logging
import os
import re
import sqlite3
import json
import math
import statistics
import threading
import time
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import requests
from flask import Flask, Response, abort, jsonify, redirect, render_template, request, send_from_directory

from airport_arrival_configs import AIRPORT_DECISION_MAPS

# Import Supabase integration (optional)
try:
    from supabase_integration import (
        supabase_checkpoint_24h_average,
        supabase_historical_24h_average,
        supabase_history_rows,
        supabase_store_samples,
    )
    SUPABASE_ENABLED = True
except ImportError:
    SUPABASE_ENABLED = False
    def supabase_store_samples(rows): pass
    def supabase_history_rows(airport_code: str, hours: int = 12, limit: int = 50000): return None
    def supabase_historical_24h_average(airport_code: str, days: int = 30, time_zone_name: str = "UTC", limit: int = 100000): return None
    def supabase_checkpoint_24h_average(airport_code: str, days: int = 30, time_zone_name: str = "UTC", limit: int = 100000): return None

APP_TZ = timezone.utc
# Bulletproof DB Path: Check for Render Disk, fallback to local
_raw_db_path = os.getenv("DB_PATH", "").strip()
if _raw_db_path:
    DB_PATH = _raw_db_path
elif os.path.isdir("/data") and os.access("/data", os.W_OK):
    DB_PATH = "/data/data.db"
else:
    DB_PATH = "data.db"

# Safe int conversion
_poll_env = os.getenv("POLL_SECONDS", "").strip()
POLL_SECONDS = int(_poll_env) if _poll_env.isdigit() else 120
COLLECT_NOW_TOKEN = os.getenv("COLLECT_NOW_TOKEN")
ENABLE_POLLER = os.getenv("ENABLE_POLLER", "true").lower() == "true"
ENABLE_ADSENSE = os.getenv("ENABLE_ADSENSE", "false").lower() == "true"
ADSENSE_CLIENT = os.getenv("ADSENSE_CLIENT", "").strip()
# Legacy slot names remain environment fallbacks, but one slot is never reused
# across responsive display and Multiplex formats.
ADSENSE_SLOT_DISPLAY = os.getenv(
    "ADSENSE_SLOT_DISPLAY",
    os.getenv("ADSENSE_SLOT_BOTTOM", os.getenv("ADSENSE_SLOT_TOP", "")),
).strip()
ADSENSE_SLOT_MULTIPLEX = os.getenv(
    "ADSENSE_SLOT_MULTIPLEX",
    os.getenv("ADSENSE_SLOT_GUIDE", ""),
).strip()
ENABLE_INTERNAL_GRAPH = os.getenv("ENABLE_INTERNAL_GRAPH", "false").lower() == "true"
DEFAULT_AIRPORT_ARRIVAL_MODE_CODES = (
    "ATL,BOS,CLT,DCA,DFW,EWR,JAX,JFK,LAS,LAX,LGA,MCO,MIA,ORD,PHL,SEA,SFO"
)
AIRPORT_ARRIVAL_MODE_CODES = {
    code.strip().upper()
    for code in os.getenv(
        "AIRPORT_ARRIVAL_MODE_CODES", DEFAULT_AIRPORT_ARRIVAL_MODE_CODES
    ).split(",")
    if code.strip()
}

# Emerald Ad Network (Performance ads)
EMERALD_ID = os.getenv("EMERALD_ID", "519508").strip()
EMERALD_TAG = os.getenv("EMERALD_TAG", "1").strip()
ENABLE_ANALYTICS = os.getenv("ENABLE_ANALYTICS", "false").lower() == "true"
GA_MEASUREMENT_ID = os.getenv("GA_MEASUREMENT_ID", "").strip()
SKIMLINKS_SCRIPT_URL = os.getenv("SKIMLINKS_SCRIPT_URL", "").strip()


SPONSOR_CTA_URL = os.getenv("SPONSOR_CTA_URL", "mailto:ads@tsatracker.com").strip()
SPONSOR_CTA_TEXT = os.getenv("SPONSOR_CTA_TEXT", "Advertise here").strip()

# Travelpayouts / Klook
TRAVELPAYOUTS_ID = os.getenv("TRAVELPAYOUTS_ID", "").strip()
TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN", "").strip()
# Affiliate monetization links.
# We append the marker directly because tp.media deep links require extra program-specific ids
# that are not configured in this app.
UBER_AFFILIATE_URL = os.getenv("UBER_AFFILIATE_URL", "https://www.uber.com/").strip()
LYFT_AFFILIATE_URL = os.getenv("LYFT_AFFILIATE_URL", "https://www.lyft.com/").strip()
PARKING_AFFILIATE_URL = os.getenv("PARKING_AFFILIATE_URL", "https://parking.com/").strip()
AIRHELP_AFFILIATE_URL = os.getenv("AIRHELP_AFFILIATE_URL", "https://airhelp.tpo.li/iHq6wvHP").strip()
KIWI_AIRPORT_PAGE_URLS = {
    "JFK": "https://www.kiwi.com/us/airport/jfk/john-f-kennedy-international-new-york-city-new-york-united-states/",
}

def get_tp_link(dest_url: str) -> str:
    if not TRAVELPAYOUTS_ID:
        return dest_url
    parsed = urlparse(dest_url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params.setdefault("marker", TRAVELPAYOUTS_ID)
    return urlunparse(parsed._replace(query=urlencode(params)))


def get_kiwi_link(airport_code: str = "") -> str:
    code = airport_code.upper().strip()
    base = KIWI_AIRPORT_PAGE_URLS.get(
        code,
        f"https://www.kiwi.com/us/?destination=anywhere&inboundDate=-&origin={code or '-'}&outboundDate=anytime",
    )
    return get_tp_link(base)

LOUNGE_AFFILIATE_URL = get_tp_link("https://www.prioritypass.com/")
KIWI_AFFILIATE_URL = get_tp_link("https://www.kiwi.com/")
KLOOK_AFFILIATE_URL = get_tp_link("https://www.klook.com/")
APP_JS_VERSION = str(int(os.path.getmtime(os.path.join(os.path.dirname(__file__), "static", "app.js"))))

def get_lite_brain_insights() -> List[str]:
    """Reads recent notes from the 'Lite Brain' to identify manual optimization cues."""
    try:
        # Connect to the external Lite Brain DB
        lb_conn = sqlite3.connect('/Users/benbirkhahn/lite-brain/smart-clipboard.db')
        cur = lb_conn.cursor()
        # Look for snippets containing monetization keywords from the last 24 hours
        cur.execute("SELECT content FROM context_snippets WHERE created_at >= datetime('now', '-1 day')")
        rows = cur.fetchall()
        lb_conn.close()
        return [r[0] for r in rows]
    except Exception as e:
        logger.error("Could not read Lite Brain: %s", e)
        return []


def get_best_offer_id(airport_code: str = None) -> str:
    """The 'Self-Learning' core: calculates CTR and checks Lite Brain insights to pick the winner."""
    insights = " ".join(get_lite_brain_insights()).lower()
    
    # Priority 1: Manual Lite Brain Override (The 'Brain' knows best)
    if "focus on klook" in insights: return "KLOOK"
    if "kiwi is better" in insights: return "KIWI"
    
    # Priority 2: Real-time Data (The 'Code' learns from users)
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Local Sort: What do users at THIS airport click most?
        if airport_code:
            cur.execute(
                "SELECT offer_id, COUNT(*) as c FROM ad_clicks WHERE airport_code = ? GROUP BY offer_id ORDER BY c DESC LIMIT 1", 
                (airport_code,)
            )
        else:
            cur.execute("SELECT offer_id, COUNT(*) as c FROM ad_clicks GROUP BY offer_id ORDER BY c DESC LIMIT 1")
            
        row = cur.fetchone()
        conn.close()
        return row[0] if row else "KIWI"
    except:
        return "KIWI"


def get_monetization_context(
    airport_code: str = "",
    page_type: str = "none",
    enable_affiliate_links: bool = False,
) -> Dict:
    """Returns a dictionary of all monetization and affiliate data, now with Smart Ranking."""
    is_airport_page = bool(airport_code and airport_code in LIVE_AIRPORTS)
    city = LIVE_AIRPORTS[airport_code].get("city", "") if is_airport_page else ""
    best_offer = get_best_offer_id(airport_code)
    adsense_enabled = ENABLE_ADSENSE and bool(ADSENSE_CLIENT) and page_type in {
        "home",
        "airport",
        "precheck-guide",
    }
    affiliates_enabled = enable_affiliate_links and bool(SKIMLINKS_SCRIPT_URL)

    return {
        "enable_adsense": adsense_enabled,
        "adsense_client": ADSENSE_CLIENT,
        "adsense_slot_display": ADSENSE_SLOT_DISPLAY,
        "adsense_slot_multiplex": ADSENSE_SLOT_MULTIPLEX,
        "show_display_ad": adsense_enabled
        and page_type in {"home", "airport"}
        and bool(ADSENSE_SLOT_DISPLAY),
        "show_multiplex_ad": adsense_enabled
        and page_type == "precheck-guide"
        and bool(ADSENSE_SLOT_MULTIPLEX),
        "emerald_id": EMERALD_ID,
        "emerald_tag": EMERALD_TAG,
        "ga_id": GA_MEASUREMENT_ID if ENABLE_ANALYTICS else "",
        "enable_affiliate_links": affiliates_enabled,
        "skimlinks_script_url": SKIMLINKS_SCRIPT_URL if affiliates_enabled else "",
        "travelpayouts_id": TRAVELPAYOUTS_ID,

        "best_offer_id": best_offer,
        "smart_learning_active": True,
        "clear_url": os.getenv("CLEAR_AFFILIATE_URL", "https://www.clearme.com/").strip(),
        "precheck_url": os.getenv("PRECHECK_AFFILIATE_URL", "https://www.tsa.gov/precheck").strip(),
        "local_offer": LOCAL_OFFERS.get(airport_code),
        "klook_url": (
            get_tp_link(f"https://www.klook.com/en-US/search?query={city}")
            if is_airport_page and city and TRAVELPAYOUTS_ID
            else KLOOK_AFFILIATE_URL
        ),
        "kiwi_url": get_kiwi_link(airport_code) if is_airport_page else KIWI_AFFILIATE_URL,
        "lyft_url": LYFT_AFFILIATE_URL,
        "parking_url": PARKING_AFFILIATE_URL,
        "airhelp_url": AIRHELP_AFFILIATE_URL,
        "lounge_url": LOUNGE_AFFILIATE_URL,
        "card_chase_url": os.getenv("CARD_CHASE_URL", "https://creditcards.chase.com/").strip(),
        "card_capitalone_url": os.getenv("CARD_CAPITALONE_URL", "https://www.capitalone.com/credit-cards/").strip(),
        "card_amex_url": os.getenv("CARD_AMEX_URL", "https://www.americanexpress.com/us/credit-cards/").strip(),
    }

# Top Airport Personalized Offers (Revenue Boosters)
LOCAL_OFFERS = {
    "JFK": {
        "title": "JFK AirTrain & Transfers",
        "sub": "Fastest way to Manhattan — pre-book",
        "url": get_tp_link("https://www.klook.com/en-US/search?query=JFK airport transfer"),
        "icon": "🚈"
    },
    "ORD": {
        "title": "Chicago L Train & Shuttles",
        "sub": "Direct to the Loop — book transfer",
        "url": get_tp_link("https://www.klook.com/en-US/search?query=Chicago+Transfer"),
        "icon": "🚆"
    },
    "MCO": {
        "title": "Disney & Universal Shuttles",
        "sub": "Skip the taxi line — pre-book now",
        "url": get_tp_link("https://www.klook.com/en-US/search?query=Orlando+Shuttle"),
        "icon": "🚐"
    }
}
TRAVEL_INSURANCE_URL = os.getenv("TRAVEL_INSURANCE_URL", "https://www.travelinsurance.com/").strip()
SITE_URL = os.getenv("SITE_URL", "https://tsatracker.com").strip().rstrip("/")
ENABLE_X_ALERTS = os.getenv("ENABLE_X_ALERTS", "false").lower() == "true"
X_API_KEY = os.getenv("X_API_KEY", "").strip()
X_API_SECRET = os.getenv("X_API_SECRET", "").strip()
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "").strip()
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "").strip()
X_ACCOUNT_HANDLE = os.getenv("X_ACCOUNT_HANDLE", "TsaTracker").strip().lstrip("@")
_x_min_wait_env = os.getenv("X_ALERT_MIN_WAIT", "").strip()
X_ALERT_MIN_WAIT = float(_x_min_wait_env) if _x_min_wait_env else 35.0
_x_extreme_wait_env = os.getenv("X_ALERT_EXTREME_WAIT", "").strip()
X_ALERT_EXTREME_WAIT = float(_x_extreme_wait_env) if _x_extreme_wait_env else 50.0
_x_min_delta_env = os.getenv("X_ALERT_MIN_DELTA", "").strip()
X_ALERT_MIN_DELTA = float(_x_min_delta_env) if _x_min_delta_env else 15.0
_x_cooldown_env = os.getenv("X_ALERT_COOLDOWN_MINUTES", "").strip()
X_ALERT_COOLDOWN_MINUTES = int(_x_cooldown_env) if _x_cooldown_env.isdigit() else 90
_x_baseline_hours_env = os.getenv("X_ALERT_BASELINE_HOURS", "").strip()
X_ALERT_BASELINE_HOURS = int(_x_baseline_hours_env) if _x_baseline_hours_env.isdigit() else 6
_x_min_samples_env = os.getenv("X_ALERT_MIN_BASELINE_SAMPLES", "").strip()
X_ALERT_MIN_BASELINE_SAMPLES = int(_x_min_samples_env) if _x_min_samples_env.isdigit() else 12
_publisher_token = ADSENSE_CLIENT.replace("ca-", "").strip() if ADSENSE_CLIENT else ""
ADS_TXT_LINE = os.getenv(
    "ADS_TXT_LINE",
    f"google.com, {_publisher_token}, DIRECT, f08c47fec0942fa0" if _publisher_token.startswith("pub-") else "",
).strip()
UA = {"User-Agent": "Mozilla/5.0 (tsa-live-site/1.0)"}

LIVE_AIRPORTS = {
    "PHL": {"name": "Philadelphia International (PHL)", "mode": "LIVE_PUBLIC", "city": "Philadelphia"},
    "BOS": {"name": "Boston Logan International Airport (BOS)", "mode": "LIVE_PUBLIC", "city": "Boston"},
    "ATL": {"name": "Hartsfield-Jackson Atlanta International (ATL)", "mode": "LIVE_PUBLIC", "city": "Atlanta"},
    "MIA": {"name": "Miami International (MIA)", "mode": "LIVE_KEY_REQUIRED", "city": "Miami"},
    "ORD": {"name": "Chicago O'Hare International (ORD)", "mode": "LIVE_PUBLIC", "city": "Chicago"},
    "CLT": {"name": "Charlotte Douglas International (CLT)", "mode": "LIVE_KEY_REQUIRED", "city": "Charlotte"},
    "MCO": {"name": "Orlando International (MCO)", "mode": "LIVE_KEY_REQUIRED", "city": "Orlando"},
    "JAX": {"name": "Jacksonville International (JAX)", "mode": "LIVE_PUBLIC", "city": "Jacksonville"},
    "DFW": {"name": "Dallas/Fort Worth International (DFW)", "mode": "LIVE_KEY_EMBEDDED", "city": "Dallas"},
    "LAX": {"name": "Los Angeles International (LAX)", "mode": "LIVE_PUBLIC", "city": "Los Angeles"},
    "JFK": {"name": "John F. Kennedy International (JFK)", "mode": "LIVE_PUBLIC", "city": "New York"},
    "EWR": {"name": "Newark Liberty International (EWR)", "mode": "LIVE_PUBLIC", "city": "Newark"},
    "LGA": {"name": "LaGuardia Airport (LGA)", "mode": "LIVE_PUBLIC", "city": "New York"},
    "LAS": {"name": "Harry Reid International (LAS)", "mode": "LIVE_PUBLIC", "city": "Las Vegas"},
    "SEA": {"name": "Seattle-Tacoma International (SEA)", "mode": "LIVE_PUBLIC", "city": "Seattle"},
    "SFO": {"name": "San Francisco International (SFO)", "mode": "LIVE_PUBLIC", "city": "San Francisco"},
    "DCA": {"name": "Ronald Reagan Washington National (DCA)", "mode": "LIVE_PUBLIC", "city": "Washington"},
}

# Exact airport anchors for the home-page satellite network map. Keeping this
# separate from LIVE_AIRPORTS makes the geographic contract explicit and lets
# tests catch newly tracked airports that have not been placed on the map yet.
AIRPORT_MAP_COORDINATES = {
    "ATL": {"lat": 33.6407, "lng": -84.4277},
    "BOS": {"lat": 42.3656, "lng": -71.0096},
    "CLT": {"lat": 35.2140, "lng": -80.9431},
    "DCA": {"lat": 38.8512, "lng": -77.0402},
    "DFW": {"lat": 32.8998, "lng": -97.0403},
    "EWR": {"lat": 40.6895, "lng": -74.1745},
    "JAX": {"lat": 30.4941, "lng": -81.6879},
    "JFK": {"lat": 40.6413, "lng": -73.7781},
    "LAS": {"lat": 36.0840, "lng": -115.1537},
    "LAX": {"lat": 33.9416, "lng": -118.4085},
    "LGA": {"lat": 40.7769, "lng": -73.8740},
    "MCO": {"lat": 28.4312, "lng": -81.3081},
    "MIA": {"lat": 25.7959, "lng": -80.2870},
    "ORD": {"lat": 41.9742, "lng": -87.9073},
    "PHL": {"lat": 39.8744, "lng": -75.2424},
    "SEA": {"lat": 47.4502, "lng": -122.3088},
    "SFO": {"lat": 37.6213, "lng": -122.3790},
}

AIRPORT_PROFILE_THEMES = {
    "PHL": {"accent": "#f97316", "secondary": "#38bdf8", "label": "Terminal maze"},
    "BOS": {"accent": "#22c55e", "secondary": "#60a5fa", "label": "Checkpoint split"},
    "ATL": {"accent": "#facc15", "secondary": "#fb7185", "label": "High-volume hub"},
    "MIA": {"accent": "#2dd4bf", "secondary": "#fb7185", "label": "International banks"},
    "ORD": {"accent": "#60a5fa", "secondary": "#f59e0b", "label": "Terminal strategy"},
    "CLT": {"accent": "#a78bfa", "secondary": "#34d399", "label": "Connection pressure"},
    "MCO": {"accent": "#fb7185", "secondary": "#facc15", "label": "Family travel waves"},
    "JAX": {"accent": "#34d399", "secondary": "#93c5fd", "label": "Compact airport"},
    "DFW": {"accent": "#f59e0b", "secondary": "#22d3ee", "label": "Skylink advantage"},
    "LAX": {"accent": "#38bdf8", "secondary": "#fb7185", "label": "Terminal routing"},
    "JFK": {"accent": "#818cf8", "secondary": "#f472b6", "label": "Terminal-specific"},
    "EWR": {"accent": "#f97316", "secondary": "#a3e635", "label": "NYC alternate"},
    "LGA": {"accent": "#22d3ee", "secondary": "#f59e0b", "label": "Short-haul flow"},
    "LAS": {"accent": "#f472b6", "secondary": "#facc15", "label": "Event-driven surges"},
    "SEA": {"accent": "#2dd4bf", "secondary": "#60a5fa", "label": "Pacific hub"},
    "SFO": {"accent": "#a3e635", "secondary": "#38bdf8", "label": "Bay Area flow"},
    "DCA": {"accent": "#93c5fd", "secondary": "#f87171", "label": "Business shuttle"},
}

AIRPORT_TIME_ZONES = {
    "ATL": "America/New_York",
    "BOS": "America/New_York",
    "CLT": "America/New_York",
    "DCA": "America/New_York",
    "EWR": "America/New_York",
    "JAX": "America/New_York",
    "JFK": "America/New_York",
    "LGA": "America/New_York",
    "MCO": "America/New_York",
    "MIA": "America/New_York",
    "ORD": "America/Chicago",
    "DFW": "America/Chicago",
    "LAS": "America/Los_Angeles",
    "LAX": "America/Los_Angeles",
    "SEA": "America/Los_Angeles",
    "SFO": "America/Los_Angeles",
    "PHL": "America/New_York",
}

AIRPORT_PAGE_GUIDES = {
    "PHL": {
        "tips": [
            "PHL security is terminal-specific. Terminal B (American Airlines hub) often moves faster than D/E, which is notorious for morning bottlenecks (5–9 AM).",
            "Terminal C checkpoint can sometimes be TSA PreCheck-only—use this to your advantage if you're flying American and have PreCheck.",
            "If you're in Terminals D or E, note that they share a combined checkpoint. D/E opens earliest at 3:30 AM for the first wave of departures.",
        ],
        "notes": [
            "Philadelphia (PHL) has seven terminals (A-West to F). Terminals B and C handle the bulk of American Airlines' domestic hub traffic.",
            "You can walk post-security between Terminals D and E, but you'll need the shuttle for distant terminal connections like A to F.",
            "Wait times at PHL checkpoints are officially capped at 38 minutes on airport displays, so a '38+' reading means significant congestion.",
        ],
        "terminal_notes": [
            "A-West handles international flights and typically closes at 10:00 PM. Terminal F is for American regional flights.",
            "D/E is often the longest line during peak periods; if you're flying Delta or United, leave extra buffer for this specific checkpoint.",
            "Terminal C is shown by PHL as TSA Pre✓ only, but the live feed exposes it as a single C checkpoint row rather than a separate PreCheck wait time.",
        ],
        "airline_notes": [
            "American Airlines passengers can drop bags at B/C even if their gate is elsewhere, allowing access to the faster PreCheck lanes in C.",
            "Low-cost carriers like Frontier, Spirit, JetBlue, and Southwest typically operate from Terminal E.",
        ],
        "links": [
            {"label": "Official PHL Wait Times", "url": "https://www.phl.org/"},
            {"label": "PHL Interactive Maps", "url": "https://maps.phl.org/"},
            {"label": "Terminal Connection Guide", "url": "https://www.ifly.com/airports/philadelphia-international-airport/terminal-map"},
        ],
    },
    "BOS": {
        "tips": [
            "Logan publishes checkpoint-specific live waits, so trust the card for your exact checkpoint instead of treating BOS like a single airport-wide line.",
            "Terminal B is split across two checkpoints, and the faster option can shift during the day, so check whether your flight is on the B1-B22 side or the B23-B40 side before heading in.",
            "Checkpoint 2 at Terminal A is TSA PreCheck-only, which can materially change your best move if you're flying Delta with PreCheck.",
        ],
        "notes": [
            "Boston Logan has four passenger terminals: A, B, C, and E. The live wait feed is organized by checkpoint rather than by one airport-wide number.",
            "Terminal E is the main international terminal, so the security experience there can behave differently from the domestic terminals during long-haul departure banks.",
            "Massport notes that the published wait times are estimates based on real-time data from queue entry points, and overflow beyond that area can make the total experience longer.",
        ],
        "terminal_notes": [
            "Terminal A uses Checkpoints 1 and 2, Terminal B uses Checkpoints 3 and 4, Terminal C uses Checkpoint 5, and Terminal E uses Checkpoints 6 and 7.",
            "Once you're comparing BOS waits, checkpoint selection matters more than the airport average because Logan distributes screening across those seven named entry points.",
        ],
        "airline_notes": [
            "Terminal A is Delta-heavy, Terminal B carries a mixed domestic airline load including American and United activity, and Terminal E handles the main international departure flow.",
            "If your itinerary involves Terminal E, add extra buffer for document checks and longer gate walks even when the checkpoint wait itself looks manageable.",
        ],
        "links": [
            {"label": "Official BOS security wait times", "url": "https://www.massport.com/logan-airport/at-the-airport/security-wait-times"},
            {"label": "Official BOS security information", "url": "https://www.massport.com/logan-airport/at-the-airport/security-information"},
            {"label": "Official BOS terminal maps", "url": "https://www.massport.com/logan-airport/at-the-airport/terminal-map"},
            {"label": "Official BOS airlines directory", "url": "https://www.massport.com/logan-airport/flights/airlines/"},
        ],
    },
    "MIA": {
        "tips": [
            "MIA has 10 distinct security checkpoints with widely varying hours and PreCheck availability—always check the live cards to see if a nearby checkpoint is faster.",
            "North Terminal (Concourse D) is massive. Use the Skytrain after security to reach distant gates (D1-D60) from Checkpoints 1, 3, or 4.",
            "Wait times at MIA spike significantly during the seasonal window from October to April. Plan for 45+ minute waits during these peaks.",
        ],
        "notes": [
            "American Airlines dominates the North Terminal (Concourse D). Non-Oneworld international carriers typically use the South Terminal (Concourses H and J).",
            "Checkpoint 3 in the North Terminal and Checkpoint 9 in the South Terminal are reliable 24-hour options if you have a very early or late departure.",
            "Movement between terminals post-security is limited outside of Concourse D; ensure you clear security in the correct terminal zone.",
        ],
        "terminal_notes": [
            "North Terminal (Concourse D) has 4 checkpoints. Central Terminal serves Concourses E, F, and G. South Terminal serves H and J.",
            "Checkpoint 2 in the North Terminal is occasionally closed—if you're flying American, check if you need to shift to Checkpoint 1 or 3.",
        ],
        "airline_notes": [
            "American Airlines and its Oneworld partners are centered in Concourses D and E.",
            "Delta and most non-alliance international carriers operate out of the South Terminal (Concourses H and J).",
        ],
        "links": [
            {"label": "Official MIA Live Wait Times", "url": "https://www.miami-airport.com/tsa-waittimes.asp"},
            {"label": "MIA Security Information", "url": "https://www.miami-airport.com/airport-security.asp"},
            {"label": "MIA Terminal Guide", "url": "https://upgradedpoints.com/travel/airports/miami-international-mia-airport/"},
        ],
    },
    "ATL": {
        "tips": [
            "ATL publishes separate live readings for Main, North, Lower North, South, and International Main, so compare those exact checkpoint names instead of relying on a single airport average.",
            "If you have TSA PreCheck, the Domestic South checkpoint is the main domestic PreCheck play; the International Terminal also posts specific PreCheck windows.",
            "ATL's official security guidance calls out 5-9 AM and the days around holidays or long weekends as the busiest security periods.",
        ],
        "notes": [
            "All concourses and aircraft gates are accessible from any ATL checkpoint, so the best choice is usually the shortest live line that matches your lane.",
            "ATL recommends arriving at least two hours before domestic departures and three hours before international departures.",
            "During busy periods, ATL specifically recommends adding buffer for parking, rental-car drop-off, airline check-in, and security screening.",
        ],
        "terminal_notes": [
            "Domestic Terminal Main is listed as a 24-hour standard-screening checkpoint.",
            "Domestic North is listed for standard and priority screening from 4:00 AM to 9:00 PM.",
            "Domestic Lower North is listed for standard screening and CLEAR Standard from 3:30 AM to 9:00 PM.",
            "Domestic South is listed for TSA PreCheck, PreCheck Touchless ID, and CLEAR with PreCheck from 4:00 AM to 9:00 PM.",
            "International Terminal Departures is listed for standard screening from 4:30 AM to midnight, with PreCheck windows from 7:00-10:00 AM and 2:00-7:00 PM.",
        ],
        "airline_notes": [
            "Delta's ATL hub volume makes domestic checkpoint choice important, but all concourses are reachable after any checkpoint.",
            "International-terminal departures should use the International Main reading instead of assuming the domestic checkpoints reflect that flow.",
        ],
        "links": [
            {"label": "Official ATL live wait times", "url": "https://dev.atl.com/atlsync/security-wait-times/"},
            {"label": "ATL passenger security", "url": "https://www.atl.com/passenger-information/passenger-security/"},
            {"label": "Official ATL airport site", "url": "https://www.atl.com/"},
            {"label": "ATL airport maps", "url": "https://www.atl.com/maps/"},
        ],
    },
    "ORD": {
        "tips": [
            "ORD travelers should confirm the exact departure terminal before choosing security because Terminals 1, 2, 3, and 5 each run their own checkpoint workflow.",
            "If you are flying international out of Terminal 5, treat that as its own security workflow rather than an extension of the domestic-terminal experience.",
            "ORD publishes checkpoint reference hours and a separate live wait feed. Use the terminal map, current reading, and airline app together before leaving.",
        ],
        "notes": [
            "The official FlyChicago map is the strongest source for matching your terminal and gate area to the correct checkpoint.",
            "Terminals 1, 2, and 3 handle most domestic traffic, while Terminal 5 is the major international workflow.",
            "ORD's official TSA page publishes reference hours, but those hours can change with airport operations and may conflict with a live feed row. Arrival Mode does not infer open or closed from a missing reading.",
        ],
        "terminal_notes": [
            "Terminal 1 is the major United terminal and has its own security entry points shown on the official ORD map.",
            "Terminal 2 carries a smaller domestic mix and should be checked separately from Terminal 1 even when your airline is connected to United.",
            "Terminal 3 is the main American Airlines terminal and should be treated as its own security decision.",
            "Terminal 5 handles many international departures and has a separate screening environment from the domestic terminals.",
            "Use the official map for the gate-side walking plan because checkpoint choice and post-security connectivity can vary by terminal and concourse.",
        ],
        "airline_notes": [
            "United drives the biggest volume in Terminal 1, while American dominates Terminal 3, so those two terminals shape most same-day congestion.",
            "Terminal 5 handles the international-carrier workflow, while Terminal 2 carries a smaller mix including Delta, Alaska, Spirit, and Air Canada.",
        ],
        "links": [
            {"label": "Official airport site", "url": "https://www.flychicago.com/ohare/home/pages/default.aspx"},
            {"label": "Official terminal map", "url": "https://www.flychicago.com/ohare/map/pages/default.aspx"},
            {"label": "Official security information", "url": "https://www.flychicago.com/ohare/myflight/security/Pages/TSA.aspx"},
        ],
    },
    "LAX": {
        "tips": [
            "LAX security is terminal-specific across Terminals 1-8 plus Terminal B, so confirm your exact terminal before heading to the checkpoint.",
            "Security screening hours vary by terminal and flight schedule, with LAX guidance generally placing screening operations from early morning into late night rather than true 24-hour access.",
            "At LAX, total departure friction often includes terminal routing, curb traffic, shuttle time, or a Terminal B connection in addition to the TSA line itself.",
        ],
        "notes": [
            "The official LAX terminal map is the key source for airline location and checkpoint placement.",
            "LAX limits terminal access to ticketed passengers, people meeting or assisting travelers, and airport business, so very early arrivals should still confirm terminal security timing.",
            "This page is most useful when you are deciding whether your main risk is the line itself, terminal layout, curbside congestion, or a Terminal B workflow.",
        ],
        "terminal_notes": [
            "Terminal 1 is a major Southwest checkpoint environment and should be checked separately from the rest of the horseshoe.",
            "Terminals 2 and 3 are heavily associated with Delta operations, but passengers should still trust the boarding pass over old terminal habits.",
            "Terminals 4 and 5 are the core American Airlines zone, while Terminal 6 is commonly associated with Alaska and partner traffic.",
            "Terminals 7 and 8 are the main United area and can have a very different flow from Terminal B.",
            "Terminal B is the core international screening environment, and some itineraries can involve check-in or movement across multiple terminal areas.",
        ],
        "airline_notes": [
            "Delta concentrates in Terminal 3, American in Terminals 4 and 5, United in Terminals 7 and 8, Southwest in Terminal 1, and Alaska in Terminal 6.",
            "Terminal B remains the core international screening environment even when the check-in step starts elsewhere.",
        ],
        "links": [
            {"label": "Official airport site", "url": "https://www.flylax.com/"},
            {"label": "Official terminal maps", "url": "https://www.flylax.com/lax-terminal-maps"},
            {"label": "Official wait-time page", "url": "https://www.flylax.com/wait-times"},
        ],
    },
    "DFW": {
        "tips": [
            "DFW allows 'checkpoint-hopping': You can clear security in ANY terminal and use the post-security Skylink train to reach your actual gate terminal.",
            "If your terminal's line is long, check the live cards for a neighboring terminal (like A or C)—clearing there and taking Skylink can save 20 minutes.",
            "Automated Screening Lanes (A21, D18, D22, D30, E18) are typically the fastest standard lanes during morning rushes.",
        ],
        "notes": [
            "American Airlines operates out of Terminals A, B, C, and D. Most non-American carriers (United, Delta, Southwest, Spirit) use Terminal E.",
            "Terminal D handles the majority of international departures and often sees the longest lines due to extra document screening layers.",
            "TSA PreCheck Touchless ID and CLEAR are specifically centered at E18 and designated lanes in A21 and D30.",
        ],
        "terminal_notes": [
            "Skylink is the key to DFW. If you clear security in Terminal A but depart from C, the train ride is under 5 minutes and runs every 2 minutes.",
            "Terminal E and D tend to be the most congested; Terminal C often moves faster for domestic travelers.",
        ],
        "airline_notes": [
            "American Airlines hub traffic is spread across A, B, C, and D. If you're on a non-American carrier, head to Terminal E unless instructed otherwise.",
            "International flights (AA and foreign carriers) almost always route through Terminal D or Terminal E.",
        ],
        "links": [
            {"label": "Official DFW Live Wait Map", "url": "https://www.dfwairport.com/security/"},
            {"label": "DFW Interactive Map", "url": "https://www.dfwairport.com/map/"},
            {"label": "DFW Terminal Guide", "url": "https://dallasfortworthairport-dfw.com/wait-times/"},
        ],
    },
    "DEN": {
        "tips": [
            "DEN has separate East and West security areas, so the better line depends on your terminal routing and the time of day.",
            "PreCheck can be materially faster at DEN, but the live cards are the better source than assuming one side is always better.",
            "Use the official DEN security tools first if you are considering Reserve or another expedited screening option.",
        ],
        "notes": [
            "Denver International uses separate checkpoint areas rather than one airport-wide line.",
            "DEN Reserve and the airport's expedited screening guidance are official airport resources, not third-party estimates.",
        ],
        "terminal_notes": [
            "East Security and West Security each have their own live wait patterns.",
            "The better checkpoint can shift by departure bank, so compare the airport's live display before leaving.",
        ],
        "links": [
            {"label": "DEN Reserve", "url": "https://www.flydenver.com/security/den-reserve/"},
            {"label": "Expedited Security Screening Options", "url": "https://www.flydenver.com/security/expedited-security-screening-options/"},
            {"label": "Official DEN security page", "url": "https://www.flydenver.com/security/"},
        ],
    },
    "MCO": {
        "tips": [
            "Orlando (MCO) is unique for its 'MCO Reserve' program, which allows you to book a security screening slot in advance (up to 7 days ahead).",
            "Terminals A and B are in the North Complex, while the new Terminal C is in the South Complex. The automated people mover (train) adds 15+ minutes to your gate transit time.",
            "Tourist peaks (Disney weeks and spring break) can push wait times to 60+ minutes—arrive 3 hours early during these seasons.",
        ],
        "notes": [
            "Security is terminal-specific: West security for Gates 1-59, East security for Gates 70-129, and the Terminal C Level 2 checkpoint.",
            "Always identify whether you are Side A, Side B, or Terminal C before arriving; the drop-off points are completely separate.",
            "If you have souvenirs or liquid-based gifts, pack them in checked luggage to avoid manual bag searches which slow down MCO's high-volume lines.",
        ],
        "terminal_notes": [
            "Terminal C serves select domestic and international carriers (like JetBlue) and typically has shorter lines than the North Terminal, but this varies with international arrival waves.",
            "North Terminal (A/B) handles the majority of domestic traffic via four separate airside concourses.",
        ],
        "airline_notes": [
            "Southwest passengers should head to West Security (Terminal A-side) for Airsides 1 and 3.",
            "Spirit, Frontier, and Delta typically use the East Security side (Airsides 2 and 4).",
        ],
        "links": [
            {"label": "Official MCO Live Wait Times", "url": "https://flymco.com/security/"},
            {"label": "MCO Reserve Booking", "url": "https://flymco.com/airport-info/mco-reserve/"},
            {"label": "MCO Interactive Map", "url": "https://flymco.com/terminal-maps/"},
        ],
    },
    "JAX": {
        "tips": [
            "JAX is usually efficient with a single central checkpoint, but note that TSA PreCheck and special needs lanes typically close around 7:00 PM daily.",
            "If you are departing after 7:00 PM, plan for the standard security lane only, regardless of your PreCheck status.",
            "Military in uniform can use a dedicated screening lane which often has a near-zero wait time (usually under 1 minute).",
        ],
        "notes": [
            "Jacksonville operates as a single terminal. Once through security, you'll cross a connector bridge to reach Concourses A or C.",
            "Concourse A serves Delta, JetBlue, and United, while Concourse C handles American, Southwest, Spirit, and Frontier.",
            "The hourly parking garage features a direct walkway to the terminal, saving significant time compared to the economy lots which often reach 100% capacity during peaks.",
        ],
        "terminal_notes": [
            "Security at JAX is centralized in the main terminal building; there are no separate checkpoints for different concourses.",
            "The checkpoint opens at 4:00 AM. Since the terminal is open 24/7 but security is not, early morning travelers should arrive right at 4:00 AM for the first wave of departures.",
        ],
        "airline_notes": [
            "Concourse A (Gates A1-A14) is your destination for Delta (and the Sky Club), JetBlue, and United.",
            "Concourse C (Gates C1 and up) serves the American Airlines hub traffic, Southwest, and low-cost carriers like Spirit and Allegiant.",
        ],
        "links": [
            {"label": "Official JAX Live Wait Times", "url": "https://www.flyjax.com/"},
            {"label": "JAX Interactive Terminal Map", "url": "https://www.flyjax.com/services"},
            {"label": "JAX Airport Guide", "url": "https://www.flyjacksonville.com"},
        ],
    },
    "CLT": {
        "tips": [
            "CLT uses three independent checkpoints (1, 2, and 3). Checkpoint 2 is the primary hub for dedicated TSA PreCheck lanes.",
            "Charlotte supports TSA PreCheck 'Touchless ID' for eligible American Airlines AAdvantage members—look for designated scanners to skip the standard document check.",
            "The airport layout is a single terminal with five concourses (A-E), and the official security page says all concourses and gates remain accessible from any checkpoint.",
        ],
        "notes": [
            "All concourses and aircraft gates are accessible from any CLT checkpoint, so the decision is mostly about queue time and lane type.",
            "CLT is a massive American Airlines hub. Security volume is driven by 'banked' connection cycles (5-8 AM and late afternoon) rather than just local traffic.",
            "Checkpoint 2 carries the dedicated Main PreCheck line and usually has the widest published operating window.",
        ],
        "terminal_notes": [
            "Checkpoint 1 publishes standard, special-assistance, and family screening from 3:45 a.m. to 8 p.m.",
            "Checkpoint 2 publishes a standard/special-assistance line from 7 p.m. to 11 p.m., a Main PreCheck line from 3:45 a.m. to 11 p.m., and an employee line from 8 p.m. to 11 p.m.",
            "Checkpoint 3 publishes standard/special-assistance and employee screening from 3:45 a.m. to 8 p.m.",
        ],
        "airline_notes": [
            "American Airlines dominates CLT across almost all concourses; check your specific gate on the CLT app before choosing a checkpoint.",
            "Delta, United, and Southwest typically operate from specific concourses, but concourse reach is long—plan for a 10-15 minute walk post-security.",
        ],
        "links": [
            {"label": "Official CLT Security Dashboard", "url": "https://www.cltairport.com/airport-info/security/"},
            {"label": "CLT Interactive Map", "url": "https://www.cltairport.com/airport-info/terminal-map/"},
            {"label": "CLT Terminal Guide", "url": "https://upgradedpoints.com/travel/airports/charlotte-douglas-airport-clt/"},
        ],
    },
    "JFK": {
        "tips": [
            "JFK terminal traffic can behave like separate mini-airports, so treat the terminal cards above as more important than the overall airport average.",
            "If your terminal is showing a long line while another looks calm, assume your terminal timing is the one that matters for departure planning.",
            "Changing terminals at JFK means exiting and reclearing security, so the wrong terminal assumption carries a real time penalty.",
        ],
        "notes": [
            "John F. Kennedy can have very different line conditions across terminals because traffic is distributed unevenly across international and domestic departure waves.",
            "This page is designed to help you decide whether your specific terminal is the issue or whether the whole airport is running hot.",
            "JFK is in an active redevelopment period, and the airport has an official security wait-times suspension notice. Check the travel impacts page and advisories before you leave.",
        ],
        "terminal_notes": [
            "JFK splits departing passengers across Terminals 1, 4, 5, 7, and 8, each with its own screening flow.",
            "Terminal 4 and Terminal 8 usually matter most for same-day congestion because of their scale and airline mix.",
            "There is no useful airport-wide average here if your actual terminal is running much hotter than the others.",
        ],
        "airline_notes": [
            "Terminal 4 is the main Delta-driven volume center, Terminal 5 is JetBlue's terminal, and Terminal 8 carries most American traffic.",
            "Terminal 1 and Terminal 7 matter most for many international and alliance-partner departures, so terminal verification is critical before you leave.",
        ],
        "links": [
            {"label": "Official airport site", "url": "https://www.jfkairport.com/"},
            {"label": "Official terminal map", "url": "https://www.jfkairport.com/explore-jfk/airport-map"},
            {"label": "JFK travel impacts / redevelopment", "url": "https://construction.jfkairport.com/jfk/en/your-travel-impacts.html"},
            {"label": "JFK alerts and advisories", "url": "https://www.jfkairport.com/alerts-advisories"},
            {"label": "Official live wait times", "url": "https://www.jfkairport.com/to-and-from/security-wait-times"},
        ],
    },
    "EWR": {
        "tips": [
            "EWR has three main terminals (A, B, C). Terminal C is the United hub and features the most consistent security pressure.",
            "Newark publishes airport wait times by terminal and gate group, so always check your specific terminal before heading to the airport.",
            "Newark offers 'CLEAR + TSA PreCheck' across all three terminals, with enrollment centers specifically in Terminals A and C.",
        ],
        "notes": [
            "Terminal A is the newest facility and often has the most efficient screening technology, but it can be a long trek from the AirTrain.",
            "If you need to change terminals mid-itinerary, factor in the AirTrain wait and a full re-screening at your new terminal—EWR is not fully connected post-security.",
            "Terminal C security surges during United's morning and evening 'banks'—if you're flying United, arrive 2.5 hours early during these windows.",
        ],
        "terminal_notes": [
            "Terminal A (Gates A1-A28) serves multiple domestic carriers. Terminal B handles international and some domestic. Terminal C is almost exclusively United.",
            "Each terminal has its own independent security checkpoints; there is no centralized screening for all of Newark.",
        ],
        "airline_notes": [
            "United Airlines passengers should head directly to Terminal C. JetBlue and American are typically in Terminal A.",
            "Delta and many international carriers (Lufthansa, British Airways) operate out of Terminal B.",
        ],
        "links": [
            {"label": "Official EWR site", "url": "https://www.newarkairport.com/"},
            {"label": "EWR security wait times", "url": "https://www.newarkairport.com/security-wait-times"},
            {"label": "Official EWR terminal maps", "url": "https://www.newarkairport.com/at-airport/airport-maps"},
        ],
    },
    "LGA": {
        "tips": [
            "LGA security is divided by terminal (A, B, C). Terminal B is often the biggest bottleneck, with waits sometimes spilling into the check-in hall.",
            "If you're flying Delta, check both Terminals A and C—Terminal C is the massive newer hub and handles the bulk of Delta's Newark-area volume.",
            "Unlike JFK, changing terminals at LGA pre-security is a hassle involving shuttles; always confirm your terminal before drop-off.",
        ],
        "notes": [
            "LaGuardia's Terminal B serves American, Southwest, United, and JetBlue. Terminal C is almost exclusively Delta.",
            "Terminal B wait times are notorious for early-morning spikes (6–9 AM)—if you're flying out of B, arrive 2.5 hours early during these windows.",
            "Holiday weekends (Thanksgiving, July 4th) at LGA can see PreCheck lines stretch to 45+ minutes—do not rely on a standard 10-minute pass.",
        ],
        "terminal_notes": [
            "LGA operates as three separate airports with no post-security connection. You MUST clear security in the terminal your flight departs from.",
            "Terminal A (Marine Air Terminal) is much smaller and generally faster but only serves Delta Shuttle and Spirit.",
        ],
        "airline_notes": [
            "Delta is split between Terminal A (Shuttle) and Terminal C (Main Hub). Double-check your app before heading to the airport.",
            "Terminal B is the 'general' terminal for most other major domestic carriers.",
        ],
        "links": [
            {"label": "Official LGA site", "url": "https://www.laguardiaairport.com/"},
            {"label": "LGA security wait times", "url": "https://www.laguardiaairport.com/security-wait-times"},
            {"label": "LGA travel tips", "url": "https://www.laguardiaairport.com/static/LGA/announcements/pages/family-travel-tips.html"},
            {"label": "LGA Official Maps", "url": "https://www.laguardiaairport.com/at-airport/airport-maps"},
            {"label": "LGA Airline-Terminal List", "url": "https://www.laguardiaairport.com/flight/airlines"},
        ],
    },
    "LAS": {
        "tips": [
            "LAS has five named TSA checkpoint groups, so match your gate letters to the right checkpoint rather than using a single airport-wide line.",
            "The C/D checkpoint is the official 24-hour option, which matters for late-night and very early departures when other LAS checkpoints may be closed.",
            "LAS recommends the standard buffer of two hours for domestic flights and three hours for international flights because checkpoint demand changes sharply by terminal and departure bank.",
        ],
        "notes": [
            "Harry Reid publishes live security wait times directly on its official airport site.",
            "The official LAS security page names A/B Gates, C Gates, C/D Gates, Terminal 3 Level 2, and Terminal 3 Level Zero Innovation as separate security choices.",
            "Checkpoint hours vary meaningfully, so a closed or limited-hours checkpoint can matter as much as the current wait number.",
        ],
        "terminal_notes": [
            "A/B Gates checkpoint is in Terminal 1 and is listed with long operating hours but not 24-hour coverage.",
            "C Gates checkpoint is specifically labeled for Southwest Airlines traffic in Terminal 1.",
            "C/D Gates checkpoint is listed as open 24 hours and can be important for overnight or very early travel.",
            "Terminal 3 Level 2 serves D and E gates, so passengers using those gates should not default to Terminal 1 security.",
            "The Terminal 3 Level Zero Innovation Checkpoint has limited daytime hours, so verify it before planning around it.",
        ],
        "airline_notes": [
            "Southwest-heavy traffic often routes through Terminal 1, while many other carriers use Terminal 3.",
            "Check your airline's terminal assignment before heading to the checkpoint, since the LAS page reports checkpoint groups rather than a single airport-wide number.",
        ],
        "links": [
            {"label": "Official LAS security wait times", "url": "https://www.harryreidairport.com/security-wait-times"},
            {"label": "Official LAS security page", "url": "https://www.harryreidairport.com/security-at-las"},
            {"label": "Official LAS airport site", "url": "https://www.harryreidairport.com/"},
        ],
    },
    "SEA": {
        "tips": [
            "SEA publishes checkpoint-by-checkpoint lane types and hours, so choose by service need: general, premium, CLEAR, SEA Spot Saver, or TSA PreCheck.",
            "SEA states that all gates are accessible from any checkpoint, which makes shortest-line selection more useful than at terminal-isolated airports.",
            "Checkpoint 4 is the 24-hour checkpoint, while the other checkpoints have published daily windows that can change by operation.",
        ],
        "notes": [
            "SEA's official security page lists six checkpoints and identifies lane types by checkpoint.",
            "The live wait-time page recommends two hours before domestic flights and three hours before international flights.",
            "SEA calls out additional peak periods from 2-5 PM and 9-11 PM, so the airport can be busy outside the normal morning rush.",
        ],
        "terminal_notes": [
            "Checkpoint 1 is closest to A and S gates and lists general screening, TSA PreCheck, and CLEAR options.",
            "Checkpoint 2 is closest to A and S gates and supports general screening plus SEA Spot Saver during its published hours.",
            "Checkpoint 3 is a central option with general screening, TSA PreCheck, Touchless ID, and premium-lane options.",
            "Checkpoint 4 is open 24 hours and is closest to the Central Terminal plus B and C gates.",
            "Checkpoints 5 and 6 are closest to C, D, and N gates; Checkpoint 5 is PreCheck-focused while Checkpoint 6 includes general, premium, PreCheck, and CLEAR options.",
        ],
        "airline_notes": [
            "Alaska Airlines passengers should aim for Checkpoints 5 or 6. Delta and international carriers typically route through A gates or the South Satellite.",
            "South Satellite (Gates S1-S16) handles almost all foreign international arrivals and selected Delta international departures.",
        ],
        "links": [
            {"label": "Official SEA Spot Saver", "url": "https://www.portseattle.org/sea/spot-saver"},
            {"label": "Official SEA Security Dashboard", "url": "https://www.portseattle.org/Security"},
            {"label": "SEA Interactive Map", "url": "https://exploresea.org/map/"},
        ],
    },
    "SFO": {
        "tips": [
            "SFO explicitly allows passengers with a same-day boarding pass to enter through any checkpoint and walk airside to all gates.",
            "SFO publishes live wait times for six checkpoints: A, B, B-Mezzanine, D, F, and G.",
            "All SFO checkpoints list TSA PreCheck, Priority Line, and CLEAR lanes, so the shortest line can be a real option even outside your closest terminal.",
        ],
        "notes": [
            "SFO's security page is server-rendered with the live wait-time table already in the HTML, so the collector can scrape it directly without a hidden API.",
            "The table includes a freshness stamp. That lets us treat the data as live airport output rather than a planning estimate.",
            "The collector labels each checkpoint with its terminal area so travelers can tell at a glance whether a time is for International Terminal A, Harvey Milk Terminal 1, Terminal 2, Terminal 3, or International Terminal G.",
        ],
        "terminal_notes": [
            "Checkpoint A serves the International Terminal A side.",
            "Checkpoint B and B-Mezzanine serve the Harvey Milk Terminal 1 side and can show different wait patterns.",
            "Checkpoint D serves Terminal 2.",
            "Checkpoint F serves Terminal 3.",
            "Checkpoint G serves the International Terminal G side.",
            "Because SFO connects all gates after security, passengers can choose a faster checkpoint and walk airside to their gate.",
        ],
        "airline_notes": [
            "Use the checkpoint closest to your gate area when waits are similar, but do not assume you must screen there if another checkpoint is materially shorter.",
            "TSA PreCheck and CLEAR travelers have flexibility because SFO lists both services across all checkpoints.",
        ],
        "links": [
            {"label": "Official SFO Security Wait Times", "url": "https://www.flysfo.com/passengers/flight-info/security-wait-times"},
            {"label": "Official SFO Check In & Security", "url": "https://www.flysfo.com/passengers/flight-info/check-in-security"},
            {"label": "SFO TSA PreCheck", "url": "https://www.flysfo.com/passengers/services-amenities/expedited-travel/tsa-precheck"},
            {"label": "Official SFO Airport Site", "url": "https://www.flysfo.com/"},
        ],
    },
    "DCA": {
        "tips": [
            "DCA has three security checkpoint locations: Terminal 1, Terminal 2 North, and Terminal 2 South.",
            "Terminal 2 North is listed as the latest-running checkpoint, so it matters most for late Terminal 2 departures.",
            "Official sources do not clearly state that Terminal 1 and Terminal 2 are fully interchangeable after security, so use the checkpoint tied to your gate area.",
        ],
        "notes": [
            "Terminal 1 serves the A-gate area, while Terminal 2 covers the B, C, D, and E gate groups.",
            "DCA checkpoint hours are published by the airport and generally start at 4:00 AM, useful for early first-bank departures.",
            "CLEAR operates at DCA and also supports TSA PreCheck enrollment or renewal at the airport.",
        ],
        "terminal_notes": [
            "Terminal 1 checkpoint serves gates A1-A9 and is listed from 4:00 AM to 9:00 PM.",
            "Terminal 2 North checkpoint serves Terminal 2 traffic and is listed from 4:00 AM to 11:00 PM.",
            "Terminal 2 South checkpoint serves Terminal 2 traffic and is listed from 4:00 AM to 9:00 PM.",
            "Airport materials note checkpoints generally open around the early-morning departure bank and close after final departures.",
            "Because Terminal 1 and Terminal 2 are separate gate groupings, confirm A versus B/C/D/E before choosing your checkpoint.",
        ],
        "airline_notes": [
            "Use the gate group on your boarding pass first: A gates point to Terminal 1, while B, C, D, and E gates point to Terminal 2.",
            "If you are not sure which side your airline is using that day, verify the gate in the airline app before heading to security.",
        ],
        "links": [
            {"label": "Official DCA security information", "url": "https://www.flyreagan.com/travel-information/security-information"},
            {"label": "Official DCA terminal map", "url": "https://www.flyreagan.com/travel-information/terminal-map"},
            {"label": "DCA TSA PreCheck enrollment", "url": "https://ir.clearme.com/news-events/press-releases/detail/112/clear-an-official-tsa-precheck-enrollment-provider"},
        ],
    },
}

AIRPORT_STATUS_NOTICES = {
    "JFK": {
        "title": "Redevelopment and wait-time suspension",
        "summary": "JFK is in an active redevelopment period, and the airport has published an official security wait-times suspension notice. Use the advisories and travel impacts pages for the current airport status.",
        "links": [
            {"label": "JFK travel impacts", "url": "https://construction.jfkairport.com/jfk/en/your-travel-impacts.html"},
            {"label": "JFK alerts and advisories", "url": "https://www.jfkairport.com/alerts-advisories"},
        ],
    },
}


GENERIC_AIRPORT_MAP_SPANS = {
    "ATL": (0.027, 0.040),
    "DFW": (0.045, 0.072),
    "JFK": (0.028, 0.044),
    "LAX": (0.026, 0.046),
    "ORD": (0.032, 0.048),
}


def _arrival_normalized_lane_type(row: Dict) -> str:
    """Recover lane semantics when an upstream feed encodes them in the label."""
    lane_type = _lane_type_key(row.get("lane_type"))
    if lane_type != "STANDARD":
        return lane_type

    checkpoint = str(row.get("checkpoint") or "").strip().lower()
    if re.search(r"\b(?:tsa[\s-]*pre|precheck|pre-check)\b", checkpoint):
        return "PRECHECK"
    if re.search(r"\bclear\b", checkpoint):
        return "CLEAR"
    if re.search(r"\bpriority lane\b", checkpoint):
        return "STANDARD"
    if re.search(r"\b(?:priority|premium|spot saver|visitor pass|premier|special needs|military in uniform)\b", checkpoint):
        return "PRIORITY"
    return "STANDARD"


def _generic_arrival_checkpoint_label(code: str, raw_label: object) -> Optional[str]:
    label = re.sub(r"\s+", " ", str(raw_label or "").strip())
    if not label or normalize_checkpoint_alias(label) in {"estimatedwait", "airportaverage"}:
        return None

    if code == "JAX" and normalize_checkpoint_alias(label) in {
        "standard", "tsapre", "prioritylane"
    }:
        return "Main checkpoint"

    label = re.sub(
        r"\s*\((?:general|regular|standard|priority|tsa[\s-]*pre|precheck|clear|premium|pre)\)\s*$",
        "",
        label,
        flags=re.IGNORECASE,
    )
    label = re.sub(
        r"\s+(?:general|regular|standard|priority lane|priority|tsa[\s-]*precheck|tsa[\s-]*pre|precheck only|precheck|clear|premium)\s*$",
        "",
        label,
        flags=re.IGNORECASE,
    ).strip(" -—:/")

    if re.fullmatch(r"\d+", label):
        label = f"Checkpoint {label}"
    elif code == "MCO" and label.lower() in {"east", "south", "west"}:
        label = f"{label.title()} checkpoint"
    return label or "Main checkpoint"


def _generic_arrival_checkpoint_id(code: str, label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return f"{code.lower()}-{slug or 'main-checkpoint'}"


def _generic_arrival_source(code: str) -> Dict:
    links = AIRPORT_PAGE_GUIDES.get(code, {}).get("links", [])
    official = links[0] if links else {
        "label": "TSA Tracker source methodology",
        "url": "/methodology",
    }
    return {
        "label": str(official.get("label") or f"Official {code} airport source"),
        "url": str(official.get("url") or ""),
        "verified_on": "2026-07-10",
    }


def build_generic_airport_arrival_config(
    code: str,
    rows: Optional[List[Dict]] = None,
    history_rows: Optional[List[Dict]] = None,
) -> Optional[Dict]:
    """Build checkpoint-only airport geometry from official feed labels."""
    meta = LIVE_AIRPORTS.get(code)
    point = AIRPORT_MAP_COORDINATES.get(code)
    if not meta or not point:
        return None

    checkpoints: Dict[str, Dict] = {}
    for row in [*(history_rows or []), *(rows or [])]:
        lane_type = _arrival_normalized_lane_type(row)
        if lane_type not in {"STANDARD", "PRECHECK"}:
            continue
        raw_label = str(row.get("checkpoint") or "").strip()
        label = _generic_arrival_checkpoint_label(code, raw_label)
        if not label:
            continue
        checkpoint_id = _generic_arrival_checkpoint_id(code, label)
        checkpoint = checkpoints.setdefault(
            checkpoint_id,
            {
                "id": checkpoint_id,
                "label": label,
                "aliases": [],
                "primary_for": [],
                "alternate_for": [],
                "hours": "",
                "note": "Checkpoint label supplied by the official airport feed.",
            },
        )
        if raw_label and raw_label not in checkpoint["aliases"]:
            checkpoint["aliases"].append(raw_label)

    lat = float(point["lat"])
    lng = float(point["lng"])
    lat_span, lng_span = GENERIC_AIRPORT_MAP_SPANS.get(code, (0.022, 0.034))
    return {
        "decision_mode": "checkpoint_only",
        "has_published_hours": False,
        "map": {
            "center": [lat, lng],
            "bounds": [[lat - lat_span, lng - lng_span], [lat + lat_span, lng + lng_span]],
            "overview_zoom": 14,
            "detail_zoom": 15.5,
            "location_accuracy": "airport_overview",
            "tile_url": "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}",
            "tile_attribution": "Imagery: USDA / USGS The National Map",
        },
        "source": _generic_arrival_source(code),
        "terminals": [
            {
                "id": "airport",
                "marker_code": code,
                "label": f"{code} airport overview",
                "summary": "Airport overview anchor; checkpoint locations are listed in the panel.",
                "anchor": [lat, lng],
                "location_accuracy": "airport_overview_anchor",
                "checkpoints": sorted(
                    checkpoints.values(), key=lambda checkpoint: checkpoint["label"].lower()
                ),
            }
        ],
    }


AIRPORT_FACTORS = {
    "ATL": 1.25, "BOS": 1.05, "CLT": 1.0, "DEN": 1.15, "DFW": 1.2, "DTW": 0.95,
    "EWR": 1.2, "FLL": 0.9, "HNL": 0.85, "IAH": 1.1, "JFK": 1.35, "LAS": 1.15,
    "LAX": 1.4, "LGA": 1.25, "MCO": 1.1, "MDW": 0.9, "MIA": 1.25, "MSP": 1.0,
    "ORD": 1.3, "PHL": 1.1, "PHX": 1.0, "SEA": 1.1, "SFO": 1.25, "SLC": 0.9,
    "DCA": 1.0,
    "TPA": 0.9, "JAX": 0.9,
}

PIPELINE_AIRPORTS = [
    {
        "code": "DEN",
        "name": "Denver International (DEN)",
        "status": "IN_RESEARCH",
        "public_note": "Live integration coming soon.",
    },

    {
        "code": "IAH",
        "name": "George Bush Intercontinental (IAH)",
        "status": "IN_RESEARCH",
        "public_note": "Live integration coming soon.",
        # internal: fly2houston.com/iah/security renders wait times dynamically (JS/AJAX).
        # Public checkpoint endpoint found at api.houstonairports.mobi, but the bundled API version is currently rejected.
        # See airport_research/pipeline/IAH.md for full investigation log.
    },
    {
        "code": "BWI",
        "name": "Baltimore/Washington International (BWI)",
        "status": "IN_RESEARCH",
        "public_note": "Live integration coming soon.",
        # internal: bwiairport.com/at-bwi/airport-security renders wait times dynamically.
        # No public JSON API found. Requires headless browser or XHR interception.
        # See airport_research/pipeline/BWI.md for full investigation log.
    },
    {
        "code": "DTW",
        "name": "Detroit Metropolitan (DTW)",
        "status": "IN_RESEARCH",
        "public_note": "Live integration coming soon.",
        # internal: metroairport.com/at-the-airport/security renders wait times dynamically.
        # No public JSON API found. Requires headless browser or XHR interception.
        # See airport_research/pipeline/DTW.md for full investigation log.
    },
    {
        "code": "IAD",
        "name": "Washington Dulles International (IAD)",
        "status": "IN_RESEARCH",
        "public_note": "Live integration coming soon.",
        # internal: flydulles.com and mwaa.com both render wait times dynamically.
        # No public JSON API found. Both are MWAA-operated (same backend).
        # See airport_research/pipeline/IAD.md for full investigation log.
    },
]
PIPELINE_AIRPORT_CODES = {airport["code"] for airport in PIPELINE_AIRPORTS}

LEGACY_PAGE_REDIRECTS = {
    "/airport-wait-times": "/airport-security-wait-times",
    "/airport-security-lines": "/airport-security-wait-times",
    "/security-wait-times": "/airport-security-wait-times",
    "/tsa-security-wait-times": "/airport-security-wait-times",
    "/tsa-wait-times": "/airport-security-wait-times",
    "/tsa-wait-times-by-airport": "/airports",
    "/how-early-should-i-arrive-for-tsa": "/best-time-to-get-to-the-airport",
    "/how-early-to-arrive-at-airport": "/best-time-to-get-to-the-airport",
    "/best-time-to-arrive-at-airport": "/best-time-to-get-to-the-airport",
    "/when-to-leave-for-airport": "/when-should-i-leave",
    "/tsa-wait-times-explained": "/guide/tsa-wait-times",
    "/tsa-precheck-vs-clear": "/guide/tsa-precheck-clear",
    "/clear-vs-tsa-precheck": "/guide/tsa-precheck-clear",
}

app = Flask(__name__)
LANE_TYPE_LABELS = {
    "STANDARD": "Standard",
    "PRECHECK": "PreCheck",
    "CLEAR": "CLEAR",
    "CLEAR_PRECHECK": "CLEAR + PreCheck",
}
LANE_TYPE_SORT_ORDER = {
    "STANDARD": 0,
    "PRECHECK": 1,
    "CLEAR": 2,
    "CLEAR_PRECHECK": 3,
}
_mia_cache = {"key": None, "endpoint": None, "fetched_at": None}
_clt_cache = {
    "key": None,
    "version": None,
    "endpoint": "https://api.cltairport.mobi/wait-times/checkpoint/CLT",
    "fetched_at": None,
}
_mco_cache = {
    "endpoint": "https://api.goaa.aero/wait-times/checkpoint/MCO",
    "key": os.getenv("MCO_API_KEY", "8eaac7209c824616a8fe58d22268cd59"),
    "version": os.getenv("MCO_API_VERSION", "140"),
}
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("tsa-tracker")
_db_init_lock = threading.Lock()
_db_initialized = False
_poll_lock = threading.Lock()
_poller_started = False
_network_history_cache = {"key": None, "generated_at": None, "payload": None}
NETWORK_HISTORY_CACHE_SECONDS = 15 * 60
HOURLY_AGGREGATE_MAX_DAYS = 90
CHECKPOINT_HISTORY_MIN_SAMPLES = 8
CHECKPOINT_HISTORY_MIN_BUCKETS = 2
CHECKPOINT_HISTORY_MAX_GROUPS = 10


def _lane_type_key(raw: object) -> str:
    return str(raw or "STANDARD").strip().upper()


def lane_type_label(raw: object) -> str:
    key = _lane_type_key(raw)
    return LANE_TYPE_LABELS.get(key, re.sub(r"[_-]+", " ", key).title())


def _lane_display_sort_key(lane: Dict) -> tuple:
    lane_type = lane.get("lane_type") if isinstance(lane, dict) else getattr(lane, "lane_type", "")
    key = _lane_type_key(lane_type)
    return (LANE_TYPE_SORT_ORDER.get(key, len(LANE_TYPE_SORT_ORDER)), lane_type_label(key))


@app.template_filter("lane_label")
def lane_label_filter(raw: object) -> str:
    return lane_type_label(raw)


@app.template_filter("lane_sort")
def lane_sort_filter(lanes: List[Dict]) -> List[Dict]:
    return sorted(lanes or [], key=_lane_display_sort_key)


@app.after_request
def add_crawl_control_headers(response):
    if request.path.startswith("/api/") or request.path == "/healthz":
        response.headers.setdefault("X-Robots-Tag", "noindex")
    if request.path in {"/link-graph", "/wide-link-graph"}:
        response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
    return response


def poll_forever() -> None:
    logger.info("poller_started poll_seconds=%s db_path=%s", POLL_SECONDS, DB_PATH)
    while True:
        try:
            with _poll_lock:
                collect_once()
        except Exception:
            logger.exception("poller_cycle_failed")
        time.sleep(POLL_SECONDS)

def start_web_runtime_once() -> None:
    global _db_initialized, _poller_started
    with _db_init_lock:
        if _db_initialized:
            return
        init_db()
        if ENABLE_POLLER and not _poller_started:
            thread = threading.Thread(target=poll_forever, name="tsa-poller", daemon=True)
            thread.start()
            _poller_started = True
        _db_initialized = True
    logger.info("web_runtime_started db_path=%s", DB_PATH)


def utc_now() -> datetime:
    return datetime.now(tz=APP_TZ)


EDITORIAL_REVIEW_DATES = {
    "/about": "2026-07-10",
    "/airport-security-wait-times": "2026-07-10",
    "/best-time-to-get-to-the-airport": "2026-07-10",
    "/guide/tsa-wait-times": "2026-07-10",
    "/guide/tsa-precheck-clear": "2026-07-10",
    "/methodology": "2026-07-10",
    "/privacy": "2026-07-10",
    "/terms": "2026-07-10",
    "/when-should-i-leave": "2026-07-10",
}


def editorial_review_date_iso(path: str) -> str:
    return EDITORIAL_REVIEW_DATES[path]


def editorial_review_date_label(path: str) -> str:
    value = datetime.strptime(editorial_review_date_iso(path), "%Y-%m-%d")
    return value.strftime("%B %d, %Y").replace(" 0", " ")


def airport_seo_slug(code: str) -> str:
    return f"/airports/{code.lower()}-tsa-wait-times"


def build_breadcrumbs(*items: tuple[str, str]) -> List[Dict]:
    return [
        {
            "position": index,
            "name": name,
            "item": f"{SITE_URL}{path}",
        }
        for index, (name, path) in enumerate(items, start=1)
    ]


def default_breadcrumb_label(title: str) -> str:
    return title.split("|", 1)[0].strip()


def build_page_seo(title: str, description: str, canonical_path: str, breadcrumbs: Optional[List[Dict]] = None) -> Dict:
    if breadcrumbs is None and canonical_path != "/":
        breadcrumbs = build_breadcrumbs(("Home", "/"), (default_breadcrumb_label(title), canonical_path))
    return {
        "title": title,
        "description": description,
        "canonical_url": f"{SITE_URL}{canonical_path}",
        "site_url": SITE_URL,
        "breadcrumbs": breadcrumbs or [],
    }


def home_page_seo() -> Dict:
    return build_page_seo(
        title="Live TSA Wait Times by Airport | TSA Tracker",
        description=(
            "Check TSA wait times by airport, compare checkpoint conditions, and see clearly labeled estimates when an official live feed is unavailable."
        ),
        canonical_path="/",
    )


def airport_page_seo(code: str, airport_name: str) -> Dict:
    clean_name = airport_name.split("(")[0].strip()
    return build_page_seo(
        title=f"{code} TSA Wait Times | {clean_name}",
        description=(
            f"Check current {code} TSA wait times, checkpoint conditions, 30-day patterns, "
            "terminal notes, and airport resources before you leave."
        ),
        canonical_path=airport_seo_slug(code),
        breadcrumbs=build_breadcrumbs(
            ("Home", "/"),
            ("Airports", "/airports"),
            (f"{code} TSA wait times", airport_seo_slug(code)),
        ),
    )


def airports_directory_seo() -> Dict:
    return build_page_seo(
        title="TSA Wait Times by Airport | Live Security Line Tracker",
        description=(
            "Compare TSA wait times by airport, see each reading's live or estimated source status, and open airport pages for checkpoint detail."
        ),
        canonical_path="/airports",
    )


def airport_security_wait_times_seo() -> Dict:
    return build_page_seo(
        title="Airport Security Wait Times | Live TSA Lines by Airport",
        description=(
            "Compare airport security wait times, source status, checkpoint details, and "
            "airport-specific guidance for major US airports."
        ),
        canonical_path="/airport-security-wait-times",
    )


def best_time_to_get_to_airport_seo() -> Dict:
    return build_page_seo(
        title="Best Time to Get to the Airport | Live TSA Timing Guide",
        description=(
            "Plan when to get to the airport using current TSA source status, normal peak-hour patterns, and airport-specific timing guidance."
        ),
        canonical_path="/best-time-to-get-to-the-airport",
    )


INTENT_PAGE_CONTENT = {
    "best-time-to-get-to-the-airport": {
        "seo": best_time_to_get_to_airport_seo,
        "eyebrow": "Timing Guide",
        "headline": "Best Time to Get to the Airport",
        "subhead": "Use live TSA wait times, normal peak-hour patterns, and airport-specific context to decide when to leave instead of relying on generic buffer rules.",
        "sections": [
            {
                "title": "The short answer",
                "body": [
                    "For most domestic trips, the best time to get to the airport is when you can clear bag drop, security, and the walk to your gate without arriving so early that you absorb a peak-hour security bank for no reason.",
                    "That usually means checking live wait times first, then comparing them against your airport's normal busy windows. Morning departures at major hubs often need more buffer than midday or late-evening departures.",
                ],
                "bullets": [
                    "Early morning flights usually need the most buffer because security lines often peak between 5 AM and 9 AM.",
                    "Late morning and mid-afternoon are often the easiest windows to clear security at major airports.",
                    "International flights still need extra buffer even if the security line looks fine.",
                ],
            },
            {
                "title": "Use live wait times before you leave",
                "body": [
                    "The best timing decision starts with the current airport page, not a rule of thumb. A normal two-hour domestic recommendation can be too much at one airport and not enough at another.",
                ],
                "bullets": [
                    "Check the current airport security wait first.",
                    "Use the 24-hour historical average to see whether the line is rising or easing.",
                    "Open the airport page if terminal layout or checkpoint choice matters at that airport.",
                ],
            },
            {
                "title": "When to add extra time",
                "body": [
                    "Add extra time if you are checking a bag, flying international, traveling with kids, using a crowded shuttle or parking lot, or flying through a hub that splits traffic across multiple terminals.",
                ],
                "bullets": [
                    "Bag drop lines can matter as much as TSA at busy airports.",
                    "Terminal-specific airports like LAX, JFK, BOS, and MIA can behave very differently by checkpoint.",
                    "If the live page is already showing elevated security timing, treat that as a warning, not a suggestion.",
                ],
            },
        ],
        "faq": [
            {
                "q": "What is the best time to get to the airport for a domestic flight?",
                "a": "Usually around 2 hours before departure, but the better answer is to check your airport's live TSA wait times first and add more buffer if the page shows a rising morning or afternoon peak.",
            },
            {
                "q": "What time of day are airport security lines shortest?",
                "a": "Late morning, mid-afternoon, and late evening are often easier than the early morning and after-work departure banks, but each airport has its own pattern.",
            },
            {
                "q": "Should I still arrive early if the live wait time is low?",
                "a": "Yes. Low security wait times help, but you still need time for parking, bag drop, terminal walking, and boarding cutoffs.",
            },
        ],
    },
}


def _forecast_hour(row: Dict) -> int:
    try:
        return int(row.get("hour", -1))
    except (TypeError, ValueError):
        return -1


def arrival_guidance_for_airport(payload: Dict) -> Dict:
    forecast = payload.get("hourlyForecast", []) if payload else []
    if forecast:
        best_candidates = [row for row in forecast if 5 <= _forecast_hour(row) <= 22]
        best_ordered = sorted(best_candidates or forecast, key=lambda row: float(row.get("waittime", 0)))
        ordered = sorted(forecast, key=lambda row: float(row.get("waittime", 0)))
        best = best_ordered[0]
        worst = ordered[-1]
        best_label = best.get("timeslot", "late morning")
        risk_label = worst.get("timeslot", "the busiest bank")
    else:
        best_label = "late morning to mid-afternoon"
        risk_label = "early morning and late afternoon"

    current = payload.get("currentWait", {}) if payload else {}
    current_minutes = float(current.get("standard", 0) or 0)
    current_desc = current.get("standardDescription", "current conditions")
    source_type = payload.get("sourceType", "estimated_fallback") if payload else "estimated_fallback"
    if source_type != "live_direct":
        recommendation = (
            "The live airport source is unavailable, so the current number is planning context rather "
            "than a measured line. Use a wider buffer and recheck before leaving."
        )
    elif current_minutes >= 20:
        recommendation = (
            f"The current official reading is elevated at {current_desc}. Add buffer; the modeled "
            f"daily baseline is also highest around {risk_label}."
        )
    else:
        recommendation = (
            f"The current official reading is {current_desc}. The modeled daily baseline is highest "
            f"around {risk_label}, so recheck if your trip overlaps that window."
        )

    return {
        "best_window": best_label,
        "risk_window": risk_label,
        "recommendation": recommendation,
        "is_live": source_type == "live_direct",
    }


def airport_page_editorial_context(code: str, payload: Optional[Dict], checkpoints: List[Dict]) -> Dict:
    guide = AIRPORT_PAGE_GUIDES.get(code, {})
    notice = airport_status_notice_for_code(code)
    source_type = (payload or {}).get("sourceType", "estimated_fallback")
    source_reason = (payload or {}).get("sourceReason", "")
    checkpoint_count = len({c["checkpoint"] for c in checkpoints})
    link_count = len(guide.get("links", []))

    if source_type == "live_direct":
        if checkpoint_count > 1:
            source_summary = f"This page is currently backed by {checkpoint_count} live {code} checkpoint readings, so the terminal and checkpoint spread matters more than a single airport-wide average."
        else:
            source_summary = f"This page is currently backed by a live {code} airport reading. Use the current number first, then the history chart to judge whether conditions are rising or easing."
    elif notice:
        source_summary = notice.get("summary", f"Live checkpoint data is limited for {code} right now, so this page leans harder on airport-specific context and planning guidance.")
    elif source_reason == "live_stale_or_unavailable":
        source_summary = f"Live checkpoint data is temporarily unavailable for {code}, so the current number is a planning estimate and the airport-specific notes below matter more than usual."
    else:
        source_summary = f"This {code} page combines the current planning estimate with airport-specific notes, official airport resources, and the normal high-risk departure windows for this airport."

    bullets = [source_summary]
    for item in guide.get("notes", []):
        if item not in bullets:
            bullets.append(item)

    body = (
        f"This page adds {code}-specific terminal context, airline routing notes, and {link_count} source or reference link"
        f"{'s' if link_count != 1 else ''} so the wait-time reading is actually usable for a same-day trip."
    )

    return {
        "summary": source_summary,
        "body": body,
        "bullets": bullets,
    }


def normalize_checkpoint_alias(value: object) -> str:
    text = str(value or "").lower().strip()
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"\bterminal\s*([0-9]+)\b", r"t\1", text)
    text = text.replace("&", "/")
    return re.sub(r"\s+", "", text)


def build_airport_decision_map(code: str, rows: List[Dict]) -> Optional[Dict]:
    config = AIRPORT_DECISION_MAPS.get(code)
    # The legacy schematic contains LAS-specific gate and check-in controls.
    # Terminal/checkpoint airports use Arrival Mode only; if their feature flag
    # is disabled they must fall back to the ordinary checkpoint page instead.
    if not config or config.get("decision_mode") != "terminal_gate":
        return None

    alias_to_node = {}
    for terminal in config["terminals"]:
        for checkpoint in terminal["checkpoints"]:
            for alias in checkpoint.get("aliases", []):
                normalized = normalize_checkpoint_alias(alias)
                existing = alias_to_node.get(normalized)
                if existing and existing != checkpoint["id"]:
                    raise ValueError(f"Duplicate checkpoint alias {alias!r}")
                alias_to_node[normalized] = checkpoint["id"]

    rows_by_node = {}
    unmatched_rows = []
    for row in rows or []:
        node_id = alias_to_node.get(normalize_checkpoint_alias(row.get("checkpoint")))
        if not node_id:
            unmatched_rows.append(row)
            continue
        rows_by_node.setdefault(node_id, []).append(row)

    terminals = []
    for terminal in config["terminals"]:
        checkpoints = []
        for checkpoint in terminal["checkpoints"]:
            live_rows = sorted(rows_by_node.get(checkpoint["id"], []), key=_lane_display_sort_key)
            lane_waits = {
                _lane_type_key(row.get("lane_type")): float(row.get("wait_minutes", 0) or 0)
                for row in live_rows
            }
            captured_values = [row.get("captured_at") for row in live_rows if row.get("captured_at")]
            captured_at = max(captured_values) if captured_values else ""
            checkpoints.append(
                {
                    **checkpoint,
                    "terminal_id": terminal["id"],
                    "terminal_label": terminal["label"],
                    "live_alias": live_rows[0].get("checkpoint", "") if live_rows else "",
                    "lanes": live_rows,
                    "lane_waits": lane_waits,
                    "standard_wait": lane_waits.get("STANDARD"),
                    "precheck_wait": lane_waits.get("PRECHECK"),
                    "status": "reporting" if live_rows else "not_reporting",
                    "captured_at": captured_at,
                    "captured_label": format_airport_timestamp(code, captured_at) if captured_at else "",
                }
            )
        terminals.append({**terminal, "checkpoints": checkpoints})

    return {
        "code": code,
        "source": config["source"],
        "terminals": terminals,
        "unmatched_rows": sorted(unmatched_rows, key=_lane_display_sort_key),
    }


AIRPORT_ARRIVAL_MODE_SCHEMA_VERSION = 1
AIRPORT_ARRIVAL_MODE_REFRESH_SECONDS = 120
AIRPORT_ARRIVAL_MODE_HISTORY_HOURS = 24
AIRPORT_ARRIVAL_MODE_LANES = ("STANDARD", "PRECHECK")


def _arrival_checkpoint_aliases(config: Dict) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    for terminal in config.get("terminals", []):
        for checkpoint in terminal.get("checkpoints", []):
            values = [checkpoint.get("id"), checkpoint.get("label"), *checkpoint.get("aliases", [])]
            for value in values:
                normalized = normalize_checkpoint_alias(value)
                if not normalized:
                    continue
                existing = aliases.get(normalized)
                if existing and existing != checkpoint["id"]:
                    raise ValueError(f"Duplicate checkpoint alias {value!r}")
                aliases[normalized] = checkpoint["id"]
    return aliases


def _arrival_checkpoint_id(row: Dict, aliases: Dict[str, str]) -> Optional[str]:
    explicit_id = normalize_checkpoint_alias(row.get("checkpoint_id"))
    if explicit_id and explicit_id in aliases:
        return aliases[explicit_id]
    return aliases.get(normalize_checkpoint_alias(row.get("checkpoint")))


def _arrival_datetime(value: object) -> Optional[datetime]:
    if not value:
        return None
    try:
        captured = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=APP_TZ)
    return captured.astimezone(APP_TZ)


def _arrival_wait_minutes(value: object) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        wait = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(wait) or wait < 0:
        return None
    return clamp_wait_minutes(wait)


def _arrival_freshness(captured_at: object, now: datetime) -> str:
    captured = _arrival_datetime(captured_at)
    if not captured:
        return "no_current_reading"
    age_minutes = max(0.0, (now - captured).total_seconds() / 60.0)
    if age_minutes <= 5:
        return "live"
    if age_minutes <= 15:
        return "aging"
    return "stale"


def _arrival_lane_trend(
    checkpoint_id: str,
    lane_type: str,
    history_rows: List[Dict],
    aliases: Dict[str, str],
) -> Dict:
    samples = []
    for row in history_rows or []:
        if _arrival_checkpoint_id(row, aliases) != checkpoint_id:
            continue
        if _arrival_normalized_lane_type(row) != lane_type:
            continue
        wait = _arrival_wait_minutes(row.get("wait_minutes"))
        captured = _arrival_datetime(row.get("captured_at"))
        if wait is None or not captured:
            continue
        samples.append((captured, wait))

    samples.sort(key=lambda sample: sample[0])
    samples = samples[-12:]
    if len(samples) < 2:
        return {"direction": None, "delta": None}

    midpoint = max(1, len(samples) // 2)
    earlier = [wait for _, wait in samples[:midpoint]]
    later = [wait for _, wait in samples[midpoint:]]
    if not later:
        return {"direction": None, "delta": None}

    delta = round((sum(later) / len(later)) - (sum(earlier) / len(earlier)), 1)
    if delta >= 2.0:
        direction = "rising"
    elif delta <= -2.0:
        direction = "falling"
    else:
        direction = "steady"
    return {"direction": direction, "delta": delta}


def build_airport_arrival_mode(
    code: str,
    rows: Optional[List[Dict]] = None,
    history_rows: Optional[List[Dict]] = None,
    now: Optional[datetime] = None,
) -> Optional[Dict]:
    """Build the reusable airport-level map model without inferring checkpoint closure."""
    code = str(code or "").strip().upper()
    meta = LIVE_AIRPORTS.get(code)
    config = AIRPORT_DECISION_MAPS.get(code) or build_generic_airport_arrival_config(
        code,
        rows=rows,
        history_rows=history_rows,
    )
    if not config or not meta:
        return None

    generated_at = now or utc_now()
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=APP_TZ)
    generated_at = generated_at.astimezone(APP_TZ)
    aliases = _arrival_checkpoint_aliases(config)
    trend_rows = history_rows if history_rows is not None else (rows or [])

    current_by_lane: Dict[tuple, Dict] = {}
    # History supplies a last-known row when latest_snapshot's 15-minute cutoff
    # has expired. The stale numeric is deliberately suppressed below.
    for row in [*(history_rows or []), *(rows or [])]:
        checkpoint_id = _arrival_checkpoint_id(row, aliases)
        if not checkpoint_id:
            continue
        lane_type = _arrival_normalized_lane_type(row)
        if lane_type not in AIRPORT_ARRIVAL_MODE_LANES:
            continue
        wait = _arrival_wait_minutes(row.get("wait_minutes"))
        captured = _arrival_datetime(row.get("captured_at"))
        if wait is None or not captured:
            continue
        key = (checkpoint_id, lane_type)
        existing = current_by_lane.get(key)
        existing_captured = _arrival_datetime(existing.get("captured_at")) if existing else None
        if not existing_captured or captured >= existing_captured:
            current_by_lane[key] = {**row, "wait_minutes": wait}

    unmatched_readings = [
        row for row in (rows or []) if not _arrival_checkpoint_id(row, aliases)
    ]
    terminals = []
    fastest = None
    aggregate_statuses = []

    for terminal in config.get("terminals", []):
        checkpoints = []
        for checkpoint in terminal.get("checkpoints", []):
            published_only = bool(checkpoint.get("published_only"))
            lanes = []
            lane_waits = {}
            for lane_type in AIRPORT_ARRIVAL_MODE_LANES:
                current = current_by_lane.get((checkpoint["id"], lane_type))
                freshness = "published_only" if published_only else "no_current_reading"
                wait_minutes = None
                captured_at = ""
                captured_label = ""
                trend = {"direction": None, "delta": None}

                if current and not published_only:
                    captured_at = str(current.get("captured_at") or "")
                    freshness = _arrival_freshness(captured_at, generated_at)
                    if freshness in {"live", "aging"}:
                        wait_minutes = _arrival_wait_minutes(current.get("wait_minutes"))
                        trend = _arrival_lane_trend(
                            checkpoint["id"], lane_type, trend_rows, aliases
                        )
                    captured_label = format_airport_timestamp(code, captured_at)

                lane = {
                    "lane_type": lane_type,
                    "label": lane_type_label(lane_type),
                    "wait_minutes": wait_minutes,
                    "freshness_status": freshness,
                    "freshness_state": freshness,
                    "trend": trend["direction"],
                    "trend_arrow": TREND_ARROWS.get(trend["direction"]),
                    "trend_delta": trend["delta"],
                    "captured_at": captured_at,
                    "captured_label": captured_label,
                    "source_label": config["source"]["label"],
                    "source_url": (current.get("source") or config["source"]["url"])
                    if current
                    else config["source"]["url"],
                }
                lanes.append(lane)
                lane_waits[lane_type] = wait_minutes
                aggregate_statuses.append(freshness)

                if wait_minutes is not None and freshness in {"live", "aging"}:
                    candidate = {
                        "checkpoint_id": checkpoint["id"],
                        "checkpoint_label": checkpoint["label"],
                        "terminal_id": terminal["id"],
                        "terminal_label": terminal["label"],
                        "lane_type": lane_type,
                        "wait_minutes": wait_minutes,
                        "freshness_status": freshness,
                        "captured_at": captured_at,
                    }
                    if fastest is None or candidate["wait_minutes"] < fastest["wait_minutes"]:
                        fastest = candidate

            checkpoint_statuses = [lane["freshness_status"] for lane in lanes]
            if "live" in checkpoint_statuses:
                checkpoint_status = "live"
            elif "aging" in checkpoint_statuses:
                checkpoint_status = "aging"
            elif "stale" in checkpoint_statuses:
                checkpoint_status = "stale"
            elif published_only:
                checkpoint_status = "published_only"
            else:
                checkpoint_status = "no_current_reading"

            checkpoints.append(
                {
                    **checkpoint,
                    "published_only": published_only,
                    "terminal_id": terminal["id"],
                    "terminal_label": terminal["label"],
                    "lanes": lanes,
                    "lane_waits": lane_waits,
                    "standard_wait": lane_waits.get("STANDARD"),
                    "precheck_wait": lane_waits.get("PRECHECK"),
                    "status": checkpoint_status,
                }
            )
        terminals.append({**terminal, "checkpoints": checkpoints})

    if "live" in aggregate_statuses:
        source_status = "live"
    elif "aging" in aggregate_statuses:
        source_status = "aging"
    elif "stale" in aggregate_statuses:
        source_status = "stale"
    else:
        source_status = "no_current_reading"

    source = {**config["source"], "freshness_status": source_status}
    map_config = dict(config.get("map", {}))
    return {
        "schema_version": AIRPORT_ARRIVAL_MODE_SCHEMA_VERSION,
        "airport": {
            "code": code,
            "name": meta["name"],
            "city": meta.get("city", ""),
        },
        "code": code,
        "generated_at": generated_at.isoformat(),
        "refresh_seconds": AIRPORT_ARRIVAL_MODE_REFRESH_SECONDS,
        "decision_mode": config.get("decision_mode", "terminal_gate"),
        "has_published_hours": bool(config.get("has_published_hours")),
        "all_checkpoints_reach_all_gates": bool(
            config.get("all_checkpoints_reach_all_gates")
        ),
        "routing_note": str(config.get("routing_note") or ""),
        "map": map_config,
        "source": source,
        "source_status": source_status,
        "lane_types": list(AIRPORT_ARRIVAL_MODE_LANES),
        "terminals": terminals,
        "fastest_fresh_reading": fastest,
        "unmatched_readings": sorted(unmatched_readings, key=_lane_display_sort_key),
        "unmatched_rows": sorted(unmatched_readings, key=_lane_display_sort_key),
    }


def airport_bad_now_actions(code: str) -> List[str]:
    actions = [
        f"Check whether {code} splits traffic by checkpoint or terminal before joining the first line you see.",
        f"If {code} offers TSA PreCheck or CLEAR lane detail, compare those lanes before assuming the standard line is your only option.",
        "If the line is already elevated, add extra buffer for bag drop, parking, and the walk to the gate instead of focusing only on the checkpoint number.",
    ]
    guide = AIRPORT_PAGE_GUIDES.get(code, {})
    for bucket in ("terminal_notes", "airline_notes", "tips"):
        for note in guide.get(bucket, []):
            if note not in actions:
                actions.append(note)
            if len(actions) >= 5:
                return actions[:5]
    return actions[:5]


def related_airports_for_code(code: str) -> List[Dict]:
    preferred = {
        "JFK": ["LGA", "EWR", "BOS", "MIA"],
        "LAX": ["SFO", "LAS", "SEA", "DFW"],
        "ORD": ["DFW", "ATL", "BOS", "MCO"],
        "DFW": ["ATL", "ORD", "MCO", "LAX"],
        "ATL": ["MCO", "DFW", "CLT", "MIA"],
        "MCO": ["ATL", "MIA", "DFW", "JFK"],
        "LGA": ["JFK", "EWR", "BOS", "ATL"],
        "EWR": ["JFK", "LGA", "BOS", "ORD"],
        "BOS": ["JFK", "LGA", "EWR", "MCO"],
        "MIA": ["MCO", "ATL", "JFK", "LAX"],
    }
    ordered_codes = preferred.get(code, [])
    related = []
    for other in ordered_codes:
        if other in LIVE_AIRPORTS and other != code:
            related.append({
                "code": other,
                "name": LIVE_AIRPORTS[other]["name"],
                "href": airport_seo_slug(other),
            })
    if related:
        return related[:4]

    fallback = []
    for other, meta in LIVE_AIRPORTS.items():
        if other == code:
            continue
        fallback.append({"code": other, "name": meta["name"], "href": airport_seo_slug(other)})
    return fallback[:4]


def airport_personality_profiles() -> Dict[str, Dict]:
    profiles = {}
    for code, meta in LIVE_AIRPORTS.items():
        guide = AIRPORT_PAGE_GUIDES.get(code, {})
        theme = AIRPORT_PROFILE_THEMES.get(code, {})
        profiles[code] = {
            "code": code,
            "name": meta.get("name", code),
            "city": meta.get("city", ""),
            "href": airport_seo_slug(code),
            "label": theme.get("label", "Live airport"),
            "accent": theme.get("accent", "#f59e0b"),
            "secondary": theme.get("secondary", "#60a5fa"),
            "terminal_highlights": guide.get("terminal_notes", [])[:5],
            "airline_highlights": guide.get("airline_notes", [])[:2],
            "strategy": guide.get("tips", [])[:3],
            "source_links": guide.get("links", [])[:2],
        }
    return profiles


def legal_page_seo(slug: str) -> Dict:
    mapping = {
        "privacy": ("Privacy Policy", "Read TSA Tracker's privacy policy and data handling details."),
        "terms": ("Terms of Service", "Read TSA Tracker's terms for using TSA wait-time services."),
        "contact": ("Contact", "Contact TSA Tracker for support, data questions, or partnerships."),
        "methodology": ("Methodology", "How TSA Tracker sources, validates, and updates airport TSA wait time data."),
    }
    title, description = mapping[slug]
    return build_page_seo(
        title=f"{title} | TSA Tracker",
        description=description,
        canonical_path=f"/{slug}",
    )


def airport_status_notice_for_code(code: str) -> Dict:
    return AIRPORT_STATUS_NOTICES.get(code, {})


def index_template_context(initial_airport_code: str, seo: Dict) -> Dict:
    is_airport_page = bool(initial_airport_code and initial_airport_code in LIVE_AIRPORTS)
    airport_display_name = ""
    initial_data = None
    initial_checkpoints = []
    if is_airport_page:
        raw_name = LIVE_AIRPORTS[initial_airport_code]["name"]
        airport_display_name = raw_name.split("(")[0].strip()
        try:
            initial_data = normalized_current_wait_for_code(initial_airport_code)
            initial_checkpoints = latest_for_code(initial_airport_code)
        except Exception as e:
            logger.error("Error fetching initial data for %s: %s", initial_airport_code, e)
        if initial_data is None:
            estimated = round(estimated_wait_for_hour(utc_now().hour, AIRPORT_FACTORS.get(initial_airport_code, 1.0)), 1)
            initial_data = {
                "available": True,
                "sourceType": "estimated_fallback",
                "sourceReason": "initial_page_fallback",
                "currentWait": {
                    "standard": estimated,
                    "standardDescription": wait_description(estimated),
                    "userReported": None,
                    "precheck": False,
                    "timestamp": utc_now().isoformat(),
                },
                "hourlyForecast": normalize_hourly_forecast(initial_airport_code, estimated),
            }
    try:
        monetization = get_monetization_context(
            initial_airport_code,
            page_type="airport" if is_airport_page else "home",
        )
    except Exception as e:
        logger.error("Error building monetization context for %s: %s", initial_airport_code or "HOME", e)
        monetization = get_monetization_context(
            "",
            page_type="airport" if is_airport_page else "home",
        )
    airport_overview = build_airport_overview_context()
    airport_summary = next(
        (a for a in airport_overview["airport_summaries"] if a["code"] == initial_airport_code), None
    ) if is_airport_page else None
    airport_arrival_mode = None
    if is_airport_page and initial_airport_code in AIRPORT_ARRIVAL_MODE_CODES:
        arrival_history = []
        try:
            arrival_history = history_for_airport(
                initial_airport_code,
                hours=AIRPORT_ARRIVAL_MODE_HISTORY_HOURS,
            )
        except Exception as e:
            logger.warning(
                "Arrival history unavailable for %s; rendering current rows without trends: %s",
                initial_airport_code,
                e,
            )
        try:
            airport_arrival_mode = build_airport_arrival_mode(
                initial_airport_code,
                rows=initial_checkpoints,
                history_rows=arrival_history,
            )
        except Exception as e:
            logger.error("Error building arrival mode for %s: %s", initial_airport_code, e)
    return {
        "airport_summary": airport_summary,
        "live_airports": LIVE_AIRPORTS,
        "pipeline_airports": PIPELINE_AIRPORTS,
        "initial_airport_code": initial_airport_code,
        "is_airport_page": is_airport_page,
        "airport_display_name": airport_display_name,
        "airport_city": LIVE_AIRPORTS[initial_airport_code].get("city") if is_airport_page and initial_airport_code in LIVE_AIRPORTS else None,
        "airport_guide": AIRPORT_PAGE_GUIDES.get(initial_airport_code, {}),
        "airport_notice": airport_status_notice_for_code(initial_airport_code) if is_airport_page else {},
        "arrival_guidance": arrival_guidance_for_airport(initial_data) if is_airport_page else None,
        "airport_editorial": airport_page_editorial_context(initial_airport_code, initial_data, initial_checkpoints) if is_airport_page else None,
        "airport_bad_now_actions": airport_bad_now_actions(initial_airport_code) if is_airport_page else [],
        "related_airports": related_airports_for_code(initial_airport_code) if is_airport_page else [],
        "airport_pages": [{"code": c, "href": airport_seo_slug(c), "name": v["name"]} for c, v in LIVE_AIRPORTS.items()],
        "airport_summaries": airport_overview["airport_summaries"],
        "overall_average": airport_overview["overall_average"],
        "fastest_airport": airport_overview["fastest_airport"],
        "slowest_airport": airport_overview["slowest_airport"],
        "live_count": airport_overview["live_count"],
        "estimated_count": airport_overview["estimated_count"],
        "seo": seo,
        "initial_data": initial_data,
        "initial_checkpoints": initial_checkpoints,
        "airport_decision_map": build_airport_decision_map(initial_airport_code, initial_checkpoints)
        if is_airport_page
        else None,
        "airport_arrival_mode": airport_arrival_mode,
        "monetization": monetization,
        "LOCAL_OFFERS_JSON": json.dumps(LOCAL_OFFERS),
        "KIWI_AIRPORT_URLS_JSON": json.dumps(KIWI_AIRPORT_PAGE_URLS),
        "AIRPORT_PROFILES_JSON": json.dumps(airport_personality_profiles()),
        "app_js_version": APP_JS_VERSION,
    }


def intent_page_context(page_key: str) -> Dict:
    page = INTENT_PAGE_CONTENT[page_key]
    overview = build_airport_overview_context()
    featured_codes = ["JFK", "LAX", "ORD", "ATL", "MCO", "DFW", "BOS", "MIA"]
    featured_code_set = set(featured_codes)
    featured_airports = []
    for code in featured_codes:
        if code in LIVE_AIRPORTS:
            featured_airports.append(
                {
                    "code": code,
                    "name": LIVE_AIRPORTS[code]["name"],
                    "href": airport_seo_slug(code),
                }
            )
    supporting_airports = [
        airport
        for airport in overview["airport_pages"]
        if airport["code"] not in featured_code_set
    ]
    return {
        "page": page,
        "seo": page["seo"](),
        "monetization": get_monetization_context(),
        "airport_pages": overview["airport_pages"],
        "featured_airports": featured_airports,
        "supporting_airports": supporting_airports,
        "fastest_airport": overview["fastest_airport"],
        "slowest_airport": overview["slowest_airport"],
        "overall_average": overview["overall_average"],
        "live_count": overview["live_count"],
        "estimated_count": overview["estimated_count"],
        "copy_updated_label": editorial_review_date_label(f"/{page_key}"),
        "copy_updated_iso": editorial_review_date_iso(f"/{page_key}"),
    }


def compute_airport_trends(window_minutes: int = 30) -> Dict[str, Dict]:
    """Compare recent average wait (last 10 min) vs the window start (25-40 min ago)
    for every airport in one query. Returns {code: {direction, delta}}."""
    now = utc_now()
    recent_cutoff = (now - timedelta(minutes=10)).isoformat()
    old_start = (now - timedelta(minutes=window_minutes + 10)).isoformat()
    old_end = (now - timedelta(minutes=window_minutes - 5)).isoformat()
    trends: Dict[str, Dict] = {}
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT airport_code,
                   AVG(CASE WHEN captured_at >= ? THEN wait_minutes END) AS recent_avg,
                   AVG(CASE WHEN captured_at >= ? AND captured_at <= ? THEN wait_minutes END) AS old_avg
            FROM samples
            WHERE captured_at >= ? AND wait_minutes > 0
            GROUP BY airport_code
            """,
            (recent_cutoff, old_start, old_end, old_start),
        )
        for code, recent_avg, old_avg in cur.fetchall():
            if recent_avg is None or old_avg is None:
                continue
            delta = round(float(recent_avg) - float(old_avg), 1)
            if delta >= 2.0:
                direction = "rising"
            elif delta <= -2.0:
                direction = "falling"
            else:
                direction = "steady"
            trends[code] = {"direction": direction, "delta": delta}
        conn.close()
    except Exception as e:
        logger.warning("trend_computation_failed: %s", e)
    return trends


TREND_ARROWS = {"rising": "↑", "falling": "↓", "steady": "→"}


def build_airport_overview_context() -> Dict:
    snapshot = latest_snapshot()
    trends = compute_airport_trends()
    airport_summaries = []
    total_wait = 0.0
    live_count = 0
    estimated_count = 0

    for code, meta in sorted(LIVE_AIRPORTS.items()):
        map_point = AIRPORT_MAP_COORDINATES.get(code, {})
        rows = snapshot.get(code, [])
        if rows:
            current_wait = average_wait_from_rows(rows)
            updated_at = max(rows, key=lambda r: r.get("captured_at", ""))["captured_at"]
            source_type = "live_direct"
            checkpoint_count = len({row.get("checkpoint") for row in rows if row.get("checkpoint")})
            source_label = f"{checkpoint_count} checkpoint{'s' if checkpoint_count != 1 else ''}"
            live_count += 1
        else:
            payload = normalized_current_wait_for_code(code)
            current = payload.get("currentWait", {})
            current_wait = float(current.get("standard", 0) or 0)
            updated_at = current.get("timestamp", utc_now().isoformat())
            source_type = payload.get("sourceType", "estimated_fallback")
            source_label = "Estimated fallback"
            estimated_count += 1

        total_wait += current_wait
        airport_summaries.append(
            {
                "code": code,
                "name": meta["name"],
                "city": meta.get("city", ""),
                "href": airport_seo_slug(code),
                "current_wait": current_wait,
                "wait_description": wait_description(current_wait),
                "tier": wait_tier_class_for_minutes(current_wait),
                "updated_at": format_airport_timestamp(code, updated_at),
                "source_type": source_type,
                "source_label": source_label,
                "is_live": source_type == "live_direct",
                "is_closed": False,
                "is_zero": current_wait <= 0,
                "trend": trends.get(code, {}).get("direction", "steady"),
                "trend_delta": trends.get(code, {}).get("delta", 0.0),
                "trend_arrow": TREND_ARROWS.get(trends.get(code, {}).get("direction", "steady"), "→"),
                "map_lat": map_point.get("lat"),
                "map_lng": map_point.get("lng"),
            }
        )

    airport_summaries.sort(key=lambda item: (-item["current_wait"], item["code"]))
    rankable = [a for a in airport_summaries if a["current_wait"] > 0]
    fastest_airport = min(rankable, key=lambda item: item["current_wait"], default=None)
    slowest_airport = max(rankable, key=lambda item: item["current_wait"], default=None)
    overall_average = round(sum(a["current_wait"] for a in rankable) / len(rankable), 1) if rankable else 0.0

    airport_pages = []
    for code, meta in sorted(LIVE_AIRPORTS.items()):
        airport_pages.append(
            {
                "code": code,
                "href": airport_seo_slug(code),
                "name": meta["name"],
                "city": meta.get("city", ""),
            }
        )
    return {
        "airport_pages": airport_pages,
        "airport_summaries": airport_summaries,
        "overall_average": overall_average,
        "fastest_airport": fastest_airport,
        "slowest_airport": slowest_airport,
        "live_count": live_count,
        "estimated_count": estimated_count,
    }


def airport_directory_context() -> Dict:
    overview = build_airport_overview_context()
    return {
        "pipeline_airports": PIPELINE_AIRPORTS,
        "airport_pages": overview["airport_pages"],
        "airport_summaries": overview["airport_summaries"],
        "overall_average": overview["overall_average"],
        "fastest_airport": overview["fastest_airport"],
        "slowest_airport": overview["slowest_airport"],
        "live_count": overview["live_count"],
        "estimated_count": overview["estimated_count"],
        "seo": airports_directory_seo(),
        "monetization": get_monetization_context(),
        "app_js_version": APP_JS_VERSION,
    }


def compute_pagerank(nodes: List[Dict], edges: List[Dict], alpha: float = 0.85, max_iter: int = 100, tol: float = 1e-10) -> Dict[str, float]:
    node_ids = [node["id"] for node in nodes]
    if not node_ids:
        return {}

    outbound = {node_id: set() for node_id in node_ids}
    for edge in edges:
        src = edge["from"]
        dst = edge["to"]
        if src in outbound and dst in outbound and src != dst:
            outbound[src].add(dst)

    n = len(node_ids)
    scores = {node_id: 1.0 / n for node_id in node_ids}

    for _ in range(max_iter):
        next_scores = {node_id: (1.0 - alpha) / n for node_id in node_ids}
        sink_total = sum(scores[node_id] for node_id in node_ids if not outbound[node_id])
        sink_share = alpha * sink_total / n
        for node_id in node_ids:
            next_scores[node_id] += sink_share
        for src, targets in outbound.items():
            if not targets:
                continue
            share = alpha * scores[src] / len(targets)
            for dst in targets:
                next_scores[dst] += share

        delta = max(abs(next_scores[node_id] - scores[node_id]) for node_id in node_ids)
        scores = next_scores
        if delta < tol:
            break

    return scores


def link_graph_context(canonical_path: str = "/link-graph") -> Dict:
    airport_codes = sorted(LIVE_AIRPORTS.keys())
    nodes = [
        {"id": "/", "label": "Home", "group": "core", "url": "/", "kind": "core"},
        {"id": "/airports", "label": "Airports", "group": "core", "url": "/airports", "kind": "core"},
        {"id": "/airport-security-wait-times", "label": "Wait Times Hub", "group": "core", "url": "/airport-security-wait-times", "kind": "core"},
        {"id": "/methodology", "label": "Methodology", "group": "core", "url": "/methodology", "kind": "core"},
        {"id": "/guide/tsa-wait-times", "label": "TSA Guide", "group": "guide", "url": "/guide/tsa-wait-times", "kind": "guide"},
        {"id": "/guide/tsa-precheck-clear", "label": "PreCheck vs CLEAR", "group": "guide", "url": "/guide/tsa-precheck-clear", "kind": "guide"},
        {"id": "/best-time-to-get-to-the-airport", "label": "Best Timing", "group": "guide", "url": "/best-time-to-get-to-the-airport", "kind": "guide"},
        {"id": "/when-should-i-leave", "label": "Leave-Time Calculator", "group": "guide", "url": "/when-should-i-leave", "kind": "guide"},
        {"id": "/about", "label": "About", "group": "info", "url": "/about", "kind": "info"},
        {"id": "/contact", "label": "Contact", "group": "info", "url": "/contact", "kind": "info"},
        {"id": "/privacy", "label": "Privacy", "group": "info", "url": "/privacy", "kind": "info"},
        {"id": "/terms", "label": "Terms", "group": "info", "url": "/terms", "kind": "info"},
    ]
    for code in airport_codes:
        nodes.append(
            {
                "id": airport_seo_slug(code),
                "label": code,
                "group": "airport",
                "url": airport_seo_slug(code),
                "kind": "airport",
            }
        )

    edges = []
    edge_keys = set()
    node_ids = {node["id"] for node in nodes}

    def add_edges(src: str, targets: List[str]) -> None:
        for target in targets:
            key = (src, target)
            if src in node_ids and target in node_ids and target != src and key not in edge_keys:
                edges.append({"from": src, "to": target})
                edge_keys.add(key)

    airport_targets = [airport_seo_slug(code) for code in airport_codes]
    guide_targets = [
        "/guide/tsa-wait-times",
        "/guide/tsa-precheck-clear",
        "/best-time-to-get-to-the-airport",
        "/when-should-i-leave",
    ]
    hub_targets = ["/", "/airports", "/airport-security-wait-times", "/methodology", "/when-should-i-leave"]

    add_edges("/", ["/airports", "/airport-security-wait-times", "/best-time-to-get-to-the-airport", "/when-should-i-leave", "/methodology", "/guide/tsa-wait-times", "/guide/tsa-precheck-clear"] + airport_targets)
    add_edges("/airports", ["/airport-security-wait-times", "/when-should-i-leave", "/guide/tsa-wait-times", "/guide/tsa-precheck-clear", "/methodology", "/about", "/contact"] + airport_targets)
    add_edges("/airport-security-wait-times", ["/", "/airports", "/methodology", "/guide/tsa-wait-times", "/best-time-to-get-to-the-airport", "/when-should-i-leave", "/guide/tsa-precheck-clear"] + airport_targets)
    add_edges("/methodology", ["/", "/airports", "/airport-security-wait-times", "/guide/tsa-wait-times", "/guide/tsa-precheck-clear", "/best-time-to-get-to-the-airport", "/about", "/contact"])
    add_edges("/guide/tsa-wait-times", ["/", "/airports", "/airport-security-wait-times", "/methodology", "/guide/tsa-precheck-clear"] + airport_targets)
    add_edges("/guide/tsa-precheck-clear", ["/", "/airports", "/airport-security-wait-times", "/guide/tsa-wait-times"] + [airport_seo_slug(code) for code in ["JFK", "LGA", "ORD", "LAX"] if code in LIVE_AIRPORTS])
    add_edges("/best-time-to-get-to-the-airport", hub_targets + airport_targets)
    add_edges("/when-should-i-leave", ["/", "/airports", "/airport-security-wait-times", "/best-time-to-get-to-the-airport", "/methodology"] + airport_targets)
    add_edges("/about", ["/", "/airports", "/airport-security-wait-times", "/methodology", "/guide/tsa-wait-times", "/guide/tsa-precheck-clear"] + airport_targets)
    add_edges("/contact", ["/", "/airports", "/airport-security-wait-times", "/about", "/methodology", "/guide/tsa-wait-times", "/guide/tsa-precheck-clear"])
    add_edges("/privacy", ["/", "/airports", "/airport-security-wait-times", "/about", "/methodology", "/guide/tsa-wait-times", "/guide/tsa-precheck-clear", "/contact"])
    add_edges("/terms", ["/", "/airports", "/airport-security-wait-times", "/about", "/methodology", "/guide/tsa-wait-times", "/guide/tsa-precheck-clear", "/contact"])
    for code in airport_codes:
        slug = airport_seo_slug(code)
        related = [airport["href"] for airport in related_airports_for_code(code)]
        add_edges(slug, hub_targets + guide_targets + related)

    ranks = compute_pagerank(nodes, edges)
    in_degree = {node["id"]: 0 for node in nodes}
    out_degree = {node["id"]: 0 for node in nodes}
    for edge in edges:
        out_degree[edge["from"]] += 1
        in_degree[edge["to"]] += 1

    ranked_nodes = sorted(
        [
            {
                **node,
                "score": round(ranks.get(node["id"], 0.0), 6),
                "in_degree": in_degree[node["id"]],
                "out_degree": out_degree[node["id"]],
            }
            for node in nodes
        ],
        key=lambda item: (-item["score"], item["label"]),
    )

    node_index = {node["id"]: node for node in ranked_nodes}
    top_nodes = ranked_nodes[:10]
    max_score = top_nodes[0]["score"] if top_nodes else 0.0
    lowest_node = ranked_nodes[-1] if ranked_nodes else None
    min_score = lowest_node["score"] if lowest_node else 0.0
    modeled_airports = {node["label"] for node in nodes if node["kind"] == "airport"}
    missing_live_airports = sorted(set(LIVE_AIRPORTS.keys()) - modeled_airports)
    weak_pages = sorted(
        [node for node in ranked_nodes if node["kind"] in {"core", "guide", "airport"}],
        key=lambda item: (item["in_degree"], item["score"], item["label"]),
    )[:8]
    weak_airports = sorted(
        [node for node in ranked_nodes if node["kind"] == "airport"],
        key=lambda item: (item["in_degree"], item["score"], item["label"]),
    )[:8]

    return {
        "seo": build_page_seo(
            title="TSA Tracker Internal Link Graph | PageRank View",
            description="Interactive PageRank view of TSA Tracker's internal link graph, showing which pages carry the most internal weight.",
            canonical_path=canonical_path,
        ),
        "monetization": get_monetization_context(),
        "nodes_json": json.dumps(ranked_nodes),
        "edges_json": json.dumps(edges),
        "top_nodes": top_nodes,
        "node_index_json": json.dumps(node_index),
        "max_score": max_score,
        "min_score": min_score,
        "lowest_node": lowest_node,
        "graph_summary": {
            "node_count": len(ranked_nodes),
            "edge_count": len(edges),
            "live_airport_count": len(LIVE_AIRPORTS),
            "modeled_airport_count": len(modeled_airports),
            "missing_live_airports": missing_live_airports,
        },
        "weak_pages": weak_pages,
        "weak_airports": weak_airports,
    }


def clamp_wait_minutes(v: float) -> float:
    return max(0.0, min(float(v), 180.0))


def wait_description(minutes: float) -> str:
    m = int(round(minutes))
    if m <= 0:
        return "under 1 minute"
    return f"{m} minutes"


def wait_tier_class_for_minutes(minutes: float) -> str:
    m = float(minutes or 0)
    if m <= 15:
        return "low"
    if m <= 30:
        return "med"
    if m <= 45:
        return "high"
    return "crit"


def format_utc_timestamp(iso_value: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_value)
    except Exception:
        return iso_value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=APP_TZ)
    return dt.astimezone(APP_TZ).strftime("%b %d, %I:%M %p UTC").replace(" 0", " ")


def format_airport_timestamp(code: str, iso_value: str) -> str:
    if not iso_value:
        return ""
    try:
        dt = datetime.fromisoformat(iso_value)
    except Exception:
        return iso_value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=APP_TZ)
    try:
        local_dt = dt.astimezone(ZoneInfo(AIRPORT_TIME_ZONES.get(code, "UTC")))
    except Exception:
        local_dt = dt.astimezone(APP_TZ)
    return local_dt.strftime("%b %d, %I:%M %p %Z").replace(" 0", " ")


def estimated_wait_for_hour(hour: int, factor: float) -> float:
    if hour < 5:
        base = 8
    elif hour < 7:
        base = 18
    elif hour < 10:
        base = 32
    elif hour < 13:
        base = 20
    elif hour < 16:
        base = 16
    elif hour < 19:
        base = 26
    elif hour < 22:
        base = 17
    else:
        base = 10
    return clamp_wait_minutes(base * factor)


def normalize_hourly_forecast(code: str, current_standard: float) -> List[Dict]:
    factor = AIRPORT_FACTORS.get(code, 1.0)
    rows = []
    for hour in range(24):
        estimated = estimated_wait_for_hour(hour, factor)
        blended = clamp_wait_minutes(estimated * 0.75 + current_standard * 0.25)
        start = datetime(2000, 1, 1, hour, 0)
        end = start + timedelta(hours=1)
        label = f"{start.strftime('%-I %p').lower()} - {end.strftime('%-I %p').lower()}"
        rows.append({"timeslot": label, "waittime": round(blended, 1), "hour": hour})
    return rows


def fetch_mco_rows() -> List[Dict]:
    endpoint = _mco_cache["endpoint"]
    headers = {
        **UA,
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "api-key": _mco_cache["key"],
        "api-version": str(_mco_cache["version"]),
        "referer": "https://flymco.com/",
    }
    resp = requests.get(endpoint, headers=headers, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    rows = []
    stamp = utc_now().isoformat()
    for rec in payload.get("data", {}).get("wait_times", []):
        if not rec.get("isDisplayable", True):
            continue
        wait_seconds = rec.get("waitSeconds")
        if wait_seconds is None:
            continue
        wait_minutes = max(0.0, float(wait_seconds) / 60.0)
        name = str(rec.get("name", "Checkpoint")).strip() or "Checkpoint"
        lane = str(rec.get("lane", "")).strip()
        checkpoint = f"{name} ({lane})" if lane else name
        rows.append(
            {
                "airport_code": "MCO",
                "checkpoint": checkpoint,
                "wait_minutes": wait_minutes,
                "source": endpoint,
                "captured_at": stamp,
            }
        )
    return rows


def refresh_clt_api_config_if_needed(force: bool = False) -> None:
    now = utc_now()
    if not force and _clt_cache["key"] and _clt_cache["version"] and _clt_cache["fetched_at"]:
        age = now - _clt_cache["fetched_at"]
        if age < timedelta(hours=6):
            return

    page = requests.get("https://www.cltairport.com/airport-info/security/", headers=UA, timeout=20).text
    js_paths = re.findall(r'<script[^>]+src=["\']([^"\']*/_next/static/chunks/[^"\']+\.js)["\']', page, re.I)
    js_urls = []
    for p in js_paths:
        if p.startswith("http"):
            js_urls.append(p)
        else:
            js_urls.append("https://www.cltairport.com" + p)

    found_key = None
    found_version = None
    for js_url in js_urls:
        try:
            js = requests.get(js_url, headers=UA, timeout=20).text
        except Exception:
            continue
        if "api.cltairport.mobi" not in js and "Api-Key" not in js:
            continue
        key_match = re.search(r'Api-Key":"([a-f0-9]{32})"', js, re.I)
        version_match = re.search(r'Api-Version":"([0-9]+)"', js, re.I)
        if key_match:
            found_key = key_match.group(1)
        if version_match:
            found_version = version_match.group(1)
        if found_key and found_version:
            break

    _clt_cache["key"] = os.getenv("CLT_API_KEY", found_key or _clt_cache["key"])
    _clt_cache["version"] = os.getenv("CLT_API_VERSION", found_version or _clt_cache["version"] or "150")
    if not _clt_cache["key"]:
        raise RuntimeError("CLT API key not found")
    _clt_cache["fetched_at"] = now


def fetch_clt_rows() -> List[Dict]:
    refresh_clt_api_config_if_needed()
    endpoint = _clt_cache["endpoint"]
    headers = {
        **UA,
        "accept": "application/json, text/plain, */*",
        "api-key": _clt_cache["key"],
        "api-version": str(_clt_cache["version"]),
        "referer": "https://www.cltairport.com/",
    }
    resp = requests.get(endpoint, headers=headers, timeout=20)
    if resp.status_code in (400, 401, 403):
        refresh_clt_api_config_if_needed(force=True)
        headers["api-key"] = _clt_cache["key"]
        headers["api-version"] = str(_clt_cache["version"])
        resp = requests.get(endpoint, headers=headers, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    rows = []
    stamp = utc_now().isoformat()
    for rec in payload.get("data", {}).get("wait_times", []):
        if not rec.get("isDisplayable", True):
            continue
        wait_seconds = rec.get("waitSeconds")
        if wait_seconds is None:
            continue
        wait_minutes = max(0.0, float(wait_seconds) / 60.0)
        checkpoint_name = str(rec.get("name", "Checkpoint")).strip() or "Checkpoint"
        attributes = rec.get("attributes") or {}
        lane_type = "PRECHECK" if attributes.get("preCheck") else "STANDARD"
        lane_label = "PreCheck" if lane_type == "PRECHECK" else "Standard"
        checkpoint_name = f"{checkpoint_name} ({lane_label})"
        rows.append(
            {
                "airport_code": "CLT",
                "checkpoint": checkpoint_name,
                "wait_minutes": wait_minutes,
                "lane_type": lane_type,
                "source": endpoint,
                "captured_at": stamp,
            }
        )
    return rows


def normalize_lane_type(raw: str) -> str:
    """Normalize a raw boarding-type/lane string to a canonical lane_type key."""
    s = raw.strip().lower()
    if "clear" in s and ("pre" in s or "tsa" in s):
        return "CLEAR_PRECHECK"
    if "clear" in s:
        return "CLEAR"
    if "pre" in s or "tsa pre" in s or "precheck" in s:
        return "PRECHECK"
    return "STANDARD"


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            airport_code TEXT NOT NULL,
            checkpoint TEXT NOT NULL,
            wait_minutes REAL NOT NULL,
            source TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            lane_type TEXT NOT NULL DEFAULT 'STANDARD'
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            airport_code TEXT NOT NULL,
            level TEXT NOT NULL,
            current_wait REAL,
            session_id TEXT,
            reported_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS page_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            airport_code TEXT,
            user_agent TEXT,
            referrer TEXT,
            captured_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ad_clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            offer_id TEXT NOT NULL,
            airport_code TEXT,
            captured_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS social_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            airport_code TEXT,
            event_type TEXT NOT NULL,
            event_key TEXT NOT NULL,
            post_text TEXT NOT NULL,
            external_id TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            posted_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hourly_wait_aggregates (
            airport_code TEXT NOT NULL,
            local_date TEXT NOT NULL,
            local_hour INTEGER NOT NULL,
            wait_sum REAL NOT NULL DEFAULT 0,
            sample_count INTEGER NOT NULL DEFAULT 0,
            refreshed_at TEXT NOT NULL,
            PRIMARY KEY (airport_code, local_date, local_hour)
        )
        """
    )
    # Migrate existing DBs that don't yet have lane_type
    try:
        cur.execute("ALTER TABLE samples ADD COLUMN lane_type TEXT NOT NULL DEFAULT 'STANDARD'")
    except Exception:
        pass  # column already exists
    try:
        cur.execute("ALTER TABLE user_reports ADD COLUMN current_wait REAL")
    except Exception:
        pass  # column already exists
    try:
        cur.execute("ALTER TABLE user_reports ADD COLUMN session_id TEXT")
    except Exception:
        pass  # column already exists
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_samples_airport_time
        ON samples (airport_code, captured_at)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_reports_airport_time
        ON user_reports (airport_code, reported_at)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_reports_session_time
        ON user_reports (session_id, reported_at)
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_social_posts_platform_event
        ON social_posts (platform, event_key)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_hourly_wait_aggregates_airport_date
        ON hourly_wait_aggregates (airport_code, local_date)
        """
    )
    conn.commit()
    conn.close()


def hourly_aggregate_bucket(airport_code: str, wait_minutes: float, captured_at: str) -> Optional[Dict]:
    try:
        tz = ZoneInfo(AIRPORT_TIME_ZONES.get(airport_code, "UTC"))
        captured = datetime.fromisoformat(str(captured_at).replace("Z", "+00:00"))
        if captured.tzinfo is None:
            captured = captured.replace(tzinfo=timezone.utc)
        local_dt = captured.astimezone(tz)
        return {
            "airport_code": airport_code,
            "local_date": local_dt.date().isoformat(),
            "local_hour": local_dt.hour,
            "wait_sum": clamp_wait_minutes(float(wait_minutes)),
            "sample_count": 1,
        }
    except Exception:
        return None


def upsert_hourly_aggregate_buckets(conn: sqlite3.Connection, buckets: List[Dict]) -> None:
    if not buckets:
        return
    now_iso = utc_now().isoformat()
    conn.executemany(
        """
        INSERT INTO hourly_wait_aggregates (
            airport_code, local_date, local_hour, wait_sum, sample_count, refreshed_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(airport_code, local_date, local_hour) DO UPDATE SET
            wait_sum = hourly_wait_aggregates.wait_sum + excluded.wait_sum,
            sample_count = hourly_wait_aggregates.sample_count + excluded.sample_count,
            refreshed_at = excluded.refreshed_at
        """,
        [
            (
                bucket["airport_code"],
                bucket["local_date"],
                int(bucket["local_hour"]),
                float(bucket["wait_sum"]),
                int(bucket["sample_count"]),
                now_iso,
            )
            for bucket in buckets
        ],
    )


def update_hourly_aggregates_for_rows(rows: List[Dict]) -> None:
    buckets = []
    for row in rows:
        airport_code = str(row.get("airport_code", "")).upper()
        if airport_code not in LIVE_AIRPORTS:
            continue
        bucket = hourly_aggregate_bucket(
            airport_code,
            row.get("wait_minutes", 0),
            row.get("captured_at", ""),
        )
        if bucket:
            buckets.append(bucket)
    if not buckets:
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        upsert_hourly_aggregate_buckets(conn, buckets)
        cutoff = (utc_now() - timedelta(days=HOURLY_AGGREGATE_MAX_DAYS + 7)).date().isoformat()
        conn.execute("DELETE FROM hourly_wait_aggregates WHERE local_date < ?", (cutoff,))
        conn.commit()
    finally:
        conn.close()


def db_insert_rows(rows: List[Dict]) -> None:
    if not rows:
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executemany(
        """
        INSERT INTO samples (airport_code, checkpoint, wait_minutes, source, captured_at, lane_type)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                r["airport_code"],
                r["checkpoint"],
                float(r["wait_minutes"]),
                r["source"],
                r["captured_at"],
                r.get("lane_type", "STANDARD"),
            )
            for r in rows
        ],
    )
    conn.commit()
    conn.close()
    update_hourly_aggregates_for_rows(rows)

    # Also store in Supabase for historical analysis
    if SUPABASE_ENABLED:
        try:
            supabase_store_samples(rows)
        except Exception as e:
            logger.warning("Supabase store failed (non-blocking): %s", e)


def log_page_view(path: str, airport_code: str = None) -> None:
    """Logs a page view to the internal database for tracking accuracy, now with referrer tracking."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO page_views (path, airport_code, user_agent, referrer, captured_at) VALUES (?, ?, ?, ?, ?)",
            (
                path, 
                airport_code, 
                request.headers.get("User-Agent"), 
                request.headers.get("Referer", ""),
                utc_now().isoformat()
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Failed to log page view: %s", e)


def fetch_phl_rows() -> List[Dict]:
    url = "https://www.phl.org/phllivereach/metrics"
    resp = requests.get(url, headers=UA, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    zone_map = {
        "4126": ("D/E", "PRECHECK"),
        "3971": ("D/E", "STANDARD"),
        "4377": ("A-West", "STANDARD"),
        "4386": ("A-East", "PRECHECK"),
        "4368": ("A-East", "STANDARD"),
        "5047": ("B", "STANDARD"),
        "5052": ("C", "PRECHECK"),
        "5068": ("F", "STANDARD"),
    }
    rows = []
    stamp = utc_now().isoformat()
    for row in payload.get("content", {}).get("rows", []):
        zone_id = str(row[0])
        if zone_id not in zone_map:
            continue
        checkpoint, lane_type = zone_map[zone_id]
        wait_minutes = float(row[1])
        rows.append(
            {
                "airport_code": "PHL",
                "checkpoint": checkpoint,
                "checkpoint_id": zone_id,
                "lane_type": lane_type,
                "wait_minutes": wait_minutes,
                "source": url,
                "captured_at": stamp,
            }
        )
    return rows


def refresh_mia_api_key_if_needed(force: bool = False) -> None:
    now = utc_now()
    if not force and _mia_cache["key"] and _mia_cache["fetched_at"]:
        age = now - _mia_cache["fetched_at"]
        if age < timedelta(hours=1):
            return

    page = requests.get("https://www.miami-airport.com/tsa-waittimes.asp", headers=UA, timeout=20).text
    js_paths = re.findall(r'<script[^>]+src=["\']([^"\']*js/wait-times/main[^"\']+\.js)["\']', page, re.I)
    if not js_paths:
        raise RuntimeError("MIA main wait-times bundle not found")
    main_js_url = "https://www.miami-airport.com" + js_paths[0]
    js = requests.get(main_js_url, headers=UA, timeout=20).text
    endpoint_match = re.search(r"https://waittime\.api\.aero/waittime/v2/current/[A-Z]+", js)
    key_match = re.search(r'x-apikey\\?"\s*:\\?"([a-f0-9]{20,})', js, re.I)
    if not endpoint_match or not key_match:
        raise RuntimeError("MIA endpoint or x-apikey not found in JS bundle")
    _mia_cache["endpoint"] = endpoint_match.group(0)
    _mia_cache["key"] = key_match.group(1)
    _mia_cache["fetched_at"] = now


def fetch_mia_rows() -> List[Dict]:
    refresh_mia_api_key_if_needed()
    endpoint = _mia_cache["endpoint"]
    key = _mia_cache["key"]
    resp = requests.get(endpoint, headers={**UA, "x-apikey": key}, timeout=20)
    if resp.status_code == 403:
        refresh_mia_api_key_if_needed(force=True)
        resp = requests.get(_mia_cache["endpoint"], headers={**UA, "x-apikey": _mia_cache["key"]}, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    stamp = utc_now().isoformat()
    rows = []
    for rec in payload.get("current", []):
        qname = rec.get("queueName")
        status = str(rec.get("status", "")).strip().lower()
        # Keep only open lanes when status metadata is present.
        if status and status != "open":
            continue
        min_wait = rec.get("projectedMinWaitMinutes")
        max_wait = rec.get("projectedMaxWaitMinutes")
        wait_val = None
        if min_wait is not None and max_wait is not None:
            wait_val = (float(min_wait) + float(max_wait)) / 2.0
        elif min_wait is not None:
            wait_val = float(min_wait)
        elif rec.get("projectedWaitTime") is not None:
            wait_val = float(rec.get("projectedWaitTime"))
        if qname is None or wait_val is None:
            continue
        wait_val = max(0.0, float(wait_val))
        rows.append(
            {
                "airport_code": "MIA",
                "checkpoint": qname,
                "wait_minutes": wait_val,
                "source": endpoint,
                "captured_at": stamp,
            }
        )
    return rows

def ord_friendly_checkpoint(metric_name: str) -> str:
    s = metric_name.lower()
    mapping = [
        ("t2c5general", "Terminal 2 — Checkpoint 5 General"),
        ("t2c5precheck", "Terminal 2 — Checkpoint 5 TSA PreCheck"),
        ("t3c6", "Terminal 3 — Checkpoint 6"),
        ("t3c7general", "Terminal 3 — Checkpoint 7 General"),
        ("t3c7a", "Terminal 3 — Checkpoint 7A"),
        ("t3c8general", "Terminal 3 — Checkpoint 8 General"),
        ("t3c8precheck", "Terminal 3 — Checkpoint 8 TSA PreCheck"),
        ("t3c9", "Terminal 3 — Checkpoint 9"),
        ("t5c10", "Terminal 5 — Checkpoint 10"),
        ("security02floor", "Terminal 1 — Economy"),
        ("tsafloor", "Terminal 1 — TSA PreCheck"),
        ("pafloor", "Terminal 1 — Priority"),
    ]
    for key, label in mapping:
        if key in s:
            return label
    return metric_name




def fetch_ord_rows() -> List[Dict]:
    endpoint = "https://tsawaittimes.flychicago.com/tsawaittimes"
    resp = requests.get(endpoint, headers=UA, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    stamp = utc_now().isoformat()
    rows = []
    for rec in payload:
        name = rec.get("name", "")
        wait_seconds = rec.get("waitTimes")
        if wait_seconds is None:
            continue
        # Ignore sentinel invalid values.
        if float(wait_seconds) >= 400000:
            continue
        wait_minutes = max(0.0, float(wait_seconds) / 60.0)
        rows.append(
            {
                "airport_code": "ORD",
                "checkpoint": ord_friendly_checkpoint(name),
                "wait_minutes": wait_minutes,
                "source": endpoint,
                "captured_at": stamp,
            }
        )
    return rows


def _parse_jax_wait_minutes(bold_text: str) -> float:
    """Convert JAX HTML bold wait-time text to minutes."""
    t = bold_text.strip().lower()
    if "less than" in t:
        return 0.5
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    if m:
        return max(0.0, float(m.group(1)))
    return 0.0


def fetch_jax_rows() -> List[Dict]:
    url = "https://www.flyjacksonville.com/content.aspx?id=3583"
    resp = requests.get(url, headers=UA, timeout=20)
    resp.raise_for_status()
    html = resp.text

    # Each checkpoint block: <div class="label...">NAME</div> … <span class="bold ml-1">TIME</span>
    # Use a single regex over the wait-times section to find label→bold pairs.
    section_match = re.search(
        r'class="wait-times".*?</div>\s*</div>\s*</div>',
        html,
        re.S | re.I,
    )
    section = section_match.group(0) if section_match else html

    block_pattern = re.compile(
        r'<div\s+class="label[^"]*"[^>]*>\s*'
        r'([\w /-]+?)'                          # checkpoint label text (before any child tags)
        r'\s*(?:<[^>]+>\s*)*</div>'             # optional child tags (e.g. <img>)
        r'.*?'
        r'<span\s+class="bold[^"]*"[^>]*>(.*?)</span>',
        re.S | re.I,
    )

    rows = []
    stamp = utc_now().isoformat()
    for m in block_pattern.finditer(section):
        raw_label = re.sub(r"\s+", " ", m.group(1)).strip()
        raw_time = m.group(2).strip()
        if not raw_label or not raw_time:
            continue
        # Skip the rotating "Military/Premier/Special Needs" slot — it shares one lane
        # with Standard; label it as "Standard/Priority" to avoid duplicate counting.
        if raw_label.lower() in ("military in uniform", "premier", "special needs"):
            raw_label = "Priority Lane"
        wait_minutes = _parse_jax_wait_minutes(raw_time)
        lane_type = "PRECHECK" if re.search(r"\btsa pre\b", raw_label, re.I) else "STANDARD"
        rows.append(
            {
                "airport_code": "JAX",
                "checkpoint": raw_label,
                "wait_minutes": wait_minutes,
                "lane_type": lane_type,
                "source": url,
                "captured_at": stamp,
            }
        )
    if not rows:
        raise RuntimeError("JAX: no checkpoint rows parsed from page")
    return rows


_DFW_API = "https://api.dfwairport.mobi/wait-times/checkpoint/DFW"
_DFW_HEADERS = {
    "Api-Key": "87856E0636AA4BF282150FCBE1AD63DE",
    "Api-Version": "170",
    "Accept": "application/json",
}


def fetch_dfw_rows() -> List[Dict]:
    resp = requests.get(_DFW_API, headers={**UA, **_DFW_HEADERS}, timeout=20)
    resp.raise_for_status()
    body = resp.json()
    wait_times = body.get("data", {}).get("wait_times", [])
    if not wait_times:
        raise RuntimeError("DFW: empty wait_times in response")
    stamp = utc_now().isoformat()
    rows = []
    for wt in wait_times:
        if not wt.get("isDisplayable"):
            continue
        name = wt.get("name", "")
        lane = wt.get("lane", "")
        checkpoint = f"{name} ({lane})" if lane else name
        wait_secs = wt.get("waitSeconds")
        if wait_secs is None:
            continue
        wait_minutes = round(wait_secs / 60, 1)
        rows.append(
            {
                "airport_code": "DFW",
                "checkpoint": checkpoint,
                "lane_type": _arrival_normalized_lane_type(
                    {"checkpoint": checkpoint}
                ),
                "wait_minutes": wait_minutes,
                "source": _DFW_API,
                "captured_at": stamp,
            }
        )
    if not rows:
        raise RuntimeError("DFW: no displayable checkpoints parsed")
    return rows


def fetch_lax_rows() -> List[Dict]:
    """HTML table scrape from flylax.com/wait-times.
    Page is server-rendered Drupal — table columns: Terminal | Boarding Type | Wait Time.
    """
    resp = requests.get("https://www.flylax.com/wait-times", headers=UA, timeout=20)
    resp.raise_for_status()
    stamp = utc_now().isoformat()
    rows: List[Dict] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", resp.text, re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        cells = [c for c in cells if c]
        if len(cells) < 3:
            continue
        terminal, boarding_type, wait_str = cells[0], cells[1], cells[2].lower()
        # Skip header rows
        if terminal.lower() in ("terminal", "security wait times"):
            continue
        m = re.search(r"(\d+(?:\.\d+)?)", wait_str)
        if not m:
            continue
        wait_minutes = float(m.group(1))
        rows.append({
            "airport_code": "LAX",
            "checkpoint": terminal,
            "wait_minutes": wait_minutes,
            "lane_type": normalize_lane_type(boarding_type),
            "source": "https://www.flylax.com/wait-times",
            "captured_at": stamp,
        })
    if not rows:
        raise RuntimeError("LAX: no checkpoint rows parsed from HTML table")
    return rows


def parse_wait_range(raw: str) -> Optional[float]:
    text = str(raw or "").strip().lower()
    if not text:
        return None
    range_match = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", text)
    if range_match:
        return (float(range_match.group(1)) + float(range_match.group(2))) / 2.0
    lt_match = re.search(r"<\s*(\d+(?:\.\d+)?)", text)
    if lt_match:
        return max(0.0, float(lt_match.group(1)) - 0.5)
    num_match = re.search(r"(\d+(?:\.\d+)?)", text)
    if num_match:
        return float(num_match.group(1))
    return None


def fetch_dca_rows() -> List[Dict]:
    """Scrape DCA wait times from the public JSON endpoint."""
    url = "https://www.flyreagan.com/security-wait-times"
    resp = requests.get(url, headers=UA, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    data = payload.get("response", {}) if isinstance(payload, dict) else {}
    res = data.get("res", {}) if isinstance(data, dict) else {}
    if not isinstance(res, dict) or not res:
        raise RuntimeError("DCA: empty security wait response")

    stamp = utc_now().isoformat()
    rows: List[Dict] = []
    for rec in res.values():
        if not isinstance(rec, dict):
            continue
        location = str(rec.get("location", "Checkpoint")).strip() or "Checkpoint"
        gates = str(rec.get("gates", "")).strip()
        gates = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", gates))
        checkpoint = f"{location} {gates}".strip() if gates else location

        wait_minutes = parse_wait_range(rec.get("waittime"))
        if wait_minutes is None:
            continue
        rows.append(
            {
                "airport_code": "DCA",
                "checkpoint": checkpoint,
                "wait_minutes": wait_minutes,
                "lane_type": "STANDARD",
                "source": url,
                "captured_at": stamp,
            }
        )

        if not rec.get("pre_disabled") and rec.get("pre"):
            pre_minutes = parse_wait_range(rec.get("pre"))
            if pre_minutes is not None:
                rows.append(
                    {
                        "airport_code": "DCA",
                        "checkpoint": checkpoint,
                        "wait_minutes": pre_minutes,
                        "lane_type": "PRECHECK",
                        "source": url,
                        "captured_at": stamp,
                    }
                )

    if not rows:
        raise RuntimeError("DCA: no checkpoint rows parsed from JSON")
    return rows


_PANYNJ_GQL = "https://api.jfkairport.com/graphql"


def _fetch_panynj_rows(airport_code: str) -> List[Dict]:
    """Shared PANYNJ GraphQL fetcher for JFK, EWR, and LGA.

    PANYNJ does not expose explicit lane types. For terminals with exactly two
    rows, assume the shorter wait is TSA PreCheck and the longer wait is Regular.
    Any extra rows remain unlabeled alternates.
    """
    query = f'{{ securityWaitTimes(airportCode: "{airport_code}") {{ checkPoint waitTime terminal }} }}'
    resp = requests.post(
        _PANYNJ_GQL,
        json={"query": query},
        headers={**UA, "Content-Type": "application/json", "Accept": "application/json"},
        timeout=20,
    )
    if resp.status_code in (401, 403):
        logger.warning("collector_skipped airport=%s status=%s upstream_auth_failed", airport_code, resp.status_code)
        return []
    resp.raise_for_status()
    items = resp.json().get("data", {}).get("securityWaitTimes", [])
    if not items:
        raise RuntimeError(f"{airport_code}: empty securityWaitTimes in response")
    stamp = utc_now().isoformat()
    grouped: Dict[str, List[Dict]] = {}
    terminal_labels: Dict[str, str] = {}
    singles: List[Dict] = []
    for item in items:
        terminal = item.get("terminal", "")
        checkpoint = item.get("checkPoint", "Checkpoint")
        wait_minutes = float(item.get("waitTime") or 0)
        label = f"Terminal {terminal}" if terminal else checkpoint
        if terminal:
            grouped.setdefault(terminal, []).append({"wait_minutes": wait_minutes, "source_label": label})
            terminal_labels[terminal] = label
        else:
            singles.append({"label": label, "wait_minutes": wait_minutes})
    rows: List[Dict] = []
    for item in singles:
        rows.append({
            "airport_code": airport_code,
            "checkpoint": item["label"],
            "wait_minutes": item["wait_minutes"],
            "lane_type": "STANDARD",
            "source": _PANYNJ_GQL,
            "captured_at": stamp,
        })
    for terminal, terminal_rows in grouped.items():
        label = terminal_labels[terminal]
        if len(terminal_rows) == 1:
            rows.append({
                "airport_code": airport_code,
                "checkpoint": label,
                "wait_minutes": terminal_rows[0]["wait_minutes"],
                "lane_type": "STANDARD",
                "source": _PANYNJ_GQL,
                "captured_at": stamp,
            })
            continue
        if len(terminal_rows) == 2:
            ordered = sorted(terminal_rows, key=lambda row: row["wait_minutes"])
            rows.append({
                "airport_code": airport_code,
                "checkpoint": label,
                "wait_minutes": ordered[1]["wait_minutes"],
                "lane_type": "STANDARD",
                "source": _PANYNJ_GQL,
                "captured_at": stamp,
            })
            rows.append({
                "airport_code": airport_code,
                "checkpoint": label,
                "wait_minutes": ordered[0]["wait_minutes"],
                "lane_type": "PRECHECK",
                "source": _PANYNJ_GQL,
                "captured_at": stamp,
            })
            continue
        for index, terminal_row in enumerate(terminal_rows):
            checkpoint_label = label if index == 0 else f"{label} Alternate"
            rows.append({
                "airport_code": airport_code,
                "checkpoint": checkpoint_label,
                "wait_minutes": terminal_row["wait_minutes"],
                "lane_type": "STANDARD",
                "source": _PANYNJ_GQL,
                "captured_at": stamp,
            })
    return rows


def fetch_jfk_rows() -> List[Dict]:
    """PANYNJ GraphQL — JFK terminals 1, 4, 5, 7, 8. No auth required."""
    return _fetch_panynj_rows("JFK")


def fetch_ewr_rows() -> List[Dict]:
    """Newark Airport API — displayed wait times by terminal and gate group."""
    url = "https://avi-prod-mpp-webapp-api.azurewebsites.net/api/v1/SecurityWaitTimesPoints/EWR"
    resp = requests.get(
        url,
        headers={
            **UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.newarkairport.com",
            "Referer": "https://www.newarkairport.com/security-wait-times",
            "X-Requested-With": "XMLHttpRequest",
            "api-key": "A6CE0EE926BC408B1E9D6E9EC14A5D64",
        },
        timeout=20,
    )
    if resp.status_code in (401, 403):
        logger.warning("collector_skipped airport=EWR status=%s upstream_auth_failed", resp.status_code)
        return []
    resp.raise_for_status()
    items = resp.json()
    if not items:
        raise RuntimeError("EWR: empty SecurityWaitTimesPoints response")
    stamp = utc_now().isoformat()
    rows: List[Dict] = []
    for item in items:
        terminal = str(item.get("terminal", "")).strip()
        if not terminal:
            continue
        title = item.get("title") or f"Terminal {terminal}"
        gate = str(item.get("gate", "")).strip()
        checkpoint = title if not gate or gate.lower() == "all gates" else f"{title} ({gate})"
        queue_type = str(item.get("queueType", "")).lower()
        if queue_type in ("reg", "regular", "general"):
            lane_type = "STANDARD"
        elif queue_type in ("tsapre", "pre", "precheck", "tsa pre"):
            lane_type = "PRECHECK"
        else:
            lane_type = "STANDARD"
        rows.append({
            "airport_code": "EWR",
            "checkpoint": checkpoint,
            "wait_minutes": float(item.get("timeInMinutes") or 0),
            "lane_type": lane_type,
            "source": url,
            "captured_at": stamp,
        })
    return rows


def fetch_lga_rows() -> List[Dict]:
    """LaGuardia Airport API — displayed wait times by terminal and queue type."""
    url = "https://avi-prod-mpp-webapp-api.azurewebsites.net/api/v1/SecurityWaitTimesPoints/LGA"
    resp = requests.get(
        url,
        headers={
            **UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.laguardiaairport.com",
            "Referer": "https://www.laguardiaairport.com/security-wait-times",
            "X-Requested-With": "XMLHttpRequest",
            "api-key": "A6CE0EE926BC408B1E9D6E9EC14A5D64",
        },
        timeout=20,
    )
    if resp.status_code in (401, 403):
        logger.warning("collector_skipped airport=LGA status=%s upstream_auth_failed", resp.status_code)
        return []
    resp.raise_for_status()
    items = resp.json()
    if not items:
        raise RuntimeError("LGA: empty SecurityWaitTimesPoints response")
    stamp = utc_now().isoformat()
    rows: List[Dict] = []
    for item in items:
        terminal = str(item.get("terminal", "")).strip()
        if not terminal:
            continue
        title = item.get("title") or f"Terminal {terminal}"
        queue_type = str(item.get("queueType", "")).lower()
        if queue_type in ("reg", "regular", "general"):
            lane_type = "STANDARD"
        elif queue_type in ("tsapre", "pre", "precheck", "tsa pre"):
            lane_type = "PRECHECK"
        else:
            lane_type = "STANDARD"
        rows.append({
            "airport_code": "LGA",
            "checkpoint": title,
            "wait_minutes": float(item.get("timeInMinutes") or 0),
            "lane_type": lane_type,
            "source": url,
            "captured_at": stamp,
        })
    return rows


def fetch_bos_rows() -> List[Dict]:
    """Massport Logan widget API via Zensors embeddable wait-time endpoints."""
    base = "https://embed.zensors.live/api/embeddable-widget/trpc"
    slug = "tSTQVPRW1"
    domain_slug = "BOS"
    token = "9uBjlxUu2dTQydGHYGtoDYxH5TE0vHOl"
    journey_source = f"{base}/waitTimeExplorer.update"

    init_input = {
        "0": {
            "slug": slug,
            "domainSlug": domain_slug,
            "token": token,
        }
    }
    init_resp = requests.get(
        f"{base}/waitTimeExplorer.init",
        params={"batch": "1", "input": json.dumps(init_input, separators=(",", ":"))},
        headers={**UA, "Accept": "application/json, text/plain, */*"},
        timeout=20,
    )
    init_resp.raise_for_status()
    init_payload = init_resp.json()
    if not init_payload or "result" not in init_payload[0]:
        raise RuntimeError("BOS: invalid init payload")

    journeys = init_payload[0]["result"]["data"].get("journeys", {})
    if not journeys:
        raise RuntimeError("BOS: no journeys in init payload")

    rows: List[Dict] = []
    for journey_id, meta in journeys.items():
        update_input = {
            "0": {
                "journey": journey_id,
                "slug": slug,
                "domainSlug": domain_slug,
                "token": token,
            }
        }
        update_resp = requests.get(
            f"{base}/waitTimeExplorer.update",
            params={"batch": "1", "input": json.dumps(update_input, separators=(",", ":"))},
            headers={**UA, "Accept": "application/json, text/plain, */*"},
            timeout=20,
        )
        update_resp.raise_for_status()
        update_payload = update_resp.json()
        if not update_payload or "result" not in update_payload[0]:
            continue

        checkpoint = str(meta.get("name", "")).strip()
        if not checkpoint:
            continue
        paths = update_payload[0]["result"]["data"].get("paths", {})
        for path_key, path_meta in paths.items():
            if not path_meta.get("open"):
                continue
            wait_meta = path_meta.get("waitTime") or {}
            timestamp_ms = wait_meta.get("timestamp")
            captured_at = (
                datetime.fromtimestamp(timestamp_ms / 1000, APP_TZ).isoformat()
                if timestamp_ms
                else utc_now().isoformat()
            )
            lane_type = "PRECHECK" if path_key == "precheck" else "STANDARD"
            rows.append({
                "airport_code": "BOS",
                "checkpoint": checkpoint,
                "wait_minutes": float(wait_meta.get("value") or 0),
                "lane_type": lane_type,
                "source": journey_source,
                "captured_at": captured_at,
            })

    if not rows:
        raise RuntimeError("BOS: no open checkpoint rows in response")
    return rows


def fetch_las_rows() -> List[Dict]:
    """Harry Reid's live wait-time widget via Zensors embeddable wait-time endpoints."""
    base = "https://embed.zensors.live/api/embeddable-widget/trpc"
    slug = "t1LQGTAPA"
    domain_slug = "LAS"
    token = "3Ll9yq2riLZctX1CZ94FRgLcScJimgXx"
    wait_source = f"{base}/waitTimeExplorer.update"

    init_input = {
        "0": {
            "slug": slug,
            "domainSlug": domain_slug,
            "token": token,
        }
    }
    init_resp = requests.get(
        f"{base}/waitTimeExplorer.init",
        params={"batch": "1", "input": json.dumps(init_input, separators=(",", ":"))},
        headers={**UA, "Accept": "application/json, text/plain, */*"},
        timeout=20,
    )
    init_resp.raise_for_status()
    init_payload = init_resp.json()
    if not init_payload or "result" not in init_payload[0]:
        raise RuntimeError("LAS: invalid init payload")

    journeys = init_payload[0]["result"]["data"].get("journeys", {})
    if not journeys:
        raise RuntimeError("LAS: no journeys in init payload")

    rows: List[Dict] = []
    for journey_id, meta in journeys.items():
        update_input = {
            "0": {
                "journey": journey_id,
                "slug": slug,
                "domainSlug": domain_slug,
                "token": token,
            }
        }
        update_resp = requests.get(
            f"{base}/waitTimeExplorer.update",
            params={"batch": "1", "input": json.dumps(update_input, separators=(",", ":"))},
            headers={**UA, "Accept": "application/json, text/plain, */*"},
            timeout=20,
        )
        update_resp.raise_for_status()
        update_payload = update_resp.json()
        if not update_payload or "result" not in update_payload[0]:
            continue

        checkpoint = str(meta.get("name", "")).strip()
        if not checkpoint:
            continue
        paths = update_payload[0]["result"]["data"].get("paths", {})
        for path_key, path_meta in paths.items():
            if not path_meta.get("open"):
                continue
            wait_meta = path_meta.get("waitTime") or {}
            wait_minutes = _arrival_wait_minutes(wait_meta.get("value"))
            if wait_minutes is None:
                continue
            timestamp_ms = wait_meta.get("timestamp")
            captured_at = (
                datetime.fromtimestamp(timestamp_ms / 1000, APP_TZ).isoformat()
                if timestamp_ms
                else utc_now().isoformat()
            )
            lane_type = "PRECHECK" if path_key == "precheck" else "STANDARD"
            rows.append({
                "airport_code": "LAS",
                "checkpoint": checkpoint,
                "wait_minutes": wait_minutes,
                "lane_type": lane_type,
                "source": wait_source,
                "captured_at": captured_at,
            })

    if not rows:
        raise RuntimeError("LAS: no open checkpoint rows in response")
    return rows


_SEA_API = "https://www.portseattle.org/api/cwt/wait-times"

_SEA_LANE_MAP = {
    "Pre":        "PRECHECK",
    "Clear":      "CLEAR",
    "General":    "STANDARD",
    "Premium":    "STANDARD",   # premium is still standard screening
    "Spot Saver": "STANDARD",
    "Visitor Pass": "STANDARD",
}


def fetch_sea_rows() -> List[Dict]:
    """Port of Seattle public JSON API — 6 checkpoints, per-checkpoint wait + lane availability.

    Endpoint: GET https://www.portseattle.org/api/cwt/wait-times
    No auth required. Refreshes every 5 minutes per their own widget.
    Response: list of checkpoints with IsOpen, WaitTimeMinutes, Options[{Name, Availability}].

    Strategy: emit one row per available lane type per checkpoint so lane badges work.
    If a checkpoint has no active lane breakdown, emit a single STANDARD row.
    """
    resp = requests.get(_SEA_API, headers=UA, timeout=20)
    resp.raise_for_status()
    checkpoints = resp.json()
    if not checkpoints:
        raise RuntimeError("SEA: empty response from portseattle.org API")
    stamp = utc_now().isoformat()
    rows: List[Dict] = []
    for cp in checkpoints:
        if not cp.get("IsOpen") or not cp.get("IsDataAvailable"):
            continue
        name = f"Checkpoint {cp.get('Name', '?')}"
        wait_minutes = float(cp.get("WaitTimeMinutes") or 0)
        # Build per-lane rows from Options
        available_lanes = [
            opt["Name"] for opt in cp.get("Options", [])
            if opt.get("Availability") in ("Available", "Only")
        ]
        # Deduplicate canonical lane types
        seen_lanes: set = set()
        emitted = False
        for lane_name in available_lanes:
            lane_type = _SEA_LANE_MAP.get(lane_name, "STANDARD")
            if lane_type in seen_lanes:
                continue
            seen_lanes.add(lane_type)
            rows.append({
                "airport_code": "SEA",
                "checkpoint": name,
                "wait_minutes": wait_minutes,
                "lane_type": lane_type,
                "source": _SEA_API,
                "captured_at": stamp,
            })
            emitted = True
        if not emitted:
            rows.append({
                "airport_code": "SEA",
                "checkpoint": name,
                "wait_minutes": wait_minutes,
                "lane_type": "STANDARD",
                "source": _SEA_API,
                "captured_at": stamp,
            })
    if not rows:
        raise RuntimeError("SEA: no open checkpoints in response")
    return rows


def fetch_sfo_rows() -> List[Dict]:
    """SFO server-rendered wait-time table scrape from flysfo.com."""
    url = "https://www.flysfo.com/passengers/flight-info/security-wait-times"
    resp = requests.get(url, headers=UA, timeout=20)
    resp.raise_for_status()
    html = resp.text
    table_match = re.search(
        r'<table[^>]*class="[^"]*flysfo-checkpoints-table[^"]*"[^>]*>(.*?)</table>',
        html,
        re.S | re.I,
    )
    if not table_match:
        raise RuntimeError("SFO: checkpoint table not found")
    stamp = utc_now().isoformat()
    rows: List[Dict] = []
    checkpoint_terminal = {
        "Checkpoint A": "International Terminal A",
        "Checkpoint B": "Harvey Milk Terminal 1",
        "Checkpoint B - Mezzanine Level": "Harvey Milk Terminal 1",
        "Checkpoint D": "Terminal 2",
        "Checkpoint F": "Terminal 3",
        "Checkpoint G": "International Terminal G",
    }
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), re.S | re.I):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S | re.I)
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        if len(cells) < 3 or cells[0].lower() == "checkpoint":
            continue
        checkpoint, general_wait, precheck_wait = cells[:3]
        terminal = checkpoint_terminal.get(checkpoint, "")
        display_checkpoint = f"{checkpoint} · {terminal}" if terminal else checkpoint
        for lane_type, raw_wait in (("STANDARD", general_wait), ("PRECHECK", precheck_wait)):
            raw_wait_lower = raw_wait.lower()
            if not raw_wait_lower or raw_wait_lower in ("not available", "n/a", "no data"):
                continue
            match = re.search(r"(\d+(?:\.\d+)?)", raw_wait_lower)
            if not match:
                continue
            rows.append({
                "airport_code": "SFO",
                "checkpoint": display_checkpoint,
                "wait_minutes": float(match.group(1)),
                "lane_type": lane_type,
                "source": url,
                "captured_at": stamp,
            })
    if not rows:
        raise RuntimeError("SFO: no checkpoint rows parsed from HTML table")
    return rows


def fetch_den_rows() -> List[Dict]:
    """DFW-style API for Denver International Airport.
    Endpoint: https://api.denverairport.com/wait-times/checkpoint/DEN
    Key: 87856E0636AA4BF282150FCBE1AD63DE (Shared with DFW)
    """
    url = "https://api.denverairport.com/wait-times/checkpoint/DEN"
    resp = requests.get(url, headers={**UA, "Api-Key": "87856E0636AA4BF282150FCBE1AD63DE", "Api-Version": "170"}, timeout=20)
    resp.raise_for_status()
    try:
        body = resp.json()
    except requests.exceptions.JSONDecodeError:
        logger.warning("DEN: non-JSON response from upstream. Skipping this cycle.")
        return []
    items = body.get("data", {}).get("wait_times", [])
    if not items:
        # Fallback: check if the data key itself is a list
        items = body.get("data", []) if isinstance(body.get("data"), list) else []
    
    if not items:
        logger.warning("DEN: empty wait_times in response. Skipping this cycle.")
        return []
        
    stamp = utc_now().isoformat()
    rows = []
    for it in items:
        if not it.get("isDisplayable", True): continue
        name = it.get("name", "Checkpoint")
        lane = it.get("lane", "")
        cp = f"{name} ({lane})" if lane else name
        wait_secs = it.get("waitSeconds", 0)
        rows.append({
            "airport_code": "DEN",
            "checkpoint": cp,
            "wait_minutes": float(wait_secs) / 60.0,
            "lane_type": normalize_lane_type(lane or name),
            "source": url,
            "captured_at": stamp,
        })
    return rows


def fetch_atl_rows() -> List[Dict]:
    """Scrape ATL wait times from the official ATL Next page.

    The public `atl.com/times/` page is Cloudflare-protected, but the ATL Next
    security page renders the same live values in HTML blocks that are easier to
    parse directly.
    """
    url = "https://dev.atl.com/atlsync/security-wait-times/"
    resp = requests.get(url, headers=UA, timeout=20)
    resp.raise_for_status()
    html = resp.text
    stamp = utc_now().isoformat()
    rows: List[Dict] = []

    checkpoint_labels = {
        "MAIN": "Main Checkpoint",
        "NORTH": "North Checkpoint",
        "LOWER NORTH": "Lower North Checkpoint",
        "SOUTH": "South Checkpoint",
        "INTERNATIONAL MAIN": "International Main Checkpoint",
    }

    for label, checkpoint in checkpoint_labels.items():
        match = re.search(
            rf'<h2[^>]*>\s*{re.escape(label)}\s*</h2>.*?'
            rf'<text[^>]*>(\d+(?:\.\d+)?)\s*Min</text>.*?'
            rf'<div class="gauge-text"[^>]*>.*?'
            rf'Last updated\s+([^<]+)</p>',
            html,
            re.S | re.I,
        )
        if not match:
            continue
        rows.append(
            {
                "airport_code": "ATL",
                "checkpoint": checkpoint,
                "wait_minutes": float(match.group(1)),
                "lane_type": "STANDARD",
                "source": url,
                "captured_at": stamp,
                "last_updated": match.group(2).strip(),
            }
        )

    if not rows:
        raise RuntimeError("ATL: no checkpoint rows parsed from official ATL page")
    return rows



def collect_once() -> Dict:
    result = {"ok": [], "errors": []}
    collectors = [
        ("PHL", fetch_phl_rows),
        ("BOS", fetch_bos_rows),
        ("MIA", fetch_mia_rows),
        ("ORD", fetch_ord_rows),
        ("CLT", fetch_clt_rows),
        ("MCO", fetch_mco_rows),
        ("JAX", fetch_jax_rows),
        ("DFW", fetch_dfw_rows),
        ("LAX", fetch_lax_rows),
        ("JFK", fetch_jfk_rows),
        ("EWR", fetch_ewr_rows),
        ("LGA", fetch_lga_rows),
        ("LAS", fetch_las_rows),
        ("SEA", fetch_sea_rows),
        ("SFO", fetch_sfo_rows),
        ("DCA", fetch_dca_rows),
        ("DEN", fetch_den_rows),
        ("ATL", fetch_atl_rows),
    ]

    all_rows = []
    for code, fn in collectors:
        try:
            rows = fn()
            all_rows.extend(rows)
            result["ok"].append({"airport": code, "rows": len(rows)})
            logger.info("collector_success airport=%s rows=%s", code, len(rows))
        except Exception as e:
            result["errors"].append({"airport": code, "error": str(e)})
            logger.exception("collector_failure airport=%s", code)
    db_insert_rows(all_rows)
    maybe_post_x_alerts(all_rows)
    return result


def latest_snapshot() -> Dict:
    cutoff = (utc_now() - timedelta(minutes=15)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT airport_code, checkpoint, wait_minutes, source, captured_at,
               COALESCE(lane_type, 'STANDARD') AS lane_type
        FROM samples
        WHERE captured_at >= ?
        ORDER BY captured_at DESC
        """,
        (cutoff,),
    )
    rows = cur.fetchall()
    conn.close()
    out: Dict[str, List[Dict]] = {}
    seen = set()
    for airport_code, checkpoint, wait_minutes, source, captured_at, lane_type in rows:
        if airport_code == "ORD":
            checkpoint = ord_friendly_checkpoint(checkpoint)
        key = (airport_code, checkpoint, lane_type)
        if key in seen:
            continue
        seen.add(key)
        out.setdefault(airport_code, []).append(
            {
                "checkpoint": checkpoint,
                "wait_minutes": wait_minutes,
                "lane_type": lane_type,
                "captured_at": captured_at,
            }
        )
    return out


def latest_for_code(airport_code: str) -> List[Dict]:
    return latest_snapshot().get(airport_code, [])


def normalized_current_wait_for_code(code: str) -> Dict:
    rows = latest_for_code(code)
    if rows:
        active = [r for r in rows if float(r.get("wait_minutes", 0)) > 0]
        sample = active if active else rows
        values = [clamp_wait_minutes(float(r.get("wait_minutes", 0))) for r in sample]
        standard = round(sum(values) / len(values), 1) if values else 0.0
        has_pre = any(str(r.get("lane_type", "")).upper() == "PRECHECK" for r in rows)
        latest_ts = max(rows, key=lambda r: r.get("captured_at", ""))["captured_at"]
        return {
            "available": True,
            "sourceType": "live_direct",
            "sourceReason": "fresh_live_data",
            "currentWait": {
                "standard": standard,
                "standardDescription": wait_description(standard),
                "userReported": None,
                "precheck": has_pre,
                "timestamp": latest_ts,
            },
            "hourlyForecast": normalize_hourly_forecast(code, standard),
        }

    now = utc_now()
    estimated = round(estimated_wait_for_hour(now.hour, AIRPORT_FACTORS.get(code, 1.0)), 1)
    if code in LIVE_AIRPORTS:
        source_reason = "live_stale_or_unavailable"
    else:
        source_reason = "airport_not_live_integrated"
    return {
        "available": True,
        "sourceType": "estimated_fallback",
        "sourceReason": source_reason,
        "currentWait": {
            "standard": estimated,
            "standardDescription": wait_description(estimated),
            "userReported": None,
            "precheck": False,
            "timestamp": now.isoformat(),
        },
        "hourlyForecast": normalize_hourly_forecast(code, estimated),
    }


def history_for_airport(airport_code: str, hours: int = 12) -> List[Dict]:
    supabase_rows = supabase_history_rows(airport_code, hours=hours)
    if supabase_rows:
        return [
            {
                "airport_code": r.get("airport_code", airport_code),
                "checkpoint": r.get("checkpoint", ""),
                "wait_minutes": r.get("wait_minutes", 0),
                "lane_type": _lane_type_key(r.get("lane_type")),
                "captured_at": r.get("captured_at", ""),
            }
            for r in supabase_rows
        ]

    cutoff = (utc_now() - timedelta(hours=hours)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT airport_code, checkpoint, wait_minutes,
               COALESCE(lane_type, 'STANDARD') AS lane_type,
               captured_at
        FROM samples
        WHERE airport_code = ? AND captured_at >= ?
        ORDER BY captured_at ASC
        """,
        (airport_code, cutoff),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "airport_code": r[0],
            "checkpoint": r[1],
            "wait_minutes": r[2],
            "lane_type": _lane_type_key(r[3]),
            "captured_at": r[4],
        }
        for r in rows
    ]


def read_hourly_aggregate_rows(airport_code: str, days: int = 30) -> List[Dict]:
    bounded_days = max(1, min(days, HOURLY_AGGREGATE_MAX_DAYS))
    tz = ZoneInfo(AIRPORT_TIME_ZONES.get(airport_code, "UTC"))
    cutoff_date = (utc_now().astimezone(tz) - timedelta(days=bounded_days)).date().isoformat()
    buckets = {hour: {"sum": 0.0, "count": 0} for hour in range(24)}
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT local_hour, SUM(wait_sum), SUM(sample_count)
        FROM hourly_wait_aggregates
        WHERE airport_code = ? AND local_date >= ?
        GROUP BY local_hour
        """,
        (airport_code, cutoff_date),
    )
    rows = cur.fetchall()
    conn.close()
    for local_hour, wait_sum, sample_count in rows:
        try:
            hour = int(local_hour)
            if hour not in buckets:
                continue
            buckets[hour]["sum"] = float(wait_sum or 0)
            buckets[hour]["count"] = int(sample_count or 0)
        except Exception:
            continue

    return [
        {
            "hour": hour,
            "label": f"{hour:02d}:00",
            "avg_wait": round(bucket["sum"] / bucket["count"], 1) if bucket["count"] else None,
            "samples": bucket["count"],
        }
        for hour, bucket in buckets.items()
    ]


def refresh_hourly_aggregates_from_local_samples(airport_code: str, days: int = 30) -> None:
    bounded_days = max(1, min(days, HOURLY_AGGREGATE_MAX_DAYS))
    tz = ZoneInfo(AIRPORT_TIME_ZONES.get(airport_code, "UTC"))
    cutoff_dt = utc_now() - timedelta(days=bounded_days + 2)
    cutoff_date = (utc_now().astimezone(tz) - timedelta(days=bounded_days)).date().isoformat()
    aggregate: Dict[tuple, Dict] = {}

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT wait_minutes, captured_at
        FROM samples
        WHERE airport_code = ? AND captured_at >= ?
        ORDER BY captured_at ASC
        """,
        (airport_code, cutoff_dt.isoformat()),
    )
    for wait_minutes, captured_at in cur.fetchall():
        bucket = hourly_aggregate_bucket(airport_code, wait_minutes, captured_at)
        if not bucket or bucket["local_date"] < cutoff_date:
            continue
        key = (bucket["airport_code"], bucket["local_date"], bucket["local_hour"])
        current = aggregate.setdefault(
            key,
            {
                "airport_code": bucket["airport_code"],
                "local_date": bucket["local_date"],
                "local_hour": bucket["local_hour"],
                "wait_sum": 0.0,
                "sample_count": 0,
            },
        )
        current["wait_sum"] += bucket["wait_sum"]
        current["sample_count"] += 1

    conn.execute(
        "DELETE FROM hourly_wait_aggregates WHERE airport_code = ? AND local_date >= ?",
        (airport_code, cutoff_date),
    )
    if aggregate:
        now_iso = utc_now().isoformat()
        conn.executemany(
            """
            INSERT INTO hourly_wait_aggregates (
                airport_code, local_date, local_hour, wait_sum, sample_count, refreshed_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    bucket["airport_code"],
                    bucket["local_date"],
                    int(bucket["local_hour"]),
                    float(bucket["wait_sum"]),
                    int(bucket["sample_count"]),
                    now_iso,
                )
                for bucket in aggregate.values()
            ],
        )
    conn.commit()
    conn.close()


def aggregate_rows_have_samples(rows: List[Dict]) -> bool:
    return any(int(row.get("samples") or 0) > 0 for row in rows)


def historical_24h_average_for_airport(airport_code: str, days: int = 30, sample_limit: int = 100000) -> List[Dict]:
    aggregate_rows = read_hourly_aggregate_rows(airport_code, days=days)
    if aggregate_rows_have_samples(aggregate_rows):
        return aggregate_rows

    refresh_hourly_aggregates_from_local_samples(airport_code, days=days)
    aggregate_rows = read_hourly_aggregate_rows(airport_code, days=days)
    if aggregate_rows_have_samples(aggregate_rows):
        return aggregate_rows

    time_zone_name = AIRPORT_TIME_ZONES.get(airport_code, "UTC")
    tz = ZoneInfo(time_zone_name)
    cutoff = (utc_now() - timedelta(days=max(1, min(days, 90)))).isoformat()
    buckets = {hour: {"sum": 0.0, "count": 0} for hour in range(24)}
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT wait_minutes, captured_at
        FROM samples
        WHERE airport_code = ? AND captured_at >= ?
        ORDER BY captured_at ASC
        LIMIT ?
        """,
        (airport_code, cutoff, max(1000, min(sample_limit, 100000))),
    )
    rows = cur.fetchall()
    conn.close()

    for wait_minutes, captured_at in rows:
        try:
            wait = clamp_wait_minutes(float(wait_minutes))
            captured = datetime.fromisoformat(str(captured_at))
            if captured.tzinfo is None:
                captured = captured.replace(tzinfo=timezone.utc)
            local_hour = captured.astimezone(tz).hour
        except Exception:
            continue
        buckets[local_hour]["sum"] += wait
        buckets[local_hour]["count"] += 1

    return [
        {
            "hour": hour,
            "label": f"{hour:02d}:00",
            "avg_wait": round(bucket["sum"] / bucket["count"], 1) if bucket["count"] else None,
            "samples": bucket["count"],
        }
        for hour, bucket in buckets.items()
    ]


def checkpoint_24h_average_for_airport(airport_code: str, days: int = 30, sample_limit: int = 100000) -> List[Dict]:
    bounded_days = max(1, min(days, 90))
    time_zone_name = AIRPORT_TIME_ZONES.get(airport_code, "UTC")
    tz = ZoneInfo(time_zone_name)
    raw_rows = None
    aggregate_groups = None

    if SUPABASE_ENABLED:
        aggregate_groups = supabase_checkpoint_24h_average(
            airport_code,
            days=bounded_days,
            time_zone_name=time_zone_name,
            limit=sample_limit,
        )
        if not aggregate_groups:
            raw_rows = supabase_history_rows(airport_code, hours=bounded_days * 24, limit=sample_limit)

    if aggregate_groups:
        rows = []
    elif raw_rows:
        rows = [
            (
                str(row.get("checkpoint", "")).strip(),
                row.get("wait_minutes", 0),
                row.get("captured_at", ""),
            )
            for row in raw_rows
        ]
    else:
        cutoff = (utc_now() - timedelta(days=bounded_days)).isoformat()
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT checkpoint, wait_minutes, captured_at
            FROM samples
            WHERE airport_code = ? AND captured_at >= ?
            ORDER BY captured_at ASC
            LIMIT ?
            """,
            (airport_code, cutoff, max(1000, min(sample_limit, 100000))),
        )
        rows = cur.fetchall()
        conn.close()

    groups: Dict[str, Dict] = {}
    if aggregate_groups:
        for aggregate_group in aggregate_groups:
            checkpoint = str(aggregate_group.get("checkpoint") or "").strip()
            if not checkpoint:
                continue
            if airport_code == "ORD":
                checkpoint = ord_friendly_checkpoint(checkpoint)
            group = groups.setdefault(
                checkpoint,
                {
                    "checkpoint": checkpoint,
                    "buckets": {hour: {"sum": 0.0, "count": 0} for hour in range(24)},
                },
            )
            for row in aggregate_group.get("rows") or []:
                try:
                    hour = int(row.get("hour"))
                    samples = int(row.get("samples") or 0)
                    avg_wait = row.get("avg_wait")
                    if hour not in group["buckets"] or samples <= 0 or avg_wait is None:
                        continue
                    group["buckets"][hour]["sum"] += float(avg_wait) * samples
                    group["buckets"][hour]["count"] += samples
                except Exception:
                    continue
    else:
        for checkpoint, wait_minutes, captured_at in rows:
            checkpoint = str(checkpoint or "").strip()
            if not checkpoint:
                continue
            if airport_code == "ORD":
                checkpoint = ord_friendly_checkpoint(checkpoint)
            try:
                wait = clamp_wait_minutes(float(wait_minutes))
                if wait <= 0:
                    continue
                captured = datetime.fromisoformat(str(captured_at).replace("Z", "+00:00"))
                if captured.tzinfo is None:
                    captured = captured.replace(tzinfo=timezone.utc)
                local_hour = captured.astimezone(tz).hour
            except Exception:
                continue
            group = groups.setdefault(
                checkpoint,
                {
                    "checkpoint": checkpoint,
                    "buckets": {hour: {"sum": 0.0, "count": 0} for hour in range(24)},
                },
            )
            group["buckets"][local_hour]["sum"] += wait
            group["buckets"][local_hour]["count"] += 1

    out = []
    for checkpoint, group in groups.items():
        rows_24h = []
        total_samples = 0
        bucket_count = 0
        peak_hour = None
        peak_avg = None
        for hour, bucket in group["buckets"].items():
            count = int(bucket["count"])
            avg_wait = round(bucket["sum"] / count, 1) if count else None
            if count:
                total_samples += count
                bucket_count += 1
            if avg_wait is not None and (peak_avg is None or avg_wait > peak_avg):
                peak_hour = hour
                peak_avg = avg_wait
            rows_24h.append(
                {
                    "hour": hour,
                    "label": f"{hour:02d}:00",
                    "avg_wait": avg_wait,
                    "samples": count,
                }
            )
        if total_samples < CHECKPOINT_HISTORY_MIN_SAMPLES or bucket_count < CHECKPOINT_HISTORY_MIN_BUCKETS:
            continue
        out.append(
            {
                "checkpoint": checkpoint,
                "label": checkpoint,
                "samples": total_samples,
                "buckets": bucket_count,
                "peak_hour": peak_hour,
                "peak_avg": peak_avg,
                "rows": rows_24h,
            }
        )

    out.sort(key=lambda group: (-int(group["samples"]), -(float(group["peak_avg"] or 0)), group["checkpoint"]))
    return out[:CHECKPOINT_HISTORY_MAX_GROUPS]


def x_alerts_enabled() -> bool:
    return ENABLE_X_ALERTS and all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET])


def average_wait_from_rows(rows: List[Dict]) -> float:
    active = [clamp_wait_minutes(float(r.get("wait_minutes", 0))) for r in rows if float(r.get("wait_minutes", 0)) > 0]
    values = active if active else [clamp_wait_minutes(float(r.get("wait_minutes", 0))) for r in rows]
    if not values:
        return 0.0
    return round(sum(values) / len(values), 1)


def historical_baseline_wait(airport_code: str, as_of: str) -> Optional[float]:
    end_dt = datetime.fromisoformat(as_of) - timedelta(minutes=20)
    start_dt = end_dt - timedelta(hours=X_ALERT_BASELINE_HOURS)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT wait_minutes
        FROM samples
        WHERE airport_code = ? AND captured_at >= ? AND captured_at < ?
        ORDER BY captured_at ASC
        """,
        (airport_code, start_dt.isoformat(), end_dt.isoformat()),
    )
    values = [clamp_wait_minutes(float(row[0])) for row in cur.fetchall() if float(row[0]) > 0]
    conn.close()
    if len(values) < X_ALERT_MIN_BASELINE_SAMPLES:
        return None
    return round(float(statistics.median(values)), 1)


def has_recent_social_post(platform: str, airport_code: str, event_type: str, now_iso: str) -> bool:
    cutoff = (datetime.fromisoformat(now_iso) - timedelta(minutes=X_ALERT_COOLDOWN_MINUTES)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM social_posts
        WHERE platform = ? AND airport_code = ? AND event_type = ? AND status = 'posted' AND posted_at >= ?
        LIMIT 1
        """,
        (platform, airport_code, event_type, cutoff),
    )
    found = cur.fetchone() is not None
    conn.close()
    return found


def record_social_post(platform: str, airport_code: str, event_type: str, event_key: str, post_text: str, status: str, external_id: str = "", error_message: str = "", posted_at: str = "") -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO social_posts (platform, airport_code, event_type, event_key, post_text, external_id, status, error_message, posted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            platform,
            airport_code,
            event_type,
            event_key,
            post_text,
            external_id,
            status,
            error_message[:500],
            posted_at or utc_now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def build_airport_wait_alert(code: str, rows: List[Dict]) -> Optional[Dict]:
    if not rows:
        return None
    current_avg = average_wait_from_rows(rows)
    if current_avg < X_ALERT_MIN_WAIT:
        return None

    as_of = max(r.get("captured_at", "") for r in rows)
    baseline = historical_baseline_wait(code, as_of)
    delta = round(current_avg - baseline, 1) if baseline is not None else None

    if baseline is None and current_avg < X_ALERT_EXTREME_WAIT:
        return None
    if baseline is not None and current_avg < X_ALERT_EXTREME_WAIT and delta < X_ALERT_MIN_DELTA:
        return None
    if has_recent_social_post("x", code, "abnormal_wait", as_of):
        return None

    top_rows = sorted(rows, key=lambda row: float(row.get("wait_minutes", 0)), reverse=True)[:2]
    checkpoint_summary = ", ".join(
        f"{str(row.get('checkpoint', 'Checkpoint')).split('(')[0].strip()} {int(round(float(row.get('wait_minutes', 0))))}m"
        for row in top_rows
    )
    link = f"{SITE_URL}{airport_seo_slug(code)}"
    baseline_text = "well above normal" if baseline is None else f"vs {int(round(baseline))}m baseline"
    text = (
        f"Abnormal TSA wait at {code}: avg live wait is {int(round(current_avg))}m right now "
        f"({baseline_text}). Top lanes: {checkpoint_summary}. Live updates: {link} #{code} #tsa"
    )
    if len(text) > 280:
        text = (
            f"Abnormal TSA wait at {code}: avg live wait is {int(round(current_avg))}m right now "
            f"({baseline_text}). Live updates: {link} #{code} #tsa"
        )

    as_of_dt = datetime.fromisoformat(as_of)
    bucket_minutes = math.floor(as_of_dt.minute / 30) * 30
    event_key = f"x:abnormal_wait:{code}:{as_of_dt.strftime('%Y%m%d%H')}:{bucket_minutes:02d}"
    return {
        "airport_code": code,
        "event_type": "abnormal_wait",
        "event_key": event_key,
        "post_text": text,
        "posted_at": as_of,
    }


def post_to_x(text: str) -> str:
    from requests_oauthlib import OAuth1

    resp = requests.post(
        "https://api.x.com/2/tweets",
        json={"text": text},
        auth=OAuth1(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET),
        timeout=20,
    )
    resp.raise_for_status()
    body = resp.json()
    post_id = body.get("data", {}).get("id")
    if not post_id:
        raise RuntimeError(f"X post response missing id: {body}")
    return str(post_id)


def maybe_post_x_alerts(rows: List[Dict]) -> None:
    if not x_alerts_enabled() or not rows:
        return

    grouped: Dict[str, List[Dict]] = {}
    for row in rows:
        code = row.get("airport_code", "")
        if code in LIVE_AIRPORTS:
            grouped.setdefault(code, []).append(row)

    for code, airport_rows in grouped.items():
        payload = build_airport_wait_alert(code, airport_rows)
        if not payload:
            continue
        try:
            external_id = post_to_x(payload["post_text"])
            record_social_post(
                platform="x",
                airport_code=payload["airport_code"],
                event_type=payload["event_type"],
                event_key=payload["event_key"],
                post_text=payload["post_text"],
                status="posted",
                external_id=external_id,
                posted_at=payload["posted_at"],
            )
            logger.info("x_alert_posted airport=%s event=%s id=%s", payload["airport_code"], payload["event_type"], external_id)
        except Exception as e:
            record_social_post(
                platform="x",
                airport_code=payload["airport_code"],
                event_type=payload["event_type"],
                event_key=payload["event_key"],
                post_text=payload["post_text"],
                status="failed",
                error_message=str(e),
                posted_at=payload["posted_at"],
            )
            logger.exception("x_alert_failed airport=%s event=%s", payload["airport_code"], payload["event_type"])


@app.route("/favicon.ico")
def favicon_ico():
    return send_from_directory(os.path.join(app.root_path, "static"), "favicon.ico", mimetype="image/vnd.microsoft.icon")


@app.before_request
def canonicalize_public_origin():
    if request.method not in {"GET", "HEAD"}:
        return None

    canonical = urlparse(SITE_URL)
    canonical_host = canonical.netloc.lower()
    if not canonical.scheme or not canonical_host:
        return None

    request_host = request.host.split(":", 1)[0].lower()
    forwarded_proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    request_scheme = forwarded_proto.split(",", 1)[0].strip().lower()
    if request_scheme not in {"http", "https"}:
        request_scheme = request.scheme

    is_www_variant = request_host == f"www.{canonical_host}"
    is_insecure_canonical = request_host == canonical_host and request_scheme != canonical.scheme
    if not (is_www_variant or is_insecure_canonical):
        return None

    target = f"{canonical.scheme}://{canonical.netloc}{request.full_path}"
    if target.endswith("?"):
        target = target[:-1]
    return redirect(target, code=301)


@app.before_request
def redirect_legacy_paths():
    if request.method not in {"GET", "HEAD"}:
        return None
    normalized_path = request.path.rstrip("/") if request.path != "/" else request.path
    target = LEGACY_PAGE_REDIRECTS.get(normalized_path)
    if target:
        return redirect(target, code=301)
    return None


@app.before_request
def canonicalize_trailing_slash_urls():
    if request.path != "/" and request.path.endswith("/") and not request.path.startswith("/api/"):
        target = request.path.rstrip("/")
        if request.query_string:
            target = f"{target}?{request.query_string.decode('utf-8', errors='ignore')}"
        return redirect(target, code=301)


@app.before_request
def ensure_web_runtime_started() -> None:
    start_web_runtime_once()

@app.route("/sw.js")
def sw_js():
    return send_from_directory(app.root_path, "sw.js", mimetype="application/javascript")


@app.route("/favicon-48x48.png")
def favicon_png():
    return send_from_directory(os.path.join(app.root_path, "static"), "favicon-48x48.png", mimetype="image/png")

@app.route("/apple-touch-icon.png")
def favicon_apple():
    return send_from_directory(os.path.join(app.root_path, "static"), "apple-touch-icon.png", mimetype="image/png")

@app.route("/")
def index():
    log_page_view("/", None)
    return render_template("home.html", **index_template_context("", home_page_seo()))

@app.route("/tsa-wait-times")
@app.route("/tsa-wait-times/")
@app.route("/airport-wait-times")
@app.route("/airport-wait-times/")
@app.route("/airport-security-lines")
@app.route("/airport-security-lines/")
@app.route("/security-wait-times")
@app.route("/security-wait-times/")
def wait_times_alias():
    return redirect("/airport-security-wait-times", code=301)

@app.route("/airports/<airport_slug>/")
@app.route("/airports/<airport_slug>")
def airport_page(airport_slug: str):
    normalized_slug = airport_slug.strip().lower()
    short_code = re.fullmatch(r"([a-z]{3})", normalized_slug)
    if short_code:
        code = short_code.group(1).upper()
        if code in LIVE_AIRPORTS:
            return redirect(airport_seo_slug(code), code=301)
        if code in PIPELINE_AIRPORT_CODES:
            return redirect("/airports", code=301)

    m = re.fullmatch(r"([a-z]{3})-tsa-wait-times", normalized_slug)
    if not m:
        log_page_view(f"/airports/{airport_slug}", None)
        return jsonify({"error": "Not found"}), 404
    code = m.group(1).upper()
    log_page_view(f"/airports/{airport_slug}", code)
    if code not in LIVE_AIRPORTS and code in PIPELINE_AIRPORT_CODES:
        return redirect("/airports", code=301)
    meta = LIVE_AIRPORTS.get(code)
    if not meta:
        return jsonify({"error": "Airport page unavailable"}), 404
    canonical_path = airport_seo_slug(code)
    if request.path != canonical_path:
        return redirect(canonical_path, code=301)
    return render_template("airport.html", **index_template_context(code, airport_page_seo(code, meta["name"])))


@app.route("/<legacy_airport_slug>")
def legacy_top_level_airport_page(legacy_airport_slug: str):
    m = re.fullmatch(r"([a-zA-Z]{3})-tsa-wait-times", legacy_airport_slug.strip())
    if not m:
        abort(404)
    code = m.group(1).upper()
    if code in LIVE_AIRPORTS:
        return redirect(airport_seo_slug(code), code=301)
    if code in PIPELINE_AIRPORT_CODES:
        return redirect("/airports", code=301)
    abort(404)


@app.route("/about")
def about_page():
    seo = build_page_seo(
        title="About TSA Tracker | Airport Wait-Time Sources",
        description="Learn how TSA Tracker labels official live airport readings, fallback estimates, source freshness, and airport-specific planning guidance.",
        canonical_path="/about",
    )
    return render_template(
        "about.html",
        seo=seo,
        monetization=get_monetization_context(),
        live_airports=LIVE_AIRPORTS,
        copy_updated_label=editorial_review_date_label("/about"),
        copy_updated_iso=editorial_review_date_iso("/about"),
    )


@app.route("/link-graph")
def link_graph_page():
    if not ENABLE_INTERNAL_GRAPH:
        abort(404)
    return render_template("link_graph.html", **link_graph_context())


@app.route("/wide-link-graph")
def wide_link_graph_page():
    if not ENABLE_INTERNAL_GRAPH:
        abort(404)
    return render_template("wide_link_graph.html", **link_graph_context("/wide-link-graph"))


@app.route("/airports")
def airports_page():
    return render_template("airports.html", **airport_directory_context())


@app.route("/when-should-i-leave")
def when_should_i_leave_page():
    log_page_view("/when-should-i-leave", None)
    overview = build_airport_overview_context()
    calc_airports = {
        a["code"]: {
            "name": a["name"],
            "city": a["city"],
            "wait": a["current_wait"],
            "live": a["is_live"],
            "trend": a["trend"],
            "delta": a["trend_delta"],
        }
        for a in overview["airport_summaries"]
    }
    requested_airport = str(request.args.get("airport") or "").strip().upper()
    requested_checkpoint = str(request.args.get("checkpoint") or "").strip().lower()
    requested_lane = _lane_type_key(request.args.get("lane")) if request.args.get("lane") else ""
    selected_airport = requested_airport if requested_airport in LIVE_AIRPORTS else ""
    selected_checkpoint = ""
    selected_lane = (
        requested_lane
        if selected_airport and requested_lane in AIRPORT_ARRIVAL_MODE_LANES
        else ""
    )

    calculator_arrival_mode = None
    if selected_airport in AIRPORT_ARRIVAL_MODE_CODES:
        calculator_history = []
        try:
            calculator_history = history_for_airport(
                selected_airport,
                hours=AIRPORT_ARRIVAL_MODE_HISTORY_HOURS,
            )
        except Exception as e:
            logger.warning(
                "Calculator checkpoint history unavailable for %s; using current rows: %s",
                selected_airport,
                e,
            )
        try:
            calculator_arrival_mode = build_airport_arrival_mode(
                selected_airport,
                rows=latest_for_code(selected_airport),
                history_rows=calculator_history,
            )
        except Exception as e:
            logger.error(
                "Error building calculator checkpoint context for %s: %s",
                selected_airport,
                e,
            )

    configured_checkpoint_ids = {
        checkpoint["id"]
        for terminal in (calculator_arrival_mode or {}).get("terminals", [])
        for checkpoint in terminal.get("checkpoints", [])
    }
    if (
        selected_airport in AIRPORT_ARRIVAL_MODE_CODES
        and requested_checkpoint in configured_checkpoint_ids
        and selected_lane
    ):
        selected_checkpoint = requested_checkpoint
    elif requested_checkpoint:
        # Checkpoint and lane are a single piece of context; discard both if
        # the checkpoint does not belong to the selected airport.
        selected_lane = ""

    calculator_selection = {
        "airport": selected_airport,
        "checkpoint": selected_checkpoint,
        "lane": selected_lane,
    }
    seo = build_page_seo(
        "Airport Leave-Time Calculator | TSA Tracker",
        "Enter your airport and flight time to combine the current live-or-estimated TSA wait, recent trend, 30-day pattern, drive time, and trip buffer.",
        "/when-should-i-leave",
    )
    return render_template(
        "calculator.html",
        seo=seo,
        monetization=get_monetization_context(),
        calc_airports_json=json.dumps(calc_airports),
        calculator_selection=calculator_selection,
        calculator_checkpoints=calculator_arrival_mode or {},
        airport_summaries=overview["airport_summaries"],
        copy_updated_label=editorial_review_date_label("/when-should-i-leave"),
        copy_updated_iso=editorial_review_date_iso("/when-should-i-leave"),
    )


@app.route("/airport-security-wait-times")
def airport_security_wait_times_page():
    overview = build_airport_overview_context()
    return render_template(
        "airport_security_wait_times.html",
        seo=airport_security_wait_times_seo(),
        monetization=get_monetization_context(),
        live_airports=LIVE_AIRPORTS,
        airport_pages=overview["airport_pages"],
        airport_summaries=overview["airport_summaries"],
        fastest_airport=overview["fastest_airport"],
        slowest_airport=overview["slowest_airport"],
        overall_average=overview["overall_average"],
        live_count=overview["live_count"],
        estimated_count=overview["estimated_count"],
        copy_updated_label=editorial_review_date_label("/airport-security-wait-times"),
        copy_updated_iso=editorial_review_date_iso("/airport-security-wait-times"),
    )


@app.route("/best-time-to-get-to-the-airport")
def best_time_to_get_to_airport_page():
    return render_template("intent_guide.html", **intent_page_context("best-time-to-get-to-the-airport"))


@app.route("/how-early-should-i-arrive-for-tsa")
def how_early_should_i_arrive_for_tsa_page():
    return redirect("/best-time-to-get-to-the-airport", code=301)


@app.route("/tsa-wait-times-by-airport")
def tsa_wait_times_by_airport_page():
    return redirect("/airports", code=301)


@app.route("/privacy")
def privacy():
    seo = build_page_seo(
        title="Privacy Policy | TSA Tracker",
        description="TSA Tracker's privacy policy — how we collect, use, and protect your information when you use our live airport security wait time service.",
        canonical_path="/privacy",
    )
    return render_template(
        "privacy.html",
        seo=seo,
        monetization=get_monetization_context(),
        copy_updated_label=editorial_review_date_label("/privacy"),
    )


@app.route("/terms")
def terms():
    seo = build_page_seo(
        title="Terms of Service | TSA Tracker",
        description="TSA Tracker terms of service — the rules and conditions for using our live airport TSA wait time service.",
        canonical_path="/terms",
    )
    return render_template(
        "terms.html",
        seo=seo,
        monetization=get_monetization_context(),
        copy_updated_label=editorial_review_date_label("/terms"),
    )


@app.route("/contact")
def contact():
    seo = build_page_seo(
        title="Contact | TSA Tracker",
        description="Get in touch with the TSA Tracker team — questions, feedback, bug reports, airport data requests, and partnership inquiries.",
        canonical_path="/contact",
    )
    return render_template("contact.html", seo=seo, monetization=get_monetization_context())


@app.route("/guide/tsa-wait-times")
def guide_tsa_wait_times():
    seo = build_page_seo(
        title="TSA Wait Times Explained | Airport Security Guide 2026",
        description="Learn how airport security waits are measured, how source freshness works, when lines peak, and how to use checkpoint and lane data.",
        canonical_path="/guide/tsa-wait-times",
    )
    airport_pages = [{"code": c, "href": airport_seo_slug(c), "name": v["name"]} for c, v in LIVE_AIRPORTS.items()]
    return render_template(
        "guide.html",
        seo=seo,
        monetization=get_monetization_context(),
        live_airports=LIVE_AIRPORTS,
        airport_pages=airport_pages,
        copy_updated_label=editorial_review_date_label("/guide/tsa-wait-times"),
        copy_updated_iso=editorial_review_date_iso("/guide/tsa-wait-times"),
    )


@app.route("/guide/tsa-precheck-clear")
def guide_tsa_precheck_clear():
    seo = build_page_seo(
        title="TSA PreCheck vs CLEAR | Costs, Enrollment, Which Is Faster",
        description="Compare TSA PreCheck, CLEAR, and Global Entry, including how they work, official enrollment options, and relevant travel-card benefits.",
        canonical_path="/guide/tsa-precheck-clear",
    )
    return render_template(
        "precheck_clear.html",
        seo=seo,
        monetization=get_monetization_context(
            page_type="precheck-guide",
            enable_affiliate_links=True,
        ),
        copy_updated_label=editorial_review_date_label("/guide/tsa-precheck-clear"),
        copy_updated_iso=editorial_review_date_iso("/guide/tsa-precheck-clear"),
    )


@app.route("/methodology")
def methodology_page():
    seo = build_page_seo(
        title="TSA Data Methodology | TSA Tracker",
        description="How TSA Tracker sources, validates, and updates airport checkpoint wait times, including source transparency and known limitations.",
        canonical_path="/methodology",
    )
    return render_template(
        "methodology.html",
        seo=seo,
        live_airports=LIVE_AIRPORTS,
        monetization=get_monetization_context(),
        copy_updated_label=editorial_review_date_label("/methodology"),
        copy_updated_iso=editorial_review_date_iso("/methodology"),
    )


@app.route("/api/live")
def api_live():
    public_airports = {
        code: {
            "name": meta["name"],
            "city": meta.get("city", ""),
        }
        for code, meta in LIVE_AIRPORTS.items()
    }
    data = latest_snapshot()
    for code in LIVE_AIRPORTS:
        if data.get(code):
            continue
        payload = normalized_current_wait_for_code(code)
        current = payload.get("currentWait", {})
        data[code] = [{
            "checkpoint": "Estimated Wait",
            "wait_minutes": current.get("standard", 0),
            "lane_type": "STANDARD",
            "captured_at": current.get("timestamp", utc_now().isoformat()),
            "source": payload.get("sourceType", "estimated_fallback"),
        }]
    return jsonify(
        {
            "generated_at": utc_now().isoformat(),
            "live_airports": public_airports,
            "data": data,
        }
    )


@app.route("/api/airport-arrival-mode")
def api_airport_arrival_mode():
    code = str(request.args.get("airport") or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", code) or code not in LIVE_AIRPORTS:
        return jsonify({"error": "Unknown airport"}), 400
    if code not in AIRPORT_ARRIVAL_MODE_CODES:
        return jsonify({"error": "Arrival mode unavailable"}), 404

    history_rows = []
    try:
        history_rows = history_for_airport(code, hours=AIRPORT_ARRIVAL_MODE_HISTORY_HOURS)
    except Exception as e:
        logger.warning(
            "Arrival history API dependency unavailable for %s; returning current rows without trends: %s",
            code,
            e,
        )
    try:
        model = build_airport_arrival_mode(
            code,
            rows=latest_for_code(code),
            history_rows=history_rows,
        )
    except Exception as e:
        logger.error("Error building arrival mode API response for %s: %s", code, e)
        return jsonify({"error": "Arrival mode temporarily unavailable"}), 503
    if not model:
        return jsonify({"error": "Arrival mode unavailable"}), 404
    return jsonify(model)


@app.route("/api/history")
def api_history():
    code = request.args.get("airport", "PHL").upper()
    hours = request.args.get("hours", 12, type=int) or 12
    hours = max(1, min(hours, 720))
    if code not in LIVE_AIRPORTS:
        return jsonify({"error": "Unknown airport"}), 400
    return jsonify(
        {
            "airport": code,
            "hours": hours,
            "timezone": AIRPORT_TIME_ZONES.get(code, "UTC"),
            "generated_at": utc_now().isoformat(),
            "rows": history_for_airport(code, hours=hours),
        }
    )

@app.route("/api/history-24h-average")
def api_history_24h_average():
    code = request.args.get("airport", "PHL").upper()
    days = request.args.get("days", 30, type=int)
    include_checkpoints = str(request.args.get("include_checkpoints", "")).lower() in {"1", "true", "yes"}
    if code not in LIVE_AIRPORTS:
        return jsonify({"error": "Unknown airport"}), 400
    bounded_days = max(1, min(days, 90))
    payload = {
        "airport": code,
        "days": bounded_days,
        "timezone": AIRPORT_TIME_ZONES.get(code, "UTC"),
        "generated_at": utc_now().isoformat(),
        "rows": historical_24h_average_for_airport(code, days=bounded_days),
    }
    if include_checkpoints:
        payload["checkpoint_groups"] = checkpoint_24h_average_for_airport(code, days=bounded_days)
        payload["checkpoint_min_samples"] = CHECKPOINT_HISTORY_MIN_SAMPLES
    return jsonify(payload)

@app.route("/api/checkpoint-history-24h-average")
def api_checkpoint_history_24h_average():
    code = request.args.get("airport", "PHL").upper()
    days = request.args.get("days", 30, type=int)
    if code not in LIVE_AIRPORTS:
        return jsonify({"error": "Unknown airport"}), 400
    bounded_days = max(1, min(days, 90))
    return jsonify(
        {
            "airport": code,
            "days": bounded_days,
            "timezone": AIRPORT_TIME_ZONES.get(code, "UTC"),
            "generated_at": utc_now().isoformat(),
            "min_samples": CHECKPOINT_HISTORY_MIN_SAMPLES,
            "groups": checkpoint_24h_average_for_airport(code, days=bounded_days),
        }
    )

@app.route("/api/network-history-24h-average")
def api_network_history_24h_average():
    days = max(1, min(request.args.get("days", 30, type=int) or 30, 90))
    cache_key = f"days:{days}"
    now = utc_now()
    cached_at = _network_history_cache.get("generated_at")
    if (
        _network_history_cache.get("key") == cache_key
        and cached_at
        and (now - cached_at).total_seconds() < NETWORK_HISTORY_CACHE_SECONDS
        and _network_history_cache.get("payload")
    ):
        payload = dict(_network_history_cache["payload"])
        payload["cached"] = True
        return jsonify(payload)

    airports = []
    for code, meta in LIVE_AIRPORTS.items():
        rows = historical_24h_average_for_airport(code, days=days, sample_limit=20000)
        airports.append(
            {
                "code": code,
                "name": meta["name"],
                "timezone": AIRPORT_TIME_ZONES.get(code, "UTC"),
                "href": airport_seo_slug(code),
                "rows": rows,
            }
        )

    payload = {
        "days": days,
        "generated_at": now.isoformat(),
        "cache_seconds": NETWORK_HISTORY_CACHE_SECONDS,
        "cached": False,
        "airports": airports,
    }
    _network_history_cache.update({"key": cache_key, "generated_at": now, "payload": payload})
    return jsonify(payload)

@app.route("/api/historical-average")
def api_historical_average():
    """
    Get historical average wait time for a specific hour.
    Query: /api/historical-average?airport=LAX&hour=5&days=30
    Returns: {"airport": "LAX", "hour": 5, "avg_wait": 12.3, "days": 30}
    """
    if not SUPABASE_ENABLED:
        return jsonify({"error": "Historical data not enabled"}), 503

    code = request.args.get("airport", "").upper()
    hour = request.args.get("hour", type=int)
    days = request.args.get("days", 30, type=int)

    if not code or not re.fullmatch(r"[A-Z]{3}", code):
        return jsonify({"error": "Invalid airport code"}), 400
    if hour is None or hour < 0 or hour > 23:
        return jsonify({"error": "Hour must be 0-23"}), 400

    try:
        from supabase_integration import get_average_wait_at_hour
        avg = get_average_wait_at_hour(code, hour, days)
        return jsonify({
            "airport": code,
            "hour": hour,
            "days": days,
            "avg_wait": avg,
            "description": wait_description(avg) if avg else "No data",
            "timestamp": utc_now().isoformat()
        })
    except Exception as e:
        logger.error("Historical average query failed: %s", e)
        return jsonify({"error": str(e)}), 500

@app.route("/api/peak-hours")
def api_peak_hours():
    """
    Get busiest hours at an airport over the past N days.
    Query: /api/peak-hours?airport=LAX&days=30&top=3
    Returns: [{"hour": 17, "avg_wait": 28.5, "samples": 42}, ...]
    """
    if not SUPABASE_ENABLED:
        return jsonify({"error": "Historical data not enabled"}), 503

    code = request.args.get("airport", "").upper()
    days = request.args.get("days", 30, type=int)
    top_n = request.args.get("top", 3, type=int)

    if not code or not re.fullmatch(r"[A-Z]{3}", code):
        return jsonify({"error": "Invalid airport code"}), 400

    try:
        from supabase_integration import get_peak_hours
        peaks = get_peak_hours(code, days, top_n)
        return jsonify({
            "airport": code,
            "days": days,
            "peak_hours": peaks,
            "timestamp": utc_now().isoformat()
        })
    except Exception as e:
        logger.error("Peak hours query failed: %s", e)
        return jsonify({"error": str(e)}), 500

@app.route("/api/tsa-wait-times")
def api_tsa_wait_times():
    code = request.args.get("code", "").upper().strip()
    if not re.fullmatch(r"[A-Z]{3}", code):
        return jsonify(
            {
                "code": code,
                "available": False,
                "error": "Invalid Airport Code",
                "timestamp": utc_now().isoformat(),
            }
        ), 400
    payload = normalized_current_wait_for_code(code)
    return jsonify({"code": code, **payload, "airportNotice": airport_status_notice_for_code(code), "timestamp": utc_now().isoformat()})


@app.route("/api/pipeline")
def api_pipeline():
    public = [
        {"code": a["code"], "name": a["name"], "status": a.get("status", "IN_RESEARCH"), "note": a.get("public_note", "")}
        for a in PIPELINE_AIRPORTS
    ]
    return jsonify({"generated_at": utc_now().isoformat(), "airports": public})


@app.route("/robots.txt")
def robots_txt():
    body = (
        "User-agent: *\n"
        "Allow: /\n\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")

@app.route("/google708d930580927d7c.html")
def google_verify():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "google708d930580927d7c.html", mimetype="text/html")

@app.route("/sitemap.xml")
def sitemap_xml():
    dynamic_lastmod = utc_now().date().isoformat()
    dynamic_paths = [
        "/",
        "/airports",
        "/airport-security-wait-times",
        "/when-should-i-leave",
        *[airport_seo_slug(code) for code in LIVE_AIRPORTS],
    ]
    static_paths = [
        "/best-time-to-get-to-the-airport",
        "/about",
        "/methodology",
        "/privacy",
        "/terms",
        "/guide/tsa-wait-times",
        "/guide/tsa-precheck-clear",
    ]
    pages = [(path, dynamic_lastmod) for path in dynamic_paths]
    pages.extend((path, EDITORIAL_REVIEW_DATES[path]) for path in static_paths)
    pages.append(("/contact", ""))
    entries = []
    for path, lastmod in pages:
        lastmod_tag = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
        entries.append(
            "<url>"
            f"<loc>{SITE_URL}{path}</loc>"
            f"{lastmod_tag}"
            "</url>"
        )
    body = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"
        + "".join(entries)
        + "</urlset>"
    )
    return Response(body, mimetype="application/xml")

@app.route("/ads.txt")
def ads_txt():
    """Serve a first-party ads.txt file from the app root."""
    root_dir = os.path.dirname(os.path.abspath(__file__))
    ads_txt_path = os.path.join(root_dir, "ads.txt")
    if os.path.exists(ads_txt_path):
        return send_from_directory(root_dir, "ads.txt", mimetype="text/plain")
    body = f"{ADS_TXT_LINE}\n" if ADS_TXT_LINE else ""
    return Response(body, mimetype="text/plain")

@app.route("/healthz")
def healthz():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1")
        conn.close()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "generated_at": utc_now().isoformat()})


@app.route("/api/collect-now", methods=["POST"])
def api_collect_now():
    expected = COLLECT_NOW_TOKEN
    if expected:
        provided = request.headers.get("x-collect-token")
        if provided != expected:
            return jsonify({"error": "Unauthorized"}), 401
    with _poll_lock:
        result = collect_once()
    return jsonify(result)

@app.route("/api/report-wait", methods=["POST"])
def api_report_wait():
    data = request.json or {}
    code = str(data.get("code", "")).upper().strip()
    level = data.get("level")
    session_id = str(data.get("session_id", "")).strip()[:80]
    current_wait_raw = data.get("current_wait")
    current_wait = None
    if current_wait_raw is not None:
        try:
            current_wait = clamp_wait_minutes(float(current_wait_raw))
        except Exception:
            current_wait = None
    if code not in LIVE_AIRPORTS or level not in ["accurate", "not_accurate", "short", "med", "long"] or not session_id:
        return jsonify({"error": "Invalid request"}), 400

    cooldown_cutoff = (utc_now() - timedelta(minutes=5)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    recent = conn.execute(
        """
        SELECT 1 FROM user_reports
        WHERE airport_code = ? AND session_id = ? AND reported_at >= ?
        LIMIT 1
        """,
        (code, session_id, cooldown_cutoff),
    ).fetchone()
    if recent:
        conn.close()
        return jsonify({"error": "Rate limited", "retry_minutes": 5}), 429

    conn.execute(
        """
        INSERT INTO user_reports (airport_code, level, current_wait, session_id, reported_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (code, level, current_wait, session_id, utc_now().isoformat())
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/community-status")
def community_status():
    code = str(request.args.get("code", "")).upper().strip()
    if code not in LIVE_AIRPORTS:
        return jsonify({"error": "No code"}), 400
    
    cutoff = (utc_now() - timedelta(minutes=30)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT level, COUNT(*) AS count, AVG(current_wait) AS avg_wait, MAX(reported_at) AS last_reported_at
        FROM user_reports
        WHERE airport_code = ? AND reported_at >= ?
        GROUP BY level
        ORDER BY count DESC, last_reported_at DESC
        """,
        (code, cutoff)
    )
    rows = cur.fetchall()
    conn.close()
    
    counts = [
        {
            "level": row[0],
            "count": int(row[1]),
            "avg_current_wait": round(float(row[2]), 1) if row[2] is not None else None,
            "last_reported_at": row[3],
        }
        for row in rows
    ]
    top = counts[0] if counts else None
    return jsonify({
        "airport": code,
        "window_minutes": 30,
        "level": top["level"] if top else None,
        "count": top["count"] if top else 0,
        "counts": counts,
    })


@app.route("/api/community-summary")
def community_summary():
    if COLLECT_NOW_TOKEN and request.headers.get("x-collect-token") != COLLECT_NOW_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401
    minutes = request.args.get("minutes", 30, type=int)
    minutes = max(5, min(minutes or 30, 1440))
    cutoff = (utc_now() - timedelta(minutes=minutes)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT airport_code, level, COUNT(*) AS count, AVG(current_wait) AS avg_wait, MAX(reported_at) AS last_reported_at
        FROM user_reports
        WHERE reported_at >= ?
        GROUP BY airport_code, level
        ORDER BY airport_code ASC, count DESC, last_reported_at DESC
        """,
        (cutoff,),
    )
    rows = cur.fetchall()
    conn.close()

    airports = {}
    for code, level, count, avg_wait, last_reported_at in rows:
        airports.setdefault(code, []).append({
            "level": level,
            "count": int(count),
            "avg_current_wait": round(float(avg_wait), 1) if avg_wait is not None else None,
            "last_reported_at": last_reported_at,
        })
    return jsonify({
        "generated_at": utc_now().isoformat(),
        "window_minutes": minutes,
        "airports": airports,
    })


@app.route("/api/log-click", methods=["GET", "POST"])
def log_ad_click():
    if request.method == "GET":
        return ("", 204)
    data = request.get_json(silent=True) or {}
    offer_id = data.get("offer_id")
    code = data.get("code")
    if not offer_id:
        return jsonify({"error": "No offer_id"}), 400
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO ad_clicks (offer_id, airport_code, captured_at) VALUES (?, ?, ?)",
            (offer_id, code, utc_now().isoformat())
        )
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    start_web_runtime_once()
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
