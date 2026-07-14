# Airport Research Notes

Reference for every airport we've investigated — how we get live TSA wait data, what auth is involved, and what's still blocked.

---

## Status Overview

| Code | Name | Status | Auth |
|------|------|--------|------|
| PHL | Philadelphia International | ✅ Live | Public |
| MIA | Miami International | ✅ Live | Rotating key (scraped from JS) |
| ORD | Chicago O'Hare | ✅ Live | Public |
| CLT | Charlotte Douglas | ✅ Live | Rotating key (scraped from JS) |
| MCO | Orlando International | ✅ Live | Static key (env / bundle) |
| JAX | Jacksonville International | ✅ Live | Public |
| DFW | Dallas/Fort Worth | ✅ Live | Static key (embedded in bundle) |
| BOS | Boston Logan | ✅ Live | Public |
| ATL | Hartsfield-Jackson Atlanta | ✅ Live | Public |
| BWI | Baltimore/Washington International | ✅ Live | Homepage security widget |
| DTW | Detroit Metro | ✅ Live | Public JSON proxy |
| LAX | Los Angeles International | ✅ Live | Public (HTML table scrape) |
| JFK | John F. Kennedy International | ✅ Live | Public (GraphQL, PANYNJ) |
| EWR | Newark Liberty International | ✅ Live | Public (Azure API, api-key) |
| LGA | LaGuardia Airport | ✅ Live | Public (Azure API, api-key) |
| LAS | Harry Reid International | ✅ Live | Public widget (Zensors) |
| SEA | Seattle-Tacoma International | ✅ Live | Public (Drupal JSON API, portseattle.org) |
| SFO | San Francisco International | ✅ Live | Public HTML table scrape |
| DEN | Denver International | 🔬 Research | 403 Forbidden on direct probe |
| IAH | Houston Intercontinental | 🔬 Research | Public checkpoint endpoint found, but current API version is rejected |
| IAD | Washington Dulles | 🔬 Research | Wait times rendered dynamically; no public JSON API confirmed |
| DCA | Reagan National | ✅ Live | Public JSON endpoint at `/security-wait-times` |

---

## Notes Structure

```
airport_research/
  live/       — fully integrated airports
  pipeline/   — airports still under investigation
```

Each file records: endpoint URL, required headers/auth, key refresh strategy (if any), response schema, and any gotchas.
