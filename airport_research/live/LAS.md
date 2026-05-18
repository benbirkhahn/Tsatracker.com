# LAS — Harry Reid International Airport

## Status: LIVE

## Method
Public Zensors widget embedded on the airport's official security wait-times page.
No authentication required for the embedded wait-time API calls.

## Page
```
https://www.harryreidairport.com/security-wait-times
```

## Widget Endpoints
```
GET https://embed.zensors.live/api/embeddable-widget/trpc/waitTimeExplorer.init
GET https://embed.zensors.live/api/embeddable-widget/trpc/waitTimeExplorer.update
```

## Widget Params
- `domainSlug`: `LAS`
- `slug`: `t1LQGTAPA`
- `token`: `3Ll9yq2riLZctX1CZ94FRgLcScJimgXx`

## Response Shape
```json
{
  "journeys": {
    "t2K25H6KA": {"name": "T1 - A/B Gates", "availablePaths": ["precheck", "standard"]},
    "t0CSXP4SK": {"name": "T3 - D/E Gates", "availablePaths": ["precheck", "standard"]}
  },
  "initialJourneyData": {
    "paths": {
      "standard": {"open": true, "waitTime": {"timestamp": 1779116130000, "value": 1.5}},
      "precheck": {"open": true, "waitTime": {"timestamp": 1779116130000, "value": 1}}
    }
  }
}
```

- `waitTime.value` is already in minutes.
- Each journey reports `standard` and `precheck` paths.
- Journey names correspond to checkpoint groupings, such as `T1 - A/B Gates` and `T3 - D/E Gates`.

## Discovery Notes
- The official airport page renders two embedded Zensors iframes: `waitTimeExplorer` and `journeyPlanner`.
- The live data comes from the embeddable widget API, not from HTML scraped off the page.
- The embedded widget uses the same `waitTimeExplorer.init/update` pattern as our BOS integration.

## Auth Mode
`LIVE_PUBLIC`
