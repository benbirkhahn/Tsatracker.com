# Analytics configuration change log

This public log records changes without account identifiers, private traffic reports or operational audit findings. Keep detailed usage analysis in a private record.

## 2026-10-19 — external GA4 key-event classification correction

**Reason:** Standard activity events were classified as key events, making automatic visits look like completed product goals.

**Changed outside this repository:** Unmarked `click`, `first_visit`, `page_view`, `scroll`, `session_start` and `user_engagement` as GA4 key events. The platform's locked default `purchase` entry was left unchanged. Underlying event collection was not disabled.

**Verification:** Reloaded GA4 Admin > Events and verified those six names no longer appear under Key events.

**Scope:** No site code, tag loader, consent behavior, access permissions or deployment changed as part of this correction. No new product outcome event has yet been implemented.

**Reporting boundary:** The change affects future key-event/conversion classification, including linked accounts. It does not repair historical conversion, engagement or bounce metrics. Avoid comparing periods across this boundary as though definitions were unchanged.

**Rollback:** In GA4 Admin > Events > Recent events, star the same six names again only if intentionally reverting the definition. Reinstating automatic events as outcomes is not recommended.

## Future instrumentation plan — not implemented

Distinguish intermediate actions (airport, terminal and lane selection, calculator start and map interaction) from successful outcomes (valid selected wait result displayed; valid leave-time calculation completed). Implement and validate actual UI behavior before marking outcomes as key events. Preserve optional consent, avoid duplicate tags and do not send personal information or user-entered travel details. Do not upload behavior captured before consent.

## Handover template

For each change record:
- Date and user request/problem
- Evidence and decision
- Source files or external setting changed
- Commit, deployment and production-verification status separately
- Verification and limitations
- Rollback
- Remaining work and private evidence location when applicable

Never claim code is deployed merely because it is committed, or that a configuration correction repairs historical data.
