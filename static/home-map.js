(function () {
  "use strict";

  var mapElement = document.getElementById("airport-map");
  var dataElement = document.getElementById("airport-map-data");
  var stage = document.querySelector("[data-network-map-stage]");
  var markerLayer = document.querySelector("[data-map-marker-layer]");
  var loading = document.querySelector("[data-map-loading]");
  var errorMessage = document.querySelector("[data-map-error]");
  var status = document.getElementById("airport-map-status");
  var preview = document.querySelector("#airport-map-preview");
  var previewLink = preview && preview.querySelector("[data-map-preview-link]");
  var previewClose = preview && preview.querySelector("[data-map-preview-close]");
  var cluster = document.querySelector("[data-map-cluster='nyc']");
  var resetButton = document.querySelector("[data-map-reset]");
  var zoomControls = document.querySelector("[data-map-zoom-controls]");
  var zoomInButton = document.querySelector("[data-map-zoom-in]");
  var zoomOutButton = document.querySelector("[data-map-zoom-out]");
  var zoomLevel = document.querySelector("[data-map-zoom-level]");
  var gestureHint = document.querySelector("[data-map-gesture-hint]");
  var expandButton = document.querySelector("[data-map-expand]");
  var exitButton = document.querySelector("[data-map-exit]");
  var searchInput = document.getElementById("q");
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  var coarsePointer = window.matchMedia("(pointer: coarse)");
  var mobileLayout = window.matchMedia("(max-width: 700px)");
  var NYC_CODES = ["EWR", "JFK", "LGA"];
  var MOBILE_OVERVIEW_CODES = ["SEA", "SFO", "LAX", "LAS", "DFW", "ORD", "ATL", "MIA", "BOS"];
  var AIRPORT_REVEAL_ZOOM = 13;
  var AIRPORT_REVEAL_DURATION = 1.25;
  var AIRPORT_REVEAL_HOLD_MS = 1500;
  var AIRPORT_REVEAL_TILE_WAIT_MS = 1200;
  var AIRPORT_REVEAL_FALLBACK_MS = 5000;
  var AIRPORT_HANDOFF_KEY = "tsaAirportHandoffV1";
  var LABEL_LAYOUT = {
    BOS: { side: "left", y: -10 },
    DCA: { side: "left", y: 14 },
    EWR: { side: "left", y: 2 },
    JFK: { side: "right", y: 17 },
    LGA: { side: "right", y: -18 },
    LAS: { side: "right", y: -15 },
    LAX: { side: "right", y: 16 },
    MCO: { side: "left", y: -2 },
    MIA: { side: "left", y: 2 },
    PHL: { side: "left", y: -13 },
    SFO: { side: "left", y: -8 }
  };

  if (!mapElement || !dataElement || !stage || !markerLayer) return;

  var rawAirports;
  try {
    rawAirports = JSON.parse(dataElement.textContent || "[]");
  } catch (_error) {
    showFatalError("The airport map data could not be read.");
    return;
  }

  var airports = rawAirports
    .filter(function (airport) {
      return Number.isFinite(Number(airport.map_lat)) && Number.isFinite(Number(airport.map_lng));
    })
    .map(function (airport) {
      return {
        code: String(airport.code || "").toUpperCase(),
        name: String(airport.name || airport.code || "Airport"),
        city: String(airport.city || ""),
        href: String(airport.href || "/airports"),
        lat: Number(airport.map_lat),
        lng: Number(airport.map_lng),
        wait: Number(airport.current_wait || 0),
        tier: String(airport.tier || "low"),
        isLive: Boolean(airport.is_live),
        source: String(airport.source_label || "Estimated fallback"),
        trend: String(airport.trend || "steady"),
        trendArrow: String(airport.trend_arrow || "→"),
        updatedAt: String(airport.updated_at || "")
      };
    });

  var airportByCode = new Map(airports.map(function (airport) {
    return [airport.code, airport];
  }));
  var markerByCode = new Map();
  var map = null;
  var overviewBounds = null;
  var overviewCenter = null;
  var overviewZoom = null;
  var activeCode = null;
  var pinnedCode = null;
  var navigationTimer = null;
  var revealTimer = null;
  var revealLoadHandler = null;
  var searchTimer = null;
  var tileErrors = 0;
  var initialTilesResolved = false;
  var initialTileTimer = null;
  var frameRequested = false;
  var leaving = false;
  var isMapExpanded = false;

  function usesTapPreview() {
    return coarsePointer.matches || window.innerWidth <= 700;
  }

  function isMobileMap() {
    return mobileLayout.matches;
  }

  function showFatalError(message) {
    if (loading) loading.hidden = true;
    if (errorMessage) {
      errorMessage.textContent = message;
      errorMessage.hidden = false;
    }
    if (status) status.textContent = message;
    stage.setAttribute("aria-busy", "false");
  }

  function settleInitialTiles() {
    if (initialTilesResolved) return;
    initialTilesResolved = true;
    window.clearTimeout(initialTileTimer);
    if (loading) loading.hidden = true;
    stage.setAttribute("aria-busy", "false");
  }

  if (!window.L || airports.length === 0) {
    showFatalError("Satellite imagery is unavailable. Use the airport board below.");
    return;
  }

  markerLayer.querySelectorAll(".airport-map-marker[data-map-airport-link]").forEach(function (marker) {
    var code = String(marker.dataset.mapCode || "").toUpperCase();
    if (!airportByCode.has(code)) return;
    var layout = LABEL_LAYOUT[code] || { side: "right", y: 0 };
    marker.classList.toggle("is-label-left", layout.side === "left");
    marker.classList.toggle("is-mobile-overview-label", MOBILE_OVERVIEW_CODES.indexOf(code) > -1);
    marker.style.setProperty("--marker-label-y", layout.y + "px");
    markerByCode.set(code, marker);
  });

  map = window.L.map(mapElement, {
    attributionControl: true,
    boxZoom: true,
    doubleClickZoom: true,
    dragging: true,
    keyboard: true,
    keyboardPanDelta: 72,
    maxBounds: [[5, -170], [72, -25]],
    maxBoundsViscosity: 0.82,
    scrollWheelZoom: true,
    tap: true,
    touchZoom: true,
    wheelDebounceTime: 32,
    wheelPxPerZoomLevel: 90,
    zoomControl: false,
    zoomDelta: 1,
    zoomSnap: 0.25,
    preferCanvas: true
  });

  var imagery = window.L.tileLayer(
    "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}",
    {
      minZoom: 3,
      maxNativeZoom: 16,
      maxZoom: 16,
      noWrap: true,
      updateWhenIdle: true,
      keepBuffer: 2,
      attribution: 'Imagery: <a href="https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer" target="_blank" rel="noopener">USDA / USGS The National Map</a>'
    }
  );

  imagery.on("loading", function () {
    tileErrors = 0;
  });
  imagery.on("tileerror", function () {
    tileErrors += 1;
    if (tileErrors >= 4 && errorMessage) {
      errorMessage.hidden = false;
      if (status) status.textContent = "Satellite imagery is unavailable. Use the airport board below.";
      settleInitialTiles();
    }
  });
  imagery.on("load", function () {
    if (errorMessage) errorMessage.hidden = tileErrors < 4;
    if (tileErrors < 4 && status && status.textContent.indexOf("Satellite imagery") === 0) {
      status.textContent = "Satellite imagery restored.";
    }
    settleInitialTiles();
  });
  imagery.addTo(map);

  overviewBounds = window.L.latLngBounds(airports.map(function (airport) {
    return [airport.lat, airport.lng];
  }));
  map.fitBounds(overviewBounds, { padding: [34, 34], maxZoom: 4.75, animate: false });
  captureOverviewView();

  map.on("move zoom resize", requestMarkerPosition);
  map.on("zoomend moveend", function () {
    positionMarkers();
    updateClusterState();
    updateMapControls();
  });
  map.on("dragstart zoomstart", markMapEngaged);

  map.whenReady(function () {
    markerLayer.hidden = false;
    if (zoomControls) zoomControls.hidden = false;
    if (gestureHint) gestureHint.hidden = false;
    syncMobileMapMode();
    requestMarkerPosition();
    updateClusterState();
    updateMapControls();
  });
  initialTileTimer = window.setTimeout(function () {
    if (initialTilesResolved) return;
    if (errorMessage) errorMessage.hidden = false;
    if (status) status.textContent = "Satellite imagery is taking longer than expected. Airport links remain available.";
    settleInitialTiles();
  }, 5000);

  function requestMarkerPosition() {
    if (frameRequested) return;
    frameRequested = true;
    window.requestAnimationFrame(function () {
      frameRequested = false;
      positionMarkers();
    });
  }

  function setPosition(element, lat, lng) {
    if (!element || !map) return;
    var point = map.latLngToContainerPoint([lat, lng]);
    element.style.left = Math.round(point.x) + "px";
    element.style.top = Math.round(point.y) + "px";
  }

  function positionMarkers() {
    airports.forEach(function (airport) {
      setPosition(markerByCode.get(airport.code), airport.lat, airport.lng);
    });
    if (cluster && map) {
      var clusterPoint = map.latLngToContainerPoint([40.72, -74.02]);
      cluster.style.left = Math.round(clusterPoint.x + 32) + "px";
      cluster.style.top = Math.round(clusterPoint.y - 8) + "px";
    }
  }

  function isNycExpanded() {
    return map && map.getZoom() >= 7;
  }

  function captureOverviewView() {
    if (!map) return;
    overviewCenter = map.getCenter();
    overviewZoom = map.getZoom();
  }

  function isOverviewView() {
    if (!map || !overviewCenter || overviewZoom === null) return true;
    return Math.abs(map.getZoom() - overviewZoom) < 0.1 &&
      map.getCenter().distanceTo(overviewCenter) < 75000;
  }

  function markMapEngaged() {
    stage.classList.add("is-map-engaged");
  }

  function zoomLabel(value) {
    var rounded = Math.round(value * 4) / 4;
    return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(2).replace(/0$/, "");
  }

  function updateMapControls() {
    if (!map) return;
    var currentZoom = map.getZoom();
    if (zoomOutButton) zoomOutButton.disabled = currentZoom <= map.getMinZoom() + 0.01;
    if (zoomInButton) zoomInButton.disabled = currentZoom >= map.getMaxZoom() - 0.01;
    if (zoomLevel) zoomLevel.textContent = "Z " + zoomLabel(currentZoom);
    if (resetButton) resetButton.hidden = isOverviewView();
    stage.classList.toggle("is-mobile-detail", isMobileMap() && currentZoom >= 5.5);
  }

  function announceZoom() {
    if (status) status.textContent = "Map zoom level " + zoomLabel(map.getZoom()) + ".";
  }

  function updateClusterState() {
    var expanded = isNycExpanded();
    NYC_CODES.forEach(function (code) {
      var marker = markerByCode.get(code);
      if (marker) marker.classList.toggle("is-clustered", !expanded);
    });
    if (cluster) cluster.hidden = expanded;
  }

  function readableName(airport) {
    return airport.name.replace(new RegExp("\\s*\\(" + airport.code + "\\)\\s*$", "i"), "");
  }

  function formattedWait(wait) {
    var minutes = Math.max(0, Math.round(Number(wait) || 0));
    return minutes === 0 ? "<1 min" : minutes + " min";
  }

  function setPreviewText(selector, value) {
    var element = preview && preview.querySelector(selector);
    if (element) element.textContent = value;
  }

  function clearActiveMarker() {
    markerByCode.forEach(function (marker) {
      marker.classList.remove("is-active");
      marker.setAttribute("aria-expanded", "false");
    });
    if (cluster) cluster.classList.remove("is-active");
  }

  function showPreview(code, options) {
    options = options || {};
    var airport = airportByCode.get(code);
    if (!airport || !preview || leaving) return;
    activeCode = code;
    if (options.pinned) pinnedCode = code;

    clearActiveMarker();
    var marker = markerByCode.get(code);
    if (marker) {
      marker.setAttribute("aria-expanded", "true");
      if (!marker.classList.contains("is-clustered")) marker.classList.add("is-active");
    }
    if (NYC_CODES.indexOf(code) > -1 && !isNycExpanded() && cluster) cluster.classList.add("is-active");

    setPreviewText("[data-map-preview-code]", airport.code);
    setPreviewText("[data-map-preview-city]", airport.city || "Airport");
    setPreviewText("[data-map-preview-name]", readableName(airport));
    setPreviewText("[data-map-preview-wait]", formattedWait(airport.wait));
    setPreviewText(
      "[data-map-preview-trend]",
      airport.isLive ? airport.trendArrow + " " + airport.trend : "estimate"
    );
    setPreviewText(
      "[data-map-preview-source]",
      airport.isLive ? "LIVE / " + airport.source : "ESTIMATED FALLBACK"
    );
    setPreviewText("[data-map-preview-updated]", airport.updatedAt ? "Updated " + airport.updatedAt : "");
    setPreviewText("[data-map-preview-link-code]", airport.code);

    if (previewLink) {
      previewLink.href = airport.href;
      previewLink.dataset.mapCode = airport.code;
      previewLink.setAttribute(
        "aria-label",
        "Fly into " + airport.code + " satellite view and open airport details"
      );
    }
    preview.hidden = false;
    preview.setAttribute("aria-live", options.announce ? "polite" : "off");
    stage.classList.toggle("has-pinned-airport", Boolean(pinnedCode));
    if (options.announce && status) {
      status.textContent = airport.code + " selected. " + formattedWait(airport.wait) + ". " +
        (airport.isLive ? airport.trend + ", live source." : "Estimated fallback.");
    }
    if (options.pinned && !options.handoff && isMobileMap()) panAirportAbovePreview(airport);
  }

  function panAirportAbovePreview(airport) {
    window.requestAnimationFrame(function () {
      if (!map || !preview || preview.hidden || pinnedCode !== airport.code) return;
      map.panInside([airport.lat, airport.lng], {
        animate: !reduceMotion.matches,
        paddingTopLeft: [48, 62],
        paddingBottomRight: [48, preview.offsetHeight + 26]
      });
    });
  }

  function clearPreview(options) {
    options = options || {};
    if (!options.keepPinned) pinnedCode = null;
    if (pinnedCode) {
      showPreview(pinnedCode, { pinned: true, announce: false });
      return;
    }
    activeCode = null;
    clearActiveMarker();
    stage.classList.remove("has-pinned-airport");
    if (preview) preview.hidden = true;
  }

  function isModifiedClick(event) {
    return event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
  }

  function navigateToAirport(airport) {
    if (leaving && stage.dataset.navigationStarted === "true") return;
    clearHandoffTimers();
    stage.dataset.navigationStarted = "true";
    window.location.assign(airport.href);
  }

  function storeAirportHandoff(airport, zoom) {
    try {
      window.sessionStorage.setItem(AIRPORT_HANDOFF_KEY, JSON.stringify({
        version: 1,
        code: airport.code,
        center: [airport.lat, airport.lng],
        zoom: zoom,
        startedAt: Date.now(),
        source: "home-map"
      }));
    } catch (_error) {
      // Storage can be unavailable in private or locked-down browsing contexts.
    }
  }

  function clearHandoffTimers() {
    window.clearTimeout(navigationTimer);
    window.clearTimeout(revealTimer);
    navigationTimer = null;
    revealTimer = null;
    if (revealLoadHandler && imagery) imagery.off("load", revealLoadHandler);
    revealLoadHandler = null;
  }

  function holdAirportReveal(airport) {
    var finishReveal = function () {
      if (!leaving || stage.dataset.navigationStarted === "true") return;
      window.clearTimeout(revealTimer);
      if (revealLoadHandler && imagery) imagery.off("load", revealLoadHandler);
      revealLoadHandler = null;
      revealTimer = window.setTimeout(function () {
        navigateToAirport(airport);
      }, AIRPORT_REVEAL_HOLD_MS);
    };

    if (imagery && typeof imagery.isLoading === "function" && imagery.isLoading()) {
      revealLoadHandler = finishReveal;
      imagery.once("load", revealLoadHandler);
      revealTimer = window.setTimeout(finishReveal, AIRPORT_REVEAL_TILE_WAIT_MS);
      return;
    }

    revealTimer = window.setTimeout(function () {
      navigateToAirport(airport);
    }, AIRPORT_REVEAL_HOLD_MS);
  }

  function beginHandoff(event, airport) {
    if (!airport || leaving || isModifiedClick(event) || event.detail === 0) return;
    event.preventDefault();
    pinnedCode = airport.code;
    showPreview(airport.code, { pinned: true, announce: true, handoff: true });
    leaving = true;
    stage.classList.add("is-departing");
    stage.setAttribute("aria-busy", "true");
    markerByCode.forEach(function (marker, code) {
      marker.classList.toggle("is-departure-target", code === airport.code);
    });
    var targetZoom = Math.min(AIRPORT_REVEAL_ZOOM, map.getMaxZoom());
    storeAirportHandoff(airport, targetZoom);
    stage.dataset.revealCode = airport.code;
    stage.dataset.revealZoom = String(targetZoom);
    if (status) {
      status.textContent = "Zooming into " + airport.code +
        " satellite view before opening airport details.";
    }

    if (reduceMotion.matches) {
      navigateToAirport(airport);
      return;
    }

    clearHandoffTimers();
    map.once("moveend", function () {
      holdAirportReveal(airport);
    });
    navigationTimer = window.setTimeout(function () {
      navigateToAirport(airport);
    }, AIRPORT_REVEAL_FALLBACK_MS);
    map.flyTo([airport.lat, airport.lng], targetZoom, {
      duration: AIRPORT_REVEAL_DURATION,
      easeLinearity: 0.18
    });
  }

  markerByCode.forEach(function (marker, code) {
    marker.addEventListener("pointerenter", function () {
      if (!usesTapPreview()) showPreview(code, { announce: false });
    });
    marker.addEventListener("focus", function () {
      showPreview(code, { announce: false });
    });
    marker.addEventListener("click", function (event) {
      var airport = airportByCode.get(code);
      if (isModifiedClick(event) || event.detail === 0) return;
      if (usesTapPreview()) {
        if (pinnedCode === code && activeCode === code) {
          beginHandoff(event, airport);
          return;
        }
        event.preventDefault();
        showPreview(code, { pinned: true, announce: true });
        return;
      }
      beginHandoff(event, airport);
    });
  });

  stage.addEventListener("pointerleave", function () {
    if (!usesTapPreview() && !pinnedCode && !leaving) clearPreview();
  });
  stage.addEventListener("focusout", function () {
    window.setTimeout(function () {
      if (!stage.contains(document.activeElement) && !pinnedCode && !leaving) clearPreview();
    }, 0);
  });
  stage.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    if (pinnedCode || activeCode) {
      event.preventDefault();
      clearPreview();
    } else if (isMapExpanded) {
      event.preventDefault();
      setMapExpanded(false, { focus: true, reset: true });
    } else if (map.getZoom() >= 5.5) {
      event.preventDefault();
      resetOverview(true);
    }
  });

  if (previewClose) {
    previewClose.addEventListener("click", function () {
      clearPreview();
    });
  }
  if (previewLink) {
    previewLink.addEventListener("click", function (event) {
      var airport = airportByCode.get(String(previewLink.dataset.mapCode || activeCode || ""));
      beginHandoff(event, airport);
    });
  }

  if (cluster) {
    cluster.addEventListener("click", function (event) {
      var moveFocusToJfk = function () {
        if (event.detail !== 0) return;
        var jfkMarker = markerByCode.get("JFK");
        if (jfkMarker) jfkMarker.focus({ preventScroll: true });
      };
      clearPreview();
      if (reduceMotion.matches) {
        map.setView([40.72, -74.02], 8, { animate: false });
        window.requestAnimationFrame(moveFocusToJfk);
      } else {
        map.once("moveend", moveFocusToJfk);
        map.flyTo([40.72, -74.02], 8, { duration: 0.46, easeLinearity: 0.35 });
      }
      if (status) status.textContent = "New York area expanded. Choose JFK, LaGuardia, or Newark.";
    });
  }

  function resetOverview(animate) {
    clearPreview();
    if (reduceMotion.matches || !animate) {
      map.fitBounds(overviewBounds, { padding: [34, 34], maxZoom: 4.75, animate: false });
      updateMapControls();
    } else {
      map.flyToBounds(overviewBounds, { padding: [34, 34], maxZoom: 4.75, duration: 0.46 });
    }
    if (status) status.textContent = "National airport map restored.";
  }

  if (zoomInButton) {
    zoomInButton.addEventListener("click", function () {
      markMapEngaged();
      map.once("zoomend", announceZoom);
      map.zoomIn(1, { animate: !reduceMotion.matches });
    });
  }

  if (zoomOutButton) {
    zoomOutButton.addEventListener("click", function () {
      markMapEngaged();
      map.once("zoomend", announceZoom);
      map.zoomOut(1, { animate: !reduceMotion.matches });
    });
  }

  if (resetButton) {
    resetButton.addEventListener("click", function () {
      resetOverview(true);
    });
  }

  function syncMobileMapMode() {
    if (!map) return;
    var mobile = isMobileMap();
    var gesturesEnabled = !mobile || isMapExpanded;

    stage.classList.toggle("is-mobile-map", mobile);
    stage.classList.toggle("is-mobile-embedded", mobile && !isMapExpanded);
    stage.classList.toggle("is-map-expanded", mobile && isMapExpanded);
    document.body.classList.toggle("map-is-expanded", mobile && isMapExpanded);

    if (expandButton) {
      expandButton.hidden = !mobile || isMapExpanded;
      expandButton.setAttribute("aria-expanded", isMapExpanded ? "true" : "false");
    }
    if (exitButton) exitButton.hidden = !mobile || !isMapExpanded;

    [map.dragging, map.touchZoom, map.doubleClickZoom].forEach(function (handler) {
      if (!handler) return;
      if (gesturesEnabled) handler.enable();
      else handler.disable();
    });
    if (map.scrollWheelZoom) {
      if (mobile) map.scrollWheelZoom.disable();
      else map.scrollWheelZoom.enable();
    }
    updateMapControls();
  }

  function setMapExpanded(expanded, options) {
    options = options || {};
    if (expanded && !isMobileMap()) return;
    isMapExpanded = Boolean(expanded);
    if (!isMapExpanded) clearPreview();
    syncMobileMapMode();

    window.requestAnimationFrame(function () {
      map.invalidateSize({ animate: false });
      if (!isMapExpanded && options.reset !== false) {
        resetOverview(false);
      } else if (isMapExpanded && overviewBounds && isOverviewView()) {
        map.fitBounds(overviewBounds, { padding: [42, 42], maxZoom: 4.75, animate: false });
        captureOverviewView();
      }
      requestMarkerPosition();
    });

    if (options.focus !== false) {
      var focusTarget = isMapExpanded ? exitButton : expandButton;
      if (focusTarget) focusTarget.focus({ preventScroll: true });
    }
    if (status) {
      status.textContent = isMapExpanded
        ? "Expanded airport map. Drag or pinch to explore."
        : "Embedded airport map restored.";
    }
  }

  if (expandButton) {
    expandButton.addEventListener("click", function () {
      setMapExpanded(true, { focus: true, reset: false });
    });
  }
  if (exitButton) {
    exitButton.addEventListener("click", function () {
      setMapExpanded(false, { focus: true, reset: true });
    });
  }

  var onMobileLayoutChange = function () {
    if (!isMobileMap() && isMapExpanded) isMapExpanded = false;
    syncMobileMapMode();
    window.requestAnimationFrame(function () {
      map.invalidateSize({ animate: false });
      requestMarkerPosition();
    });
  };
  if (typeof mobileLayout.addEventListener === "function") {
    mobileLayout.addEventListener("change", onMobileLayoutChange);
  } else if (typeof mobileLayout.addListener === "function") {
    mobileLayout.addListener(onMobileLayoutChange);
  }

  function syncSearch() {
    if (!searchInput) return;
    var term = String(searchInput.value || "").trim().toLowerCase();
    var exact = airportByCode.get(term.toUpperCase());
    markerByCode.forEach(function (marker) {
      var match = !term || String(marker.dataset.search || "").indexOf(term) > -1;
      marker.classList.toggle("is-search-dimmed", !match);
    });
    if (cluster) {
      var nycMatch = !term || NYC_CODES.some(function (code) {
        var marker = markerByCode.get(code);
        return marker && String(marker.dataset.search || "").indexOf(term) > -1;
      });
      cluster.classList.toggle("is-search-dimmed", !nycMatch);
    }

    window.clearTimeout(searchTimer);
    if (exact) {
      searchTimer = window.setTimeout(function () {
        showPreview(exact.code, { pinned: false, announce: false });
        var targetZoom = NYC_CODES.indexOf(exact.code) > -1 ? 8 : 5.75;
        if (reduceMotion.matches) map.setView([exact.lat, exact.lng], targetZoom, { animate: false });
        else map.flyTo([exact.lat, exact.lng], targetZoom, { duration: 0.36 });
      }, 180);
    } else if (!term && map.getZoom() >= 5.5) {
      resetOverview(false);
    }
  }

  if (searchInput) searchInput.addEventListener("input", syncSearch);

  document.querySelectorAll("[data-hero-search]").forEach(function (result) {
    var code = String(result.dataset.code || "").toUpperCase();
    result.addEventListener("pointerenter", function () {
      if (!usesTapPreview()) showPreview(code, { announce: false });
    });
    result.addEventListener("focus", function () {
      showPreview(code, { announce: false });
    });
  });

  var resizeObserver = typeof ResizeObserver !== "undefined"
    ? new ResizeObserver(function () {
        map.invalidateSize({ animate: false });
        if (
          overviewBounds &&
          !leaving &&
          !pinnedCode &&
          map.getZoom() < 5.5 &&
          (!searchInput || !String(searchInput.value || "").trim())
        ) {
          map.fitBounds(overviewBounds, { padding: [34, 34], maxZoom: 4.75, animate: false });
          captureOverviewView();
          updateMapControls();
        }
        requestMarkerPosition();
      })
    : null;
  if (resizeObserver) resizeObserver.observe(mapElement);

  window.addEventListener("pagehide", function () {
    clearHandoffTimers();
    window.clearTimeout(searchTimer);
    window.clearTimeout(initialTileTimer);
  });
  window.addEventListener("pageshow", function (event) {
    if (!event.persisted) return;
    leaving = false;
    stage.dataset.navigationStarted = "false";
    isMapExpanded = false;
    syncMobileMapMode();
    delete stage.dataset.revealCode;
    delete stage.dataset.revealZoom;
    stage.classList.remove("is-departing");
    stage.setAttribute("aria-busy", "false");
    markerByCode.forEach(function (marker) {
      marker.classList.remove("is-departure-target");
    });
    map.invalidateSize({ animate: false });
    resetOverview(false);
    syncSearch();
  });
})();
