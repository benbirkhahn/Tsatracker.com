# LGA — LaGuardia Airport

## Status: LIVE

## Method
GraphQL API operated by PANYNJ (Port Authority of New York & New Jersey).
Same backend as JFK and EWR. No authentication required.

## Endpoint
```
POST https://api.jfkairport.com/graphql
Content-Type: application/json
```

## Query
```graphql
{ securityWaitTimes(airportCode: "LGA") { checkPoint waitTime terminal } }
```

## Response Shape
```json
{
  "data": {
    "securityWaitTimes": [
      {"checkPoint": "Main ChekPoint", "waitTime": 0, "terminal": "A"},
      {"checkPoint": "Main ChekPoint", "waitTime": 0, "terminal": "A"},
      {"checkPoint": "Main ChekPoint", "waitTime": 0, "terminal": "B"},
      {"checkPoint": "Main ChekPoint", "waitTime": 0, "terminal": "B"},
      {"checkPoint": "Main ChekPoint", "waitTime": 0, "terminal": "C"},
      {"checkPoint": "Main ChekPoint", "waitTime": 0, "terminal": "C"}
    ]
  }
}
```

- `waitTime` is **already in minutes** (integer).
- `terminal` is "A", "B", or "C" (string).
- `checkPoint` contains same upstream typo ("ChekPoint") as JFK/EWR — preserved as-is.
- Returns **2 rows per terminal** — strongly suggests one row per lane type (standard + PreCheck).
  The API currently does not expose a lane type field. Tracked in PreCheck plan.
- 6 total rows across Terminals A, B, C.

## Discovery Notes
- Confirmed live 2026-03-24 by probing `airportCode: "LGA"` on the PANYNJ GraphQL endpoint.
- No separate LGA-specific API domain found. Uses `api.jfkairport.com`.
- Same dual-row pattern as JFK and EWR — all three airports return 2 entries per terminal checkpoint.

## Auth Mode
`LIVE_PUBLIC`
