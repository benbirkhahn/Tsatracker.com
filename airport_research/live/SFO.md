# SFO — San Francisco International Airport

## Status: LIVE

## Method
Public HTML table scrape from the server-rendered wait-times page.
No auth required.

## Endpoint
```
GET https://www.flysfo.com/passengers/flight-info/security-wait-times
```

## Response Shape
The page HTML includes:
- `table.flysfo-checkpoints-table`
- `Checkpoint data last updated: ...`

## Notes
- The wait times are embedded in the rendered HTML, so a standard HTTP fetch is enough.
- Skip rows that say `Not Available`.
- The table shows both `General` and `TSA PreCheck` lanes per checkpoint.

## Auth Mode
`LIVE_PUBLIC`
