import re

with open('app.py', 'r') as f:
    content = f.read()

# 1. Add fetch_dtw_rows and fetch_iah_rows
functions = """def fetch_dtw_rows() -> List[Dict]:
    endpoint = "https://proxy.metroairport.com/SkyFiiTSAProxy.ashx"
    headers = {
        **UA,
        "origin": "https://www.metroairport.com",
        "referer": "https://www.metroairport.com/"
    }
    resp = requests.get(endpoint, headers=headers, timeout=20)
    resp.raise_for_status()
    payload = resp.json()

    rows = []
    stamp = utc_now().isoformat()

    for rec in payload:
        name = rec.get("Name")
        wait_minutes = rec.get("WaitTime")
        if name is None or wait_minutes is None:
            continue

        rows.append(
            {
                "airport_code": "DTW",
                "checkpoint": f"{name} Terminal",
                "wait_minutes": float(wait_minutes),
                "source": "https://proxy.metroairport.com/SkyFiiTSAProxy.ashx",
                "captured_at": stamp,
            }
        )

    return rows

def fetch_iah_rows() -> List[Dict]:
    api_key = os.getenv("IAH_API_KEY")
    if not api_key:
        logger.warning("IAH_API_KEY is not set.")
        return []

    endpoint = "https://api.houstonairports.mobi/wait-times/checkpoint/iah"
    headers = {
        **UA,
        "api-key": api_key,
        "api-version": "120"
    }

    resp = requests.get(endpoint, headers=headers, timeout=20)
    resp.raise_for_status()
    payload = resp.json()

    rows = []
    stamp = utc_now().isoformat()

    for rec in payload.get("data", {}).get("wait_times", []):
        if not rec.get("isDisplayable", True):
            continue

        name = rec.get("name")
        wait_seconds = rec.get("waitSeconds")

        if name is None or wait_seconds is None:
            continue

        # Ignore immigration/FIS checkpoints
        if "FIS" in str(rec.get("lane", "")) or "Immigration" in name:
            continue

        wait_minutes = max(0.0, float(wait_seconds) / 60.0)

        rows.append(
            {
                "airport_code": "IAH",
                "checkpoint": name,
                "wait_minutes": wait_minutes,
                "source": "https://api.houstonairports.mobi/wait-times/checkpoint/iah",
                "captured_at": stamp,
            }
        )

    return rows

"""

content = content.replace("def _fetch_panynj_rows", functions + "def _fetch_panynj_rows")

# 2. Add to LIVE_AIRPORTS block
live_airports_block = """LIVE_AIRPORTS = {
    "PHL": {"name": "Philadelphia International (PHL)", "mode": "LIVE_PUBLIC"},"""
new_live_airports_block = """LIVE_AIRPORTS = {
    "DTW": {"name": "Detroit Metropolitan (DTW)", "mode": "LIVE_PUBLIC"},
    "IAH": {"name": "George Bush Intercontinental (IAH)", "mode": "LIVE_KEY_REQUIRED"},
    "PHL": {"name": "Philadelphia International (PHL)", "mode": "LIVE_PUBLIC"},"""
content = content.replace(live_airports_block, new_live_airports_block)


# 3. Add to fetchers map
fetchers_block = """    fetchers = {
        "PHL": fetch_phl_rows,"""
new_fetchers_block = """    fetchers = {
        "DTW": fetch_dtw_rows,
        "IAH": fetch_iah_rows,
        "PHL": fetch_phl_rows,"""
content = content.replace(fetchers_block, new_fetchers_block)


# 4. Remove from PIPELINE_AIRPORTS (since they are now in LIVE_AIRPORTS)
pipeline_dtw = """    {
        "code": "DTW",
        "name": "Detroit Metropolitan",
        "status": "IN_RESEARCH",
        "public_note": "Researching internal API integrations.",
    },
"""
content = content.replace(pipeline_dtw, "")

pipeline_iah = """    {
        "code": "IAH",
        "name": "George Bush Intercontinental",
        "status": "IN_RESEARCH",
        "public_note": "Researching internal API integrations.",
    },
"""
content = content.replace(pipeline_iah, "")

with open('app.py', 'w') as f:
    f.write(content)
