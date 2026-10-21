#!/usr/bin/env python3
"""Build a dated, attributed history supplement. Requires pandas and pyarrow.

Usage: python scripts/recover_airport_history.py --input-dir DIR --output FILE
Input: pinned waits_raw parquet partitions named DFW.parquet, IAH.parquet, MCO.parquet.
No production database writes. No network requests. Original archives stay intact.
"""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd

REVISION = "8f22142a51a1c0e974f7682229e45c3f0a107571"
ZONES = {"DFW": "America/Chicago", "IAH": "America/Chicago", "MCO": "America/New_York"}


def recover(frame, code):
    frame = frame.copy()
    frame["scraped_at"] = pd.to_datetime(frame["scraped_at"], utc=True, errors="coerce")
    valid = (frame.is_open.eq(True) & frame.status.isin(["open", "no_wait"])
             & frame.wait_is_estimated.eq(False) & frame.queue_type.isin(["standard", "precheck"])
             & frame.wait_minutes.between(0, 180) & frame.scraped_at.notna())
    # The archive misclassifies IAH Premier as PreCheck. It is eligibility-restricted.
    valid &= ~frame.terminal.str.contains("premier|priority|customs|arrivals", case=False, na=True)
    frame = frame[valid].copy()
    local = frame.scraped_at.dt.tz_convert(ZONES[code])
    frame["date"] = local.dt.strftime("%Y-%m-%d")
    frame["hour"] = local.dt.hour
    # Recover missing days only; our production history begins October 19.
    frame = frame[frame.date.between("2026-09-21", "2026-10-18")].copy()
    frame = frame.drop_duplicates(["terminal", "queue_type", "scraped_at", "wait_minutes"])
    frame["minute"] = frame.scraped_at.dt.floor("min")
    # Equal weight to each minute prevents bursts of repeated polls dominating.
    minutes = frame.groupby(["date", "hour", "queue_type", "minute"]).wait_minutes.mean()
    buckets = minutes.groupby(level=[0, 1, 2]).agg(["mean", "count"])
    counts = frame.groupby(["date", "hour", "queue_type"]).size()
    result = []
    for (date, hour, lane), bucket in buckets.iterrows():
        if bucket["count"] < 30:
            continue
        result.append({"airport": code, "date": date, "hour": int(hour), "lane": lane.upper(),
                       "mean": round(float(bucket["mean"]), 4), "samples": int(counts.loc[(date, hour, lane)]),
                       "minutesCovered": int(bucket["count"])})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows, hashes = [], {}
    for code in ZONES:
        path = args.input_dir / f"{code}.parquet"
        hashes[code] = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.extend(recover(pd.read_parquet(path), code))
    payload = {"schemaVersion": 1, "source": {
        "name": "US Airport Security & Immigration Wait Times", "author": "Henry Williams / digitalhen",
        "url": "https://huggingface.co/datasets/digitalhen/us-airport-wait-times",
        "revision": REVISION, "license": "CC BY 4.0", "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
        "inputSha256": hashes,
        "transform": "Open, numeric Standard/PreCheck readings only; IAH Premier excluded; UTC converted to airport local time; duplicate polls removed; minute means averaged into daily hourly means; at least 30 sampled minutes per hour."
    }, "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    for code in ZONES:
        subset = [r for r in rows if r["airport"] == code]
        print(code, len(subset), "hour/lane buckets;", len({r['date'] for r in subset}), "days;", sum(r['samples'] for r in subset), "readings")


if __name__ == "__main__":
    main()
