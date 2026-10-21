'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { zonedInstants, localDate, sourceFor, buildPlan } = require('../static/planner.js');
const now = Date.parse('2026-10-02T16:00:00Z');
const buffers = { drive: 30, parking: 10, bag: 20, security: 30, walk: 15, boarding: 45 };
const noSource = { wait: null, state: 'no_current_reading' };
function checkpoint(overrides) {
  return { lanes: [{ lane_type: 'STANDARD', wait_minutes: 40, freshness_state: 'live', captured_at: '2026-10-02T15:59:00Z', ...overrides }] };
}
test('flight-local conversion is independent of the browser time zone', () => {
  assert.equal(zonedInstants('2026-10-02', '18:00', 'America/New_York')[0], Date.parse('2026-10-02T22:00:00Z'));
  assert.equal(zonedInstants('2026-10-02', '18:00', 'America/Los_Angeles')[0], Date.parse('2026-10-03T01:00:00Z'));
  assert.equal(localDate(Date.parse('2026-10-03T01:00:00Z'), 'America/Los_Angeles'), '2026-10-02');
});
test('overnight departure plan keeps the previous date', () => {
  const dep = zonedInstants('2026-10-03', '00:30', 'America/New_York')[0];
  const result = buildPlan(dep, buffers, noSource, now);
  assert.equal(result.total, 150);
  assert.equal(result.leave, Date.parse('2026-10-03T02:00:00Z'));
  assert.equal(localDate(result.leave, 'America/New_York'), '2026-10-02');
  assert.equal(result.airport, result.leave + 30 * 60000);
  assert.equal(result.gate, dep - 45 * 60000);
});
test('DST spring gap is rejected and autumn repeat requires explicit occurrence', () => {
  assert.deepEqual(zonedInstants('2026-03-08', '02:30', 'America/New_York'), []);
  assert.deepEqual(zonedInstants('2026-11-01', '01:30', 'America/New_York'), [Date.parse('2026-11-01T05:30:00Z'), Date.parse('2026-11-01T06:30:00Z')]);
  assert.equal(zonedInstants('2026-03-08', '03:30', 'America/New_York')[0], Date.parse('2026-03-08T07:30:00Z'));
});
test('invalid calendar days and incomplete times are rejected', () => {
  for (const [date, time] of [['2026-02-30', '10:00'], ['2026-10-02', '25:00'], ['', '12:00'], ['2026-10-02', '']]) assert.deepEqual(zonedInstants(date, time, 'America/New_York'), []);
});
test('zero is valid, missing is unavailable, and PreCheck never inherits Standard', () => {
  assert.equal(sourceFor(checkpoint({ wait_minutes: 0 }), 'STANDARD', {}, now).wait, 0);
  assert.equal(sourceFor(checkpoint({ wait_minutes: null }), 'STANDARD', {}, now).wait, null);
  assert.equal(sourceFor(checkpoint({ wait_minutes: '' }), 'STANDARD', {}, now).wait, null);
  assert.equal(sourceFor(checkpoint(), 'PRECHECK', {}, now).wait, null);
  assert.equal(sourceFor(null, 'STANDARD', {}, now).state, 'unselected');
});
test('open-tab readings expire against the capture time and shared thresholds', () => {
  assert.equal(sourceFor(checkpoint(), 'STANDARD', {}, now).wait, 40);
  assert.equal(sourceFor(checkpoint(), 'STANDARD', {}, now + 6 * 60000).state, 'aging');
  assert.equal(sourceFor(checkpoint(), 'STANDARD', {}, now + 15 * 60000).state, 'stale');
  assert.equal(sourceFor(checkpoint(), 'STANDARD', { stale_after_minutes: 1 }, now + 60000).wait, null);
  assert.equal(sourceFor(checkpoint({ captured_at: '2026-10-02T16:05:00Z' }), 'STANDARD', {}, now).wait, null);
  assert.equal(sourceFor(checkpoint({ captured_at: '' }), 'STANDARD', {}, now).wait, null);
});
test('published context and stale numeric values are never used as current observations', () => {
  assert.equal(sourceFor({ ...checkpoint(), published_only: true }, 'STANDARD', {}, now).wait, null);
  assert.equal(sourceFor(checkpoint({ freshness_state: 'stale' }), 'STANDARD', {}, now).wait, null);
});
test('security uses the larger allowance for near trips and never invents future predictions', () => {
  const near = now + 3 * 60 * 60000;
  assert.equal(buildPlan(near, buffers, { wait: 60 }, now).security, 60);
  assert.equal(buildPlan(near, buffers, { wait: 2 }, now).security, 30);
  assert.equal(buildPlan(near, buffers, noSource, now).security, 30);
  assert.equal(buildPlan(now + 24 * 60 * 60000, buffers, { wait: 60 }, now).security, 30);
});
test('past leave and past flights have distinct urgent states', () => {
  assert.equal(buildPlan(now + 60 * 60000, buffers, noSource, now).status, 'leave_past');
  assert.equal(buildPlan(now - 60 * 60000, buffers, noSource, now).status, 'flight_past');
  assert.equal(buildPlan(now + 180 * 60000, buffers, noSource, now).status, 'planned');
});
test('buffer durations remain elapsed minutes across a DST jump', () => {
  const dep = zonedInstants('2026-03-08', '04:00', 'America/New_York')[0];
  const plan = buildPlan(dep, buffers, noSource, Date.parse('2026-03-07T12:00:00Z'));
  assert.equal(plan.departure - plan.leave, 150 * 60000);
  assert.equal(plan.leave, Date.parse('2026-03-08T05:30:00Z'));
});
