# IAH — George Bush Intercontinental Airport

**Status:** 🔬 In Research  
**Pipeline status:** `IN_RESEARCH`  
**Last investigated:** 2026-05-18  

---

## Target URL

`https://www.fly2houston.com/iah/security`

---

## Investigation Log

### Pass 1 (2026-03-23 — static scan)

`fly2houston.com/iah/security` returns HTTP 200 with server-rendered HTML containing wait-time keyword context. However, the actual wait-time data is **not present in the static HTML** — it is loaded dynamically via JavaScript/AJAX.

Key findings:
- Page contains `<meta>` tags and structural content
- No JSON API key extraction possible from JS bundles
- No skydive/mobi API domain (`api.iahairport.mobi`) exists
- No standard REST or GraphQL endpoint found
- Wait time data fetched via client-side JS (XHR/fetch)

### Pass 2 (2026-03-23 — API pattern probes)

Tested common endpoint patterns:
- `https://api.fly2houston.com/wait-times` → 404
- `https://api.iah.aero/wait-times` → 404/timeout
- `https://www.fly2houston.com/api/wait-times` → 404
- No GraphQL endpoint detected

### Pass 3 (2026-05-18 — live endpoint discovery)

The current page bundle exposes the live Houston Airports API host and checkpoint route:

- `GET https://api.houstonairports.mobi/wait-times/checkpoint/<CHECKPOINT_ID>`
- Required headers:
  - `Api-Key: 9ACB3B733BE94B11A03B6E84CA87E895`
  - `Api-Version: 100`

Observed behavior:
- The endpoint is reachable, but every tested version value returns `412` with `API version is no longer supported!`
- Omitting `Api-Version` returns `500`
- The browser-facing page still renders the error state instead of live wait times

---

## Most Promising Lead

**Dynamic client-side rendering via XHR**

The page loads wait-time data after initial HTML render, likely via:
1. A private airport API (not publicly documented)
2. A third-party wait-time vendor (QLess, Passur, etc.)
3. An embedded iframe or widget

**Current blocker:** The live endpoint is known, but the bundled API version is already rejected by the provider. IAH should stay in research until Houston publishes a supported version or refreshes the client bundle.

---

## Next Steps

1. Refresh the page bundle and re-check the API version header.
2. Re-probe the checkpoint endpoint if Houston publishes a supported version.
3. Keep IAH in research until the provider-side version mismatch is resolved.

---

## Notes

- Part of batch onboarding (IAH, LAS, BWI, DTW, IAD, DCA) on 2026-03-23
- All 6 airports follow same pattern: server-rendered page + dynamic JS-loaded data
- IAH now has a confirmed endpoint, but the published client version is stale
