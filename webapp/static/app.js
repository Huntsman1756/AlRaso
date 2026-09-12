"use strict";
const $ = (id) => document.getElementById(id);
const state = { lat: null, lon: null, marker: null, poiCategory: null, poiAlt: null, selectedName: null };
let poiClickGuard = 0;

// Proveedor de basemap NO hardcodeado: se pide a /api/config (el server lee
// ALRASO_MAP_STYLE_URL). Default del lado cliente solo por si el fetch falla.
const FALLBACK_STYLE_URL = "https://tiles.openfreemap.org/styles/positron";

const POI_CATS = {
  refuge: { emoji: "🏠", label: "Refugio", anonymousLabel: "Refugio", color: "#b45309" },
  shelter: { emoji: "🛖", label: "Abrigo / cabaña", anonymousLabel: "Abrigo", color: "#f97316" },
  water: { emoji: "💧", label: "Agua", anonymousLabel: "Agua", color: "#0ea5e9" },
  camping: { emoji: "⛺", label: "Camping / bivouac", anonymousLabel: "Camping", color: "#16a34a" },
  protected_area: { emoji: "🌲", label: "Referencia OSM: espacio natural protegido", color: "#0d9488" },
};
// protected_area queda en el snapshot (provenance) pero NO se renderiza ni es
// interactivo: un centroide de relación de parque no es un destino del usuario.
const POI_ORDER = ["refuge", "shelter", "water", "camping"];

let map = null;

// ─────────────────────────────────────────────
// TAB NAVIGATION
// ─────────────────────────────────────────────
function showTab(name) {
  const views = document.querySelectorAll(".view");
  views.forEach(function (v) { v.hidden = true; });
  var target = $("view-" + name);
  if (target) target.hidden = false;

  // Set aria-current on nav buttons
  var navBtns = document.querySelectorAll('nav button[data-tab]');
  navBtns.forEach(function (b) {
    if (b.getAttribute("data-tab") === name) {
      b.setAttribute("aria-current", "page");
    } else {
      b.removeAttribute("aria-current");
    }
  });

  // Sync hash
  location.hash = "#" + name;

  // Resize map if going back to explore
  if (name === "explore" && map) {
    setTimeout(function () { map.resize(); }, 50);
  }

  // Update UI for specific views
  if (name === "saved") renderFavorites();
  if (name === "outings") renderOutings();
  if (name === "profile") updateStats();
}

// Boot: read hash, set initial tab
(function initTabs() {
  var hash = location.hash.replace("#", "");
  if (hash && ["explore", "saved", "outings", "profile"].indexOf(hash) !== -1) {
    showTab(hash);
  } else {
    showTab("explore");
  }

  var navBtns = document.querySelectorAll('nav button[data-tab]');
  navBtns.forEach(function (b) {
    b.addEventListener("click", function () { showTab(b.getAttribute("data-tab")); });
  });
})();

// Listen for back/forward
window.addEventListener("hashchange", function () {
  var hash = location.hash.replace("#", "");
  if (hash && ["explore", "saved", "outings", "profile"].indexOf(hash) !== -1) {
    showTab(hash);
  }
});

// ─────────────────────────────────────────────
// MAP BOOT
// ─────────────────────────────────────────────
async function boot() {
  let styleUrl = FALLBACK_STYLE_URL;
  try {
    const cfg = await (await fetch("/api/config")).json();
    if (cfg && typeof cfg.mapStyleUrl === "string" && cfg.mapStyleUrl) styleUrl = cfg.mapStyleUrl;
  } catch (e) { console.error("config fallback", e); }

  map = new maplibregl.Map({
    container: "map",
    style: styleUrl,
    center: [-2.5, 42.9],
    zoom: 6.8,
    attributionControl: true,
  });

  map.on("load", async () => {
    try {
      const fc = await (await fetch("/api/coverage")).json();
      map.addSource("coverage", { type: "geojson", data: fc });
      map.addLayer({
        id: "cov-fill", type: "fill", source: "coverage",
        paint: {
          "fill-color": ["match", ["get", "coverage"], "VERIFIED", "#22c55e", "PARTIAL", "#f59e0b", "#94a3b8"],
          "fill-opacity": 0.06,
        },
      });
      const covColor = ["match", ["get", "coverage"], "VERIFIED", "#22c55e", "PARTIAL", "#f59e0b", "#94a3b8"];
      map.addLayer({
        id: "cov-line", type: "line", source: "coverage",
        filter: ["==", ["get", "boundary"], "oficial"],
        paint: { "line-color": covColor, "line-width": 1.0, "line-opacity": 0.4 },
      });
      map.addLayer({
        id: "cov-line-esquematico", type: "line", source: "coverage",
        filter: ["==", ["get", "boundary"], "esquematico"],
        paint: { "line-color": covColor, "line-width": 0.9, "line-opacity": 0.35, "line-dasharray": [3, 3] },
      });
      await loadPois();
      await loadProtectedAreas();
      map.fitBounds([[-5.35, 42.45], [0.25, 43.4]], { padding: 30 });
    } catch (e) { console.error(e); }
  });

  map.on("click", (e) => {
    if (Date.now() - poiClickGuard < 150) return;
    selectPoint(e.lngLat.lat, e.lngLat.lng, null, false);
  });
}

// ─────────────────────────────────────────────
// POIS — runtime-generated canvas icons (U3)
// ─────────────────────────────────────────────
function makePoiIconDataUrl(cat) {
  var c = POI_CATS[cat];
  try {
    var canvas = document.createElement("canvas");
    canvas.width = 52;
    canvas.height = 52;
    var ctx = canvas.getContext("2d");
    // Circle background with category color and 3px white border
    ctx.beginPath();
    ctx.arc(26, 26, 22, 0, 2 * Math.PI);
    ctx.fillStyle = c.color;
    ctx.fill();
    ctx.lineWidth = 3;
    ctx.strokeStyle = "#ffffff";
    ctx.stroke();
    // Centered emoji ~26px
    ctx.font = "26px system-ui, Segoe UI Emoji, Noto Color Emoji, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = "#ffffff";
    ctx.fillText(c.emoji, 26, 27);
    return canvas.toDataURL("image/png");
  } catch (err) {
    console.warn("Failed to generate POI icon for " + cat, err);
    return null;
  }
}

async function loadPois() {
  var fc;
  try { fc = await (await fetch("/api/pois")).json(); }
  catch (e) { console.error("pois", e); return; }
  map.addSource("pois", { type: "geojson", data: fc });

  // Genera y registra los iconos ANTES de crear las capas (sin carreras async)
  var loadedIcons = {};
  function loadPoiIcon(cat) {
    return new Promise(function (resolve) {
      var dataUrl = null;
      try { dataUrl = makePoiIconDataUrl(cat); } catch (err) {
        console.warn("Failed to generate POI icon for " + cat, err); resolve(null); return;
      }
      if (!dataUrl) { resolve(null); return; }
      var img = new Image();
      img.onload = function () {
        try { map.addImage("poi-icon-" + cat, img); resolve(true); }
        catch (e) { console.warn("addImage failed for " + cat, e); resolve(null); }
      };
      img.onerror = function () { console.warn("Failed to load POI image for " + cat); resolve(null); };
      img.src = dataUrl;
    });
  }

  await Promise.all(POI_ORDER.map(function (cat) {
    return loadPoiIcon(cat).then(function (ok) { if (ok) loadedIcons[cat] = true; });
  }));

  POI_ORDER.forEach(function (cat) {
    if (loadedIcons[cat]) {
      map.addLayer({
        id: "poi-icons-" + cat, type: "symbol", source: "pois",
        filter: ["==", ["get", "category"], cat],
        layout: {
          "icon-image": "poi-icon-" + cat,
          "icon-size": ["interpolate", ["linear"], ["zoom"], 8, 0.5, 11, 0.85, 14, 1.15],
          "icon-allow-overlap": true,
        },
      });
      map.on("click", "poi-icons-" + cat, function (e) { onPoiClick(e); });
    }
    if (cat !== "water") {
      map.addLayer({
        id: "poi-labels-" + cat, type: "symbol", source: "pois",
        // Unnamed POIs remain icon-only.  ``name`` is the nullable
        // display_name field; source_ref must never become a map label.
        filter: ["all", ["==", ["get", "category"], cat],
                 ["!=", ["get", "name"], null]],
        minzoom: 9,
        layout: { "text-field": ["get", "name"], "text-size": 11,
                  "text-offset": [0, 1.1], "text-anchor": "top",
                  "text-optional": true, "text-max-width": 9,
                  "text-font": ["Noto Sans Regular"] },
        paint: { "text-color": "#1f2937", "text-halo-color": "#ffffff",
                 "text-halo-width": 1.2 },
      });
    }
  });
  bindLayerToggles();
}

/*
PA_FILL_COLOR: "fill" color constant for protected-area polygons.
  Mapped from a documented constant so the visual can be reviewed/changed in one place.
  Value chosen: low-opacity teal, consistent with cartographic context (not legal coverage).
*/
const PA_FILL_COLOR = "#0d9488";

async function loadProtectedAreas() {
  var fc;
  try { fc = await (await fetch("/api/protected-areas")).json(); }
  catch (e) { console.error("protected-areas", e); return; }
  map.addSource("protected-areas", { type: "geojson", data: fc });
  map.addLayer({
    id: "pa-fill", type: "fill", source: "protected-areas",
    layout: { visibility: $("lg-protected").checked ? "visible" : "none" },
    paint: { "fill-color": PA_FILL_COLOR, "fill-opacity": 0.12 },
  });
  map.addLayer({
    id: "pa-line", type: "line", source: "protected-areas",
    layout: { visibility: $("lg-protected").checked ? "visible" : "none" },
    paint: { "line-color": "#0d9488", "line-width": 1.5, "line-opacity": 0.5 },
  });
  map.on("click", "pa-fill", function (e) { onPaClick(e); });
  map.on("click", "pa-line", function (e) { onPaClick(e); });
  // Cursor change on hover
  map.on("mouseenter", "pa-fill", function () { map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", "pa-fill", function () { map.getCanvas().style.cursor = ""; });
  map.on("mouseenter", "pa-line", function () { map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", "pa-line", function () { map.getCanvas().style.cursor = ""; });
}

function bindLayerToggles() {
  const groups = {
    "lg-refuge": ["poi-icons-refuge", "poi-labels-refuge"],
    "lg-shelter": ["poi-icons-shelter", "poi-labels-shelter"],
    "lg-water": ["poi-icons-water"],
    "lg-camping": ["poi-icons-camping", "poi-labels-camping"],
    "lg-protected": ["pa-fill", "pa-line"],
    "lg-coverage": ["cov-fill", "cov-line", "cov-line-esquematico"],
  };
  Object.keys(groups).forEach((boxId) => {
    const box = $(boxId);
    if (!box) return;
    box.addEventListener("change", () => {
      groups[boxId].forEach((id) => {
        if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", box.checked ? "visible" : "none");
      });
    });
  });
}

function onPoiClick(e) {
  const f = e.features && e.features[0];
  if (!f) return;
  const p = f.properties;
  poiClickGuard = Date.now();
  selectPoint(f.geometry.coordinates[1], f.geometry.coordinates[0], p.name, false);
  renderPoi(p);
}

function onPaClick(e) {
  const f = e.features && e.features[0];
  if (!f) return;
  const p = f.properties;
  poiClickGuard = Date.now();
  // Use the exact clicked coordinates for the CTA (coords-only invariant).
  var clickedLat = e.lngLat.lat;
  var clickedLon = e.lngLat.lng;
  selectPoint(clickedLat, clickedLon, null, false);
  // Wire CTA with clicked coordinates only — no name, no facts.
  var ctaBtn = $("pa-legal-btn");
  if (ctaBtn) {
    ctaBtn.disabled = false;
    ctaBtn.setAttribute("data-lat", String(clickedLat));
    ctaBtn.setAttribute("data-lon", String(clickedLon));
  }
  renderPa(p);
}

function renderPoi(p) {
  const cat = POI_CATS[p.category] || { emoji: "📍", label: p.category };
  const displayName = typeof p.name === "string" && p.name.trim() ? p.name.trim() : null;
  $("poi").hidden = false;
  $("pa-card").hidden = true;
  $("poi-emoji").textContent = cat.emoji;
  $("poi-name").textContent = displayName || (cat.anonymousLabel || cat.label) + " sin nombre";
  const parts = [cat.label];
  if (p.alt_m) parts.push(`${p.alt_m} m`);
  if (p.source_label) parts.push(`fuente: ${p.source_label}`);
  $("poi-meta").textContent = parts.join(" · ");
  $("poi-note").textContent = p.note || "";
  // CTA: wire the legal button with POI coordinates only.
  const ctaBtn = $("poi-legal-btn");
  if (ctaBtn) {
    ctaBtn.disabled = false;
    ctaBtn.setAttribute("data-lat", String(p.lat));
    ctaBtn.setAttribute("data-lon", String(p.lon));
  }
  // Provenance disclosure: source label, snapshot date, attribution (and OSM URL if available).
  const box = $("poi-srcbox"), details = $("poi-src-details");
  if (details) {
    let html = "";
    if (p.osm_url) {
      html += `<div><a href="${esc(p.osm_url)}" target="_blank" rel="noopener">${esc(p.osm_url)}</a></div>`;
    }
    if (p.source_label) html += `<div><span class="src-label">Fuente: </span>${esc(p.source_label)}</div>`;
    if (p.source_ref) {
      const refLabel = p.source === "openstreetmap" ? "Objeto OSM" : "Referencia";
      html += `<div><span class="src-label">${refLabel}: </span>${esc(p.source_ref)}</div>`;
    }
    if (p.snapshot_date) html += `<div><span class="src-label">Fecha de instantánea: </span>${esc(p.snapshot_date)}</div>`;
    if (p.attribution) html += `<div><span class="src-label">Atribución: </span>${esc(p.attribution)}</div>`;
    if (p.source_license) html += `<div><span class="src-label">Licencia: </span>${esc(p.source_license)}</div>`;
    details.innerHTML = html;
    box.style.display = "";
  }
  state.poiCategory = p.category;
  state.poiAlt = p.alt_m || null;
}

function renderPa(p) {
  $("poi").hidden = true;
  $("pa-card").hidden = false;
  $("pa-name").textContent = p.name || "";
  var metaParts = [];
  if (p.region) metaParts.push(p.region);
  metaParts.push("referencia OSM · no ámbito legal");
  $("pa-meta").textContent = metaParts.join(" · ");
  $("pa-note").textContent = p.note || "";
  // CTA: coords only from clicked point — data-lat and data-lon set by onPaClick.
  // The button is wired in onPaClick before renderPa is called.
  var ctaBtn = $("pa-legal-btn");
  if (ctaBtn) {
    ctaBtn.disabled = false;
  }
  // Provenance disclosure
  var box = $("pa-srcbox"), details = $("pa-src-details");
  if (details) {
    let html = "";
    if (p.osm_url) {
      html += `<div><a href="${esc(p.osm_url)}" target="_blank" rel="noopener">${esc(p.osm_url)}</a></div>`;
    }
    if (p.source_label) html += `<div><span class="src-label">Fuente: </span>${esc(p.source_label)}</div>`;
    if (p.snapshot_date) html += `<div><span class="src-label">Fecha de instantánea: </span>${esc(p.snapshot_date)}</div>`;
    if (p.attribution) html += `<div><span class="src-label">Atribución: </span>${esc(p.attribution)}</div>`;
    if (p.source_license) html += `<div><span class="src-label">Licencia: </span>${esc(p.source_license)}</div>`;
    details.innerHTML = html;
    box.style.display = "";
  }
}

// ─────────────────────────────────────────────
// BOTTOM SHEET (R2, mobile <=820px) — states: closed / peek / full
// Tap/handle navigation is the REQUIRED path; a minimal Pointer Events
// drag is a progressive enhancement. No physics, no inertia, no library.
// ─────────────────────────────────────────────
var SHEET_STATES = ["closed", "peek", "full"];
var sheetState = "closed";

function isMobileLayout() {
  return window.matchMedia("(max-width: 820px)").matches;
}

function setSheetState(next) {
  if (!isMobileLayout() || SHEET_STATES.indexOf(next) === -1) return;
  sheetState = next;
  var card = $("card");
  SHEET_STATES.forEach(function (s) { card.classList.toggle("sheet-" + s, s === next); });
  var handle = $("sheet-handle");
  if (handle) handle.setAttribute("aria-expanded", next === "full" ? "true" : "false");
  // MapLibre may need a resize pass after the layout settles (grey/misaligned canvas guard)
  if (map) setTimeout(function () { map.resize(); }, 60);
}

function openSheetForSelection() {
  if (!isMobileLayout()) return;
  if (sheetState === "closed") setSheetState("peek");
}

(function initSheet() {
  var card = $("card");
  var handle = $("sheet-handle");
  if (!card || !handle) return;

  handle.addEventListener("click", function () {
    // Explicit cycle: closed -> peek -> full -> closed (drag never required)
    var i = SHEET_STATES.indexOf(sheetState);
    setSheetState(SHEET_STATES[(i + 1) % SHEET_STATES.length]);
  });

  // OPTIONAL drag: simple vertical delta with fixed snap thresholds.
  var dragStartY = null, dragDelta = 0;
  handle.addEventListener("pointerdown", function (ev) {
    if (!isMobileLayout()) return;
    dragStartY = ev.clientY;
    dragDelta = 0;
    card.style.transition = "none";
    handle.setPointerCapture(ev.pointerId);
  });
  handle.addEventListener("pointermove", function (ev) {
    if (dragStartY === null) return;
    dragDelta = ev.clientY - dragStartY;
    var base = sheetState === "full" ? 0
      : sheetState === "peek" ? card.offsetHeight - 176 : card.offsetHeight - 44;
    card.style.transform = "translateY(" + Math.max(0, base + dragDelta) + "px)";
  });
  function endDrag() {
    if (dragStartY === null) return;
    card.style.transition = "";
    card.style.transform = "";
    dragStartY = null;
    var order = { closed: 0, peek: 1, full: 2 };
    var i = order[sheetState];
    if (dragDelta > 60 && i > 0) setSheetState(SHEET_STATES[i - 1]);
    else if (dragDelta < -60 && i < SHEET_STATES.length - 1) setSheetState(SHEET_STATES[i + 1]);
    else setSheetState(sheetState); // snap back
    dragDelta = 0;
  }
  handle.addEventListener("pointerup", endDrag);
  handle.addEventListener("pointercancel", endDrag);

  // Escape closes things one level at a time: dropdown -> layers panel -> sheet
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape" || ev.defaultPrevented) return;
    var suggest = $("suggest");
    if (suggest && !suggest.hidden) return; // dropdown owns this Escape
    var layersPanel = $("layers-panel");
    if (layersPanel && !layersPanel.hasAttribute("hidden")) return; // layers owns this Escape
    if (!isMobileLayout()) return;
    if (sheetState === "full") setSheetState("peek");
    else if (sheetState === "peek") setSheetState("closed");
  });
})();

// Onboarding CTA: on mobile it floats over the map (the sheet would cover it)
(function relocateExploreCta() {
  var cta = $("explore-cta");
  if (!cta || !isMobileLayout()) return;
  $("map-container").appendChild(cta);
})();

// ─────────────────────────────────────────────
// GEOLocation
// ─────────────────────────────────────────────
(function initGeo() {
  var geoBtn = $("geo-btn");
  if (!geoBtn) return;
  if (!navigator.geolocation) {
    $("searchmsg").textContent = "No se pudo obtener tu ubicación. La app sigue funcionando con normalidad.";
    return;
  }
  geoBtn.addEventListener("click", function () {
    navigator.geolocation.getCurrentPosition(function (pos) {
      var lat = pos.coords.latitude;
      var lon = pos.coords.longitude;
      var acc = pos.coords.accuracy;
      selectPoint(lat, lon, null, true);
      var accStr = acc != null ? " ±" + Math.round(acc) + " m" : "";
      $("searchmsg").textContent = "Ubicación encontrada" + accStr;
    }, function (err) {
      var msg = "";
      switch (err.code) {
        case 1: // PERMISSION_DENIED
          msg = "Permiso de ubicación denegado. Puedes seguir usando el mapa sin tu ubicación.";
          break;
        case 2: // POSITION_UNAVAILABLE
        case 3: // TIMEOUT
        default:
          msg = "No se pudo obtener tu ubicación. La app sigue funcionando con normalidad.";
          break;
      }
      if (err.code === 3) msg = "No se pudo obtener tu ubicación. La app sigue funcionando con normalidad.";
      $("searchmsg").textContent = msg;
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
  });
})();

// ─────────────────────────────────────────────
// LAYERS PANEL TOGGLE (U1)
// ─────────────────────────────────────────────
(function initLayersPanel() {
  var btn = $("layers-btn");
  var panel = $("layers-panel");
  if (!btn || !panel) return;

  btn.addEventListener("click", function (e) {
    e.stopPropagation();
    if (panel.hasAttribute("hidden")) {
      panel.removeAttribute("hidden");
    } else {
      panel.setAttribute("hidden", "");
    }
  });

  // Close on Escape
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && !panel.hasAttribute("hidden")) {
      panel.setAttribute("hidden", "");
    }
  });

  // Cierra el panel al hacer clic fuera (sin tocar el mapa: map puede ser
  // null durante el arranque, y el canvas queda cubierto por closest()).
  document.addEventListener("click", function (ev) {
    if (ev.target.closest &&
        !ev.target.closest("#layers-panel") &&
        !ev.target.closest("#layers-btn")) {
      panel.setAttribute("hidden", "");
    }
  });
})();

// ─────────────────────────────────────────────
// EXPLORE CTA — preselected verified zones (U8)
// ─────────────────────────────────────────────
(function initExploreCta() {
  var cta = $("explore-cta");
  if (!cta) return;

  // Notes come from /api/places (single source of truth) — no stale claims here
  var zones = [
    { id: "cares-picos", label: "⛰ Picos de Europa · Cares" },
    { id: "refugio-goriz", label: "🏔 Refugio de Góriz" },
    { id: "pradera-ordesa", label: "🌲 Pradera de Ordesa" },
  ];

  // Fetch /api/places to use real data (no new endpoint)
  fetch("/api/places")
    .then(function (r) { return r.json(); })
    .then(function (data) {
      // Build a lookup from the places API by id
      var placeMap = {};
      (data.places || []).forEach(function (p) {
        placeMap[p.id] = p;
      });

      cta.innerHTML = "";
      zones.forEach(function (z) {
        var place = placeMap[z.id];
        var note = place && place.note ? place.note : "";
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "cta-btn";
        btn.innerHTML = '<span class="cta-label">' + z.label + '</span>' +
          (note ? '<span class="cta-note">' + esc(note) + '</span>' : '');
        btn.setAttribute("aria-label", "Explorar " + z.label);
        btn.addEventListener("click", function () {
          if (place) {
            selectPoint(place.lat, place.lon, place.name, true);
          } else {
            // Fresh resolve — use /api/find to look up the zone
            fetch("/api/find?q=" + encodeURIComponent(z.label))
              .then(function (r) { return r.json(); })
              .then(function (f) {
                if (f.kind === "place" || f.kind === "coords") {
                  selectPoint(f.lat, f.lon, f.name || null, true);
                }
              })
              .catch(function () {});
          }
        });
        // Ensure minimum 44px hit target on mobile (enforced by CSS min-height:44px)
        cta.appendChild(btn);
      });
      cta.removeAttribute("hidden");
    })
    .catch(function () {
      // If fetch fails, keep CTA empty (no crash)
    });
})();

// ─────────────────────────────────────────────
// SELECT POINT & FRESH RESOLVE
// ─────────────────────────────────────────────
function selectPoint(lat, lon, name, fly, preserveContext) {
  if (fly === undefined) fly = true;
  state.lat = lat;
  state.lon = lon;
  state.selectedName = name || null;
  if (map) {
    var ll = [lon, lat];
    if (!state.marker) {
      state.marker = new maplibregl.Marker({ color: "#e11d48" }).setLngLat(ll).addTo(map);
    } else {
      state.marker.setLngLat(ll);
    }
    if (fly) map.flyTo({ center: ll, zoom: Math.max(map.getZoom(), 10) });
  }
  // A fresh coordinate/name selection replaces any contextual card from a
  // previous POI or protected-area click. The specialized renderers show the
  // relevant card again after this reset. Legal CTAs opt into preserving the
  // card that the user is using while the resolver refreshes below it.
  if (!preserveContext) {
    $("poi").hidden = true;
    $("pa-card").hidden = true;
    state.poiCategory = null;
    state.poiAlt = null;
    var paLegalBtn = $("pa-legal-btn");
    if (paLegalBtn) {
      paLegalBtn.disabled = true;
      paLegalBtn.removeAttribute("data-lat");
      paLegalBtn.removeAttribute("data-lon");
    }
  }
  $("searchmsg").textContent = name ? `Zona seleccionada: ${name}` : "";
  document.body.classList.toggle("has-selection", state.lat !== null);
  openSheetForSelection();
  loadWeather(lat, lon);
  refresh();
}

// ─────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────
function currentPlaceName() {
  return state.selectedName || (state.lat !== null ? "Punto " + state.lat.toFixed(5) + ", " + state.lon.toFixed(5) : "");
}

// ─────────────────────────────────────────────
// SAVE / FAVORITES UI
// ─────────────────────────────────────────────
function updateSaveButton() {
  var saveBtn = $("save-btn");
  var planBtn = $("plan-add-btn");
  var hasPoint = state.lat !== null;
  saveBtn.disabled = !hasPoint;
  planBtn.disabled = !hasPoint;
  if (!hasPoint) {
    saveBtn.textContent = "♡ Guardar";
    return;
  }
  var fav = AlRasoStore.findFavoriteByPoint(state.lat, state.lon);
  saveBtn.textContent = fav ? "♥ Guardado" : "♡ Guardar";
}

$("save-btn").addEventListener("click", function () {
  if (state.lat === null) return;
  var name = state.selectedName || "Punto guardado";
  var fav = AlRasoStore.findFavoriteByPoint(state.lat, state.lon);
  if (fav) {
    AlRasoStore.removeFavorite(fav.id);
    $("searchmsg").textContent = "Lugar eliminado de Guardados.";
  } else {
    AlRasoStore.addFavorite({ name: name, lat: state.lat, lon: state.lon, category: state.poiCategory || undefined });
    $("searchmsg").textContent = "Lugar guardado en Guardados.";
  }
  updateSaveButton();
  updateStats();
});

// ─────────────────────────────────────────────
// PLAN ADD BUTTON + CHOOSER MODAL
// ─────────────────────────────────────────────
var _planAddTrigger = null;

$("plan-add-btn").addEventListener("click", function () {
  if (state.lat === null) return;
  openChooser();
});

function openChooser() {
  var overlay = $("chooser-overlay");
  overlay.hidden = false;

  if (state.lat === null) {
    $("chooser-no-point").hidden = false;
    $("chooser-content").hidden = true;
  } else {
    $("chooser-no-point").hidden = true;
    $("chooser-content").hidden = false;

    // Populate select with PLANNED outings
    var sel = $("chooser-select");
    sel.innerHTML = "";
    var outings = AlRasoStore.outings().filter(function (o) { return o.status === "PLANNED"; });
    if (outings.length === 0) {
      // No outings, show new form
      $("chooser-new").hidden = false;
      $("chooser-new-name").value = "";
      $("chooser-new-date").value = new Date().toISOString().slice(0, 10);
      sel.parentElement.style.display = "none";
      $("chooser-ok-btn").textContent = "Crear y añadir";
    } else {
      var optDefault = document.createElement("option");
      optDefault.value = "__new__";
      optDefault.textContent = "Crear nueva salida…";
      sel.appendChild(optDefault);
      outings.forEach(function (o) {
        var opt = document.createElement("option");
        opt.value = o.id;
        opt.textContent = o.name + " (" + o.date + ")";
        sel.appendChild(opt);
      });
      sel.style.display = "";
      sel.parentElement.style.display = "";
      // Initialize visibility from current select value (default is "__new__")
      if (sel.value === "__new__") {
        $("chooser-new").hidden = false;
        $("chooser-new-name").value = "";
        $("chooser-new-date").value = new Date().toISOString().slice(0, 10);
      } else {
        $("chooser-new").hidden = true;
      }
      $("chooser-ok-btn").textContent = "Añadir";
    }
  }

  // Focus into dialog
  overlay.querySelector("button, input, select").focus();

  // Add keydown handler for Escape
  overlay._keyHandler = function (ev) {
    if (ev.key === "Escape") { closeChooser(); }
  };
  document.addEventListener("keydown", overlay._keyHandler);

  // Close on backdrop click
  overlay._clickHandler = function (ev) {
    if (ev.target === overlay) closeChooser();
  };
  overlay.addEventListener("click", overlay._clickHandler);
}

function closeChooser() {
  var overlay = $("chooser-overlay");
  if (overlay._keyHandler) document.removeEventListener("keydown", overlay._keyHandler);
  if (overlay._clickHandler) overlay.removeEventListener("click", overlay._clickHandler);
  overlay.hidden = true;
}

$("chooser-close").addEventListener("click", closeChooser);

$("chooser-select").addEventListener("change", function () {
  if (this.value === "__new__") {
    $("chooser-new").hidden = false;
    $("chooser-new-name").value = "";
    $("chooser-new-date").value = new Date().toISOString().slice(0, 10);
  } else {
    $("chooser-new").hidden = true;
  }
});

$("chooser-ok-btn").addEventListener("click", function () {
  if (state.lat === null) return;
  var sel = $("chooser-select");
  var val = sel.value;

  if (val === "__new__" || $("chooser-new").hidden === false) {
    // Create new outing then add place
    var oName = $("chooser-new-name").value.trim() || "Nueva salida";
    var date = $("chooser-new-date").value || new Date().toISOString().slice(0, 10);
    var outing = AlRasoStore.addOuting({ name: oName, date: date });
    AlRasoStore.addPlaceToOuting(outing.id, { lat: state.lat, lon: state.lon, name: currentPlaceName() });
    $("searchmsg").textContent = "Lugar añadido a la salida «" + esc(oName) + "».";
  } else if (val && val !== "__new__") {
    // Add to existing outing
    var outings = AlRasoStore.outings();
    var chosen = null;
    for (var i = 0; i < outings.length; i++) { if (outings[i].id === val) { chosen = outings[i]; break; } }
    AlRasoStore.addPlaceToOuting(val, { lat: state.lat, lon: state.lon, name: currentPlaceName() });
    $("searchmsg").textContent = chosen ? "Lugar añadido a la salida «" + esc(chosen.name) + "»." : "Lugar añadido a la salida.";
  }
  closeChooser();
});

// ─────────────────────────────────────────────
// CENTER BUTTON (existing hook, now inside #detail-box)
// ─────────────────────────────────────────────
$("center-btn").addEventListener("click", function () {
  if (!map) return;
  var c = map.getCenter();
  selectPoint(c.lat, c.lng, null, false);
});

// ─────────────────────────────────────────────
// POI LEGAL CTA — reuse existing selectPoint/refresh (coordinates only)
// ─────────────────────────────────────────────
var poiLegalBtn = $("poi-legal-btn");
if (poiLegalBtn) {
  poiLegalBtn.addEventListener("click", function () {
    var lat = parseFloat(poiLegalBtn.getAttribute("data-lat"));
    var lon = parseFloat(poiLegalBtn.getAttribute("data-lon"));
    if (isNaN(lat) || isNaN(lon)) return;
    selectPoint(lat, lon, state.selectedName, true, true);
  });
}

// PA LEGAL CTA — same coords-only pattern (no name/fact injection)
// ─────────────────────────────────────────────
var paLegalBtn = $("pa-legal-btn");
if (paLegalBtn) {
  paLegalBtn.addEventListener("click", function () {
    var lat = parseFloat(paLegalBtn.getAttribute("data-lat"));
    var lon = parseFloat(paLegalBtn.getAttribute("data-lon"));
    if (isNaN(lat) || isNaN(lon)) return;
    selectPoint(lat, lon, null, true, true);
  });
}

// ─────────────────────────────────────────────
// SEARCH
// ─────────────────────────────────────────────
// ─────────────────────────────────────────────
// SUGGEST DROPDOWN (R3) — replaces datalist; source: existing /api/places ONLY
// Selection = one tap; manual/coordinates search keeps working via submit.
// ─────────────────────────────────────────────
(function initSuggest() {
  var input = $("q");
  var box = $("suggest");
  if (!input || !box) return;
  var places = [];
  var matches = [];
  var active = -1;

  fetch("/api/places")
    .then(function (r) { return r.json(); })
    .then(function (data) { places = (data.places || []).slice(); })
    .catch(function (e) { console.error("places", e); });

  function close() {
    box.hidden = true;
    box.innerHTML = "";
    active = -1;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }
  function render(q) {
    var ql = q.trim().toLowerCase();
    matches = places.filter(function (p) {
      return !ql || p.name.toLowerCase().indexOf(ql) !== -1 || (p.note || "").toLowerCase().indexOf(ql) !== -1;
    });
    box.innerHTML = "";
    active = -1;
    matches.forEach(function (p, i) {
      var opt = document.createElement("button");
      opt.type = "button";
      opt.className = "suggest-opt";
      opt.id = "suggest-opt-" + i;
      opt.setAttribute("role", "option");
      opt.setAttribute("aria-selected", "false");
      opt.innerHTML = '<span class="suggest-name">' + esc(p.name) + '</span>' +
        (p.note ? '<span class="suggest-note">' + esc(p.note) + '</span>' : '');
      opt.addEventListener("click", function () { choose(p); });
      box.appendChild(opt);
    });
  }
  function open() {
    render(input.value);
    if (!matches.length) { close(); return; }
    box.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }
  function choose(p) {
    input.value = p.name;
    close();
    selectPoint(p.lat, p.lon, p.name, true);
  }
  input.addEventListener("focus", open);
  input.addEventListener("input", open);
  input.addEventListener("keydown", function (ev) {
    var opts = box.querySelectorAll(".suggest-opt");
    if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
      if (box.hidden || !opts.length) return;
      ev.preventDefault();
      var dir = ev.key === "ArrowDown" ? 1 : -1;
      active = (active + dir + opts.length) % opts.length;
      Array.prototype.forEach.call(opts, function (o, i) {
        o.setAttribute("aria-selected", i === active ? "true" : "false");
      });
      input.setAttribute("aria-activedescendant", opts[active].id);
    } else if (ev.key === "Enter") {
      if (!box.hidden && active >= 0 && matches[active]) {
        ev.preventDefault();
        choose(matches[active]);
      }
      // Enter sin opcion activa: submit normal (busqueda manual o coordenadas)
    } else if (ev.key === "Escape") {
      if (!box.hidden) { ev.preventDefault(); ev.stopPropagation(); close(); }
    }
  });
  document.addEventListener("click", function (ev) {
    if (ev.target.closest && !ev.target.closest("#searchform")) close();
  });
})();

$("searchform").addEventListener("submit", async function (ev) {
  ev.preventDefault();
  var q = $("q").value.trim();
  if (!q) return;
  var f;
  try {
    f = await (await fetch("/api/find?q=" + encodeURIComponent(q))).json();
  } catch (e) {
    $("searchmsg").textContent = "No se pudo consultar la búsqueda.";
    return;
  }
  if (f.kind === "coords") {
    selectPoint(f.lat, f.lon, null);
  } else if (f.kind === "place") {
    selectPoint(f.lat, f.lon, f.name);
  } else if (f.kind === "poi") {
    selectPoint(f.lat, f.lon, f.name, true);
    renderPoi(f);
  } else if (f.kind === "ambiguous") {
    $("searchmsg").textContent = "Varias zonas coinciden: " +
      f.matches.map(function (m) { return m.name; }).join(" · ") + ". Concreta la búsqueda.";
  } else {
    $("searchmsg").textContent =
      "Sin coincidencias. Escribe coordenadas «lat, lon» (ej. 42.6627, 0.0160) " +
      "o elige una zona conocida de la lista.";
  }
});

// ─────────────────────────────────────────────
// FRESH RESOLVE (api/resolve)
// ─────────────────────────────────────────────
function factsFromForm() {
  var out = [];
  document.querySelectorAll("#factbox input").forEach(function (el) {
    if (el.type === "checkbox") { if (el.checked) out.push(el.name + "=true"); }
    else if (el.value !== "") out.push(el.name + "=" + el.value);
  });
  return out;
}

var resolveRequestId = 0;

async function refresh() {
  updateSaveButton();
  var p = new URLSearchParams({
    lat: state.lat, lon: state.lon,
    activity: $("activity").value,
    date: $("date").value || new Date().toISOString().slice(0, 10),
    knowledge: new Date().toISOString().slice(0, 10),
  });
  factsFromForm().forEach(function (kv) { var parts = kv.split("="); p.set(parts[0], parts.slice(1).join("=")); });
  resolveRequestId += 1;
  var myId = resolveRequestId;
  try {
    var r = await fetch("/api/resolve?" + p.toString());
    var d = await r.json();
    if (myId !== resolveRequestId) return; // stale response: discarded
    render(d);
  } catch (e) {
    console.error("resolve error", e);
    $("searchmsg").textContent = "No se pudo obtener la determinación. Inténtalo de nuevo.";
  }
}

$("date").valueAsDate = new Date();
["activity", "date"].forEach(function (id) {
  $(id).addEventListener("change", function () {
    if (state.lat !== null) refresh();
  });
});

// ─────────────────────────────────────────────
// RENDER — full card restructure
// ─────────────────────────────────────────────
const FACT_LABELS = {
  refuge_capacity_full: "el refugio está sin capacidad",
  nights: "número de noches",
  noches: "número de noches",
  cota_m: "altitud (m)",
  actividad_montana_o_escalada: "actividad de montaña o escalada",
};
const INTERNAL_FACTS = new Set(["jurisdiction_boundary_safe"]);
const OP_TEXT = {
  is_true: function (l) { return l; },
  is_false: function (l) { return l + " (no)"; },
  lte: function (l, v) { return l + " ≤ " + v; },
  gte: function (l, v) { return l + " ≥ " + v; },
  lt: function (l, v) { return l + " < " + v; },
  gt: function (l, v) { return l + " > " + v; },
  eq: function (l, v) { return l + " = " + v; },
};
function conditionText(c) {
  var parts = ((c && c.ast && c.ast.all) || [])
    .filter(function (x) { return !INTERNAL_FACTS.has(x.field); })
    .map(function (x) {
      var label = FACT_LABELS[x.field] || x.field;
      var fn = OP_TEXT[x.op];
      if (fn) return fn(label, x.value);
      return x.value === undefined ? label + ": " + x.op : label + " " + x.op + " " + x.value;
    });
  var body = parts.join(" y ");
  if (c && c.holds === false) return "No se cumple: " + (body || "—") + ".";
  return "Se cumplen las condiciones: " + (body || "—") + ".";
}

const ACT_LABELS = {
  VIVAC_AL_RASO: "dormir al raso (vivac)",
  FUNDA_VIVAC: "pernoctar con funda vivac",
  TIENDA_NOCTURNA: "usar tienda de campaña nocturna",
  ACAMPADA: "acampar",
  PERNOCTA_REFUGIO: "pernoctar en refugio",
};
function whyText(d) {
  var legal = d.determination.legalStatus;
  var act = ACT_LABELS[d.query.activity] || d.query.activity;
  var scope = (d.applicableScope || [])[0];
  var zone = scope ? ' en «' + scope.official_name + '»' : '';
  if (legal === "PERMITTED")
    return 'La normativa verificada permite ' + act + zone +
      ((d.conditions || []).length ? ", siempre que se cumplan las condiciones indicadas." : ".");
  if (legal === "PROHIBITED") return 'La normativa verificada prohíbe ' + act + zone + '.';
  if (legal === "AUTHORIZATION_REQUIRED") return 'Para ' + act + zone + ' hace falta una autorización previa según la normativa verificada.';
  if (d.coverage.status === "UNKNOWN")
    return "Ninguna norma del corpus de AlRaso llega a este punto, así que no podemos afirmar ni permiso ni prohibición. Los códigos canónicos de esta comprobación están en «Detalle técnico».";
  if (d.coverage.status === "PARTIAL")
    return "Conocemos la normativa de esta zona, pero la comprobación punto a punto no está cerrada: para este punto concreto no afirmamos ni permiso ni prohibición.";
  return "Faltan datos por confirmar (mira las condiciones de arriba): sin ellos AlRaso no afirma ni permiso ni prohibición.";
}

function badge(el, value, plain) {
  el.textContent = plain;
  el.dataset.code = value;
  el.className = "badge " + (
    { PERMITTED: "ok", PROHIBITED: "bad", AUTHORIZATION_REQUIRED: "warn", UNDETERMINED: "unk",
      CURRENT: "ok", INCOMPLETE: "warn", CONFLICTING: "bad",
      VERIFIED: "ok", PARTIAL: "warn", UNKNOWN: "unk" }[value] || "unk");
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}

// Emoji mapping per legalStatus (never color-only)
var LEGAL_EMOJI = {
  PERMITTED: "✅",
  PROHIBITED: "⛔",
  AUTHORIZATION_REQUIRED: "🟠",
  UNDETERMINED: "⚠️",
};

var LEGAL_BORDER_COLOR = {
  PERMITTED: "#22c55e",
  PROHIBITED: "#ef4444",
  AUTHORIZATION_REQUIRED: "#f59e0b",
  UNDETERMINED: "#93a1b0",
};

function render(d) {
  $("card-empty").hidden = true;
  $("card-result").hidden = false;

  var ui = d.ui || {};

  // ── outdoor info block ──
  // Coords — use ACT_LABELS for Spanish label (U5)
  var actLabel = ACT_LABELS[d.query.activity] || d.query.activity;
  $("coords").textContent = state.lat.toFixed(5) + ", " + state.lon.toFixed(5) + " · " + actLabel + " · " + d.query.activity_date;

  // Altitude: only from dem.value_m (POI altitude stays in the POI card only).
  var altLine = $("altitude-line");
  if (d.dem && typeof d.dem.value_m === "number") {
    altLine.hidden = false;
    altLine.textContent = "Altitud: " + d.dem.value_m + " m · Fuente: " + esc(d.dem.source || "");
  } else {
    altLine.hidden = true;
    altLine.textContent = "";
  }

  // ── legal result ──
  var legalStatus = d.determination.legalStatus;
  var emoji = LEGAL_EMOJI[legalStatus] || "";
  $("legal-emoji").textContent = emoji;
  $("headline").textContent = ui.headline || d.determination.legalStatus;
  var resultEl = $("legal-result");
  resultEl.style.borderLeftColor = LEGAL_BORDER_COLOR[legalStatus] || "#999";

  badge($("legal"), d.determination.legalStatus, ui.legal || d.determination.legalStatus);
  badge($("knowledge"), d.determination.knowledgeStatus, ui.knowledge || d.determination.knowledgeStatus);
  badge($("coverage"), d.coverage.status, ui.coverage || d.coverage.status);

  // Plain-language conditions (bullets)
  var plainConds = $("plain-conds");
  plainConds.innerHTML = "";
  var conds = d.conditions || [];
  if (legalStatus !== "UNDETERMINED" && conds.length > 0) {
    plainConds.hidden = false;
    conds.forEach(function (c) {
      var li = document.createElement("li");
      var text = _plainCondition(c);
      if (text) li.textContent = text;
      if (li.textContent) plainConds.appendChild(li);
    });
  } else {
    plainConds.hidden = true;
  }

  // ui.knowledge explanation when UNDETERMINED
  var uiKnow = $("ui-knowledge");
  if (legalStatus === "UNDETERMINED" && ui.knowledge) {
    uiKnow.hidden = false;
    uiKnow.textContent = ui.knowledge;
  } else {
    uiKnow.hidden = true;
    uiKnow.textContent = "";
  }

  // ── detail box (technical) ──
  renderFacts(d);

  var demInfo = $("dem-info");
  if (d.dem && typeof d.dem.value_m === "number") {
    demInfo.hidden = false;
    demInfo.innerHTML = "Altitud obtenida automáticamente: <b>" + d.dem.value_m.toFixed(0) + " m</b> · Fuente: " + esc(d.dem.source || "") + (d.dem.product ? " (" + esc(d.dem.product) + ")" : "") +
      (d.cotaFactSource === "OFFICIAL_DEM" ? " · no hace falta que indiques la altitud" : "");
    var cota = document.querySelector('[name=cota_m]');
    if (cota && d.cotaFactSource === "OFFICIAL_DEM") cota.value = d.dem.value_m;
  } else {
    demInfo.hidden = true;
    demInfo.innerHTML = "";
  }

  var cl = $("cond-list");
  cl.innerHTML = "";
  (d.conditions || []).forEach(function (c) {
    var li = document.createElement("li");
    li.textContent = conditionText(c);
    cl.appendChild(li);
  });
  $("condiciones").style.display = (d.conditions || []).length ? "" : "none";

  $("decision").textContent = whyText(d);

  var zones = $("region-list");
  zones.innerHTML = "";
  if (!(d.coverage.regions || []).length) {
    zones.innerHTML = '<div class="region">Ninguna región cubierta contiene este punto.<br><span class="meta">AlRaso no tiene corpus aquí y por eso no puede afirmar nada: ni permiso ni prohibición.</span></div>';
  }
  (d.coverage.regions || []).forEach(function (r) {
    var div = document.createElement("div");
    div.className = "region";
    var norms = (r.norms || []).map(function (n) {
      return '<li>' + esc(n.title) + (n.canonical_url ? ' — <a target="_blank" rel="noopener" href="' + esc(n.canonical_url) + '">fuente</a>' : '') + (n.official_status ? ' <i>(' + esc(n.official_status) + ')</i>' : '') + '</li>';
    }).join("");
    var notes = (r.notes || []).map(function (n) { return '<li>' + esc(n) + '</li>'; }).join("");
    div.innerHTML =
      '<div class="rhead"><span>' + esc(r.name) + '</span><span class="chip ' + (r.coverage === "VERIFIED" ? "ok" : "warn") + '">' + (r.coverage === "VERIFIED" ? "completa" : "parcial") + '</span></div>' +
      '<div class="meta">verificado ' + esc(r.verified_at) + ' · límite ' + (r.boundary === "oficial" ? 'OFICIAL (geometría del motor)' : 'ESQUEMÁTICO (informativo, sin valor legal)') + '</div>' +
      '<p>' + esc(r.summary) + '</p>' +
      '<details><summary>normas y fuentes de la zona</summary><ul>' + norms + '</ul>' + (notes ? '<ul>' + notes + '</ul>' : '') + '</details>';
    zones.appendChild(div);
  });

  var src = $("sources");
  src.innerHTML = "";
  (d.sources || []).forEach(function (s) {
    var li = document.createElement("li");
    li.innerHTML = esc(s.title) + (s.canonical_url ? ' — <a target="_blank" rel="noopener" href="' + esc(s.canonical_url) + '">documento</a>' : '') + (s.official_status ? ' <i>(' + esc(s.official_status) + ')</i>' : '');
    src.appendChild(li);
  });
  if (!(d.sources || []).length) src.innerHTML = "<li>Sin fuentes: ninguna norma verificada cubre este punto. Eso no es una prohibición.</li>";

  var tech = $("tech-codes");
  tech.innerHTML = "";
  var codes = [
    "legalStatus=" + d.determination.legalStatus,
    "knowledgeStatus=" + d.determination.knowledgeStatus,
    "coverage=" + d.coverage.status,
    "decisionReason=" + (d.determination.decisionReason || "—"),
    "cotaFactSource=" + (d.cotaFactSource || "NONE"),
  ];
  if (d.dem) codes.push("dem=" + JSON.stringify(d.dem));
  if (d.userVsDem) codes.push("userVsDem=" + JSON.stringify(d.userVsDem));
  (d.determination.reasonCodes || []).forEach(function (rc) { codes.push(rc); });
  (d.conditions || []).forEach(function (c) { codes.push("condition=" + JSON.stringify(c)); });
  codes.forEach(function (rc) {
    var li = document.createElement("li");
    li.textContent = rc;
    tech.appendChild(li);
  });

  $("warning").textContent = (d.determination.warnings || [])[0] || "";
}

function _plainCondition(c) {
  var all = (c && c.ast && c.ast.all) || [];
  var parts = [];
  for (var i = 0; i < all.length; i++) {
    var x = all[i];
    if (INTERNAL_FACTS.has(x.field)) continue;
    var label = FACT_LABELS[x.field] || x.field;
    if (x.field === "actividad_montana_o_escalada" && x.op === "is_true") {
      parts.push("Actividad de montaña o escalada");
    } else if (x.field === "nights" && x.op === "lte") {
      parts.push("Máximo " + x.value + " noches");
    } else if (x.field === "cota_m" && x.op === "gt") {
      parts.push("Por encima de " + x.value + " m");
    } else if (x.field === "refuge_capacity_full" && x.op === "is_true") {
      parts.push("Solo si el refugio está sin capacidad");
    } else {
      var fn = OP_TEXT[x.op];
      if (fn) {
        parts.push(fn(label, x.value));
      } else {
        parts.push(x.value === undefined ? label + ": " + x.op : label + " " + x.op + " " + x.value);
      }
    }
  }
  return parts.join(" y ") || null;
}

// ─────────────────────────────────────────────
// FACTS
// ─────────────────────────────────────────────
const FACT_INPUTS = {
  refuge_capacity_full: { kind: "checkbox", label: "el refugio está sin capacidad" },
  actividad_montana_o_escalada: { kind: "checkbox", label: "Actividad de montaña o escalada" },
  cota_m: {
    kind: "number", label: "Altitud indicada por ti (m)", noDefault: true,
    note: "La altitud se obtiene automáticamente del DEM oficial cuando hay cobertura; indícala sólo si quieres aportar un valor concreto.",
  },
  nights: { kind: "number", label: "Número de noches" },
};

function renderFacts(d) {
  var box = $("factbox");
  var had = new Set();
  box.querySelectorAll("[name]").forEach(function (el) { had.add(el.name); });
  var wanted = new Map();
  (d.conditions || []).forEach(function (c) {
    if (c && c.field && !INTERNAL_FACTS.has(c.field)) wanted.set(c.field, c);
  });
  var forced = ["nights"];
  var gorizScope = (d.applicableScope || []).some(function (s) {
    return String(s.scope_id || s.id || "").startsWith("ss-ordesa");
  });
  var picosScope = (d.applicableScope || []).some(function (s) {
    return String(s.scope_id || s.id || "").startsWith("ss-pnpe-es-");
  });
  if (gorizScope) forced.push("refuge_capacity_full");
  if (picosScope) forced.push("actividad_montana_o_escalada", "cota_m");
  forced.forEach(function (f) { wanted.set(f, { field: f }); });

  var wantedNames = new Set(wanted.keys());
  box.querySelectorAll("[name]").forEach(function (el) {
    if (!wantedNames.has(el.name) && el.parentElement) el.parentElement.remove();
  });
  wanted.forEach(function (c, f) {
    if (had.has(f)) return;
    var spec = FACT_INPUTS[f] || { kind: "number", label: f };
    if (spec.kind === "checkbox") {
      var label = document.createElement("label");
      label.innerHTML = '<input type="checkbox" name="' + f + '"> ' + spec.label;
      box.appendChild(label);
    } else {
      var label = document.createElement("label");
      label.innerHTML = spec.label + ' <input type="number" name="' + f + '" min="0" style="width:80px">';
      if (spec.note) {
        var note = document.createElement("span");
        note.className = "fact-note";
        note.textContent = spec.note;
        label.appendChild(note);
      }
      box.appendChild(label);
    }
    var el = box.querySelector('[name="' + f + '"]');
    el.addEventListener("change", function () { if (state.lat !== null) refresh(); });
  });
}

// ─────────────────────────────────────────────
// SAVED VIEW RENDER
// ─────────────────────────────────────────────
function renderFavorites() {
  var listEl = $("favorites-list");
  var favs = AlRasoStore.favorites();
  if (favs.length === 0) {
    listEl.innerHTML = '<p class="empty-state">Todavía no has guardado ningún sitio.</p>' +
      '<p class="hint">Explora el mapa y pulsa ♡ Guardar en la ficha de un lugar.</p>';
    return;
  }
  listEl.innerHTML = "";
  favs.forEach(function (fav) {
    var row = document.createElement("div");
    row.className = "fav-row";
    var subtitle = fav.category ? POI_CATS[fav.category] ? POI_CATS[fav.category].label : fav.category : fav.lat.toFixed(5) + ", " + fav.lon.toFixed(5);
    row.innerHTML =
      '<div class="fav-info"><span class="fav-name">♥ ' + esc(fav.name) + '</span><span class="fav-sub">' + esc(subtitle) + '</span></div>' +
      '<div class="fav-actions">' +
        '<button class="view-on-map-btn" data-lat="' + fav.lat + '" data-lon="' + fav.lon + '" data-name="' + esc(fav.name) + '">Ver en mapa</button>' +
        '<button class="del-fav-btn" data-id="' + esc(fav.id) + '">Eliminar</button>' +
      '</div>';
    listEl.appendChild(row);
  });

  // Attach events
  listEl.querySelectorAll(".view-on-map-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var lat = parseFloat(btn.dataset.lat);
      var lon = parseFloat(btn.dataset.lon);
      var name = btn.dataset.name;
      showTab("explore");
      selectPoint(lat, lon, name, true);
    });
  });
  listEl.querySelectorAll(".del-fav-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      AlRasoStore.removeFavorite(btn.dataset.id);
      renderFavorites();
      updateSaveButton();
      updateStats();
    });
  });
}

// ─────────────────────────────────────────────
// OUTINGS VIEW RENDER
// ─────────────────────────────────────────────
function formatDate(ds) {
  var parts = ds.split("-");
  return parts[2] + "/" + parts[1] + "/" + parts[0];
}

function renderOutings() {
  var listEl = $("outings-list");
  var outings = AlRasoStore.outings();

  if (outings.length === 0) {
    listEl.innerHTML = '<p class="empty-state">Todavía no has preparado ninguna salida.</p>' +
      '<p class="hint">Desde la ficha de un lugar, pulsa "Añadir a una salida" o crea una aquí.</p>';
    return;
  }

  var planned = outings.filter(function (o) { return o.status === "PLANNED"; }).sort(function (a, b) { return a.date.localeCompare(b.date); });
  var completed = outings.filter(function (o) { return o.status === "COMPLETED"; });

  var html = "";

  if (planned.length > 0) {
    html += '<h3>Próximas</h3>';
    planned.forEach(function (o) { html += outingRow(o); });
  }

  if (completed.length > 0) {
    html += '<h3>Realizadas</h3>';
    completed.forEach(function (o) { html += outingRow(o); });
  }

  listEl.innerHTML = html;

  // Attach events
  listEl.querySelectorAll(".outing-toggle-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = btn.dataset.id;
      var row = btn.closest(".outing-row");
      var placesDiv = row.querySelector(".outing-places");
      if (placesDiv.style.display === "block") {
        placesDiv.style.display = "none";
        btn.textContent = "Ver";
      } else {
        renderOutingPlaces(row, id);
        placesDiv.style.display = "block";
        btn.textContent = "Ocultar";
      }
    });
  });
  listEl.querySelectorAll(".outing-view-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var lat = parseFloat(btn.dataset.lat);
      var lon = parseFloat(btn.dataset.lon);
      var name = btn.dataset.name;
      showTab("explore");
      selectPoint(lat, lon, name, true);
    });
  });
  listEl.querySelectorAll(".outing-complete-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      AlRasoStore.completeOuting(btn.dataset.id);
      renderOutings();
      updateStats();
    });
  });
  listEl.querySelectorAll(".outing-del-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      AlRasoStore.removeOuting(btn.dataset.id);
      renderOutings();
      updateStats();
    });
  });
}

function outingRow(o) {
  var statusLabel = o.status === "COMPLETED" ? " · realizada ✓" : "";
  var placeCount = (o.places || []).length;
  var notesHtml = o.notes ? '<span class="outing-notes">' + esc(o.notes) + '</span>' : '';
  return '<div class="outing-row" data-outing-id="' + esc(o.id) + '">' +
    '<div class="outing-info">' +
      '<span class="outing-name">' + esc(o.name) + '</span>' +
      ' · ' + formatDate(o.date) +
      ' · ' + placeCount + ' lugar' + (placeCount !== 1 ? 'es' : '') +
      statusLabel +
      notesHtml +
    '</div>' +
    '<div class="outing-actions">' +
      '<button class="outing-toggle-btn" data-id="' + esc(o.id) + '">Ver</button>' +
      (o.status === "PLANNED" ? '<button class="outing-complete-btn" data-id="' + esc(o.id) + '">Marcar realizada</button>' : '') +
      '<button class="outing-del-btn" data-id="' + esc(o.id) + '">Eliminar</button>' +
    '</div>' +
    '<div class="outing-places" style="display:none"></div>' +
  '</div>';
}

function renderOutingPlaces(row, outingId) {
  var placesDiv = row.querySelector(".outing-places");
  var outings = AlRasoStore.outings();
  var outing = null;
  for (var i = 0; i < outings.length; i++) {
    if (outings[i].id === outingId) { outing = outings[i]; break; }
  }
  if (!outing || !outing.places || outing.places.length === 0) {
    placesDiv.innerHTML = '<p class="empty-state">Sin lugares en esta salida.</p>';
    return;
  }
  placesDiv.innerHTML = "";
  outing.places.forEach(function (p) {
    var div = document.createElement("div");
    div.className = "outing-place-item";
    div.innerHTML = '<span>' + esc(p.name || p.lat.toFixed(5) + ", " + p.lon.toFixed(5)) + '</span>' +
      '<button class="outing-view-btn" data-lat="' + p.lat + '" data-lon="' + p.lon + '" data-name="' + esc(p.name || '') + '">Ver en mapa</button>';
    placesDiv.appendChild(div);
  });
}

// ─────────────────────────────────────────────
// NEW OUTING FORM
// ─────────────────────────────────────────────
$("new-outing-btn").addEventListener("click", function () {
  $("outing-form").hidden = false;
  $("outing-name").value = "";
  $("outing-date").value = new Date().toISOString().slice(0, 10);
  $("outing-notes").value = "";
  $("outing-name").focus();
});

$("outing-cancel-btn").addEventListener("click", function () {
  $("outing-form").hidden = true;
});

$("outing-confirm-btn").addEventListener("click", function () {
  var name = $("outing-name").value.trim();
  var date = $("outing-date").value;
  var notes = $("outing-notes").value.trim();
  if (!name) { $("outing-name").focus(); return; }
  AlRasoStore.addOuting({ name: name, date: date, notes: notes });
  $("outing-form").hidden = true;
  $("searchmsg").textContent = "Salida creada.";
  renderOutings();
  updateStats();
});

// ─────────────────────────────────────────────
// PROFILE STATS
// ─────────────────────────────────────────────
function updateStats() {
  var s = AlRasoStore.stats();
  $("stat-favorites").textContent = s.favorites;
  $("stat-planned").textContent = s.planned;
  $("stat-completed").textContent = s.completed;
}

// Initial stats load
updateStats();

// ─────────────────────────────────────────────
// BOOT
// ─────────────────────────────────────────────
void boot();

// ─────────────────────────────────────────────
// M5: PWA + OFFLINE RESILIENCE (installable shell, two-signal connectivity UI)
// Two different failures must never be conflated:
//   - no internet/map tiles (remote cartography unreachable)
//   - local legal server down (no NEW determination can be computed: fail-closed)
// The probe reuses the existing /api/config endpoint; no extra health route is added.
// ─────────────────────────────────────────────
(function initPwa() {
  var banner = $("conn-banner");
  var swSupported = "serviceWorker" in navigator && window.isSecureContext === true;
  document.body.setAttribute("data-sw-supported", swSupported ? "1" : "0");

  if (swSupported) {
    navigator.serviceWorker.register("/sw.js").then(function () {
      document.body.setAttribute("data-sw-registered", "1");
    }).catch(function () {
      document.body.setAttribute("data-sw-registered", "0");
    });
  } else {
    document.body.setAttribute("data-sw-registered", "0");
  }

  var apiOk = null; // null = unknown yet, true/false = last probe result
  function setBanner() {
    if (!banner) return;
    if (apiOk === false) {
      banner.textContent = "Servidor de verificación no disponible — no podemos calcular una determinación nueva.";
      banner.className = "conn-banner api-down";
      banner.hidden = false;
    } else if (navigator.onLine === false) {
      banner.textContent = "Sin internet — se muestran recursos cartográficos guardados; la verificación jurídica sigue disponible mientras el servidor local responda.";
      banner.className = "conn-banner offline";
      banner.hidden = false;
    } else {
      banner.hidden = true;
    }
  }
  function probeApi() {
    if (typeof AbortController === "undefined") return;
    var ctl = new AbortController();
    var timer = setTimeout(function () { ctl.abort(); }, 4000);
    fetch("/api/config", { cache: "no-store", signal: ctl.signal })
      .then(function (r) { apiOk = r.ok; })
      .catch(function () { apiOk = false; })
      .then(function () { clearTimeout(timer); setBanner(); });
  }
  window.addEventListener("online", probeApi);
  window.addEventListener("offline", setBanner);
  probeApi();
  setInterval(probeApi, 30000);
})();

// ─────────────────────────────────────────────
// M6: WEATHER CONDITIONS (Open-Meteo, observational outdoor context)
// NOT legal evidence: the resolver never consumes these values.
// - direct browser fetch (CORS), no API key, no new server endpoint
// - one request per point selection (never per refresh)
// - coordinates rounded to 3 decimals (~100 m) for the weather URL only;
//   the legal resolution keeps the original coordinates
// - monotonic request generation guard: a stale response can never render
// - weather is never cached (stale weather is worse than no weather)
// ─────────────────────────────────────────────
var weatherRequestId = 0;
var weatherAbort = null;

function loadWeather(lat, lon) {
  var block = $("weather-block");
  if (!block || lat === null || lat === undefined) return;
  weatherRequestId += 1;
  var myId = weatherRequestId;
  if (weatherAbort) { try { weatherAbort.abort(); } catch (e) { /* already aborted */ } }
  weatherAbort = typeof AbortController !== "undefined" ? new AbortController() : null;
  // clear previous values immediately: no old data may survive a new selection
  block.hidden = false;
  block.removeAttribute("data-lat");
  block.removeAttribute("data-lon");
  block.innerHTML = "";
  var loading = document.createElement("p");
  loading.className = "weather-loading";
  loading.textContent = "Cargando condiciones…";
  block.appendChild(loading);

  var url = "https://api.open-meteo.com/v1/forecast" +
    "?latitude=" + Number(lat.toFixed(3)) +
    "&longitude=" + Number(lon.toFixed(3)) +
    "&current=temperature_2m,wind_speed_10m,wind_gusts_10m" +
    "&hourly=temperature_2m,precipitation_probability,wind_speed_10m,wind_gusts_10m" +
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max" +
    "&timezone=auto&forecast_days=3&wind_speed_unit=kmh";
  fetch(url, { cache: "no-store", signal: weatherAbort ? weatherAbort.signal : undefined })
    .then(function (r) { if (!r.ok) throw new Error("weather_http_" + r.status); return r.json(); })
    .then(function (data) {
      if (myId !== weatherRequestId) return; // stale response: discarded
      renderWeather(block, lat, lon, data);
    })
    .catch(function () {
      if (myId !== weatherRequestId) return; // aborted or superseded
      block.innerHTML = "";
      var p = document.createElement("p");
      p.className = "weather-unavailable";
      p.textContent = "Sin conexión: no hay datos meteorológicos disponibles.";
      block.appendChild(p);
    });
}

function fmtTemp(v) {
  return (v === null || v === undefined) ? "–" : Math.round(v) + "°";
}
function fmtKmh(v) {
  return (v === null || v === undefined) ? "–" : Math.round(v) + " km/h";
}
function fmtProb(v) {
  return (v === null || v === undefined) ? "–" : v + "%";
}
function minOf(arr) {
  var a = (arr || []).filter(function (v) { return v !== null && v !== undefined; });
  return a.length ? Math.min.apply(null, a) : null;
}
function maxOf(arr) {
  var a = (arr || []).filter(function (v) { return v !== null && v !== undefined; });
  return a.length ? Math.max.apply(null, a) : null;
}
function nextDayStr(dateStr) {
  var d = new Date(dateStr + "T00:00Z"); d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}
function prevDayStr(dateStr) {
  var d = new Date(dateStr + "T00:00Z"); d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}
// Current local instant at the location ("YYYY-MM-DDTHH:MM"), string-based
// on utc_offset_seconds - never the browser clock.
function localNow(data) {
  var off = (data.utc_offset_seconds || 0) * 1000;
  return new Date(Date.now() + off).toISOString().slice(0, 16);
}

// Three following chronological LOCAL periods (06-12, 12-18, 18-06),
// skipping elapsed ones; day shown when the date changes. All time math is
// string-based on the location's local time via utc_offset_seconds.
function computeWeatherPeriods(data) {
  var hourly = data.hourly || {};
  var times = hourly.time || [];
  if (!times.length) return [];
  var nowLocal = localNow(data);
  var buckets = {}, order = [];
  for (var i = 0; i < times.length; i++) {
    var t = times[i];
    var date = t.slice(0, 10), hh = Number(t.slice(11, 13));
    var bDate, bIdx, bStart, bEnd;
    if (hh >= 6 && hh < 12) {
      bDate = date; bIdx = 0; bStart = date + "T06:00"; bEnd = date + "T12:00";
    } else if (hh >= 12 && hh < 18) {
      bDate = date; bIdx = 1; bStart = date + "T12:00"; bEnd = date + "T18:00";
    } else if (hh >= 18) {
      bDate = date; bIdx = 2; bStart = date + "T18:00"; bEnd = nextDayStr(date) + "T06:00";
    } else {
      bDate = prevDayStr(date); bIdx = 2; bStart = bDate + "T18:00"; bEnd = date + "T06:00";
    }
    if (t <= nowLocal) continue; // past hour: must never enter the current slot
    if (bEnd <= nowLocal) continue; // fully elapsed: skip
    var key = bDate + "#" + bIdx;
    if (!buckets[key]) {
      buckets[key] = { bDate: bDate, bIdx: bIdx, temps: [], rain: [], wind: [], gust: [] };
      order.push(key);
    }
    buckets[key].temps.push(hourly.temperature_2m ? hourly.temperature_2m[i] : null);
    buckets[key].rain.push(hourly.precipitation_probability ? hourly.precipitation_probability[i] : null);
    buckets[key].wind.push(hourly.wind_speed_10m ? hourly.wind_speed_10m[i] : null);
    buckets[key].gust.push(hourly.wind_gusts_10m ? hourly.wind_gusts_10m[i] : null);
  }
  order.sort();
  var today = nowLocal.slice(0, 10);
  var tomorrow = nextDayStr(today);
  return order.slice(0, 3).map(function (key) {
    var b = buckets[key];
    var base = ["por la mañana", "por la tarde", "por la noche"][b.bIdx];
    var label;
    if (b.bDate === today) label = (b.bIdx === 2 ? "Esta " : "") + base;
    else if (b.bDate === tomorrow) label = "Mañana " + base;
    else label = b.bDate.slice(5).replace("-", "/") + " " + base;
    var lo = minOf(b.temps), hi = maxOf(b.temps);
    return {
      label: label,
      temp: fmtTemp(lo) + "/" + fmtTemp(hi),
      rain: fmtProb(maxOf(b.rain)),
      wind: fmtKmh(maxOf(b.wind)) + "/" + fmtKmh(maxOf(b.gust))
    };
  });
}

function renderWeather(block, lat, lon, data) {
  block.innerHTML = "";
  block.setAttribute("data-lat", lat.toFixed(3));
  block.setAttribute("data-lon", lon.toFixed(3));

  var head = document.createElement("p");
  head.className = "weather-head";
  head.innerHTML = 'Condiciones <span class="weather-src">Tiempo: ' +
    '<a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a>' +
    ' (CC BY 4.0)</span>';
  block.appendChild(head);

  var cur = data.current || {};
  var now = document.createElement("p");
  now.className = "weather-line";
  now.textContent = "Ahora: " + fmtTemp(cur.temperature_2m) +
    " · viento " + fmtKmh(cur.wind_speed_10m) +
    " · rachas " + fmtKmh(cur.wind_gusts_10m);
  block.appendChild(now);

  var daily = data.daily || {};
  // "Hoy" consumes ONLY the daily index of the current local day: aggregating
  // the whole daily.* arrays would present tomorrow's extremes as today's.
  var di = (daily.time || []).indexOf(localNow(data).slice(0, 10));
  var dailyMin = di >= 0 ? (daily.temperature_2m_min || [])[di] : null;
  var dailyMax = di >= 0 ? (daily.temperature_2m_max || [])[di] : null;
  var dailyProb = di >= 0 ? (daily.precipitation_probability_max || [])[di] : null;
  var today = document.createElement("p");
  today.className = "weather-line";
  today.textContent = "Hoy: " + fmtTemp(dailyMin) +
    " / " + fmtTemp(dailyMax) +
    " · lluvia " + fmtProb(dailyProb);
  block.appendChild(today);

  var periods = computeWeatherPeriods(data);
  if (!periods.length) return;
  var title = document.createElement("p");
  title.className = "weather-sub";
  title.textContent = "Próximas 24 h";
  block.appendChild(title);
  periods.forEach(function (p) {
    var row = document.createElement("p");
    row.className = "weather-line weather-period";
    row.textContent = p.label + ": " + p.temp + " · lluvia " + p.rain +
      " · viento " + p.wind;
    block.appendChild(row);
  });
}
