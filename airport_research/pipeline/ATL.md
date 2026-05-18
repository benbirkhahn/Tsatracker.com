# ATL — Hartsfield-Jackson Atlanta International Airport

**Status:** ✅ Live  
**Pipeline status:** `LIVE_DIRECT`  

---

## Working Source

`https://dev.atl.com/atlsync/security-wait-times/`

---

## What We Tried (2026-03-22)

### Static scan (curl + Python)

All requests to `atl.com` return **HTTP 403** with a Cloudflare challenge:

```
cf-mitigated: challenge
server: cloudflare
```

This applies to:
- `https://www.atl.com/times/` (main page)
- `https://www.atl.com/api/wait-times`
- `https://www.atl.com/wp-json/atl/v1/times`
- `https://www.atl.com/wp-admin/admin-ajax.php`

Even with full browser-like headers (Sec-CH-UA, Sec-Fetch-*, etc.) the challenge fires.

### Smoke test

The ATL Next security page renders live values in plain HTML and parses cleanly with a simple HTML scrape. The page returned 5 checkpoint rows during the smoke test.

### TSA DHS endpoint

`https://apps.tsa.dhs.gov/mytsa/wait_times_detail.aspx?airport=ATL` — returns 200 but is the generic MyTSA mobile app marketing page, not actual live wait time data (same 75KB HTML regardless of airport code).

### Other services

The public `atl.com/times/` page is still blocked by Cloudflare, but the ATL Next page exposes the live wait times without the challenge.

---

## Notes

- ATL is the world's busiest airport — high-value addition.
- `AIRPORT_FACTORS["ATL"] = 1.25` is already set for forecast scaling.
- The live source is `dev.atl.com/atlsync/security-wait-times/`, not `www.atl.com/times/`.
