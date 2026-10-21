/* Historical observations only. Missing hours remain gaps, never zeroes. */
(function () {
  "use strict";
  var mount = document.getElementById("tsa-forecast");
  if (!mount) return;
  var code = (mount.dataset.airport || "").toUpperCase();
  function escape(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (character) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character];
    });
  }
  function numeric(value) {
    if (value === null || value === undefined || value === "" || typeof value === "boolean") return null;
    var number = Number(value);
    return Number.isFinite(number) && number >= 0 ? number : null;
  }
  function hourLabel(hour) { return (hour % 12 || 12) + (hour < 12 ? " AM" : " PM"); }
  function valueLabel(value) { var number = numeric(value); return number === null ? "No observations" : Math.round(number * 10) / 10 + " min"; }
  function fail() {
    mount.innerHTML = '<section class="airport-history-card"><h2>Typical waits</h2><p class="airport-history-empty" role="status">Historical observations are unavailable right now. Check the current reading above or try again later.</p></section>';
  }
  function chart(hours) {
    var values = [];
    hours.forEach(function (row) { [row.standard, row.precheck].forEach(function (value) { if (numeric(value) !== null) values.push(Number(value)); }); });
    if (!values.length) return '<p class="airport-history-empty">No historical observations are available for this airport. Missing data is not a zero-minute wait.</p>';
    var width = 800, height = 270, left = 42, right = 24, top = 24, bottom = 36;
    var maximum = Math.max(30, Math.ceil(Math.max.apply(null, values) / 15) * 15);
    var x = function (hour) { return left + hour / 23 * (width - left - right); };
    var y = function (value) { return top + (1 - value / maximum) * (height - top - bottom); };
    var svg = '<svg viewBox="0 0 800 270" role="img" aria-labelledby="typical-chart-title typical-chart-description"><title id="typical-chart-title">Observed average waits by airport local hour</title><desc id="typical-chart-description">Standard and PreCheck history. Gaps mean no observations. Exact values and sample counts are available in the table below.</desc>';
    for (var tick = 0; tick <= maximum; tick += maximum / 3) {
      svg += '<line x1="' + left + '" x2="' + (width-right) + '" y1="' + y(tick) + '" y2="' + y(tick) + '" stroke="#334451"/><text x="' + (left-8) + '" y="' + (y(tick)+4) + '" text-anchor="end" fill="#a8b9c5" font-size="11">' + Math.round(tick) + '</text>';
    }
    [0,4,8,12,16,20,23].forEach(function (hour) { svg += '<text x="' + x(hour) + '" y="258" text-anchor="middle" fill="#a8b9c5" font-size="11">' + hourLabel(hour) + '</text>'; });
    ["standard", "precheck"].forEach(function (lane) {
      var path = "", connected = false, dots = "", color = lane === "standard" ? "#5fe1bd" : "#edaa73";
      hours.forEach(function (row) {
        var value = numeric(row[lane]);
        if (value === null) { connected = false; return; }
        path += (connected ? "L" : "M") + x(row.hour).toFixed(1) + " " + y(value).toFixed(1) + " ";
        connected = true;
        dots += '<circle cx="' + x(row.hour) + '" cy="' + y(value) + '" r="3" fill="' + color + '"/>';
      });
      svg += '<path d="' + path + '" fill="none" stroke="' + color + '" stroke-width="2.5"' + (lane === "precheck" ? ' stroke-dasharray="5 4"' : '') + '/>' + dots;
    });
    return svg + '</svg>';
  }
  function render(data) {
    var byHour = {};
    (data.hours || []).forEach(function (row) { if (Number.isInteger(row.hour) && row.hour >= 0 && row.hour < 24) byHour[row.hour] = row; });
    var hours = Array.from({length: 24}, function (_, hour) { return byHour[hour] || {hour: hour, standard: null, precheck: null}; });
    var standardHours = hours.filter(function (row) { return numeric(row.standard) !== null; }).length;
    var precheckHours = hours.filter(function (row) { return numeric(row.precheck) !== null; }).length;
    var coverage = data.coverage || {};
    var timezone = data.timezone || "airport local time";
    var coverageText = 'Standard: ' + standardHours + '/24 hours with observations. PreCheck: ' + precheckHours + '/24 hours.';
    if (numeric(coverage.daysWithSamples) !== null) coverageText += ' Observations on ' + coverage.daysWithSamples + ' of the last ' + (data.days || 30) + ' days.';
    var rows = hours.map(function (row) {
      return '<tr><th scope="row">' + hourLabel(row.hour) + '</th><td>' + valueLabel(row.standard) + '</td><td>' + (numeric(row.standardSamples) === null ? '—' : escape(row.standardSamples)) + '</td><td>' + valueLabel(row.precheck) + '</td><td>' + (numeric(row.precheckSamples) === null ? '—' : escape(row.precheckSamples)) + '</td></tr>';
    }).join('');
    mount.innerHTML = '<section class="airport-history-card" aria-labelledby="typical-waits-title"><h2 id="typical-waits-title">Typical waits</h2>' +
      '<p class="airport-history-source">Recorded airport checkpoint observations from the past ' + escape(data.days || 30) + ' days, grouped by hour in ' + escape(timezone) + '. These airport-wide averages describe past readings and do not predict your flight’s wait.</p>' +
      '<p class="airport-history-coverage">' + escape(coverageText) + '</p><div class="airport-history-chart">' + chart(hours) + '</div>' +
      '<div class="airport-history-legend"><span><i aria-hidden="true"></i>Standard</span><span><i class="precheck" aria-hidden="true"></i>PreCheck</span><span>Gaps = no observations</span></div>' +
      '<details class="airport-history-table"><summary>View hourly values and sample counts</summary><div class="airport-history-table-scroll"><table><caption>' + escape(code) + ' historical averages in ' + escape(timezone) + '. Samples are recorded readings, not individual travelers.</caption><thead><tr><th scope="col">Local hour</th><th scope="col">Standard</th><th scope="col">Samples</th><th scope="col">PreCheck</th><th scope="col">Samples</th></tr></thead><tbody>' + rows + '</tbody></table></div></details></section>';
  }
  fetch('/api/forecast-data?airport=' + encodeURIComponent(code))
    .then(function (response) { if (!response.ok) throw new Error('History unavailable'); return response.json(); })
    .then(function (data) { if (!data || !Array.isArray(data.hours)) throw new Error('History unavailable'); render(data); })
    .catch(fail);
})();
