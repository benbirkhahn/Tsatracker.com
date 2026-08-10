/* TSA Tracker — airport forecast + heatmap.
   Mounts on #tsa-forecast[data-airport], fed by /api/forecast-data.
   Self-contained (injects its own dark "Midnight" styling). */
(function () {
  var mount = document.getElementById("tsa-forecast");
  if (!mount) return;
  var code = (mount.dataset.airport || "").toUpperCase();

  injectStyles();
  mount.innerHTML =
    '<div class="tsafc">' +
      '<section class="tsafc-card">' +
        '<span class="tsafc-badge">' + code + ' · live history</span>' +
        '<h3 class="tsafc-h">24-hour forecast</h3>' +
        '<div class="tsafc-sub">predicted wait · standard vs PreCheck</div>' +
        '<div class="tsafc-chart" id="tsafc-line"><div class="tsafc-empty">Loading…</div></div>' +
        '<div class="tsafc-legend">' +
          '<span><i class="sw std"></i>Standard</span>' +
          '<span><i class="sw pre"></i>PreCheck</span>' +
          '<span><i class="sw now"></i>Now</span>' +
          '<span><i class="sw best"></i>Best window</span>' +
        '</div>' +
      '</section>' +
      '<section class="tsafc-card">' +
        '<h3 class="tsafc-h">Typical waits by day &amp; hour</h3>' +
        '<div class="tsafc-sub">last 30 days</div>' +
        '<div class="tsafc-heatwrap"><div class="tsafc-rows" id="tsafc-rows"></div><div class="tsafc-grid" id="tsafc-grid"></div></div>' +
        '<div class="tsafc-x" id="tsafc-x"></div>' +
      '</section>' +
    '</div>';

  fetch("/api/forecast-data?airport=" + encodeURIComponent(code))
    .then(function (r) { return r.json(); })
    .then(function (d) { if (d && d.hours) render(d); else fail(); })
    .catch(fail);

  function fail() {
    var el = document.getElementById("tsafc-line");
    if (el) el.innerHTML = '<div class="tsafc-empty">Forecast data unavailable right now.</div>';
  }

  function fmtHour(h) { var ap = h < 12 ? "AM" : "PM"; var hr = h % 12; if (hr === 0) hr = 12; return hr + ap; }
  function fill(arr) {
    var out = arr.slice(), last = null, i;
    for (i = 0; i < 24; i++) { if (out[i] == null) out[i] = last != null ? last : 0; else last = out[i]; }
    var next = null;
    for (i = 23; i >= 0; i--) { if (arr[i] != null) next = arr[i]; else if (next != null) out[i] = next; }
    return out;
  }

  function render(d) {
    var stdRaw = d.hours.map(function (r) { return r.standard; });
    var preRaw = d.hours.map(function (r) { return r.precheck; });
    var STD = fill(stdRaw), PRE = fill(preRaw);
    var nowHour = (d.now && d.now.hour != null) ? d.now.hour : new Date().getHours();
    var nowVal = (d.now && d.now.standard != null) ? Math.round(d.now.standard) : Math.round(STD[nowHour]);
    var best = 5;
    for (var h = 6; h <= 23; h++) { if (STD[h] < STD[best]) best = h; }

    var W = 940, H = 320, L = 46, R = 64, T = 26, B = 40, iw = W - L - R, ih = H - T - B;
    var ymax = Math.max(45, Math.ceil((Math.max.apply(null, STD) * 1.25) / 15) * 15);
    var X = function (h) { return L + (h / 23) * iw; };
    var Y = function (v) { return T + (1 - Math.min(v, ymax) / ymax) * ih; };
    var g = "";
    for (var v = 0; v <= ymax; v += 15) {
      var y = Y(v);
      g += '<line x1="' + L + '" y1="' + y + '" x2="' + (W - R) + '" y2="' + y + '" stroke="#212b38" stroke-width="1"/>';
      g += '<text x="' + (L - 8) + '" y="' + (y + 4) + '" text-anchor="end" font-size="11" fill="#6f7d8f" font-family="IBM Plex Mono,monospace">' + v + '</text>';
    }
    [0, 4, 8, 12, 16, 20, 23].forEach(function (h) {
      g += '<text x="' + X(h) + '" y="' + (H - 14) + '" text-anchor="middle" font-size="11" fill="#6f7d8f" font-family="IBM Plex Mono,monospace">' + fmtHour(h) + '</text>';
    });
    var up = "", dn = "";
    STD.forEach(function (v, h) { up += (h ? "L" : "M") + X(h).toFixed(1) + "," + Y(v * 1.22).toFixed(1) + " "; });
    for (var k = 23; k >= 0; k--) { dn += "L" + X(k).toFixed(1) + "," + Y(STD[k] * 0.8).toFixed(1) + " "; }
    g += '<path d="' + up + dn + 'Z" fill="rgba(34,211,184,.14)" stroke="none"/>';
    g += '<line x1="' + X(best) + '" y1="' + T + '" x2="' + X(best) + '" y2="' + (H - B) + '" stroke="#7fe6cf" stroke-width="1" stroke-dasharray="2 4" opacity=".7"/>';
    g += '<path d="M' + (X(best) - 6) + ',' + (H - B + 2) + ' L' + (X(best) + 6) + ',' + (H - B + 2) + ' L' + X(best) + ',' + (H - B - 6) + ' Z" fill="#7fe6cf"/>';
    g += '<text x="' + X(best) + '" y="' + (T - 8) + '" text-anchor="middle" font-size="11" fill="#7fe6cf" font-family="IBM Plex Mono,monospace">BEST ' + fmtHour(best) + '</text>';
    var sp = ""; STD.forEach(function (v, h) { sp += (h ? "L" : "M") + X(h).toFixed(1) + "," + Y(v).toFixed(1) + " "; });
    g += '<path d="' + sp + '" fill="none" stroke="#22d3b8" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>';
    var pp = ""; PRE.forEach(function (v, h) { pp += (h ? "L" : "M") + X(h).toFixed(1) + "," + Y(v).toFixed(1) + " "; });
    g += '<path d="' + pp + '" fill="none" stroke="#e0763a" stroke-width="2.2" stroke-dasharray="2 5" stroke-linecap="round"/>';
    g += '<line x1="' + X(nowHour) + '" y1="' + T + '" x2="' + X(nowHour) + '" y2="' + (H - B) + '" stroke="#22d3b8" stroke-width="1.5" stroke-dasharray="3 3" opacity=".85"/>';
    g += '<circle cx="' + X(nowHour) + '" cy="' + Y(nowVal) + '" r="5" fill="#22d3b8" stroke="#141b24" stroke-width="2"/>';
    g += '<text x="' + X(nowHour) + '" y="' + (T - 8) + '" text-anchor="middle" font-size="12" fill="#f3f6fa" font-weight="700" font-family="IBM Plex Mono,monospace">NOW ' + nowVal + 'm</text>';
    document.getElementById("tsafc-line").innerHTML =
      '<svg width="100%" viewBox="0 0 ' + W + ' ' + H + '" style="display:block">' + g + "</svg>";

    // heatmap
    var days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    var ramp = ["#12233b", "#1c4a86", "#2f77d6", "#5aa0ef", "#9cc6f6"];
    document.getElementById("tsafc-rows").innerHTML = days.map(function (x) { return "<span>" + x + "</span>"; }).join("");
    document.getElementById("tsafc-x").innerHTML = [0, 3, 6, 9, 12, 15, 18, 21].map(function (h) { return '<span style="grid-column:span 3">' + fmtHour(h) + "</span>"; }).join("");
    var cells = "", d0, h0, val, b;
    var HM = d.heatmap || [];
    for (d0 = 0; d0 < 7; d0++) {
      for (h0 = 0; h0 < 24; h0++) {
        val = (HM[d0] && HM[d0][h0] != null) ? HM[d0][h0] : null;
        b = val == null ? 0 : Math.min(4, Math.floor(val / 15));
        cells += '<div class="hc" style="background:' + (val == null ? "#0e1622" : ramp[b]) + '"></div>';
      }
    }
    document.getElementById("tsafc-grid").innerHTML = cells;
  }

  function injectStyles() {
    if (document.getElementById("tsafc-style")) return;
    var s = document.createElement("style");
    s.id = "tsafc-style";
    s.textContent =
      '.tsafc{display:grid;gap:18px;margin:8px 0}' +
      '.tsafc-card{background:#141b24;border:1px solid rgba(255,255,255,.09);border-radius:16px;padding:18px 20px;color:#f3f6fa;font-family:"Space Grotesk",system-ui,sans-serif}' +
      '.tsafc-badge{display:inline-block;background:rgba(34,211,184,.14);color:#22d3b8;font-family:"IBM Plex Mono",monospace;font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;padding:3px 9px;border-radius:20px;margin-bottom:8px}' +
      '.tsafc-h{font-family:"Oswald","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.02em;font-size:1.12rem;margin:0 0 2px;font-weight:700}' +
      '.tsafc-sub{color:#6f7d8f;font-size:.82rem;margin-bottom:12px;font-family:"IBM Plex Mono",monospace;letter-spacing:.03em}' +
      '.tsafc-empty{color:#6f7d8f;font-size:.9rem;padding:36px 0;text-align:center}' +
      '.tsafc-legend{display:flex;gap:18px;flex-wrap:wrap;font-size:.82rem;color:#aab6c4;margin-top:10px}' +
      '.tsafc-legend span{display:inline-flex;align-items:center;gap:7px}' +
      '.tsafc-legend .sw{width:16px;height:0;border-top:3px solid #22d3b8;border-radius:3px}' +
      '.tsafc-legend .sw.pre{border-top:3px dotted #e0763a}' +
      '.tsafc-legend .sw.now{width:0;height:14px;border-left:2px dashed #22d3b8}' +
      '.tsafc-legend .sw.best{width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:9px solid #7fe6cf}' +
      '.tsafc-heatwrap{display:grid;grid-template-columns:34px 1fr;gap:10px;align-items:center;margin-top:4px}' +
      '.tsafc-rows{display:grid;grid-template-rows:repeat(7,1fr);gap:4px;font-size:11px;color:#6f7d8f;text-align:right;font-family:"IBM Plex Mono",monospace}' +
      '.tsafc-rows span{height:20px;line-height:20px}' +
      '.tsafc-grid{display:grid;grid-template-columns:repeat(24,1fr);grid-auto-rows:20px;gap:3px}' +
      '.tsafc-grid .hc{border-radius:3px}' +
      '.tsafc-x{display:grid;grid-template-columns:repeat(24,1fr);gap:3px;font-size:9.5px;color:#6f7d8f;margin:6px 0 0 44px;font-family:"IBM Plex Mono",monospace}';
    document.head.appendChild(s);
  }
})();
