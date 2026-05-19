# DCA — Ronald Reagan Washington National Airport

**Status:** ✅ Live

## Method
Public JSON endpoint fetched directly from the official airport page.

## Endpoint
```text
GET https://www.flyreagan.com/security-wait-times
```

## Response Shape
The endpoint returns JSON with:
- `response.res` containing checkpoint rows
- `response.header` containing column labels

Example checkpoints:
- Terminal 1
- Terminal 2 South
- Terminal 2 North

Each row includes:
- `location`
- `gates`
- `waittime`
- optional `pre`
- optional `pre_disabled`
- `url`

## Notes
- The page renders a live table with General and TSA Pre columns.
- The response is publicly accessible with a standard browser request.
- General and TSA Pre values are kept as separate rows in the collector.

