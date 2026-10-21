const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const script = fs.readFileSync(require('node:path').join(__dirname, '../static/journey-analytics.js'), 'utf8');
function setup(consent = 'granted') {
  const events = [], handlers = {}, elements = {
    plannerForm: {}, apt: { value: 'DFW' }, pre: { checked: false }, sourceCard: { dataset: { state: 'stale' } }
  };
  const document = { readyState: 'loading', getElementById: id => elements[id] || null,
    querySelector: () => null, addEventListener: (name, fn) => { handlers[name] = fn; } };
  const window = { document, __tsaAnalyticsLoaded: true, localStorage: { getItem: () => consent },
    location: { origin: 'https://tsatracker.com', pathname: '/when-should-i-leave', href: 'https://tsatracker.com/when-should-i-leave?private=secret' },
    gtag: (...args) => events.push(args) };
  vm.runInNewContext(script, { window, document, Set, URL, Date });
  return { window, events, handlers, elements };
}
test('consent is required; storage failures do not break planning', () => {
  for (const consent of ['denied', null]) {
    const s = setup(consent); s.handlers.DOMContentLoaded(); s.window.tsaAnalytics.completed('planned');
    assert.equal(s.events.length, 0);
  }
  const s = setup(); s.window.localStorage.getItem = () => { throw Error('blocked'); };
  assert.doesNotThrow(() => s.window.tsaAnalytics.completed('planned')); assert.equal(s.events.length, 0);
});
test('ordered context, completion deduplication, and no trip input values', () => {
  const s = setup(); s.handlers.DOMContentLoaded(); s.handlers['tsa:analytics-ready']();
  s.window.tsaAnalytics.completed('planned'); s.window.tsaAnalytics.completed('planned');
  assert.deepEqual(s.events.map(e => e[1]), ['airport_selected','planner_started','planner_opened','trip_details_started','plan_completed','plan_revised']);
  const event = s.events.find(e => e[1] === 'plan_completed')[2];
  assert.equal(event.airport_code, 'DFW'); assert.equal(event.source_state, 'stale');
  assert.equal(event.page_location, 'https://tsatracker.com/when-should-i-leave');
  s.window.tsaAnalytics.track('plan_submit', { flightDate: '2030-01-01', departure_time: '12:00', error_type: '<private>' });
  const data = s.events.at(-1)[2];
  assert.equal(data.flightDate, undefined); assert.equal(data.departure_time, undefined); assert.equal(data.error_type, undefined);
  assert.equal(s.window.tsaAnalytics.track('unknown_event'), false);
});
test('a past flight is an error, not a completed plan', () => {
  const s = setup(); s.window.tsaAnalytics.completed('flight_past');
  assert.equal(s.events.filter(e => e[1] === 'plan_completed').length, 0);
  assert.equal(s.events.at(-1)[2].error_type, 'flight_past');
});
test('a new airport has a separate completion, automatic context refresh does not', () => {
  const s = setup(); s.window.tsaAnalytics.completed('planned');
  s.elements.apt.value = 'MCO'; s.window.tsaAnalytics.airportSelected('MCO', 'planner');
  s.window.tsaAnalytics.completed('planned'); s.handlers['tsa:analytics-ready']();
  assert.equal(s.events.filter(e => e[1] === 'plan_completed').length, 2);
});
