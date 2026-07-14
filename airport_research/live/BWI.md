# BWI — Baltimore/Washington International Airport

**Status:** ✅ Live

## Method
Public homepage security widget fetched directly from bwiairport.com.

## Endpoint
```text
GET https://bwiairport.com/
```

## Response Shape
The homepage renders a security widget with:
- `Checkpoint A`
- `Checkpoint B`
- `Checkpoint C`
- `Checkpoint D/E`

Each checkpoint shows live values for:
- General
- Priority
- TSA Pre
- Clear

## Notes
- The security page confirms the homepage widget is the source of real-time wait times.
- `Closed` values are preserved as omitted lanes instead of being coerced to zero.
- Checkpoint hours are published separately on the security page and remain part of the guidance copy.
