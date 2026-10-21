/* The time/source functions are shared by the browser and Node regression tests. */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root && root.document) { root.TripPlanner = api; api.mount(root); }
})(typeof window !== 'undefined' ? window : null, function () {
  'use strict';
  var MINUTE = 60000;
  var formatterCache = new Map();
  function partsAt(epoch, zone) {
    if (!formatterCache.has(zone)) formatterCache.set(zone, new Intl.DateTimeFormat('en-US', {
      timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
    }));
    var out = {};
    formatterCache.get(zone).formatToParts(epoch).forEach(function (part) { if (part.type !== 'literal') out[part.type] = Number(part.value); });
    return out;
  }
  function localDate(epoch, zone) {
    var p = partsAt(epoch, zone);
    return p.year + '-' + String(p.month).padStart(2, '0') + '-' + String(p.day).padStart(2, '0');
  }
  function zonedInstants(date, time, zone) {
    // Find every matching instant. A DST gap has none; a repeated hour has two.
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date || '') || !/^\d{2}:\d{2}$/.test(time || '')) return [];
    var d = date.split('-').map(Number), t = time.split(':').map(Number);
    if (d[0] < 2000 || d[1] < 1 || d[1] > 12 || d[2] < 1 || d[2] > 31 || t[0] > 23 || t[1] > 59) return [];
    var wall = Date.UTC(d[0], d[1] - 1, d[2], t[0], t[1]);
    if (new Date(wall).getUTCDate() !== d[2]) return [];
    var offsets = new Set(), matches = [];
    for (var step = -36; step <= 36; step += 6) {
      var sample = wall + step * 60 * MINUTE, p = partsAt(sample, zone);
      offsets.add(Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute) - sample);
    }
    offsets.forEach(function (offset) {
      var candidate = wall - offset, p = partsAt(candidate, zone);
      if (p.year === d[0] && p.month === d[1] && p.day === d[2] && p.hour === t[0] && p.minute === t[1]) matches.push(candidate);
    });
    return matches.sort(function (a, b) { return a - b; });
  }
  function validMinutes(value) {
    if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null;
    var n = Number(value);
    return Number.isFinite(n) && n >= 0 ? n : null;
  }
  function sourceFor(checkpoint, lane, rules, now) {
    if (!checkpoint) return { wait: null, state: 'unselected', capturedAt: null };
    var row = (checkpoint.lanes || []).find(function (r) { return r.lane_type === lane; });
    if (!row) return { wait: null, state: 'no_current_reading', capturedAt: null };
    var status = row.freshness_state || row.freshness_status;
    var wait = validMinutes(row.wait_minutes), captured = Date.parse(row.captured_at || '');
    var maxAge = Number(rules && (rules.stale_after_minutes || rules.aging_max_minutes || rules.stale_minutes)) || 15;
    var liveAge = Number(rules && (rules.live_max_minutes || rules.live_minutes)) || 5;
    var age = (now - captured) / MINUTE;
    if (status === 'published_only' || checkpoint.published_only) return { wait: null, state: 'published_only', capturedAt: null };
    if (!Number.isFinite(captured) || wait === null || age < -1 || (status !== 'live' && status !== 'aging')) {
      return { wait: null, state: status === 'stale' ? 'stale' : 'no_current_reading', capturedAt: Number.isFinite(captured) ? captured : null };
    }
    if (age > maxAge) return { wait: null, state: 'stale', capturedAt: captured };
    return { wait: wait, state: age > liveAge ? 'aging' : 'live', capturedAt: captured, label: row.source_label || 'Airport checkpoint feed' };
  }
  function buildPlan(departure, buffers, source, now) {
    var security = buffers.security;
    var readingUsed = source.wait !== null && departure > now && departure - now <= 4 * 60 * MINUTE;
    if (readingUsed) security = Math.max(security, Math.ceil(source.wait));
    var total = buffers.drive + buffers.parking + buffers.bag + security + buffers.walk + buffers.boarding;
    var leave = departure - total * MINUTE;
    return {
      departure: departure, leave: leave, airport: leave + buffers.drive * MINUTE,
      securityStart: departure - (security + buffers.walk + buffers.boarding) * MINUTE,
      gate: departure - buffers.boarding * MINUTE, total: total, security: security, readingUsed: readingUsed,
      status: departure <= now ? 'flight_past' : leave <= now ? 'leave_past' : 'planned'
    };
  }
  function mount(win) {
    var doc = win.document;
    if (!doc.getElementById('plannerForm')) return;
    var $ = function (id) { return doc.getElementById(id); };
    var airports = win.AIRPORTS || {}, initial = win.CALCULATOR_SELECTION || {};
    var model = null, requestVersion = 0, activeRequest = null, refreshTimer = null, hasPlan = false, dateTouched = false, lastDstKey = '';
    var initialTerminal = new URLSearchParams(win.location.search).get('terminal') || '';
    var fields = ['apt', 'terminal', 'checkpoint', 'pre', 'flightDate', 'dep', 'dstChoice', 'drive', 'parking', 'bag', 'bagMinutes', 'securityAllowance', 'walk', 'boarding', 'intl'];
    function code() { return $('apt').value; }
    function zone() { return (model && model.timezone) || (airports[code()] || {}).timezone || ''; }
    function lane() { return $('pre').checked ? 'PRECHECK' : 'STANDARD'; }
    function format(epoch, options) { return new Intl.DateTimeFormat('en-US', Object.assign({ timeZone: zone() }, options)).format(epoch); }
    function timeLabel(epoch) { return format(epoch, { hour: 'numeric', minute: '2-digit', timeZoneName: 'short' }); }
    function dateLabel(epoch) { return format(epoch, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }); }
    function stamp(epoch) { return dateLabel(epoch) + ' · ' + timeLabel(epoch); }
    function selectedTerminal() { return ((model || {}).terminals || []).find(function (t) { return t.id === $('terminal').value; }); }
    function selectedCheckpoint() { return ((selectedTerminal() || {}).checkpoints || []).find(function (c) { return c.id === $('checkpoint').value; }); }
    function currentSource() { return sourceFor(selectedCheckpoint(), lane(), (model || {}).freshness_rules, Date.now()); }
    function setOptions(select, label, rows, value) {
      select.replaceChildren(new Option(label, ''));
      rows.forEach(function (r) { select.add(new Option(r.label, r.id)); });
      select.value = rows.some(function (r) { return r.id === value; }) ? value : '';
    }
    function updateLinks() {
      var href = code() ? '/airports/' + code().toLowerCase() + '-tsa-wait-times' : '/airports';
      var params = new URLSearchParams();
      if ($('terminal').value) params.set('terminal', $('terminal').value);
      if ($('checkpoint').value) params.set('checkpoint', $('checkpoint').value);
      params.set('lane', lane());
      if (code()) href += '?' + params.toString();
      $('airportLink').href = href; $('recheckLink').href = href;
      var url = new URL(win.location.href);
      ['airport', 'terminal', 'checkpoint', 'lane'].forEach(function (key) { url.searchParams.delete(key); });
      if (code()) {
        url.searchParams.set('airport', code()); url.searchParams.set('lane', lane());
        if ($('terminal').value) url.searchParams.set('terminal', $('terminal').value);
        if ($('checkpoint').value) url.searchParams.set('checkpoint', $('checkpoint').value);
      }
      win.history.replaceState(null, '', url.pathname + url.search + url.hash);
    }
    function updateClock() {
      if (!zone()) { $('airportTimezone').textContent = 'Choose an airport to set the flight’s local time zone.'; return; }
      if (!dateTouched) $('flightDate').value = localDate(Date.now(), zone());
      $('airportTimezone').textContent = 'Flight time and every result use ' + code() + ' local time (' + zone().replace(/_/g, ' ') + ').';
    }
    function updateSource() {
      var cp = selectedCheckpoint(), source = currentSource(), laneName = lane() === 'PRECHECK' ? 'PreCheck' : 'Standard';
      $('sourceCard').hidden = !code();
      $('sourceCard').dataset.state = source.state;
      $('sourceLabel').textContent = laneName + ' security · ' + (cp ? cp.label : 'Checkpoint not selected');
      if (source.wait !== null) {
        $('sourceReading').textContent = Math.round(source.wait) + ' min observed';
        $('sourceDetail').textContent = source.label + ' · ' + (source.state === 'aging' ? 'Older reading, captured ' : 'Captured ') + stamp(source.capturedAt) + '. This is a current observation, not a forecast.';
      } else {
        $('sourceReading').textContent = source.state === 'unselected' ? 'Plan with your security allowance' : 'Current wait unavailable';
        var why = source.state === 'stale' ? 'The last reading is too old to use. ' : source.state === 'published_only' ? 'This airport publishes checkpoint information without a live reading. ' : '';
        $('sourceDetail').textContent = why + 'Your plan will use the security allowance you choose below.';
      }
      $('checkpointNote').textContent = cp ? [cp.note, cp.hours ? 'Published hours: ' + cp.hours : ''].filter(Boolean).join(' ') : '';
      updateLinks();
    }
    function populateCheckpoints(wanted, preserveEmpty) {
      var terminal = selectedTerminal(), checkpoints = (terminal || {}).checkpoints || [];
      setOptions($('checkpoint'), terminal ? 'Not sure yet / use an allowance' : 'Choose a terminal first', checkpoints, wanted);
      if (!preserveEmpty && !wanted && checkpoints.length === 1) $('checkpoint').value = checkpoints[0].id;
      $('checkpoint').disabled = checkpoints.length === 0;
      updateSource();
    }
    function populateModel(next, wantedCheckpoint, wantedTerminal, preserveSelection) {
      model = next;
      var terminals = next.terminals || [], owner = terminals.find(function (t) { return (t.checkpoints || []).some(function (cp) { return cp.id === wantedCheckpoint; }); });
      if (owner && wantedTerminal && owner.id !== wantedTerminal) { wantedCheckpoint = ''; owner = null; }
      setOptions($('terminal'), 'Not sure yet / use an allowance', terminals, wantedTerminal || (owner ? owner.id : ''));
      if (!preserveSelection && !owner && !wantedTerminal && terminals.length === 1) $('terminal').value = terminals[0].id;
      $('terminal').disabled = terminals.length === 0;
      $('airportStatus').textContent = next.routing_note || 'Choose the terminal on your booking, then a checkpoint serving your gate.';
      if (!terminals.length) $('airportStatus').textContent = 'Checkpoint details are unavailable. You can still plan with your own security allowance.';
      populateCheckpoints(wantedCheckpoint, preserveSelection); updateClock();
    }
    async function loadAirport(wantedCheckpoint, wantedTerminal, refresh) {
      var selectedCode = code(), thisRequest = ++requestVersion;
      if (activeRequest) activeRequest.abort();
      if (refreshTimer) win.clearTimeout(refreshTimer);
      $('retryAirport').hidden = true;
      if (!selectedCode) {
        model = null; setOptions($('terminal'), 'Choose an airport first', [], ''); $('terminal').disabled = true;
        populateCheckpoints(''); updateClock(); return;
      }
      if (!refresh) {
        model = null; setOptions($('terminal'), 'Loading terminals…', [], ''); $('terminal').disabled = true;
        setOptions($('checkpoint'), 'Loading checkpoints…', [], ''); $('checkpoint').disabled = true;
        updateClock(); updateSource();
      }
      $('airportStatus').textContent = refresh ? 'Refreshing checkpoint readings…' : 'Loading terminals and checkpoint readings…';
      $('sourceCard').setAttribute('aria-busy', 'true');
      var controller = new AbortController(); activeRequest = controller;
      var timeout = win.setTimeout(function () { controller.abort(); }, 12000);
      try {
        var response = await win.fetch('/api/airport-arrival-mode?airport=' + encodeURIComponent(selectedCode), { signal: controller.signal, cache: 'no-store' });
        if (!response.ok) throw new Error('checkpoint response');
        var payload = await response.json();
        if (thisRequest !== requestVersion || selectedCode !== code()) return;
        if (payload.code !== selectedCode || !Array.isArray(payload.terminals)) throw new Error('checkpoint data');
        populateModel(payload, refresh ? $('checkpoint').value : wantedCheckpoint, refresh ? $('terminal').value : wantedTerminal, refresh);
        refreshTimer = win.setTimeout(function () { loadAirport($('checkpoint').value, $('terminal').value, true); }, Math.max(30000, Math.min(120000, (payload.refresh_seconds || 120) * 1000)));
      } catch (error) {
        if (thisRequest !== requestVersion) return;
        $('airportStatus').textContent = 'We could not refresh checkpoint readings. You can still build a plan with your security allowance.';
        $('retryAirport').hidden = false;
        // Keep routing choices, but never present cached readings as newly refreshed.
        if (model) model.terminals.forEach(function (t) { (t.checkpoints || []).forEach(function (cp) { (cp.lanes || []).forEach(function (r) { r.freshness_state = 'no_current_reading'; }); }); });
        else { setOptions($('terminal'), 'Details unavailable', [], ''); setOptions($('checkpoint'), 'Use a planning allowance', [], ''); }
        updateSource();
      } finally {
        win.clearTimeout(timeout);
        if (thisRequest === requestVersion) { $('sourceCard').removeAttribute('aria-busy'); if (hasPlan) calculate(false); }
      }
    }
    function fail(message, interactive, focusId) {
      $('plannerError').textContent = message; $('plannerError').hidden = !message;
      $('resultContent').hidden = true; $('resultPlaceholder').hidden = false;
      $('planResult').setAttribute('aria-labelledby', 'planResultTitle');
      if (interactive && focusId) $(focusId).focus();
      return null;
    }
    function departureInstant(interactive) {
      if (!zone()) return fail('Choose an airport with an available local time zone.', interactive, 'apt');
      var matches = zonedInstants($('flightDate').value, $('dep').value, zone());
      var key = code() + $('flightDate').value + $('dep').value;
      if (lastDstKey !== key) { $('dstChoice').value = ''; lastDstKey = key; }
      $('dstChoiceField').hidden = matches.length !== 2;
      if (!matches.length) return fail('That local date and time does not exist. Check your ticket, including any daylight saving change.', interactive, 'dep');
      if (matches.length === 2) {
        var old = $('dstChoice').value;
        setOptions($('dstChoice'), 'Choose the time zone shown on your ticket', matches.map(function (epoch) { return { id: String(epoch), label: timeLabel(epoch) }; }), old);
        if (!$('dstChoice').value) return fail('This local time occurs twice. Choose the time zone shown on your ticket.', interactive, 'dstChoice');
        return Number($('dstChoice').value);
      }
      return matches[0];
    }
    function addText(parent, tag, text, className) {
      var el = doc.createElement(tag); el.textContent = text; if (className) el.className = className; parent.appendChild(el); return el;
    }
    function calculate(interactive) {
      if (!$('plannerForm').checkValidity()) { if (interactive) $('plannerForm').reportValidity(); return fail('', false); }
      var departure = departureInstant(interactive); if (departure === null) return;
      var source = currentSource(), now = Date.now();
      var buffers = { drive: +$('drive').value, parking: +$('parking').value, bag: $('bag').checked ? +$('bagMinutes').value : 0, security: +$('securityAllowance').value, walk: +$('walk').value, boarding: +$('boarding').value };
      var plan = buildPlan(departure, buffers, source, now);
      hasPlan = true; dateTouched = true; $('plannerError').hidden = true; $('resultPlaceholder').hidden = true; $('resultContent').hidden = false;
      $('planResult').setAttribute('aria-labelledby', 'leaveLabel');
      $('resultContext').textContent = [code(), (selectedTerminal() || {}).label, (selectedCheckpoint() || {}).label, lane() === 'PRECHECK' ? 'PreCheck' : 'Standard'].filter(function (label, index, values) { return label && values.indexOf(label) === index; }).join(' · ');
      $('leave').textContent = timeLabel(plan.leave);
      $('leaveDate').textContent = dateLabel(plan.leave) + (localDate(plan.leave, zone()) !== localDate(plan.departure, zone()) ? ' · Before your flight date' : '');
      $('leaveLabel').textContent = plan.status === 'flight_past' ? 'This flight time has passed' : plan.status === 'leave_past' ? 'Your planned leave time has passed' : 'Plan to leave by';
      $('verdict').dataset.status = plan.status;
      $('verdict').textContent = plan.status === 'flight_past' ? 'Check the flight date and time. This plan is in the past.' : plan.status === 'leave_past' ? 'You are ' + Math.ceil((now - plan.leave) / MINUTE) + ' min past this plan’s leave time. Recheck your route and airline deadlines now.' : 'Based on the time you allowed for each step. Recheck your route and airport before leaving.';
      $('timeline').replaceChildren();
      [['Leave for airport', plan.leave], ['Arrive at airport', plan.airport], ['Reach security', plan.securityStart], ['Be at your gate', plan.gate], ['Flight departs', plan.departure]].forEach(function (step) {
        var row = addText($('timeline'), 'li', ''); addText(row, 'span', step[0]); var tm = addText(row, 'time', stamp(step[1])); tm.dateTime = new Date(step[1]).toISOString();
      });
      $('bk').replaceChildren();
      [['Travel', buffers.drive], ['Parking / transfer', buffers.parking], ['Bag drop', buffers.bag], ['Security allowance', plan.security], ['Walk to gate', buffers.walk], ['At gate before departure', buffers.boarding], ['Total time before flight', plan.total]].forEach(function (item) {
        var row = addText($('bk'), 'div', '', 'bk-row'); addText(row, 'span', item[0]); addText(row, 'span', item[1] + ' min');
      });
      var sourceText = 'Security: ' + plan.security + ' min planning allowance. ';
      if (plan.readingUsed && source.wait > buffers.security) sourceText += 'Raised from your ' + buffers.security + ' min allowance to cover the current ' + Math.round(source.wait) + ' min checkpoint reading.';
      else if (plan.readingUsed) sourceText += 'The current ' + Math.round(source.wait) + ' min reading is within your allowance. It may change before you arrive.';
      else if (source.wait !== null) sourceText += 'The current ' + Math.round(source.wait) + ' min observation is not used to predict a later trip.';
      else sourceText += 'No usable current reading for your selection; this is the time you chose.';
      $('srcNote').textContent = sourceText;
      $('resultTimezone').textContent = 'Every time above is in ' + code() + ' local time (' + zone().replace(/_/g, ' ') + '), including your leave time.';
      $('resultAnnouncement').textContent = $('leaveLabel').textContent + ': ' + stamp(plan.leave) + '. Arrive at airport ' + stamp(plan.airport) + '. ' + $('verdict').textContent;
      if (interactive) { $('planResult').focus({ preventScroll: true }); $('planResult').scrollIntoView({ behavior: win.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' }); }
    }
    $('plannerForm').addEventListener('submit', function (event) { event.preventDefault(); calculate(true); });
    $('apt').addEventListener('change', function () { hasPlan = false; fail('', false); loadAirport('', '', false); });
    $('terminal').addEventListener('change', function () { populateCheckpoints(''); if (hasPlan) calculate(false); });
    $('checkpoint').addEventListener('change', function () { updateSource(); if (hasPlan) calculate(false); });
    $('pre').addEventListener('change', function () { updateSource(); if (hasPlan) calculate(false); });
    $('bag').addEventListener('change', function () { $('bagMinutes').disabled = !$('bag').checked; if (hasPlan) calculate(false); });
    $('intl').addEventListener('change', function () { if (['45', '60'].indexOf($('boarding').value) >= 0) $('boarding').value = $('intl').checked ? '60' : '45'; if (hasPlan) calculate(false); });
    $('flightDate').addEventListener('input', function () { dateTouched = true; });
    $('dep').addEventListener('input', function () { dateTouched = true; });
    fields.filter(function (id) { return ['apt', 'terminal', 'checkpoint', 'pre', 'bag', 'intl'].indexOf(id) < 0; }).forEach(function (id) { $(id).addEventListener('input', function () { if (hasPlan) calculate(false); }); });
    $('retryAirport').addEventListener('click', function () { loadAirport($('checkpoint').value, $('terminal').value, Boolean(model)); });
    $('editPlan').addEventListener('click', function () { $('apt').focus(); $('plannerForm').scrollIntoView({ block: 'start' }); });
    // Expire observations even while the tab remains open and refresh when it regains focus.
    win.setInterval(function () { if (!doc.hidden && code()) { updateSource(); if (hasPlan) calculate(false); } }, 30000);
    doc.addEventListener('visibilitychange', function () { if (!doc.hidden && code()) loadAirport($('checkpoint').value, $('terminal').value, Boolean(model)); });
    if (initial.airport && Object.prototype.hasOwnProperty.call(airports, initial.airport)) $('apt').value = initial.airport;
    $('pre').checked = initial.lane === 'PRECHECK';
    if (code()) {
      var embedded = win.CALCULATOR_CHECKPOINTS;
      if (embedded && embedded.code === code() && Array.isArray(embedded.terminals)) populateModel(embedded, initial.checkpoint || '', initialTerminal);
      loadAirport(initial.checkpoint || '', initialTerminal, Boolean(model));
    } else updateClock();
  }
  return { zonedInstants: zonedInstants, localDate: localDate, sourceFor: sourceFor, buildPlan: buildPlan, mount: mount };
});
