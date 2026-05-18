# LAS — Harry Reid International Airport

**Status:** ✅ Live  
**Pipeline status:** `LIVE`  
**Last investigated:** 2026-05-18  

---

## Target URL

`https://www.harryreidairport.com/security-wait-times`

---

## Investigation Log

### Pass 1 (2026-03-23 — static scan)

`harryreidairport.com/security-wait-times` renders current wait times through embedded Zensors iframes. The wait-time data is not present in the static HTML, but the widget API is public and callable directly.

Key findings:
- Page contains two embedded wait-time widgets: `waitTimeExplorer` and `journeyPlanner`
- Live data is available through `waitTimeExplorer.init` and `waitTimeExplorer.update`
- No airport login or cookie auth is required for the widget API
- Journey names map to checkpoint groupings such as `T1 - A/B Gates` and `T3 - D/E Gates`

### Pass 2 (2026-03-23 — API pattern probes)

Tested common endpoint patterns:
- `https://api.harryreidairport.com/wait-times` → 404
- `https://www.harryreidairport.com/api/wait-times` → 404
- The page's embedded widget uses Zensors tRPC rather than a site-local JSON API

---

## Most Promising Lead

**Public Zensors widget API**

The page embeds the official wait-time widget, and the underlying tRPC endpoint can be called directly with the widget slug, domain, and token.

---

## Next Steps

1. Keep the live collector pointed at the Zensors widget API
2. Re-check the airport page if the embed token or widget slug changes

---

## Notes

- Part of batch onboarding (IAH, LAS, BWI, DTW, IAD, DCA) on 2026-03-23
- All 6 airports follow same pattern: server-rendered page + dynamic JS-loaded data
