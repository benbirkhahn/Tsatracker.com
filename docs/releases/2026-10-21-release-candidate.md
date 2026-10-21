# Consolidated release candidate — October 21, 2026

Status: locally verified candidate; not pushed or deployed. Branch: `codex/tsa-release-candidate`.

## Included changes

- One shared navigation and airport → terminal/lane → departure-plan journey, with searchable directories, empty-state recovery, and optional maps.
- Unknown terminal does not choose the fastest reading from a disconnected terminal. Terminal and lane carry between airport details and the planner. A conflicting checkpoint link cannot override an explicitly selected terminal.
- MCO West/East/South source aliases and explicit PreCheck classification, including legacy labels and genuine zero-minute readings.
- IAH-prefixed checkpoint names map correctly. C North Premier is classified as Priority, excluded from ordinary Standard/PreCheck recommendations. Arrivals customs is classified separately and excluded from departure waits, with an explanatory disclosure.
- DFW A7 is a separate Terminal A checkpoint, not an alias for A12. Terminal coordinates remain approximate building locations.
- SFO Checkpoint B Departure Level and Mezzanine Level remain separate physical checkpoints.
- Missing, stale, or future-dated readings cannot become current waits. Standard summaries exclude other lanes. Historical gaps remain gaps; retained raw samples rebuild Standard-only versioned aggregates without overwriting legacy aggregates.
- Planner uses flight-local dates/time zones, handles overnight trips and daylight-saving ambiguity, and keeps adjustable allowances separate from observations. Fresh higher readings only increase near-term security time.
- Manual collection requires a configured nonblank token, with constant-time comparison.

Mapping evidence: saved October 21 public API review, plus official [SFO security information](https://www.flysfo.com/flight-info/security), [DFW security information](https://www.dfwairport.com/security/), and [IAH security information](https://www.fly2houston.com/iah/security/). Source labels are covered by regression tests. Fresh upstream checks returned 10 SFO rows and 9 JFK rows, all mapped without exclusions. DFW, IAH, and MCO connection attempts timed out from this machine; their mappings were verified using saved source examples and regression tests. Fresh production checks for those three airports remain part of release verification.

## Verification

- 98 Python tests pass, including current/history lane integrity, aliases, terminal scoping, source fallback, endpoint authentication, and rendered route contracts.
- 10 Node planner tests pass: local time, DST gaps/repeats, overnight dates, zero vs missing, freshness, allowance use, and urgency.
- SEO smoke check and whitespace checks pass.
- Browser review: desktop 1440×1000 and mobile 369px; home, JFK terminal-first journey, Terminal 4 PreCheck carryover, plan calculation, DFW A7 selection, separate SFO B levels, and conflicting terminal/checkpoint links verified.
- Mobile planner has no horizontal overflow; inspected browser warning/error log empty. This is Chromium viewport testing, not a native Safari device test.
- Preview uses a separate temporary database, polling/analytics/social publishing disabled. SFO and JFK were populated from a one-time official source fetch; other airports show missing-data and allowance states. Readings expire normally. The preview does not certify deployed live feeds.

## Release procedure

Release requires a separate deployment decision. Do not push/merge automatically: main auto-deploys.

1. Review this branch against its base, `65b7f7c`.
2. Preserve the deployed SQLite database and existing `/data/data.db` configuration. Take a backup before release; do not replace production data with the local preview database.
3. Deploy the approved candidate. Check deep health, normal collection, and the MCO/IAH/DFW/SFO source mappings against fresh production rows.
4. Check airport → planner selection and stale/missing data behavior in production. Versioned historical rebuilding is incremental; initial coverage can be sparse until retained samples have been processed.
5. Rollback can use the previous deployment; legacy aggregate tables are preserved. Do not roll back the persistent-disk configuration.

Remaining follow-up: product-success analytics, external backup/restore verification, and native mobile Safari QA. Supabase activation is not included. No claims of improved conversion or live deployment are made.

Private analytics/audit exports, original patch files, and old worktree notes are excluded from this release commit. Original work was backed up before consolidation.
