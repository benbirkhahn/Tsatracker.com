let chart;

function fmtMinutes(v) {
  const n = Number(v);
  if (Number.isNaN(n)) return "-";
  return `${Math.max(0, Math.round(n))} min`;
}
function waitTierClass(waitMinutes) {
  const n = Number(waitMinutes);
  if (n <= 7) return "wait-pill low";
  if (n <= 15) return "wait-pill med";
  if (n <= 25) return "wait-pill high";
  return "wait-pill critical";
}

function cleanCheckpointLabel(label) {
  if (!label) return "Checkpoint";
  return String(label)
    .replace(/ProjectedQueueTime.*$/i, "")
    .replace(/JourneyTime.*$/i, "")
    .replace(/\s+/g, " ")
    .trim();
}

function latestCapturedAt(rows) {
  if (!rows.length) return null;
  const ts = rows
    .map((r) => new Date(r.captured_at))
    .filter((d) => !Number.isNaN(d.getTime()))
    .sort((a, b) => b - a);
  return ts[0] || null;
}

function renderLiveCards(payload) {
  const host = document.getElementById("live-cards");
  host.innerHTML = "";
  const data = payload.data || {};
  const liveAirports = payload.live_airports || {};

  Object.keys(liveAirports).forEach((code) => {
    const card = document.createElement("div");
    card.className = "airport-card";
    const list = (data[code] || []).sort((a, b) => b.wait_minutes - a.wait_minutes).slice(0, 8);
    card.innerHTML = `<h3>${code} — ${liveAirports[code].name}</h3>`;
    if (!list.length) {
      card.innerHTML += `<div class="muted">No rows collected yet.</div>`;
    } else {
      list.forEach((row) => {
        const el = document.createElement("div");
        el.className = "checkpoint-row";
        el.innerHTML = `
          <div class="checkpoint-name">${cleanCheckpointLabel(row.checkpoint)}</div>
          <div class="${waitTierClass(row.wait_minutes)}">${fmtMinutes(row.wait_minutes)}</div>
        `;
        card.appendChild(el);
      });
      const updatedAt = latestCapturedAt(list);
      if (updatedAt) {
        const foot = document.createElement("div");
        foot.className = "updated-meta";
        foot.textContent = `Updated ${updatedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
        card.appendChild(foot);
      }
    }
    host.appendChild(card);
  });
}

function renderPipeline(rows) {
  const host = document.getElementById("pipeline-list");
  host.innerHTML = "";
  rows.forEach((row) => {
    const el = document.createElement("div");
    el.className = "pipeline-item";
    el.innerHTML = `
      <div><strong>${row.code}</strong> — ${row.name}</div>
      <div style="margin-top:6px;"><span class="status-badge">${row.status}</span></div>
      <div class="muted" style="margin-top:8px;">${row.notes}</div>
    `;
    host.appendChild(el);
  });
}

function normalizeHistory(rows) {
  // Aggregate by minute timestamp average to produce a clean stock-like line.
  const bucket = {};
  rows.forEach((r) => {
    const t = new Date(r.captured_at);
    const key = `${t.getUTCFullYear()}-${t.getUTCMonth() + 1}-${t.getUTCDate()} ${t.getUTCHours()}:${t.getUTCMinutes()}`;
    if (!bucket[key]) bucket[key] = { ts: t, sum: 0, c: 0 };
    bucket[key].sum += Number(r.wait_minutes) || 0;
    bucket[key].c += 1;
  });
  const points = Object.values(bucket)
    .sort((a, b) => a.ts - b.ts)
    .map((x) => ({
      label: x.ts.toISOString().slice(11, 16),
      value: x.c ? x.sum / x.c : 0,
    }));
  return points;
}

function drawChart(points, airportCode) {
  const ctx = document.getElementById("history-chart");
  if (chart) {
    chart.destroy();
  }
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: points.map((p) => p.label),
      datasets: [
        {
          label: `${airportCode} Avg Wait`,
          data: points.map((p) => p.value),
          borderColor: "#34d399",
          pointRadius: 0,
          borderWidth: 2,
          tension: 0.2,
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: {
          ticks: { color: "#9cb3d9" },
          grid: { color: "#24395f" },
        },
        y: {
          ticks: { color: "#9cb3d9" },
          grid: { color: "#24395f" },
          title: { display: true, text: "Minutes" },
        },
      },
      plugins: {
        legend: { labels: { color: "#e8f0ff" } },
      },
    },
  });
}

async function loadHistory(airportCode) {
  const resp = await fetch(`/api/history?airport=${airportCode}&hours=12`);
  const payload = await resp.json();
  const points = normalizeHistory(payload.rows || []);
  drawChart(points, airportCode);
}

async function bootstrap() {
  const [liveResp, pipeResp] = await Promise.all([fetch("/api/live"), fetch("/api/pipeline")]);
  const livePayload = await liveResp.json();
  const pipePayload = await pipeResp.json();
  renderLiveCards(livePayload);
  renderPipeline(pipePayload.airports || []);

  const select = document.getElementById("airport-select");
  Object.keys(livePayload.live_airports || {}).forEach((code) => {
    const opt = document.createElement("option");
    opt.value = code;
    opt.textContent = code;
    select.appendChild(opt);
  });
  select.addEventListener("change", (e) => loadHistory(e.target.value));
  if (select.value) {
    await loadHistory(select.value);
  }
}

bootstrap();
