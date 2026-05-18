# SFO — San Francisco International Airport

## Status: SUPERSEDED

## Investigated
- Initial probes found the wait-times page and ruled out obvious API-style endpoints.
- Later verification showed the public wait-time table is present in the server-rendered HTML.

## Conclusion
The wait-time data is publicly readable from the rendered HTML table, so
the live integration uses a standard HTTP scrape.

## Next Steps
- See `airport_research/live/SFO.md` for the live integration details.
