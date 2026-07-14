# DTW — Detroit Metropolitan Airport

**Status:** ✅ Live

## Method
Public JSON response fetched from the metroairport.com SkyFii proxy.

## Endpoint
```text
GET https://proxy.metroairport.com/SkyFiiTSAProxy.ashx
```

## Response Shape
The endpoint returns a JSON array with:
- `Name`
- `WaitTime`

Observed terminal labels:
- McNamara
- Evans

## Notes
- The airport page loads the same feed through Angular on the public site.
- `WaitTime` is already in minutes.
- The collector normalizes the terminal names to `McNamara Terminal` and `Evans Terminal` for the arrival-mode UI.
