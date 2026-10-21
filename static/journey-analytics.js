/* Consent-gated product events. No trip dates/times, locations, or free text. */
(function (win, doc) {
  'use strict';
  var sent = new Set(), lastSubmit = 0;
  var names = new Set(['airport_selected', 'planner_opened', 'planner_started', 'trip_details_started',
    'planner_cta_click', 'routing_selected', 'plan_submit', 'plan_completed', 'plan_revised',
    'plan_validation_error', 'airport_data_error', 'airport_data_retry']);
  var fields = new Set(['apt', 'terminal', 'checkpoint', 'pre', 'flightDate', 'dep', 'dstChoice',
    'drive', 'parking', 'bag', 'bagMinutes', 'securityAllowance', 'walk', 'boarding', 'intl']);
  function context() {
    var planner = doc.getElementById('plannerForm');
    var root = doc.querySelector('[data-airport-arrival-mode]');
    var airport = planner ? doc.getElementById('apt').value : root ? root.dataset.airportCode : '';
    var source = doc.getElementById('sourceCard');
    return { airport_code: /^[A-Z]{3}$/.test(airport) ? airport : 'none',
      entry_point: planner ? 'planner' : root ? 'airport_page' : 'site',
      source_state: source ? source.dataset.state || 'unknown' : root ? root.dataset.sourceState || 'unknown' : 'unknown',
      lane: planner ? (doc.getElementById('pre').checked ? 'PRECHECK' : 'STANDARD') :
        ((doc.querySelector('[name="decision-lane"]:checked') || {}).value || 'unknown').toUpperCase() };
  }
  function track(name, params, once) {
    if (!win.__tsaAnalyticsLoaded || typeof win.gtag !== 'function' || !names.has(name)) return false;
    try { if (win.localStorage.getItem('tsaTrackerAnalyticsConsent') !== 'granted') return false; } catch (_) { return false; }
    if (once && sent.has(once)) return false;
    var values = Object.assign(context(), params || {}), safe = { funnel_version: 'v1' };
    ['airport_code', 'entry_point', 'source_state', 'lane', 'selection_type', 'error_field', 'error_type', 'plan_status'].forEach(function (key) {
      var value = values[key];
      if (typeof value === 'string' && /^[a-zA-Z0-9_]{1,40}$/.test(value)) safe[key] = value;
    });
    // Never include query parameters in analytics URLs (including future trip inputs).
    safe.page_location = win.location.origin + win.location.pathname;
    if (once) sent.add(once);
    win.gtag('event', name, safe);
    return true;
  }
  function airportSelected(code, entry) {
    if (!/^[A-Z]{3}$/.test(code || '')) return;
    track('airport_selected', { airport_code: code, entry_point: entry }, 'airport:' + code);
    if (doc.getElementById('plannerForm')) track('planner_started', { airport_code: code }, 'planner:' + code);
  }
  function detailsStarted() {
    var code = context().airport_code;
    if (code !== 'none') {
      airportSelected(code, 'planner');
      track('trip_details_started', {}, 'details:' + code);
    }
  }
  function submitAttempt() {
    detailsStarted();
    if (Date.now() - lastSubmit > 500) track('plan_submit');
    lastSubmit = Date.now();
  }
  win.tsaAnalytics = { track: track, airportSelected: airportSelected,
    completed: function (status) {
      detailsStarted();
      // Past-flight results ask the visitor to fix their inputs; they are not successful plans.
      if (status === 'flight_past') { track('plan_validation_error', { error_field: 'flightDate', error_type: 'flight_past' }); return; }
      var key = 'completed:' + context().airport_code;
      if (!track('plan_completed', { plan_status: status }, key)) {
        if (sent.has(key)) track('plan_revised', { plan_status: status });
      }
    }
  };
  function initializeContext() {
    airportSelected(context().airport_code, context().entry_point);
    if (doc.getElementById('plannerForm')) track('planner_opened', {}, 'opened');
  }
  doc.addEventListener('tsa:analytics-ready', initializeContext);
  doc.addEventListener('change', function (event) {
    var target = event.target;
    if (target.id === 'apt') airportSelected(target.value, 'planner');
    var selection = { terminal: 'terminal', checkpoint: 'checkpoint', pre: 'lane',
      'decision-terminal': 'terminal', 'decision-lane': 'lane', 'decision-gate': 'gate' }[target.name || target.id];
    if (selection) track('routing_selected', { selection_type: selection });
    if (target.closest('#plannerForm') && fields.has(target.id)) detailsStarted();
  });
  doc.addEventListener('input', function (event) {
    if (event.target.closest('#plannerForm') && fields.has(event.target.id)) detailsStarted();
  });
  doc.addEventListener('click', function (event) {
    var target = event.target.closest('a,button');
    if (!target) return;
    if (target.matches('#plannerForm [type="submit"]')) submitAttempt();
    if (target.matches('[data-arrival-checkpoint-choice]')) track('routing_selected', { selection_type: 'checkpoint' });
    if (target.tagName === 'A') {
      var url = new URL(target.href, win.location.href);
      if (url.origin === win.location.origin && url.pathname === '/when-should-i-leave') track('planner_cta_click');
    }
  });
  doc.addEventListener('keydown', function (event) {
    if (event.key === 'Enter' && event.target.closest('#plannerForm') && event.target.tagName !== 'BUTTON') submitAttempt();
  });
  doc.addEventListener('submit', function (event) { if (event.target.id === 'plannerForm') submitAttempt(); });
  doc.addEventListener('invalid', function (event) {
    if (Date.now() - lastSubmit < 1000 && fields.has(event.target.id)) {
      track('plan_validation_error', { error_field: event.target.id, error_type: 'invalid_field' });
    }
  }, true);
  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', initializeContext);
  else initializeContext();
})(window, document);
