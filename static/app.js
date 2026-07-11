let chart;
let networkChart;
let livePayloadCache = null;
let selectedAirportCode = null;
let chartJsPromise = null;
let lastUpdateTimestamp = null;
let terminalMap = null;
let terminalMarkers = {};
let leafletAssetPromise = null;
const hasRIC = typeof window !== "undefined" && "requestIdleCallback" in window;
const airportProfiles = (typeof window !== "undefined" && window.AIRPORT_PROFILES) || {};
const COMMUNITY_REPORT_COOLDOWN_MS = 5 * 60 * 1000;
const HISTORY_AVERAGE_MIN_BUCKETS = 18;
const HISTORY_RECENT_HOURS = 12;
const HISTORY_BUCKET_MINUTES = 15;

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function communitySessionId() {
  try {
    let id = localStorage.getItem("tsa_community_session_id");
    if (!id) {
      id = (crypto && crypto.randomUUID) ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      localStorage.setItem("tsa_community_session_id", id);
    }
    return id;
  } catch {
    return "session-unavailable";
  }
}

const PHL_CONFIG = {
  "airportCode": "PHL",
  "config": { "post_security_connected": true, "default_zoom": 16, "shuttle_active": true, "center": [39.8775, -75.244] },
  "terminals": [
    {
      "id": "A_WEST", "name": "A-West (Intl)", "shortName": "A", "checkpoints": [4377], "coords": [39.875023, -75.249537],
      "airlines": ["British Airways", "Aer Lingus", "Lufthansa", "Qatar Airways", "American (Intl)"],
      "notes": "Primary International Terminal."
    },
    {
      "id": "A_EAST", "name": "Terminal A-East", "shortName": "A", "checkpoints": [4386, 4368], "coords": [39.875500, -75.246500],
      "airlines": ["American Airlines", "Aer Lingus", "Icelandair"],
      "notes": "Walkable to A-West and B."
    },
    {
      "id": "BC_HUB", "name": "B/C Hub", "shortName": "B/C", "checkpoints": [5047, 5052], "coords": [39.876148, -75.243988],
      "airlines": ["American Airlines"],
      "notes": "Main domestic hub for American."
    },
    {
      "id": "D_HUB", "name": "Terminal D", "shortName": "D", "checkpoints": [3971], "coords": [39.877168, -75.240543],
      "airlines": ["Delta", "United", "Alaska"],
      "notes": "Use the D/E Connector entry."
    },
    {
      "id": "E_HUB", "name": "Terminal E", "shortName": "E", "checkpoints": [4126], "coords": [39.878594, -75.239604],
      "airlines": ["Southwest", "Frontier", "Spirit", "JetBlue"],
      "notes": "Terminal E is connected to D airside."
    },
    {
      "id": "F_REGIONAL", "name": "Terminal F", "shortName": "F", "checkpoints": [5068], "coords": [39.880363, -75.239777],
      "airlines": ["American Eagle"],
      "notes": "Regional flights. Shuttle from C."
    }
  ],
  "routing_logic": [
    { "from": "F_REGIONAL", "to": "BC_HUB", "mode": "shuttle", "instruction": "Take the airside shuttle near Gate F10 to Terminal C." },
    { "from": "A_WEST", "to": "A_EAST", "mode": "walk", "instruction": "Direct airside walking path available." }
  ]
};

const PHL_CHECKPOINT_IDS_BY_NAME = {
  "D/E TSA PreCheck": 4126,
  "D/E General": 3971,
  "A-West General": 4377,
  "A-East TSA PreCheck": 4386,
  "A-East General": 4368,
  "B General": 5047,
  "C General": 5052,
  "F General": 5068,
};

function phlCheckpointId(row) {
  const rawId = Number(row?.checkpoint_id);
  if (Number.isFinite(rawId) && rawId > 0) return rawId;
  return PHL_CHECKPOINT_IDS_BY_NAME[row?.checkpoint] || null;
}

function scheduleNonCriticalTask(fn, timeout = 800) {
  if (hasRIC) {
    window.requestIdleCallback(fn, { timeout });
    return;
  }
  setTimeout(fn, 0);
}

function loadChartJs() {
  if (chartJsPromise) return chartJsPromise;
  if (window.Chart) {
    chartJsPromise = Promise.resolve(window.Chart);
    return chartJsPromise;
  }
  chartJsPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    const timeout = window.setTimeout(() => reject(new Error("Chart.js load timed out")), 8000);
    script.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js";
    script.onload = () => {
      window.clearTimeout(timeout);
      resolve(window.Chart);
    };
    script.onerror = () => {
      window.clearTimeout(timeout);
      reject(new Error("Chart.js failed to load"));
    };
    document.head.appendChild(script);
  });
  return chartJsPromise;
}

function loadLeafletAssets() {
  if (leafletAssetPromise) return leafletAssetPromise;
  if (window.L) {
    leafletAssetPromise = Promise.resolve(window.L);
    return leafletAssetPromise;
  }

  leafletAssetPromise = new Promise((resolve, reject) => {
    const cssId = "leaflet-css";
    const jsId = "leaflet-js";

    const finish = () => {
      if (window.L) {
        resolve(window.L);
      } else {
        reject(new Error("Leaflet failed to load"));
      }
    };

    if (!document.getElementById(cssId)) {
      const link = document.createElement("link");
      link.id = cssId;
      link.rel = "stylesheet";
      link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
      link.integrity = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=";
      link.crossOrigin = "";
      document.head.appendChild(link);
    }

    if (document.getElementById(jsId)) {
      finish();
      return;
    }

    const script = document.createElement("script");
    script.id = jsId;
    script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    script.integrity = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=";
    script.crossOrigin = "";
    script.onload = finish;
    script.onerror = reject;
    document.head.appendChild(script);
  });

  return leafletAssetPromise;
}

async function fetchJsonWithTimeout(url, timeoutMs = 10000) {
  const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timeout = window.setTimeout(() => {
    if (controller) controller.abort();
  }, timeoutMs);
  try {
    const resp = await fetch(url, controller ? { signal: controller.signal } : undefined);
    if (!resp.ok) throw new Error(`Request failed with ${resp.status}`);
    return await resp.json();
  } finally {
    window.clearTimeout(timeout);
  }
}

function fmtMinutes(v) {
  const n = Number(v);
  if (Number.isNaN(n) || n < 0) return null; // null = truly closed/no data
  if (n === 0) return 0;                      // 0 = "< 1 min" — open with no queue
  return Math.max(1, Math.round(n));
}

// Returns a short tier class (low/med/high/crit/none)
function waitTierClass(waitMinutes) {
  const n = Number(waitMinutes);
  if (Number.isNaN(n) || n < 0) return "none";
  if (n <= 15) return "low";   // includes 0 — essentially no wait
  if (n <= 30) return "med";
  if (n <= 45) return "high";
  return "crit";
}

function cleanCheckpointLabel(label) {
  if (!label) return "Checkpoint";
  return String(label)
    .replace(/ProjectedQueueTime.*$/i, "")
    .replace(/JourneyTime.*$/i, "")
    .replace(/\s+/g, " ")
    .trim();
}

function inferredLaneType(label) {
  const s = String(label || "").trim().toLowerCase();
  if (!s) return null;
  if (s.includes("clear") && (s.includes("pre") || s.includes("tsa"))) return "CLEAR_PRECHECK";
  if (s.includes("clear")) return "CLEAR";
  if (s.includes("priority") || s.includes("premier")) return "PRIORITY";
  if (s.includes("pre")) return "PRECHECK";
  if (s.includes("general") || s.includes("regular") || s.includes("standard")) return "STANDARD";
  return null;
}

function normalizeCheckpointRow(row) {
  const rawCheckpoint = cleanCheckpointLabel(row.checkpoint);
  let checkpoint = rawCheckpoint;
  let laneType = row.lane_type || "STANDARD";

  const leadingNumberMatch = rawCheckpoint.match(/^(\d+)\s+(.+)$/);
  if (leadingNumberMatch) {
    const inferred = inferredLaneType(leadingNumberMatch[2]);
    if (inferred) {
      checkpoint = `Checkpoint ${leadingNumberMatch[1]}`;
      laneType = inferred;
    }
  }

  const parenLaneMatch = checkpoint.match(/^(.*?)\s*\(([^)]+)\)$/);
  if (parenLaneMatch) {
    const inferred = inferredLaneType(parenLaneMatch[2]);
    if (inferred) {
      checkpoint = parenLaneMatch[1].trim();
      laneType = inferred;
    }
  }

  const trailingLaneMatch = checkpoint.match(/^(.*?)(?:\s+|-)(General|Regular|Standard|Priority|Premier|Clear|TSA[- ]?Pre(?:Check)?|PreCheck)$/i);
  if (trailingLaneMatch && trailingLaneMatch[1].trim()) {
    const inferred = inferredLaneType(trailingLaneMatch[2]);
    if (inferred) {
      checkpoint = trailingLaneMatch[1].trim();
      laneType = inferred;
    }
  }

  return { ...row, checkpoint, lane_type: laneType };
}

function latestCapturedAt(rows) {
  if (!rows.length) return null;
  const ts = rows
    .map((r) => new Date(r.captured_at))
    .filter((d) => !Number.isNaN(d.getTime()))
    .sort((a, b) => b - a);
  return ts[0] || null;
}

// Lane display config: label, badge CSS class, sort priority
const LANE_CONFIG = {
  STANDARD: { label: "Regular", cls: "lane-std", order: 0 },
  PRIORITY: { label: "Priority", cls: "lane-pri", order: 1 },
  PRECHECK: { label: "TSA Pre\u2714", cls: "lane-pre", order: 2 },
  CLEAR: { label: "CLEAR", cls: "lane-clr", order: 3 },
  CLEAR_PRECHECK: { label: "CLEAR + Pre\u2714", cls: "lane-clrpre", order: 4 },
};

function laneConfig(lane_type) {
  return LANE_CONFIG[lane_type] || LANE_CONFIG.STANDARD;
}

// Build the big-number right side of a cp-block
function bigNumHtml(wait_minutes, tier) {
  const mins = fmtMinutes(wait_minutes);
  if (mins === null) {
    return `<div class="big-num none">Closed</div>`;
  }
  if (mins === 0) {
    return `<div class="big-num low" style="font-size:38px">&lt;1</div><span class="big-unit">min</span>`;
  }
  return `<div class="big-num ${tier}">${mins}</div><span class="big-unit">${mins === 1 ? "min" : "mins"}</span>`;
}

// Compact inline wait for per-lane display (multi-lane mode)
function laneWaitText(wait_minutes, tier) {
  const mins = fmtMinutes(wait_minutes);
  if (mins === null) return `<span class="lane-wait ${tier}">Closed</span>`;
  if (mins === 0) return `<span class="lane-wait low">&lt;1 min</span>`;
  return `<span class="lane-wait ${tier}">${mins} ${mins === 1 ? "min" : "mins"}</span>`;
}

function checkpointSummary(rows) {
  const grouped = new Map();
  rows.forEach((row) => {
    const checkpointName = cleanCheckpointLabel(row.checkpoint || "Checkpoint");
    if (/estimated wait/i.test(checkpointName)) return;
    const wait = Number(row.wait_minutes);
    if (!Number.isFinite(wait) || wait < 0) return;
    const current = grouped.get(checkpointName) || [];
    current.push(wait);
    grouped.set(checkpointName, current);
  });
  const ranked = Array.from(grouped.entries())
    .map(([name, waits]) => ({
      name,
      avg: waits.reduce((sum, wait) => sum + wait, 0) / waits.length,
    }))
    .sort((a, b) => a.avg - b.avg);
  return {
    best: ranked[0],
    worst: ranked[ranked.length - 1],
    count: ranked.length,
  };
}

function updateCheckpointRecommendation(code, rows = []) {
  const panel = document.getElementById("checkpoint-recommendation");
  if (!panel) return;
  const summary = checkpointSummary(rows);
  if (!code || !summary.best || summary.count < 2) {
    panel.classList.remove("is-visible");
    return;
  }

  const title = document.getElementById("checkpoint-rec-title");
  const copy = document.getElementById("checkpoint-rec-copy");
  const minutes = document.getElementById("checkpoint-rec-minutes");
  const bestMinutes = Math.round(summary.best.avg);
  const worstText = summary.worst && summary.worst.name !== summary.best.name
    ? ` Highest current pressure is at ${summary.worst.name} around ${Math.round(summary.worst.avg)} minutes.`
    : "";

  if (title) title.textContent = `${summary.best.name} is currently the shortest listed checkpoint`;
  if (copy) {
    copy.textContent = `${code} has multiple live checkpoint readings right now. Use this as a routing hint only after confirming it serves your terminal or gate.${worstText}`;
  }
  if (minutes) {
    minutes.innerHTML = `${bestMinutes}<span>min</span>`;
  }
  panel.classList.add("is-visible");
}

function terminalChipLabel(note, index) {
  const text = String(note || "");
  const knownLabels = [
    ["Domestic Terminal Main", "Main checkpoint"],
    ["Domestic North", "North checkpoint"],
    ["Domestic Lower North", "Lower North"],
    ["Domestic South", "South PreCheck"],
    ["International Terminal", "International Main"],
    ["Terminals 2 and 3", "T2/T3 Delta"],
    ["Terminals 4 and 5", "T4/T5 American"],
    ["Terminals 7 and 8", "T7/T8 United"],
    ["Terminal B is", "Terminal B Intl"],
    ["Terminal 2 North", "T2 North"],
    ["Terminal 2 South", "T2 South"],
    ["Terminal 2", "Terminal 2"],
    ["Terminal 1 checkpoint", "Terminal 1"],
    ["A/B Gates", "A/B gates"],
    ["C Gates", "C gates"],
    ["C/D Gates", "C/D 24-hour"],
    ["Terminal 3 Level 2", "T3 Level 2"],
    ["Terminal 3 Level Zero", "Innovation"],
    ["Checkpoint 1", "Checkpoint 1"],
    ["Checkpoint 2", "Checkpoint 2"],
    ["Checkpoint 3", "Checkpoint 3"],
    ["Checkpoint 4", "Checkpoint 4"],
    ["Checkpoint 5", "Checkpoint 5"],
    ["Checkpoint 6", "Checkpoint 6"],
    ["Checkpoint A", "Checkpoint A"],
    ["Checkpoint B and B-Mezzanine", "B / B-Mezz"],
    ["Checkpoint B", "Checkpoint B"],
    ["Checkpoint D", "Checkpoint D"],
    ["Checkpoint F", "Checkpoint F"],
    ["Checkpoint G", "Checkpoint G"],
    ["A-West", "A-West"],
    ["D/E", "D/E connector"],
    ["Terminal C", "Terminal C"],
    ["Terminal A", "Terminal A"],
    ["Terminal B", "Terminal B"],
    ["Terminal 5", "Terminal 5"],
    ["Terminal 1", "Terminal 1"],
    ["Terminal 3", "Terminal 3"],
  ];
  const match = knownLabels.find(([needle]) => text.includes(needle));
  if (match) return match[1];
  return `Terminal note ${index + 1}`;
}

function updateAirportIntelligence(code, rows = []) {
  const profile = airportProfiles[code];
  const panel = document.getElementById("airport-intelligence-panel");
  if (!panel || !profile) return;

  panel.style.display = "";
  panel.style.setProperty("--airport-accent", profile.accent || "#2dd4bf");
  panel.style.setProperty("--airport-secondary", profile.secondary || "#fb7185");

  const mark = document.getElementById("airport-intel-mark");
  const kicker = document.getElementById("airport-intel-kicker");
  const title = document.getElementById("airport-intel-title");
  const city = document.getElementById("airport-intel-city");
  if (mark) mark.textContent = profile.code;
  if (kicker) kicker.textContent = `${profile.label || "Live airport"} intelligence`;
  if (title) title.textContent = profile.name;
  if (city) city.textContent = `${profile.city || "Airport"} playbook: static terminal guidance plus live checkpoint stats when the airport source provides them.`;

  const summary = checkpointSummary(rows);
  const best = document.getElementById("airport-intel-best");
  const watch = document.getElementById("airport-intel-watch");
  const coverage = document.getElementById("airport-intel-coverage");
  if (best) {
    best.textContent = summary.best ? `${summary.best.name} · ${Math.round(summary.best.avg)} min` : "No live checkpoint split";
  }
  if (watch) {
    watch.textContent = summary.worst ? `${summary.worst.name} · ${Math.round(summary.worst.avg)} min` : "Static terminal guide";
  }
  if (coverage) {
    const terminalCount = (profile.terminal_highlights || []).length;
    coverage.textContent = summary.count ? `${summary.count} live checkpoint groups` : `${terminalCount} terminal guide notes`;
  }

  const terminals = document.getElementById("airport-intel-terminals");
  const terminalNote = document.getElementById("airport-intel-terminal-note");
  const terminalItems = profile.terminal_highlights || [];
  if (terminals) {
    terminals.innerHTML = terminalItems.map((note, index) => (
      `<button type="button" class="terminal-chip${index === 0 ? " is-active" : ""}" data-note="${escapeHtml(note)}">${escapeHtml(terminalChipLabel(note, index))}</button>`
    )).join("");
    terminals.querySelectorAll(".terminal-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        terminals.querySelectorAll(".terminal-chip").forEach((item) => item.classList.remove("is-active"));
        chip.classList.add("is-active");
        if (terminalNote) terminalNote.textContent = chip.dataset.note || "";
      });
    });
  }
  if (terminalNote) {
    terminalNote.textContent = terminalItems[0] || "This airport has live data but limited terminal notes so far.";
  }

  const strategy = document.getElementById("airport-intel-strategy");
  if (strategy) {
    const items = (profile.strategy || []).slice(0, 3);
    strategy.innerHTML = items.length
      ? items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
      : "<li>Use the live wait, then check the 24-hour historical average before leaving.</li>";
  }

  const airlines = document.getElementById("airport-intel-airlines");
  if (airlines) {
    const items = (profile.airline_highlights || []).slice(0, 2);
    airlines.innerHTML = items.length
      ? items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
      : "<li>Confirm your airline terminal before choosing a checkpoint.</li>";
  }

  const links = document.getElementById("airport-intel-links");
  if (links) {
    const sourceLinks = (profile.source_links || []).slice(0, 2);
    links.innerHTML = [
      `<a class="airport-intel-link" href="${escapeHtml(profile.href)}">Open ${escapeHtml(profile.code)} page</a>`,
      ...sourceLinks.map((link) => (
        `<a class="airport-intel-link" href="${escapeHtml(link.url)}" target="_blank" rel="noopener">${escapeHtml(link.label)}</a>`
      )),
    ].join("");
  }
}

function renderLiveCards(payload, selectedCode) {
  const host = document.getElementById("live-cards");
  host.innerHTML = "";
  const data = payload.data || {};
  const liveAirports = payload.live_airports || {};

  if (!selectedCode || !liveAirports[selectedCode]) {
    host.innerHTML = `<div class="muted" style="padding:16px 0 4px;">
      Tap an airport chip above to see live security wait times.
    </div>`;
    if (selectedCode) updateAirportIntelligence(selectedCode, []);
    updateCheckpointRecommendation(selectedCode, []);
    return;
  }

  const rows = (data[selectedCode] || []).map(normalizeCheckpointRow);
  updateAirportIntelligence(selectedCode, rows);
  updateCheckpointRecommendation(selectedCode, rows);

  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "airport-card";
    empty.innerHTML = `<div class="muted">No data yet — check back in a minute.</div>`;
    host.appendChild(empty);
    return;
  }

  // Group rows by checkpoint name
  const grouped = {};
  const groupOrder = [];
  rows.forEach((row) => {
    const key = cleanCheckpointLabel(row.checkpoint);
    if (!grouped[key]) { grouped[key] = []; groupOrder.push(key); }
    grouped[key].push(row);
  });

  // Sort checkpoints: worst Standard wait first
  groupOrder.sort((a, b) => {
    const stdWait = (lanes) => {
      const std = lanes.find(r => (r.lane_type || "STANDARD") === "STANDARD");
      return std ? Number(std.wait_minutes) || 0 : Math.max(...lanes.map(r => Number(r.wait_minutes) || 0));
    };
    return stdWait(grouped[b]) - stdWait(grouped[a]);
  });

  const card = document.createElement("div");
  card.className = "airport-card";

  groupOrder.forEach((cpName) => {
    const lanes = grouped[cpName]
      .slice()
      .sort((a, b) => laneConfig(a.lane_type).order - laneConfig(b.lane_type).order);

    // Determine overall tier from the Standard lane (or worst)
    const stdRow = lanes.find(r => (r.lane_type || "STANDARD") === "STANDARD") || lanes[0];
    const groupTier = waitTierClass(stdRow.wait_minutes);
    const multiLane = lanes.length > 1;

    // Build lane rows (left side)
    const laneRowsHtml = lanes.map((row) => {
      const lCfg = laneConfig(row.lane_type);
      const laneTier = waitTierClass(row.wait_minutes);
      const waitInline = multiLane ? laneWaitText(row.wait_minutes, laneTier) : "";
      return `<div class="lane-row">
        <span class="lane-badge ${lCfg.cls}">${lCfg.label}</span>
        ${waitInline}
      </div>`;
    }).join("");

    // Big number (right side) — based on Standard or primary lane
    const bigHtml = bigNumHtml(stdRow.wait_minutes, groupTier);

    const block = document.createElement("div");
    block.className = `cp-block ${groupTier}`;
    block.innerHTML = `
      <div class="cp-left">
        <div class="cp-name">${cpName}</div>
        <div class="cp-lanes">${laneRowsHtml}</div>
      </div>
      <div class="cp-right">${bigHtml}</div>
    `;
    card.appendChild(block);
  });

  const updatedAt = latestCapturedAt(rows);
  if (updatedAt) {
    const foot = document.createElement("div");
    foot.className = "updated-meta";
    foot.textContent = `Updated ${updatedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · refreshes every 2 min`;
    card.appendChild(foot);
  }

  host.appendChild(card);

  // Update map if visible
  if (selectedCode === "PHL") {
    updateMapTerminalStatus(rows);
  }
}

const NETWORK_CHART_COLORS = [
  "#5eead4", "#fbbf24", "#60a5fa", "#f87171", "#a78bfa", "#34d399",
  "#fb7185", "#38bdf8", "#f97316", "#c084fc", "#22c55e", "#e879f9",
  "#93c5fd", "#fde047", "#2dd4bf", "#fca5a5", "#86efac", "#fdba74",
];

async function renderNetworkAverageChart() {
  const canvas = document.getElementById("network-average-chart");
  const emptyEl = document.getElementById("network-chart-empty");
  if (!canvas) return;
  if (networkChart) return;
  if (emptyEl) {
    emptyEl.textContent = "Loading historical airport comparison graph.";
    emptyEl.style.display = "block";
  }

  const chartJsReady = loadChartJs();
  let payload;
  try {
    payload = await fetchJsonWithTimeout("/api/network-history-24h-average?days=30", 12000);
  } catch (_e) {
    if (emptyEl) {
      emptyEl.textContent = "Historical comparison is still warming up. Current airport cards are available below.";
      emptyEl.style.display = "block";
    }
    return;
  }

  const airports = (payload.airports || [])
    .map((airport) => ({
      ...airport,
      points: (airport.rows || []).map((row) => (
        Number.isFinite(Number(row.avg_wait)) ? Number(row.avg_wait) : null
      )),
      samples: (airport.rows || []).reduce((sum, row) => sum + (Number(row.samples) || 0), 0),
      peak: Math.max(...(airport.rows || []).map((row) => Number(row.avg_wait) || 0)),
    }))
    .filter((airport) => airport.samples > 0)
    .sort((a, b) => b.peak - a.peak);

  if (!airports.length) {
    if (emptyEl) {
      emptyEl.textContent = "Collecting enough historical data to compare airports.";
      emptyEl.style.display = "block";
    }
    return;
  }

  const labels = Array.from({ length: 24 }, (_, hour) => `${String(hour).padStart(2, "0")}:00`);
  const datasets = airports.map((airport, index) => {
    const color = NETWORK_CHART_COLORS[index % NETWORK_CHART_COLORS.length];
    return {
      label: airport.code,
      data: airport.points,
      borderColor: color,
      backgroundColor: color,
      borderWidth: 2,
      tension: 0.28,
      pointRadius: 0,
      pointHoverRadius: 4,
      spanGaps: true,
      airportName: airport.name,
      href: airport.href,
      samples: airport.samples,
    };
  });

  try {
    await chartJsReady;
  } catch (_e) {
    if (emptyEl) {
      emptyEl.textContent = "Network graph is loading slowly. Current airport cards are still available below.";
      emptyEl.style.display = "block";
    }
    return;
  }

  if (emptyEl) emptyEl.style.display = "none";
  networkChart = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "nearest", intersect: false },
      onClick: (_event, elements) => {
        const index = elements && elements[0] ? elements[0].datasetIndex : -1;
        const dataset = index >= 0 ? datasets[index] : null;
        if (dataset?.href) window.location.href = dataset.href;
      },
      scales: {
        x: {
          ticks: {
            color: "#55556a",
            font: { family: "'IBM Plex Mono'" },
            maxTicksLimit: 12,
          },
          grid: { color: "#22222e" },
          border: { color: "#22222e" },
        },
        y: {
          beginAtZero: true,
          ticks: { color: "#55556a", font: { family: "'IBM Plex Mono'" } },
          grid: { color: "#22222e" },
          border: { color: "#22222e" },
          title: {
            display: true,
            text: "Average minutes",
            color: "#55556a",
            font: { family: "'IBM Plex Mono'", size: 11 },
          },
        },
      },
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: "#a7a7bb",
            font: { family: "'IBM Plex Mono'", size: 10 },
            boxWidth: 12,
            boxHeight: 2,
            usePointStyle: true,
          },
        },
        tooltip: {
          callbacks: {
            title: (items) => `${items[0].label} local hour`,
            label: (context) => {
              const dataset = context.dataset;
              const value = Number(context.parsed.y);
              return `${dataset.label}: ${value.toFixed(1)} min avg`;
            },
            afterLabel: (context) => {
              const dataset = context.dataset;
              return `${dataset.airportName} · ${dataset.samples} samples · click to open`;
            },
          },
        },
      },
    },
  });
}

async function initTerminalMap(airportCode, rows) {
  const mapSection = document.getElementById("terminal-map-section");
  if (airportCode !== "PHL") {
    mapSection.style.display = "none";
    return;
  }

  mapSection.style.display = "block";
  try {
    await loadLeafletAssets();
  } catch (err) {
    console.warn("Leaflet load failed", err);
    return;
  }
  if (terminalMap) return; // Already init

  const cfg = PHL_CONFIG.config;
  terminalMap = L.map('terminal-map', {
    center: cfg.center,
    zoom: cfg.default_zoom,
    zoomControl: false,
    attributionControl: false
  });

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19
  }).addTo(terminalMap);

  // Line of Connectivity (Airside)
  const pathCoords = PHL_CONFIG.terminals.map(t => t.coords);
  L.polyline(pathCoords, {
    color: '#888',
    weight: 2,
    dashArray: '5, 8',
    opacity: 0.6,
    interactive: false
  }).addTo(terminalMap);

  // Add Terminal Markers
  PHL_CONFIG.terminals.forEach(t => {
    const icon = L.divIcon({
      className: 'terminal-marker-icon',
      html: `<div class="terminal-marker-inner" id="marker-${t.id}" data-label="${t.name}">${t.shortName}</div>`,
      iconSize: [34, 34]
    });

    const marker = L.marker(t.coords, { icon: icon }).addTo(terminalMap);
    marker.bindPopup(`<strong>${t.name}</strong><br>${t.notes}`);
    terminalMarkers[t.id] = marker;
  });

  // Populate Airline Lookup
  const airlineSelect = document.getElementById("airline-search-select");
  const allAirlines = [...new Set(PHL_CONFIG.terminals.flatMap(t => t.airlines))].sort();
  allAirlines.forEach(air => {
    const opt = document.createElement("option");
    opt.value = air;
    opt.textContent = air;
    airlineSelect.appendChild(opt);
  });

  airlineSelect.addEventListener("change", (e) => {
    highlightTerminalForAirline(e.target.value);
  });

  if (rows) {
    updateMapTerminalStatus(rows);
  }
}

function updateMapTerminalStatus(rows) {
  if (!terminalMap || selectedAirportCode !== "PHL" || !Array.isArray(rows)) return;

  PHL_CONFIG.terminals.forEach(t => {
    const cpRows = rows.filter(r => t.checkpoints.includes(phlCheckpointId(r)));
    if (cpRows.length) {
      const bestWait = Math.min(...cpRows.map(r => Number(r.wait_minutes) || 999));
      const tier = waitTierClass(bestWait);
      const el = document.getElementById(`marker-${t.id}`);
      if (el) {
        el.className = `terminal-marker-inner tier-${tier}`;
      }
    }
  });
}

function highlightTerminalForAirline(airline) {
  const overlay = document.getElementById("map-overlay-info");
  if (!airline) {
    document.querySelectorAll('.terminal-marker-inner').forEach(el => el.classList.remove('highlight'));
    overlay.classList.remove('active');
    return;
  }

  const terminal = PHL_CONFIG.terminals.find(t => t.airlines.includes(airline));
  if (terminal) {
    document.querySelectorAll('.terminal-marker-inner').forEach(el => el.classList.remove('highlight', 'active-terminal-glow'));
    const el = document.getElementById(`marker-${terminal.id}`);
    if (el) el.classList.add('highlight', 'active-terminal-glow');

    terminalMap.setView(terminal.coords, 16);

    const routing = PHL_CONFIG.routing_logic.find(r => r.from === terminal.id);

    let content = `
      <div style="margin-bottom:12px;">
        <span style="font-size: 11px; color: var(--amber); font-weight:700; text-transform:uppercase; letter-spacing:0.05em;">Recommended Priority</span>
        <div style="font-size:16px; font-weight:700; color:#fff; margin-top:2px;">Go to ${terminal.name} Security</div>
      </div>
    `;

    if (routing) {
      content += `
        <div class="routing-step">
          <div class="routing-icon">${routing.mode === 'shuttle' ? '🚌' : '🚶'}</div>
          <div class="routing-text">
            <strong>Transfer Route:</strong> ${routing.instruction}
          </div>
        </div>
      `;
    } else {
      content += `
        <div style="font-size:12px; color:var(--muted);">All ${airline} flights depart from here. Airside connections available to other terminals.</div>
      `;
    }

    overlay.innerHTML = content;
    overlay.classList.add('active');
  }
}

function renderPipeline(rows) {
  const host = document.getElementById("pipeline-list");
  host.innerHTML = "";
  rows.forEach((row) => {
    const el = document.createElement("div");
    el.className = "pipeline-item";
    const note = row.note || "Live integration coming soon.";
    el.innerHTML = `
      <div class="pipeline-icon">✈️</div>
      <div class="pipeline-info">
        <div class="pipeline-name">${row.code} — ${row.name}</div>
        <div class="pipeline-note">${note}</div>
      </div>
      <span class="status-badge">Coming soon</span>
    `;
    host.appendChild(el);
  });
}

function formatAirportTimeLabel(date, timeZone = "UTC") {
  try {
    return new Intl.DateTimeFormat("en-US", {
      timeZone,
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(date);
  } catch {
    return date.toISOString().slice(11, 16);
  }
}

function normalizeHistory(rows, timeZone = "UTC", bucketMinutes = HISTORY_BUCKET_MINUTES) {
  const bucket = {};
  const bucketMs = Math.max(1, bucketMinutes) * 60 * 1000;
  rows.forEach((r) => {
    const t = new Date(r.captured_at);
    if (Number.isNaN(t.getTime())) return;
    const bucketTime = Math.floor(t.getTime() / bucketMs) * bucketMs;
    const key = String(bucketTime);
    if (!bucket[key]) bucket[key] = { ts: new Date(bucketTime), sum: 0, c: 0 };
    bucket[key].sum += Number(r.wait_minutes) || 0;
    bucket[key].c += 1;
  });
  return Object.values(bucket)
    .sort((a, b) => a.ts - b.ts)
    .map((x) => ({
      ts: x.ts.getTime(),
      label: formatAirportTimeLabel(x.ts, timeZone),
      value: x.c ? x.sum / x.c : 0,
      samples: x.c,
    }));
}

function getStoredHistory(airportCode) {
  try {
    const stored = localStorage.getItem(`history_${airportCode}`);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function saveHistoryPoint(airportCode, rows) {
  try {
    const now = new Date();
    const bucket = {};
    rows.forEach((r) => {
      const t = new Date(r.captured_at);
      const key = `${t.getUTCFullYear()}-${t.getUTCMonth() + 1}-${t.getUTCDate()} ${t.getUTCHours()}:${t.getUTCMinutes()}`;
      if (!bucket[key]) bucket[key] = { ts: t, sum: 0, c: 0 };
      bucket[key].sum += Number(r.wait_minutes) || 0;
      bucket[key].c += 1;
    });

    const newPoints = Object.values(bucket).map((x) => ({
      ts: x.ts.getTime(),
      label: x.ts.toISOString().slice(11, 16),
      value: x.c ? x.sum / x.c : 0
    }));

    let allPoints = getStoredHistory(airportCode);
    newPoints.forEach(np => {
      if (!allPoints.find(p => p.label === np.label)) {
        allPoints.push(np);
      }
    });

    // Legacy rolling cache fallback; the visible chart now uses server-side 24-hour averages.
    const historyCutoff = now.getTime() - (24 * 60 * 60 * 1000);
    allPoints = allPoints.filter(p => p.ts >= historyCutoff);

    localStorage.setItem(`history_${airportCode}`, JSON.stringify(allPoints));
  } catch {
    // silently fail
  }
}

function getMergedHistory(apiRows, airportCode) {
  const apiNormalized = normalizeHistory(apiRows);
  const storedPoints = getStoredHistory(airportCode);

  const merged = {};
  storedPoints.forEach(p => {
    merged[p.label] = p;
  });
  apiNormalized.forEach(p => {
    merged[p.label] = p;
  });

  return Object.values(merged).sort((a, b) => {
    const aTime = new Date(`1970-01-01T${a.label}`).getTime();
    const bTime = new Date(`1970-01-01T${b.label}`).getTime();
    return aTime - bTime;
  });
}

function normalizeHistoricalAverageRows(rows) {
  return (rows || [])
    .map((row) => ({
      label: row.label || `${String(row.hour).padStart(2, "0")}:00`,
      value: Number.isFinite(Number(row.avg_wait)) ? Number(row.avg_wait) : null,
      samples: Number(row.samples) || 0,
    }));
}

function setHistoryChartCopy(mode, airportCode = "") {
  const chip = document.getElementById("chart-mode-chip");
  const tip = document.getElementById("chart-planning-tip");
  const emptyEl = document.getElementById("chart-empty");

  if (mode === "recent") {
    if (chip) chip.textContent = "Recent live history";
    if (tip) {
      tip.textContent = `${airportCode} is still building a full 30-day hourly baseline, so this chart is showing recent live samples grouped into 15-minute windows.`;
    }
    if (emptyEl) emptyEl.textContent = "Collecting recent wait history for this airport.";
    return;
  }

  if (chip) chip.textContent = "24-hour average";
  if (tip) {
    tip.textContent = "This chart shows actual wait times captured over the past 30 days grouped by local hour, building a rolling history as new data arrives. Use it to spot patterns before heading to the airport.";
  }
  if (emptyEl) emptyEl.textContent = airportCode ? `Loading wait history for ${airportCode}.` : "Select an airport to view recent wait history.";
}

function averageBucketCount(points) {
  return points.filter((point) => point.value !== null && point.samples > 0).length;
}

async function drawChart(points, airportCode, mode = "average") {
  await loadChartJs();
  const ctx = document.getElementById("history-chart");
  if (chart) chart.destroy();
  const isRecent = mode === "recent";
  chart = new Chart(ctx, {
    type: isRecent ? "line" : "bar",
    data: {
      labels: points.map((p) => p.label),
      datasets: [{
        label: isRecent
          ? `${airportCode} recent avg wait (mins)`
          : `${airportCode} 24-hour historical avg wait (mins)`,
        data: points.map((p) => p.value),
        borderColor: "#5eead4",
        backgroundColor: isRecent ? "rgba(94,234,212,0.12)" : "rgba(94,234,212,0.22)",
        borderWidth: isRecent ? 2 : 1,
        borderRadius: isRecent ? 0 : 6,
        fill: false,
        tension: isRecent ? 0.28 : 0,
        pointRadius: isRecent ? 2 : 0,
      }],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          ticks: {
            color: "#55556a",
            font: { family: "'IBM Plex Mono'" },
            autoSkip: true,
            maxTicksLimit: isRecent ? 8 : 12,
          },
          grid: { color: "#22222e" },
          border: { color: "#22222e" },
        },
        y: {
          beginAtZero: true,
          ticks: { color: "#55556a", font: { family: "'IBM Plex Mono'" } },
          grid: { color: "#22222e" },
          border: { color: "#22222e" },
          title: {
            display: true, text: "Minutes", color: "#55556a",
            font: { family: "'IBM Plex Mono'", size: 11 }
          },
        },
      },
      plugins: {
        legend: { labels: { color: "#55556a", font: { family: "'IBM Plex Mono'", size: 11 } } },
        tooltip: {
          callbacks: {
            title: (items) => `${items[0].label} local hour`,
            label: (context) => {
              const value = Number(context.parsed.y);
              const prefix = isRecent ? "Recent average" : "30-day average";
              return Number.isFinite(value)
                ? `${prefix}: ${value.toFixed(1)} min`
                : `${prefix}: no data`;
            },
            afterLabel: (context) => {
              const point = points[context.dataIndex];
              return point && point.samples ? `${point.samples} samples` : "";
            },
          },
        },
      },
    },
  });
}

async function loadHistory(airportCode) {
  const emptyEl = document.getElementById("chart-empty");
  if (!airportCode) {
    if (chart) { chart.destroy(); chart = null; }
    setHistoryChartCopy("average");
    emptyEl.style.display = "block";
    return;
  }
  try {
    const averageResp = await fetch(`/api/history-24h-average?airport=${airportCode}&days=30`);
    const averagePayload = await averageResp.json();
    const averagePoints = normalizeHistoricalAverageRows(averagePayload.rows || []);
    const averageBuckets = averageBucketCount(averagePoints);

    if (averageBuckets >= HISTORY_AVERAGE_MIN_BUCKETS) {
      setHistoryChartCopy("average", airportCode);
      await drawChart(averagePoints, airportCode, "average");
      emptyEl.style.display = "none";
      return;
    }

    const recentResp = await fetch(`/api/history?airport=${airportCode}&hours=${HISTORY_RECENT_HOURS}`);
    const recentPayload = await recentResp.json();
    const recentPoints = normalizeHistory(
      recentPayload.rows || [],
      recentPayload.timezone || averagePayload.timezone || "UTC",
      HISTORY_BUCKET_MINUTES
    );

    if (recentPoints.length) {
      setHistoryChartCopy("recent", airportCode);
      await drawChart(recentPoints, airportCode, "recent");
      emptyEl.style.display = "none";
      return;
    }

    if (averageBuckets > 0) {
      setHistoryChartCopy("average", airportCode);
      await drawChart(averagePoints, airportCode, "average");
      emptyEl.style.display = "none";
      return;
    }

    if (chart) { chart.destroy(); chart = null; }
    setHistoryChartCopy("recent", airportCode);
    emptyEl.style.display = "block";
  } catch (_e) {
    if (chart) { chart.destroy(); chart = null; }
    setHistoryChartCopy("recent", airportCode);
    emptyEl.style.display = "block";
  }
}

// Source status label
function sourceStatusLabel(sourceType) {
  if (sourceType === "live_direct") return ["✓ Live airport data", "is-live"];
  if (sourceType === "estimated_fallback") return ["~ Estimated (live data not yet available)", "is-fallback"];
  return ["", "is-unknown"];
}

function renderSelectionSummary(payload) {
  const el = document.getElementById("selection-summary");
  if (!el || !payload || !payload.currentWait) return;
  const live = payload.sourceType === "live_direct";
  el.style.display = "";
  el.innerHTML = `
    <div class="selection-summary-label">${live ? "Current checkpoint average" : "Current airport estimate"}</div>
    <div class="selection-summary-value">${payload.currentWait.standardDescription || ""}</div>
    <div class="selection-summary-meta">${live ? "Refreshed from official airport checkpoint data" : "Planning estimate while live checkpoint data is unavailable"}</div>
  `;
}

function renderHeaderSourceState(payload) {
  const badge = document.getElementById("header-live-badge");
  const badgeText = document.getElementById("header-badge-text");
  const indicator = document.querySelector(".live-indicator");
  const liveText = document.getElementById("header-live-text");
  if (!badge || !badgeText || !indicator || !liveText || !payload) return;
  const live = payload.sourceType === "live_direct";
  badge.classList.toggle("is-fallback", !live);
  indicator.classList.toggle("is-fallback", !live);
  badgeText.textContent = live ? "Live" : "Estimated";
  liveText.textContent = live ? "LIVE" : "EST";
}

function renderAirportNotice(payload) {
  const el = document.getElementById("airport-status-banner");
  if (!el) return;
  const notice = payload?.airportNotice;
  if (!notice || !notice.title || !notice.summary) {
    el.style.display = "none";
    el.innerHTML = "";
    return;
  }
  const links = Array.isArray(notice.links) ? notice.links : [];
  el.style.display = "";
  el.innerHTML = `
    <div style="font-size:0.72rem;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;color:#93c5fd;margin-bottom:6px;">Official update</div>
    <div style="font-size:1rem;font-weight:700;margin-bottom:6px;color:#fff;">${notice.title}</div>
    <div style="font-size:0.95rem;line-height:1.5;margin-bottom:10px;color:#d6e4ff;">${notice.summary}</div>
    <div style="display:flex;flex-wrap:wrap;gap:10px;">
      ${links.map((link) => `<a href="${link.url}" target="_blank" rel="noopener" style="color:#93c5fd;font-weight:700;text-decoration:underline;">${link.label}</a>`).join("")}
    </div>
  `;
}

async function updateSelectionSourceStatus(airportCode) {
  const el = document.getElementById("selection-source-status");
  if (!airportCode) {
    el.textContent = "";
    el.className = "selection-source-status";
    renderAirportNotice(null);
    return;
  }
  try {
    const resp = await fetch(`/api/tsa-wait-times?code=${airportCode}`);
    const payload = await resp.json();
    const [label, cls] = sourceStatusLabel(payload.sourceType);
    el.textContent = label;
    el.className = `selection-source-status ${cls}`;
    renderAirportNotice(payload);
    renderSelectionSummary(payload);
    renderHeaderSourceState(payload);
  } catch (_e) {
    el.textContent = "";
    el.className = "selection-source-status is-unknown";
    renderAirportNotice(null);
  }
}

function renderAirportChips(payload, filterText = "") {
  const host = document.getElementById("airport-chips");
  host.innerHTML = "";
  const entries = Object.entries(payload.live_airports || {});
  const q = filterText.trim().toLowerCase();
  const filtered = entries.filter(([code, info]) =>
    !q || code.toLowerCase().includes(q) || info.name.toLowerCase().includes(q)
  );
  filtered.forEach(([code, info]) => {
    const link = document.createElement("a");
    link.className = `airport-chip${selectedAirportCode === code ? " active" : ""}`;
    link.href = `/airports/${code.toLowerCase()}-tsa-wait-times`;
    link.textContent = code;
    link.title = `${code} TSA wait times — ${info.name}`;
    link.setAttribute("aria-label", `View live TSA wait times at ${info.name} (${code})`);
    link.addEventListener("click", (event) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }
      if (selectedAirportCode === code) return;
      event.preventDefault();
      window.location.href = link.href;
    });
    host.appendChild(link);
  });
}

async function selectAirport(code, shouldPush = true) {
  selectedAirportCode = code;

  // Update URL history for SEO/Bookmarks (preventing re-push on back button)
  if (shouldPush) {
    const slug = `${code.toLowerCase()}-tsa-wait-times`;
    const newUrl = `/airports/${slug}`;
    if (window.location.pathname !== newUrl) {
      history.pushState({ airportCode: code }, "", newUrl);
    }
  }

  // Update chart dropdown
  const select = document.getElementById("airport-select");
  if (select) select.value = code;

  // Update Hero Titles & Document Title
  document.title = `${code} TSA Wait Times — TSA Tracker`;
  const heroTitle = document.getElementById("hero-title");
  if (heroTitle) heroTitle.innerHTML = `${code} TSA <em>Wait Times</em>`;

  // Update airport header
  const meta = livePayloadCache.live_airports?.[code];
  const apHeader = document.getElementById("airport-header");
  if (apHeader) apHeader.style.display = "";

  const h2Name = document.getElementById("current-airport-name");
  if (h2Name && meta) h2Name.textContent = meta.name;

  const apCode = document.getElementById("ap-code");
  if (apCode) apCode.textContent = code;
  const apName = document.getElementById("ap-name");
  if (apName && meta) apName.textContent = meta.name;

  const heroSub = document.getElementById("hero-sub");
  if (heroSub && meta) {
    heroSub.textContent = `Check ${meta.name} checkpoint conditions with clearly labeled live or estimated source status, capture time, and airport-specific planning context.`;
  }
  const toolkitSub = document.getElementById("toolkit-sub-title");
  if (toolkitSub) toolkitSub.textContent = `Save time at ${code}`;

  // --- START DYNAMIC AD UPDATE ---
  const offers = window.LOCAL_OFFERS || {};
  const currentOffer = offers[code];
  const cityName = (meta && meta.city) || "";

  // Update Featured "Local" Offer (e.g. JFK AirTrain vs ORD L-Train)
  const featuredContainer = document.getElementById("ad-featured-container");
  if (featuredContainer) {
    if (currentOffer) {
      featuredContainer.style.display = "block";
      document.getElementById("ad-featured-link").href = currentOffer.url;
      document.getElementById("ad-featured-icon").innerText = currentOffer.icon;
      document.getElementById("ad-featured-title").innerText = currentOffer.title;
      document.getElementById("ad-featured-sub").innerText = currentOffer.sub;
    } else {
      featuredContainer.style.display = "none";
    }
  }

  // Update Kiwi Link
  const kiwiLink = document.getElementById("ad-kiwi-link");
  const kiwiTitle = document.getElementById("ad-kiwi-title");
  if (kiwiLink) {
    kiwiLink.href = buildKiwiAirportUrl(code);
    if (kiwiTitle) kiwiTitle.innerText = `Cheap Flights from ${code}`;
  }

  // Update Klook Link
  const klookLink = document.getElementById("ad-klook-link");
  const klookTitle = document.getElementById("ad-klook-title");
  if (klookLink) {
    const klookTarget = `https://www.klook.com/en-US/search?query=${encodeURIComponent(cityName)}`;
    klookLink.href = buildTravelpayoutsUrl(klookTarget);
    if (klookTitle) klookTitle.innerText = `Activities in ${cityName || 'selection'}`;
  }
  // --- END DYNAMIC AD UPDATE ---

  updateSelectionSourceStatus(code);
  renderAirportChips(livePayloadCache, document.getElementById("airport-search").value);
  renderLiveCards(livePayloadCache, code);
  fetchCommunityStatus(code);
  void initTerminalMap(code, livePayloadCache?.data?.[code] || []);
  scheduleNonCriticalTask(() => loadHistory(code));

  // Scroll to results (only if the user explicitly clicked)
  if (shouldPush) {
    const resultsEl = document.getElementById("results-section");
    if (resultsEl) {
      resultsEl.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  // Update last refresh timestamp
  lastUpdateTimestamp = new Date();
  updateRefreshText();
}

/**
 * Sends ad-click data back to the server to feed the self-learning "Lite Brain" engine.
 * @param {string} offerId The ID of the ad clicked (e.g., 'CLEAR', 'KLOOK')
 */
function logAdClick(offerId) {
  if (!offerId) return;

  // Fire and forget: we don't want to block the user's navigation
  fetch("/api/log-click", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      offer_id: offerId,
      code: selectedAirportCode || "HOME"
    })
  }).catch(err => console.warn("Ad log failed", err));
}

function buildTravelpayoutsUrl(targetUrl) {
  const marker = window.MONETIZATION_CONFIG && window.MONETIZATION_CONFIG.tpMarker;
  if (!marker) return targetUrl;
  const url = new URL(targetUrl);
  if (!url.searchParams.has("marker")) {
    url.searchParams.set("marker", marker);
  }
  return url.toString();
}

function buildKiwiAirportUrl(code) {
  const upper = String(code || "").toUpperCase();
  const overrides = window.KIWI_AIRPORT_URLS || {};
  const fallback = `https://www.kiwi.com/us/?destination=anywhere&inboundDate=-&origin=${encodeURIComponent(upper || "-")}&outboundDate=anytime`;
  return buildTravelpayoutsUrl(overrides[upper] || fallback);
}


// Handle browser Back/Forward buttons
window.addEventListener("popstate", (event) => {
  if (event.state && event.state.airportCode) {
    selectAirport(event.state.airportCode, false);
  } else if (window.location.pathname === "/") {
    // Smoothly return to landing state
    selectedAirportCode = null;
    const apHeader = document.getElementById("airport-header");
    if (apHeader) apHeader.style.display = "none";
    renderAirportChips(livePayloadCache, "");
    renderLiveCards(livePayloadCache, null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
});

// Silent background refresh — only re-fetches /api/live and repaints
// the wait-time cards for the currently selected airport.
// Does NOT reset selection, does NOT touch the chart, does NOT scroll.
async function silentRefresh() {
  try {
    const resp = await fetch("/api/live");
    if (!resp.ok) return; // server error — skip this cycle, try again next time
    const fresh = await resp.json();
    // Preserve live_airports list (used by chips/dropdown) — only update data
    livePayloadCache = fresh;
    // Re-render chips to keep active state in sync
    const search = document.getElementById("airport-search");
    renderAirportChips(livePayloadCache, search ? search.value : "");
    // Re-render wait cards for the currently selected airport (no-op if none)
    if (selectedAirportCode) {
      renderLiveCards(livePayloadCache, selectedAirportCode);
      fetchCommunityStatus(selectedAirportCode);
    }
    lastUpdateTimestamp = new Date();
    updateRefreshText();
  } catch (_e) {
    // Network error — silently skip, try again next cycle
  }
}

function updateRefreshText() {
  const el = document.getElementById("last-updated-text");
  if (!el || !lastUpdateTimestamp) return;

  const now = new Date();
  const diffSec = Math.floor((now - lastUpdateTimestamp) / 1000);

  if (diffSec < 60) {
    el.textContent = "Just now";
  } else {
    const mins = Math.floor(diffSec / 60);
    el.textContent = `${mins}m ago`;
  }
}

async function reportWait(level) {
  if (!selectedAirportCode) return;
  const btn = event.currentTarget;
  const originalText = btn.textContent;
  const cooldownKey = `community_report_${selectedAirportCode}`;
  const lastReport = Number(localStorage.getItem(cooldownKey) || 0);
  if (Date.now() - lastReport < COMMUNITY_REPORT_COOLDOWN_MS) {
    btn.textContent = "WAIT 5M";
    setTimeout(() => { btn.textContent = originalText; }, 1600);
    return;
  }
  btn.textContent = "...";
  btn.disabled = true;

  try {
    const rows = livePayloadCache?.data?.[selectedAirportCode] || [];
    const summary = checkpointSummary(rows.map(normalizeCheckpointRow));
    const currentWait = summary.best ? Math.round(summary.best.avg) : null;
    const resp = await fetch("/api/report-wait", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        code: selectedAirportCode,
        level,
        current_wait: currentWait,
        session_id: communitySessionId()
      })
    });
    if (resp.ok) {
      localStorage.setItem(cooldownKey, String(Date.now()));
      btn.textContent = "✓";
      setTimeout(() => {
        btn.textContent = originalText;
        btn.disabled = false;
        fetchCommunityStatus(selectedAirportCode);
      }, 2000);
    } else if (resp.status === 429) {
      btn.textContent = "WAIT 5M";
      setTimeout(() => {
        btn.textContent = originalText;
        btn.disabled = false;
      }, 2000);
    } else {
      btn.textContent = originalText;
      btn.disabled = false;
    }
  } catch (_e) {
    btn.textContent = originalText;
    btn.disabled = false;
  }
}

async function fetchCommunityStatus(code) {
  const statusEl = document.getElementById("live-community-status");
  const levelEl = document.getElementById("community-level");
  if (!code || !statusEl) return;

  try {
    const resp = await fetch(`/api/community-status?code=${code}`);
    const data = await resp.json();
    if (data.level && data.count) {
      statusEl.style.display = "block";
      const label = data.level.replace(/_/g, " ");
      const travelerWord = data.count === 1 ? "traveler" : "travelers";
      levelEl.textContent = `${data.count} ${travelerWord} said ${label}`;
      levelEl.className = data.level;
    } else {
      statusEl.style.display = "none";
    }
  } catch (_e) {
    if (statusEl) statusEl.style.display = "none";
  }
}

async function bootstrap() {
  const liveResp = await fetch("/api/live");
  livePayloadCache = await liveResp.json();

  // Wire up hero search input
  const search = document.getElementById("airport-search");
  search.addEventListener("input", (e) => renderAirportChips(livePayloadCache, e.target.value));
  search.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const q = search.value.trim().toLowerCase();
    const match = Object.keys(livePayloadCache.live_airports || {}).find(
      (c) => c.toLowerCase() === q || livePayloadCache.live_airports[c].name.toLowerCase().includes(q)
    );
    if (match) {
      window.location.href = `/airports/${match.toLowerCase()}-tsa-wait-times`;
    }
  });

  renderAirportChips(livePayloadCache);
  renderNetworkAverageChart();
  renderLiveCards(livePayloadCache, null);

  // Auto-select airport if this is a dedicated airport page
  const initialCode = String(window.INITIAL_AIRPORT_CODE || "").toUpperCase();
  if (initialCode && livePayloadCache.live_airports?.[initialCode]) {
    selectAirport(initialCode);
  }

  scheduleNonCriticalTask(async () => {
    const select = document.getElementById("airport-select");
    if (!select) return;
    Object.keys(livePayloadCache.live_airports || {}).forEach((code) => {
      const opt = document.createElement("option");
      opt.value = code;
      opt.textContent = code;
      select.appendChild(opt);
    });
    select.addEventListener("change", (e) => selectAirport(e.target.value));
    if (selectedAirportCode && livePayloadCache.live_airports?.[selectedAirportCode]) {
      select.value = selectedAirportCode;
    } else {
      await loadHistory(null);
    }
  });

  scheduleNonCriticalTask(async () => {
    try {
      const pipeResp = await fetch("/api/pipeline");
      if (!pipeResp.ok) return;
      const pipePayload = await pipeResp.json();
      renderPipeline(pipePayload.airports || []);
    } catch (_e) {
      // no-op
    }
  }, 1200);
}

// Pull-to-Refresh for Mobile Users
let touchStart = 0;
const refreshThreshold = 80;

window.addEventListener('touchstart', (e) => {
  if (window.scrollY === 0) {
    touchStart = e.touches[0].pageY;
  } else {
    touchStart = 0;
  }
}, { passive: true });

window.addEventListener('touchend', (e) => {
  const touchEnd = e.changedTouches[0].pageY;
  if (touchStart > 0 && touchEnd - touchStart > refreshThreshold) {
    // Briefly show a visual cue (the ⟳ character in the trust/indicator section)
    const indicator = document.querySelector('.hero-trust');
    if (indicator) {
      indicator.style.color = 'var(--amber)';
      indicator.textContent = '⟳ Refreshing live data...';
      setTimeout(() => {
        indicator.style.color = '';
        indicator.textContent = '⟳ Updated about every 2 minutes — data from official airport systems';
      }, 1500);
    }
    silentRefresh();
  }
}, { passive: true });

// Auto-refresh every 2 min
setInterval(silentRefresh, 120000);
// Update the "Last Updated" text every 30 seconds
setInterval(updateRefreshText, 30 * 1000);

bootstrap();
