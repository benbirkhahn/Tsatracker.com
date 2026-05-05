# EWR Live Wait Times

Status: live

## Endpoint

GET `https://avi-prod-mpp-webapp-api.azurewebsites.net/api/v1/SecurityWaitTimesPoints/EWR`

## Required Headers

- `api-key: A6CE0EE926BC408B1E9D6E9EC14A5D64`
- `Origin: https://www.newarkairport.com`
- `Referer: https://www.newarkairport.com/security-wait-times`
- `Accept: application/json, text/plain, */*`
- `X-Requested-With: XMLHttpRequest`

## Response Shape

Each row includes:

- `title`
- `terminal`
- `gate`
- `queueType`
- `timeInMinutes`
- `status`
- `updateTimeText`

## Notes

- `queueType` maps to `STANDARD` for regular/general lanes and `PRECHECK` for TSA PreCheck lanes.
- Some terminals return multiple gate-group rows, so the app preserves `gate` in the checkpoint label.
