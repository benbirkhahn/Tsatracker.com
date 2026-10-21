# Departure-planning measurement

Configured October 21, 2026 in GA4 property 530792269 (TSA Tracker), web stream G-9MN7W14PC1.

Saved exploration: [Airport to departure plan](https://analytics.google.com/analytics/web/#/analysis/a152900081p530792269/edit/3jk2ES5uTX2VeAhqhHp8Nw).

## Funnel

Closed, indirectly followed steps, maximum 30 minutes between adjacent steps. Breakdown by device category, with elapsed time enabled. Counts represent users, not individual trips.

1. `airport_selected`: airport context reached, including direct airport-page or planner links. It is not limited to a dropdown interaction.
2. `planner_started`: planner has a selected airport. `planner_opened` separately records arrivals before an airport is selected.
3. `trip_details_started`: first interaction with a planner input, or an explicit submit attempt using existing/default values.
4. `plan_completed`: a result rendered after an explicit submission. Passive recalculation and refresh do not count. A past-flight warning is excluded; a plan whose leave time has passed still counts with `plan_status=leave_past`.

Completion is emitted once per airport per page lifetime. Further explicit submissions emit `plan_revised`. GA4 key event `plan_completed` is counted once per session, with no monetary value. Reloading starts a new page lifetime; neither raw event totals nor the key-event count is a count of unique trips.

## Diagnosing friction

- `planner_cta_click`: link to the planner clicked.
- `routing_selected`: terminal, checkpoint, lane, or gate selection.
- `plan_submit`: explicit submit attempt (click/Enter/submit duplicates within 500ms suppressed).
- `plan_validation_error`: native invalid field, invalid/ambiguous local time, or past flight.
- `airport_data_error`: airport data request failed or timed out.
- `airport_data_retry`: visitor explicitly retries data loading.

Registered event-scoped custom dimensions: Airport code (`airport_code`), Wait source state (`source_state`), Planner error type (`error_type`), Planner error field (`error_field`). Use user counts alongside event counts; one visitor can hit several invalid fields or retry repeatedly.

Interpretation: drop-off before planner start suggests navigation or intent differences; drop-off after details start with validation errors suggests input friction; data errors suggest reliability issues. These are hypotheses, not proof of motivation. Direct airport visitors may only want a wait time and never intend to create a plan.

## Privacy and coverage

Only visitors granting the existing analytics consent are measured. No pre-consent event backlog is replayed. Consent granted mid-journey initializes the current airport/planner context. No flight date, departure time, travel duration, location, or free-text input value is sent by these custom events. Parameters are allowlisted and categorical; page_location excludes the query string. Browser blocking, declined consent and processing delay mean this is not a census of visitors.

This setup measures future activity; historical page views cannot reconstruct this funnel. Do not conclude that zero recent events means no usage before collection and GA4 processing have been verified.

## Validation

Node event-contract tests plus the existing planner tests; full Python suite; browser journey checks covering grant/decline, valid submission, native validation, revisions, past-flight exclusion, data failure/retry, mobile overflow and JavaScript errors. Browser QA stubs the external Google tag so automated test journeys are not sent to the production property.
