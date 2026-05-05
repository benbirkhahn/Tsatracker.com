# LGA — LaGuardia Airport

## Status: LIVE

## Method
LaGuardia's own wait-times API backing the security page.

## Endpoint
```text
GET https://avi-prod-mpp-webapp-api.azurewebsites.net/api/v1/SecurityWaitTimesPoints/LGA
Accept: application/json
api-key: A6CE0EE926BC408B1E9D6E9EC14A5D64
Origin: https://www.laguardiaairport.com
Referer: https://www.laguardiaairport.com/security-wait-times
```

## Response Shape
```json
[
  {
    "title": "Terminal B",
    "terminal": "B",
    "queueType": "Reg",
    "timeInMinutes": 2,
    "status": "Open",
    "updateTimeText": "03:52 PM"
  }
]
```

- `timeInMinutes` is the displayed wait value in minutes.
- `queueType` distinguishes regular vs TSA PreCheck.
- `status` may show `Open` or `No Wait`.
- The site currently returns rows for Terminals B and C.

## Discovery Notes
- The `security-wait-times` page is a JS app shell that loads `api/v1/SecurityWaitTimesPoints/LGA`.
- The API is on `avi-prod-mpp-webapp-api.azurewebsites.net` and needs the airport's public `api-key`.
- The airport page text says the wait times are calculated and updated in real time.

## Auth Mode
`LIVE_KEY_REQUIRED`
