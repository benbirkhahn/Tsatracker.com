(function () {
  "use strict";

  var root = document.querySelector("[data-airport-arrival-mode]");
  if (!root) return;

  var dataElement = document.getElementById("airport-arrival-mode-data");
  var stage = root.querySelector("[data-arrival-map-stage]");
  var canvas = document.getElementById("arrival-airport-map");
  var loading = root.querySelector("[data-arrival-map-loading]");
  var fallback = root.querySelector("[data-arrival-map-fallback]");
  var markerLayer = root.querySelector("[data-arrival-terminal-markers]");
  var markers = Array.prototype.slice.call(root.querySelectorAll("[data-arrival-terminal-marker]"));
  var expandButton = root.querySelector("[data-arrival-map-expand]");
  var doneButton = root.querySelector("[data-arrival-map-done]");
  var zoomControls = root.querySelector("[data-arrival-map-zoom]");
  var zoomInButton = root.querySelector("[data-arrival-zoom-in]");
  var zoomOutButton = root.querySelector("[data-arrival-zoom-out]");
  var instruction = root.querySelector("[data-arrival-map-instruction]");
  var status = root.querySelector("[data-arrival-map-status]");
  var form = root.querySelector("[data-decision-controls]");
  var result = root.querySelector("[data-decision-result]");
  var items = Array.prototype.slice.call(root.querySelectorAll("[data-arrival-checkpoint-item]"));
  var checkpointButtons = Array.prototype.slice.call(root.querySelectorAll("[data-arrival-checkpoint-choice]"));
  var compatibleCount = root.querySelector("[data-arrival-compatible-count]");
  var calculatorLink = root.querySelector("[data-arrival-calculator-link]");
  var sheet = root.querySelector("[data-arrival-sheet]");
  var sheetToggle = root.querySelector("[data-arrival-sheet-toggle]");
  var sheetToggleLabel = root.querySelector("[data-arrival-sheet-toggle-label]");
  var currentLabel = root.querySelector("[data-arrival-current-label]");
  var currentWait = root.querySelector("[data-arrival-current-wait]");
  var currentSource = root.querySelector("[data-arrival-current-source]");
  var currentTrend = root.querySelector("[data-arrival-current-trend]");
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  var mobileLayout = window.matchMedia("(max-width: 700px)");
  var HANDOFF_KEY = "tsaAirportHandoffV1";
  var HANDOFF_MAX_AGE_MS = 10000;
  var DEFAULT_CENTER = [36.083, -115.152];
  var DEFAULT_BOUNDS = [[36.055, -115.19], [36.105, -115.125]];
  var DEFAULT_OVERVIEW_ZOOM = 13.75;
  var DEFAULT_DETAIL_ZOOM = 15.25;

  var model;
  try {
    model = JSON.parse(dataElement ? dataElement.textContent || "{}" : "{}");
  } catch (_error) {
    model = {};
  }

  var airportObject = model && typeof model.airport === "object" ? model.airport : {};
  var code = String(root.dataset.airportCode || airportObject.code || model.code || model.airport || "LAS").toUpperCase();
  var decisionMode = String(model.decision_mode || "terminal_gate");
  var checkpointOnly = decisionMode === "checkpoint_only";
  var terminalCheckpoint = decisionMode === "terminal_checkpoint";
  var gateRouting = decisionMode === "terminal_gate";
  var terminalRouting = gateRouting || terminalCheckpoint;
  var mapConfig = model.map || {};
  var map = null;
  var imagery = null;
  var checkpointById = buildCheckpointIndex(model);
  var selectedTerminal = "";
  var selectedGate = "";
  var selectedLane = "STANDARD";
  var selectedCheckpoint = "";
  var recommendedCheckpoint = "";
  var isExpanded = false;
  var isSheetDetailed = false;
  var tileErrors = 0;
  var mapUnavailable = false;
  var initialTilesSettled = false;
  var tileTimeout = null;
  var handoff = readHandoff();
  var handoffSettled = !handoff || reduceMotion.matches;
  var refreshTimer = null;
  var refreshSeconds = Math.max(30, numeric(model.refresh_seconds) || 120);
  var inertRecords = [];
  var initialSummary = {
    label: currentLabel ? currentLabel.textContent : "Current airport wait",
    wait: currentWait ? currentWait.innerHTML : "",
    waitClass: currentWait ? currentWait.className : "arrival-current-wait",
    source: currentSource ? currentSource.textContent : "",
    sourceClass: currentSource ? currentSource.className : "",
    trend: currentTrend ? currentTrend.textContent : "",
    trendClass: currentTrend ? currentTrend.className : ""
  };

  function numeric(value) {
    if (value === null || value === undefined || value === "") return null;
    var parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function coordinates(value, fallbackValue) {
    if (!Array.isArray(value) || value.length < 2) return fallbackValue;
    var lat = numeric(value[0]);
    var lng = numeric(value[1]);
    return lat === null || lng === null ? fallbackValue : [lat, lng];
  }

  function terminalId(terminal) {
    return String((terminal && terminal.id) || "").toLowerCase();
  }

  function laneType(lane) {
    return String((lane && (lane.lane_type || lane.type)) || "STANDARD").toUpperCase();
  }

  function laneFreshness(lane, checkpoint) {
    var value = String((lane && (lane.freshness_status || lane.freshness || lane.status)) || "").toLowerCase();
    if (["live", "aging", "stale", "no_current_reading", "published_only"].indexOf(value) !== -1) return value;
    if (checkpoint && checkpoint.published_only && numeric(lane && lane.wait_minutes) === null) return "published_only";
    return numeric(lane && lane.wait_minutes) === null ? "no_current_reading" : "live";
  }

  function laneLabel(lane) {
    if (lane && lane.label) return String(lane.label);
    return laneType(lane) === "PRECHECK" ? "PreCheck" : "Standard";
  }

  function buildCheckpointIndex(source) {
    var index = {};
    (source.terminals || []).forEach(function (terminal) {
      (terminal.checkpoints || []).forEach(function (checkpoint) {
        checkpoint.terminal_id = checkpoint.terminal_id || terminal.id;
        checkpoint.terminal_label = checkpoint.terminal_label || terminal.label;
        checkpoint.lanes = Array.isArray(checkpoint.lanes) ? checkpoint.lanes.slice() : [];
        ["STANDARD", "PRECHECK"].forEach(function (type) {
          if (checkpoint.lanes.some(function (lane) { return laneType(lane) === type; })) return;
          var fallbackWait = type === "STANDARD" ? checkpoint.standard_wait : checkpoint.precheck_wait;
          checkpoint.lanes.push({
            lane_type: type,
            label: type === "PRECHECK" ? "PreCheck" : "Standard",
            wait_minutes: fallbackWait === undefined ? null : fallbackWait,
            freshness_status: checkpoint.published_only ? "published_only" : (numeric(fallbackWait) === null ? "no_current_reading" : "live")
          });
        });
        index[String(checkpoint.id)] = checkpoint;
      });
    });
    return index;
  }

  function checkpointLane(checkpointId, type) {
    var checkpoint = checkpointById[checkpointId];
    if (!checkpoint) return null;
    return (checkpoint.lanes || []).find(function (lane) {
      return laneType(lane) === String(type || "STANDARD").toUpperCase();
    }) || null;
  }

  function isFreshReading(lane, checkpoint) {
    var freshness = laneFreshness(lane, checkpoint);
    return (freshness === "live" || freshness === "aging") && numeric(lane && lane.wait_minutes) !== null;
  }

  function waitTier(minutes) {
    var wait = numeric(minutes);
    if (wait === null || wait <= 15) return "low";
    if (wait <= 30) return "med";
    if (wait <= 45) return "high";
    return "crit";
  }

  function gateList(item, attribute) {
    return String(item.getAttribute(attribute) || "").split(/\s+/).filter(Boolean);
  }

  function selected(name) {
    var input = form && form.querySelector('input[name="' + name + '"]:checked');
    return input ? input.value : "";
  }

  function selectRadio(name, value) {
    if (!form) return;
    var inputs = Array.prototype.slice.call(form.querySelectorAll('input[name="' + name + '"]'));
    inputs.forEach(function (input) {
      input.checked = input.value === value;
    });
  }

  function itemName(item) {
    if (!item) return "selected checkpoint";
    var checkpoint = checkpointById[item.dataset.checkpointId];
    return checkpoint ? checkpoint.label : "checkpoint";
  }

  function terminalForId(id) {
    return (model.terminals || []).find(function (terminal) {
      return terminalId(terminal) === String(id || "").toLowerCase();
    }) || null;
  }

  function mapCenter() {
    return coordinates(mapConfig.center, DEFAULT_CENTER);
  }

  function mapBounds() {
    var bounds = Array.isArray(mapConfig.bounds) ? mapConfig.bounds : DEFAULT_BOUNDS;
    return [coordinates(bounds[0], DEFAULT_BOUNDS[0]), coordinates(bounds[1], DEFAULT_BOUNDS[1])];
  }

  function interactionBounds() {
    var bounds = mapBounds();
    var latPadding = Math.max(0.03, Math.abs(bounds[1][0] - bounds[0][0]) * 1.4);
    var lngPadding = Math.max(0.04, Math.abs(bounds[1][1] - bounds[0][1]) * 1.4);
    return [
      [bounds[0][0] - latPadding, bounds[0][1] - lngPadding],
      [bounds[1][0] + latPadding, bounds[1][1] + lngPadding]
    ];
  }

  function overviewZoom() {
    return numeric(mapConfig.overview_zoom) === null ? DEFAULT_OVERVIEW_ZOOM : Number(mapConfig.overview_zoom);
  }

  function detailZoom() {
    return numeric(mapConfig.detail_zoom) === null ? DEFAULT_DETAIL_ZOOM : Number(mapConfig.detail_zoom);
  }

  function announce(message) {
    if (status) status.textContent = message;
  }

  function readHandoff() {
    var raw = null;
    try {
      raw = window.sessionStorage.getItem(HANDOFF_KEY);
      if (raw !== null) window.sessionStorage.removeItem(HANDOFF_KEY);
    } catch (_error) {
      return null;
    }
    if (!raw) return null;

    try {
      var payload = JSON.parse(raw);
      var startedAt = numeric(payload.startedAt);
      if (startedAt === null) startedAt = Date.parse(payload.startedAt);
      var age = Date.now() - startedAt;
      var center = coordinates(payload.center, null);
      var zoom = numeric(payload.zoom);
      var source = String(payload.source || "");
      if (Number(payload.version) !== 1 || String(payload.code || "").toUpperCase() !== code ||
          !center || center[0] < -90 || center[0] > 90 || center[1] < -180 || center[1] > 180 ||
          zoom === null || zoom < 10 || zoom > 17 || source !== "home-map" ||
          !Number.isFinite(age) || age < -2000 || age > HANDOFF_MAX_AGE_MS) {
        return null;
      }
      return { center: center, zoom: zoom, source: source };
    } catch (_error) {
      return null;
    }
  }

  function backgroundTargets() {
    var targets = [];
    var rootParent = root.parentElement;
    Array.prototype.slice.call(document.body.children).forEach(function (element) {
      if (element !== rootParent && element.tagName !== "SCRIPT") targets.push(element);
    });
    if (rootParent) {
      Array.prototype.slice.call(rootParent.children).forEach(function (element) {
        if (element !== root && element.tagName !== "SCRIPT") targets.push(element);
      });
    }
    return targets;
  }

  function setBackgroundInert(active) {
    if (active) {
      if (inertRecords.length) return;
      backgroundTargets().forEach(function (element) {
        inertRecords.push({ element: element, hadAttribute: element.hasAttribute("inert") });
        element.setAttribute("inert", "");
      });
      return;
    }
    inertRecords.forEach(function (record) {
      if (!record.hadAttribute) record.element.removeAttribute("inert");
    });
    inertRecords = [];
  }

  function setLoadingSettled() {
    if (initialTilesSettled) return;
    initialTilesSettled = true;
    window.clearTimeout(tileTimeout);
    if (loading) loading.hidden = true;
    if (stage) stage.setAttribute("aria-busy", "false");
  }

  function showMapFallback(message) {
    mapUnavailable = true;
    root.classList.add("has-arrival-map-error");
    if (canvas) canvas.setAttribute("aria-hidden", "true");
    if (markerLayer) markerLayer.hidden = true;
    if (zoomControls) zoomControls.hidden = true;
    [zoomInButton, zoomOutButton].forEach(function (button) {
      if (button) button.disabled = true;
    });
    if (fallback) {
      fallback.hidden = false;
      var strong = fallback.querySelector("strong");
      if (strong && message) strong.textContent = message;
    }
    setLoadingSettled();
    syncResponsiveMap();
    announce("Satellite imagery is unavailable. Checkpoint controls remain available.");
    if (!handoffSettled) completeHandoff();
  }

  function clearMapFallback() {
    if (!mapUnavailable) return;
    mapUnavailable = false;
    root.classList.remove("has-arrival-map-error");
    if (fallback) fallback.hidden = true;
    if (canvas) canvas.setAttribute("aria-hidden", "false");
    if (markerLayer) markerLayer.hidden = false;
    if (zoomControls) zoomControls.hidden = false;
    [zoomInButton, zoomOutButton].forEach(function (button) {
      if (button) button.disabled = false;
    });
    positionMarkers();
    syncResponsiveMap();
  }

  function positionMarkers() {
    if (!map) return;
    markers.forEach(function (marker) {
      var terminal = terminalForId(marker.dataset.arrivalTerminalMarker);
      var anchor = coordinates(terminal && terminal.anchor, coordinates([marker.dataset.lat, marker.dataset.lng], null));
      if (!anchor) return;
      var point = map.latLngToContainerPoint(anchor);
      var markerOffset = terminal && Array.isArray(terminal.marker_offset) ? terminal.marker_offset : [0, 0];
      var applyOffset = map.getZoom() <= overviewZoom() + 0.5;
      var offsetX = applyOffset ? numeric(markerOffset[0]) || 0 : 0;
      var offsetY = applyOffset ? numeric(markerOffset[1]) || 0 : 0;
      marker.style.left = Math.round(point.x + offsetX) + "px";
      marker.style.top = Math.round(point.y + offsetY) + "px";
    });
  }

  function setMapHandlers(enabled) {
    if (!map) return;
    ["dragging", "touchZoom", "doubleClickZoom", "boxZoom", "keyboard"].forEach(function (name) {
      if (!map[name]) return;
      map[name][enabled ? "enable" : "disable"]();
    });
    if (map.scrollWheelZoom) map.scrollWheelZoom[enabled && !mobileLayout.matches ? "enable" : "disable"]();
  }

  function syncResponsiveMap() {
    var embeddedMobile = mobileLayout.matches && !isExpanded && handoffSettled;
    root.classList.toggle("is-mobile-arrival", mobileLayout.matches);
    root.classList.toggle("is-mobile-embedded", embeddedMobile);
    setMapHandlers(!mapUnavailable && !embeddedMobile);
    if (expandButton) {
      expandButton.hidden = mapUnavailable || !mobileLayout.matches || isExpanded || !handoffSettled;
      expandButton.setAttribute("aria-expanded", isExpanded ? "true" : "false");
    }
    if (doneButton) doneButton.hidden = !isExpanded && handoffSettled;
    if (instruction) {
      instruction.textContent = embeddedMobile
        ? "Explore airport to pan and pinch"
        : checkpointOnly ? "Drag to explore · choose a checkpoint below"
          : "Drag to explore · choose a terminal marker";
    }
  }

  function fitOverview(animate) {
    if (!map) return;
    var options = {
      animate: Boolean(animate && !reduceMotion.matches),
      paddingTopLeft: [48, 64],
      paddingBottomRight: mobileLayout.matches && isExpanded ? [48, 190] : [48, 64],
      maxZoom: overviewZoom()
    };
    map.fitBounds(mapBounds(), options);
  }

  function focusTerminal(id, animate) {
    var terminal = terminalForId(id);
    var anchor = coordinates(terminal && terminal.anchor, null);
    if (!map || !anchor) return;
    map.flyTo(anchor, detailZoom(), {
      animate: Boolean(animate && !reduceMotion.matches),
      duration: reduceMotion.matches ? 0 : 0.72,
      easeLinearity: 0.22
    });
  }

  function setSheetDetailed(detailed) {
    isSheetDetailed = Boolean(detailed);
    if (sheet) sheet.dataset.sheetState = isSheetDetailed ? "detail" : "peek";
    root.classList.toggle("is-sheet-detail", isSheetDetailed);
    if (sheetToggle) sheetToggle.setAttribute("aria-expanded", isSheetDetailed ? "true" : "false");
    if (sheetToggleLabel) sheetToggleLabel.textContent = isSheetDetailed ? "Show map" : "Show details";
    window.requestAnimationFrame(function () {
      if (map) map.invalidateSize({ pan: false });
    });
  }

  function setExpanded(expanded, options) {
    options = options || {};
    isExpanded = Boolean(expanded);
    root.classList.toggle("is-expanded", isExpanded);
    document.body.classList.toggle("arrival-map-is-expanded", isExpanded || !handoffSettled);
    setBackgroundInert(isExpanded || !handoffSettled);
    setSheetDetailed(false);
    syncResponsiveMap();
    window.requestAnimationFrame(function () {
      if (!map) return;
      map.invalidateSize({ pan: false });
      if (isExpanded) fitOverview(false);
    });
    if (options.focus) {
      var focusTarget = isExpanded ? doneButton : expandButton;
      if (focusTarget) window.setTimeout(function () { focusTarget.focus(); }, 0);
    }
    announce(isExpanded ? "Expanded airport map. Use Done or Escape to return to the page." : "Returned to the embedded airport map.");
  }

  function settleHandoff() {
    if (handoffSettled) return;
    handoffSettled = true;
    root.classList.remove("is-handoff");
    document.body.classList.remove("arrival-map-is-expanded");
    setBackgroundInert(false);
    if (doneButton) doneButton.hidden = true;
    syncResponsiveMap();
    window.setTimeout(function () {
      if (map) {
        map.invalidateSize({ pan: false });
        fitOverview(false);
      }
      if (stage) stage.focus({ preventScroll: true });
    }, 80);
    announce(code + " Arrival Mode ready. " + (checkpointOnly
      ? "Choose a screening lane or checkpoint."
      : gateRouting
        ? "Choose a terminal, gate, or checkpoint."
        : "Choose a terminal area, screening lane, or checkpoint."));
  }

  function completeHandoff() {
    if (handoffSettled) return;
    var finish = function () {
      window.setTimeout(settleHandoff, 420);
    };
    if (!map || reduceMotion.matches) {
      settleHandoff();
      return;
    }
    map.once("moveend", finish);
    map.flyTo(mapCenter(), overviewZoom(), {
      duration: 0.95,
      easeLinearity: 0.2
    });
    window.setTimeout(finish, 1500);
  }

  function initializeMap() {
    if (!window.L || !canvas) {
      showMapFallback("Satellite map could not load.");
      syncResponsiveMap();
      return;
    }

    if (handoff && !reduceMotion.matches) {
      handoffSettled = false;
      root.classList.add("is-handoff");
      document.body.classList.add("arrival-map-is-expanded");
      setBackgroundInert(true);
    }

    map = window.L.map(canvas, {
      attributionControl: true,
      boxZoom: true,
      doubleClickZoom: true,
      dragging: true,
      keyboard: true,
      keyboardPanDelta: 72,
      maxBounds: interactionBounds(),
      maxBoundsViscosity: 0.82,
      scrollWheelZoom: true,
      tap: true,
      touchZoom: true,
      zoomControl: false,
      zoomDelta: 0.5,
      zoomSnap: 0.25
    });

    imagery = window.L.tileLayer(
      String(mapConfig.tile_url || "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}"),
      {
        minZoom: 10,
        maxNativeZoom: 16,
        maxZoom: 17,
        noWrap: true,
        keepBuffer: 2,
        updateWhenIdle: true,
        attribution: mapConfig.tile_attribution || 'Imagery: <a href="https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer" target="_blank" rel="noopener">USDA / USGS The National Map</a>'
      }
    );

    imagery.on("loading", function () { tileErrors = 0; });
    imagery.on("tileerror", function () {
      tileErrors += 1;
      if (tileErrors >= 4) showMapFallback("Satellite imagery is temporarily unavailable.");
    });
    imagery.on("load", function () {
      if (tileErrors < 4) {
        clearMapFallback();
      }
      setLoadingSettled();
      if (!handoffSettled) completeHandoff();
    });
    imagery.addTo(map);

    if (handoff && !reduceMotion.matches) {
      map.setView(handoff.center, Math.min(17, Math.max(10, handoff.zoom)), { animate: false });
    } else {
      map.fitBounds(mapBounds(), { padding: [48, 48], maxZoom: overviewZoom(), animate: false });
    }

    map.on("move zoom resize", positionMarkers);
    map.on("zoomend", function () {
      if (zoomInButton) zoomInButton.disabled = map.getZoom() >= map.getMaxZoom() - 0.01;
      if (zoomOutButton) zoomOutButton.disabled = map.getZoom() <= map.getMinZoom() + 0.01;
    });
    map.whenReady(function () {
      canvas.setAttribute("aria-hidden", mapUnavailable ? "true" : "false");
      if (markerLayer) markerLayer.hidden = mapUnavailable;
      if (zoomControls) zoomControls.hidden = mapUnavailable;
      positionMarkers();
      syncResponsiveMap();
      if (!handoffSettled && doneButton) doneButton.focus({ preventScroll: true });
    });

    tileTimeout = window.setTimeout(function () {
      setLoadingSettled();
      if (!handoffSettled) completeHandoff();
    }, 5000);
  }

  function displayLaneValue(lane, checkpoint) {
    var freshness = laneFreshness(lane, checkpoint);
    var wait = numeric(lane && lane.wait_minutes);
    if (wait !== null && (freshness === "live" || freshness === "aging")) return Math.round(wait) + " min";
    if (freshness === "stale") return "Stale";
    if (freshness === "published_only") return "Published only";
    return "No current reading";
  }

  function syncLaneRows() {
    items.forEach(function (item) {
      var checkpoint = checkpointById[item.dataset.checkpointId];
      Array.prototype.slice.call(item.querySelectorAll("[data-arrival-lane-reading]")).forEach(function (row) {
        var type = String(row.dataset.laneType || "STANDARD").toUpperCase();
        var lane = checkpointLane(item.dataset.checkpointId, type);
        var value = row.querySelector("[data-arrival-lane-value]");
        row.hidden = type !== selectedLane;
        row.dataset.waitMinutes = numeric(lane && lane.wait_minutes) === null ? "" : String(lane.wait_minutes);
        row.dataset.freshness = laneFreshness(lane, checkpoint);
        row.classList.toggle("is-aging", laneFreshness(lane, checkpoint) === "aging");
        row.classList.toggle("is-stale", !isFreshReading(lane, checkpoint));
        if (value) value.textContent = displayLaneValue(lane, checkpoint);
      });
    });
  }

  function restoreCurrentSummary() {
    if (currentLabel) currentLabel.textContent = initialSummary.label;
    if (currentWait) {
      currentWait.innerHTML = initialSummary.wait;
      currentWait.className = initialSummary.waitClass;
    }
    if (currentSource) {
      currentSource.textContent = initialSummary.source;
      currentSource.className = initialSummary.sourceClass;
    }
    if (currentTrend) {
      currentTrend.textContent = initialSummary.trend;
      currentTrend.className = initialSummary.trendClass;
    }
  }

  function updateCurrentSummary(checkpointId) {
    var checkpoint = checkpointById[checkpointId];
    var lane = checkpointLane(checkpointId, selectedLane);
    if (!checkpoint || !lane) {
      restoreCurrentSummary();
      return;
    }
    var freshness = laneFreshness(lane, checkpoint);
    var wait = numeric(lane.wait_minutes);
    if (currentLabel) currentLabel.textContent = checkpoint.label + " · " + laneLabel(lane);
    if (currentWait) {
      currentWait.className = "arrival-current-wait" + (isFreshReading(lane, checkpoint) ? " " + waitTier(wait) : "");
      currentWait.innerHTML = isFreshReading(lane, checkpoint)
        ? Math.round(wait) + "<small> min</small>"
        : "<span>No fresh reading</span>";
    }
    if (currentSource) {
      currentSource.className = "arrival-current-source " + (isFreshReading(lane, checkpoint) ? "source-live" : "source-estimated");
      currentSource.textContent = freshness === "live" ? "Official checkpoint reading"
        : freshness === "aging" ? "Aging official reading"
          : freshness === "stale" ? "Stale reading suppressed"
            : freshness === "published_only" ? "Published checkpoint only" : "No current reading";
    }
    if (currentTrend) {
      currentTrend.className = "arrival-current-trend " + String(lane.trend || "");
      currentTrend.textContent = isFreshReading(lane, checkpoint)
        ? lane.trend
          ? String(lane.trend_arrow || "→") + " " + lane.trend + " for this checkpoint and lane"
          : "Fresh official reading · lane trend not available yet"
        : "Use the labeled airport estimate for planning when this reading is unavailable.";
    }
  }

  function syncTerminalMarkers(activeTerminal) {
    markers.forEach(function (marker) {
      var active = marker.dataset.arrivalTerminalMarker === activeTerminal;
      marker.classList.toggle("is-active", active);
      marker.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function updateCalculatorLink(checkpointId) {
    if (!calculatorLink) return;
    var query = new URLSearchParams({ airport: code, lane: selectedLane });
    if (checkpointId) query.set("checkpoint", checkpointId);
    calculatorLink.href = "/when-should-i-leave?" + query.toString();
    calculatorLink.setAttribute(
      "aria-label",
      "Calculate when to leave for " + code +
        (checkpointId ? " using " + itemName(items.find(function (item) { return item.dataset.checkpointId === checkpointId; })) : "") +
        " and " + (selectedLane === "PRECHECK" ? "PreCheck" : "standard screening")
    );
  }

  function updateDecision() {
    selectedTerminal = String(selected("decision-terminal") || "").toLowerCase();
    selectedGate = String(selected("decision-gate") || "").toUpperCase();
    selectedLane = String(selected("decision-lane") || "STANDARD").toUpperCase();
    var filterActive = Boolean(selectedGate || selectedTerminal);
    var allowRecommendation = Boolean(selectedGate);
    var compatible = items.slice();
    var message = "Choose a gate or terminal to compare compatible checkpoints.";
    var conflict = (selectedTerminal === "t3" && /^(A|B|C)$/.test(selectedGate)) ||
      (selectedTerminal === "t1" && selectedGate === "E");

    if (checkpointOnly) {
      filterActive = false;
      allowRecommendation = true;
      message = items.length
        ? "Comparing fresh " + (selectedLane === "PRECHECK" ? "PreCheck" : "standard-screening") + " readings across reporting checkpoints."
        : "No current checkpoint rows are available. Use the labeled airport planning estimate.";
    } else if (terminalCheckpoint) {
      filterActive = Boolean(selectedTerminal);
      allowRecommendation = true;
      if (selectedTerminal) {
        compatible = items.filter(function (item) { return item.dataset.terminal === selectedTerminal; });
        var selectedTerminalModel = terminalForId(selectedTerminal);
        message = "Comparing fresh " + (selectedLane === "PRECHECK" ? "PreCheck" : "standard-screening") +
          " readings near " + (selectedTerminalModel ? selectedTerminalModel.label : "the selected terminal area") + ".";
      } else {
        message = items.length
          ? "Comparing fresh " + (selectedLane === "PRECHECK" ? "PreCheck" : "standard-screening") + " readings across all terminal areas."
          : "No current checkpoint rows are available. Use the labeled airport planning estimate.";
      }
    } else if (conflict) {
      compatible = [];
      allowRecommendation = false;
      message = "That gate and terminal combination does not match this routing map. Recheck the terminal on your boarding pass.";
    } else if (!selectedGate && selectedTerminal) {
      compatible = items.filter(function (item) { return item.dataset.terminal === selectedTerminal; });
      allowRecommendation = false;
      message = "Showing all published checkpoints for " + (selectedTerminal === "t1" ? "Terminal 1." : "Terminal 3.");
    } else if (selectedGate) {
      compatible = items.filter(function (item) {
        return gateList(item, "data-compatible-gates").indexOf(selectedGate) !== -1 &&
          (!selectedTerminal || item.dataset.terminal === selectedTerminal);
      });
      if (selectedGate === "D" && !selectedTerminal) {
        allowRecommendation = false;
        message = "Gate D can route through Terminal 1 or Terminal 3. Choose your check-in terminal to compare the right checkpoint.";
      }
    }

    var ranked = compatible.map(function (item, index) {
      var checkpoint = checkpointById[item.dataset.checkpointId];
      var lane = checkpointLane(item.dataset.checkpointId, selectedLane);
      return {
        item: item,
        checkpoint: checkpoint,
        lane: lane,
        wait: numeric(lane && lane.wait_minutes),
        primary: gateList(item, "data-primary-gates").indexOf(selectedGate) !== -1 ? 0 : 1,
        index: index
      };
    }).filter(function (entry) {
      return isFreshReading(entry.lane, entry.checkpoint);
    }).sort(function (a, b) {
      return (a.wait - b.wait) || (a.primary - b.primary) || (a.index - b.index);
    });

    var fastest = allowRecommendation && ranked.length ? ranked[0] : null;
    recommendedCheckpoint = fastest ? fastest.item.dataset.checkpointId : "";
    if (fastest) {
      message = (checkpointOnly ? "Fastest fresh reading: " : terminalCheckpoint ? "Fastest fresh reading in this view: " : "Fastest compatible fresh reading: ") + itemName(fastest.item) + ", " +
        Math.round(fastest.wait) + " minutes for " + (selectedLane === "PRECHECK" ? "PreCheck." : "standard screening.");
    } else if (allowRecommendation && compatible.length) {
      var laneName = selectedLane === "PRECHECK" ? "PreCheck" : "standard";
      message = checkpointOnly
        ? "No reporting checkpoint has a fresh " + laneName + " reading."
        : terminalCheckpoint
          ? "No checkpoint in this view has a fresh " + laneName + " reading."
          : "Compatible checkpoints are highlighted, but no fresh " + laneName + " reading is available.";
    }

    if (selectedCheckpoint && filterActive && !compatible.some(function (item) { return item.dataset.checkpointId === selectedCheckpoint; })) {
      selectedCheckpoint = "";
    }

    items.forEach(function (item) {
      var isCompatible = compatible.indexOf(item) !== -1;
      var isFastest = Boolean(fastest && fastest.item === item);
      var isSelected = item.dataset.checkpointId === selectedCheckpoint;
      var button = item.querySelector("[data-arrival-checkpoint-choice]");
      var state = item.querySelector("[data-checkpoint-state]");
      item.classList.toggle("is-compatible", filterActive && isCompatible);
      item.classList.toggle("is-muted", filterActive && !isCompatible);
      item.classList.toggle("is-fastest", isFastest);
      item.classList.toggle("is-selected", isSelected);
      if (button) button.setAttribute("aria-pressed", isSelected ? "true" : "false");
      if (state) state.textContent = isFastest ? "Fastest fresh" : isSelected ? "Selected" : "";
    });

    syncLaneRows();
    var summaryCheckpoint = selectedCheckpoint || recommendedCheckpoint;
    if (summaryCheckpoint) updateCurrentSummary(summaryCheckpoint); else restoreCurrentSummary();
    var activeCheckpoint = checkpointById[summaryCheckpoint];
    var activeTerminal = activeCheckpoint ? String(activeCheckpoint.terminal_id || "").toLowerCase() : selectedTerminal;
    syncTerminalMarkers(activeTerminal);
    updateCalculatorLink(summaryCheckpoint);
    if (result) result.textContent = message;
    if (compatibleCount) compatibleCount.textContent = compatible.length + (checkpointOnly ? " checkpoints" : terminalCheckpoint ? " shown" : " compatible");
  }

  function chooseTerminal(id, moveMap) {
    selectedTerminal = String(id || "").toLowerCase();
    selectRadio("decision-terminal", selectedTerminal);
    selectedCheckpoint = "";
    updateDecision();
    if (selectedTerminal && moveMap) focusTerminal(selectedTerminal, true);
    var terminal = terminalForId(selectedTerminal);
    announce((terminal ? terminal.label : "Terminal") + " selected. Compatible checkpoint choices updated.");
  }

  function chooseCheckpoint(id) {
    var item = items.find(function (candidate) { return candidate.dataset.checkpointId === id; });
    if (!item) return;
    var terminal = item.dataset.terminal;
    var compatibleWithGate = !selectedGate || gateList(item, "data-compatible-gates").indexOf(selectedGate) !== -1;
    selectedCheckpoint = id;
    selectedTerminal = terminal;
    selectRadio("decision-terminal", terminal);
    if (gateRouting && !compatibleWithGate) {
      selectedGate = "";
      selectRadio("decision-gate", "");
    }
    updateDecision();
    focusTerminal(terminal, true);
    announce(itemName(item) + " selected. The leave-time calculator will use this checkpoint and lane when the reading is fresh.");
  }

  function refreshFromApi() {
    if (document.hidden || !window.fetch) return;
    window.fetch("/api/airport-arrival-mode?airport=" + encodeURIComponent(code), {
      headers: { "Accept": "application/json" },
      credentials: "same-origin"
    }).then(function (response) {
      if (!response.ok) throw new Error("Arrival Mode refresh failed");
      return response.json();
    }).then(function (payload) {
      var next = payload.airport_arrival_mode || payload;
      var nextAirport = next && typeof next.airport === "object" ? next.airport.code : (next.code || next.airport);
      if (!next || String(nextAirport || "").toUpperCase() !== code) return;
      model = next;
      mapConfig = next.map || mapConfig;
      checkpointById = buildCheckpointIndex(next);
      updateDecision();
      announce("Checkpoint readings refreshed.");
    }).catch(function () {
      announce("Current checkpoint refresh paused. Showing the most recent available data.");
    });
  }

  function startRefreshTimer() {
    window.clearInterval(refreshTimer);
    refreshTimer = window.setInterval(refreshFromApi, refreshSeconds * 1000);
  }

  if (form) {
    form.addEventListener("change", function (event) {
      updateDecision();
      if (event.target && event.target.name === "decision-terminal" && event.target.value) {
        focusTerminal(event.target.value, true);
      }
    });
  }

  markers.forEach(function (marker) {
    marker.addEventListener("click", function () {
      if (checkpointOnly) {
        fitOverview(true);
        syncTerminalMarkers(marker.dataset.arrivalTerminalMarker);
        announce(code + " airport overview focused. Choose a checkpoint from the panel for current lane detail.");
      } else if (terminalRouting) {
        chooseTerminal(marker.dataset.arrivalTerminalMarker, true);
      }
    });
  });

  checkpointButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      chooseCheckpoint(button.dataset.arrivalCheckpointChoice);
    });
  });

  if (expandButton) expandButton.addEventListener("click", function () { setExpanded(true, { focus: true }); });
  if (doneButton) doneButton.addEventListener("click", function () {
    if (!handoffSettled) settleHandoff(); else setExpanded(false, { focus: true });
  });
  if (sheetToggle) sheetToggle.addEventListener("click", function () { setSheetDetailed(!isSheetDetailed); });
  if (zoomInButton) zoomInButton.addEventListener("click", function () { if (map) map.zoomIn(0.5); });
  if (zoomOutButton) zoomOutButton.addEventListener("click", function () { if (map) map.zoomOut(0.5); });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    if (handoffSettled && !isExpanded && !root.contains(document.activeElement)) return;
    if (isSheetDetailed) {
      event.preventDefault();
      setSheetDetailed(false);
      if (sheetToggle) sheetToggle.focus();
    } else if (!handoffSettled) {
      event.preventDefault();
      settleHandoff();
    } else if (isExpanded) {
      event.preventDefault();
      setExpanded(false, { focus: true });
    }
  });

  var onMobileChange = function () {
    if (!mobileLayout.matches && isExpanded) setExpanded(false, { focus: false });
    syncResponsiveMap();
    window.requestAnimationFrame(function () { if (map) map.invalidateSize({ pan: false }); });
  };
  if (mobileLayout.addEventListener) mobileLayout.addEventListener("change", onMobileChange);
  else if (mobileLayout.addListener) mobileLayout.addListener(onMobileChange);

  window.addEventListener("pageshow", function (event) {
    if (!event.persisted) return;
    handoffSettled = true;
    root.classList.remove("is-handoff");
    setExpanded(false, { focus: false });
    startRefreshTimer();
  });

  updateDecision();
  initializeMap();
  startRefreshTimer();
  window.addEventListener("pagehide", function () {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  });
})();

(function () {
  var map = document.querySelector("[data-decision-map]");
  if (!map) return;

  var form = map.querySelector("[data-decision-controls]");
  var result = map.querySelector("[data-decision-result]");
  var nodes = Array.prototype.slice.call(map.querySelectorAll("[data-checkpoint-node]"));
  var rails = Array.prototype.slice.call(map.querySelectorAll("[data-terminal-rail]"));

  function selected(name) {
    var input = form.querySelector('input[name="' + name + '"]:checked');
    return input ? input.value : "";
  }

  function gateList(node, attribute) {
    return (node.getAttribute(attribute) || "").split(/\s+/).filter(Boolean);
  }

  function nodeName(node) {
    var heading = node.querySelector("h4");
    return heading ? heading.textContent.trim() : "checkpoint";
  }

  function setNodeState(compatible, fastest, filterActive) {
    nodes.forEach(function (node) {
      var isCompatible = compatible.indexOf(node) !== -1;
      var state = node.querySelector("[data-node-state]");
      node.classList.toggle("is-compatible", isCompatible);
      node.classList.toggle("is-muted", filterActive && !isCompatible);
      node.classList.toggle("is-fastest", node === fastest);
      if (node.parentElement) node.parentElement.classList.toggle("has-compatible", filterActive && isCompatible);
      if (state) {
        state.textContent = !filterActive ? "" : node === fastest
          ? "Fastest compatible live reading for the selected route and lane."
          : isCompatible
            ? "Compatible with the selected route."
            : "Not compatible with the selected route.";
      }
    });
    rails.forEach(function (rail) {
      var hasCompatible = compatible.some(function (node) { return rail.contains(node); });
      rail.classList.toggle("has-compatible", filterActive && hasCompatible);
    });
  }

  function update() {
    var gate = selected("decision-gate");
    var lane = selected("decision-lane") || "standard";
    var terminal = selected("decision-terminal");
    var compatible = [];
    var allowRecommendation = true;
    var message = "Choose a gate to highlight compatible checkpoints.";

    if (!gate) {
      compatible = terminal
        ? nodes.filter(function (node) { return node.dataset.terminal === terminal; })
        : [];
      message = terminal
        ? "Showing checkpoints published for " + (terminal === "t1" ? "Terminal 1." : "Terminal 3.")
        : message;
      allowRecommendation = false;
    } else {
      var conflict = (terminal === "t3" && /^(A|B|C)$/.test(gate)) ||
        (terminal === "t1" && gate === "E");
      if (conflict) {
        setNodeState([], null, true);
        result.textContent = "That gate and terminal combination does not match this routing map. Recheck the terminal on your boarding pass.";
        return;
      }

      compatible = nodes.filter(function (node) {
        return gateList(node, "data-compatible-gates").indexOf(gate) !== -1 &&
          (!terminal || node.dataset.terminal === terminal);
      });

      if (gate === "D" && !terminal) {
        message = "Gate D can route through Terminal 1 or Terminal 3. Choose your check-in terminal to compare the right checkpoint.";
        allowRecommendation = false;
      }
    }

    var waitAttribute = lane === "precheck" ? "data-precheck-wait" : "data-standard-wait";
    var ranked = compatible.map(function (node, index) {
      var raw = node.getAttribute(waitAttribute);
      return {
        node: node,
        wait: raw === "" ? NaN : Math.round(Number(raw)),
        primary: gateList(node, "data-primary-gates").indexOf(gate) !== -1 ? 0 : 1,
        index: index
      };
    }).filter(function (item) {
      return Number.isFinite(item.wait);
    }).sort(function (a, b) {
      return (a.wait - b.wait) || (a.primary - b.primary) || (a.index - b.index);
    });

    var fastest = allowRecommendation && ranked.length ? ranked[0] : null;
    setNodeState(compatible, fastest ? fastest.node : null, Boolean(gate || terminal));

    if (fastest) {
      var laneLabel = lane === "precheck" ? "PreCheck" : "standard";
      message = "Fastest compatible live reading: " + nodeName(fastest.node) +
        ", " + Math.round(fastest.wait) + " minutes for " + laneLabel + ".";
    } else if (allowRecommendation && compatible.length) {
      message = "The compatible checkpoints are highlighted, but no fresh " +
        (lane === "precheck" ? "PreCheck" : "standard") + " reading is available.";
    }

    result.textContent = message;
  }

  form.addEventListener("change", update);
  update();
})();
