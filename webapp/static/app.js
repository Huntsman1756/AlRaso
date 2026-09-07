"use strict";
const $ = (id) => document.getElementById(id);
const state = { lat: null, lon: null, marker: null, poiCategory: null, poiAlt: null, selectedName: null };
let poiClickGuard = 0;

// Proveedor de basemap NO hardcodeado: se pide a /api/config (el server lee
// ALRASO_MAP_STYLE_URL). Default del lado cliente solo por si el fetch falla.
const FALLBACK_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";

const POI_CATS = {
  refuge: { emoji: "🏠", label: "Refugio", color: "#b45309" },
  shelter: { emoji: "🛖", label: "Abrigo / cabaña", color: "#f97316" },
  water: { emoji: "💧", label: "Agua", color: "#0ea5e9" },
  camping: { emoji: "⛺", label: "Camping / bivouac", color: "#16a34a" },
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
          "fill-opacity": 0.18,
        },
      });
      const covColor = ["match", ["get", "coverage"], "VERIFIED", "#22c55e", "PARTIAL", "#f59e0b", "#94a3b8"];
      map.addLayer({
        id: "cov-line", type: "line", source: "coverage",
        filter: ["==", ["get", "boundary"], "oficial"],
        paint: { "line-color": covColor, "line-width": 1.6 },
      });
      map.addLayer({
        id: "cov-line-esquematico", type: "line", source: "coverage",
        filter: ["==", ["get", "boundary"], "esquematico"],
        paint: { "line-color": covColor, "line-width": 1.2, "line-dasharray": [3, 3] },
      });
      await loadPois();
      map.fitBounds([[-5.35, 42.45], [0.25, 43.4]], { padding: 30 });
    } catch (e) { console.error(e); }
  });

  map.on("click", (e) => {
    if (Date.now() - poiClickGuard < 150) return;
    selectPoint(e.lngLat.lat, e.lngLat.lng, null, false);
  });
}

// ─────────────────────────────────────────────
// POIS
// ─────────────────────────────────────────────
async function loadPois() {
  let fc;
  try { fc = await (await fetch("/api/pois")).json(); }
  catch (e) { console.error("pois", e); return; }
  map.addSource("pois", { type: "geojson", data: fc });
  POI_ORDER.forEach((cat) => {
    const c = POI_CATS[cat];
    map.addLayer({
      id: `poi-circles-${cat}`, type: "circle", source: "pois",
      filter: ["==", ["get", "category"], cat],
      paint: { "circle-color": c.color, "circle-radius": 5.5,
               "circle-stroke-color": "#0b0e12", "circle-stroke-width": 1.2 },
    });
    if (cat !== "water") {
      map.addLayer({
        id: `poi-labels-${cat}`, type: "symbol", source: "pois",
        filter: ["==", ["get", "category"], cat],
        minzoom: 9,
        layout: { "text-field": ["get", "name"], "text-size": 11,
                  "text-offset": [0, 1.1], "text-anchor": "top",
                  "text-optional": true, "text-max-width": 9,
                  "text-font": ["Noto Sans Regular"] },
        paint: { "text-color": "#e8edf2", "text-halo-color": "#101418",
                 "text-halo-width": 1.2 },
      });
    }
    map.on("click", `poi-circles-${cat}`, (e) => onPoiClick(e));
  });
  bindLayerToggles();
}

function bindLayerToggles() {
  const groups = {
    "lg-refuge": ["poi-circles-refuge", "poi-labels-refuge"],
    "lg-shelter": ["poi-circles-shelter", "poi-labels-shelter"],
    "lg-water": ["poi-circles-water"],
    "lg-camping": ["poi-circles-camping", "poi-labels-camping"],
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

function renderPoi(p) {
  const cat = POI_CATS[p.category] || { emoji: "📍", label: p.category };
  $("poi").hidden = false;
  $("poi-emoji").textContent = cat.emoji;
  $("poi-name").textContent = p.name;
  const parts = [cat.label];
  if (p.alt_m) parts.push(`${p.alt_m} m`);
  if (p.source_label) parts.push(`fuente: ${p.source_label}`);
  $("poi-meta").textContent = parts.join(" · ");
  $("poi-note").textContent = p.note || "";
  const box = $("poi-srcbox"), link = $("poi-src");
  if (p.osm_url) {
    link.href = p.osm_url; link.textContent = p.osm_url; box.style.display = "";
  } else {
    box.style.display = "none";
  }
  state.poiCategory = p.category;
  state.poiAlt = p.alt_m || null;
}

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
// SELECT POINT & FRESH RESOLVE
// ─────────────────────────────────────────────
function selectPoint(lat, lon, name, fly) {
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
  if (!name) { $("poi").hidden = true; state.poiCategory = null; state.poiAlt = null; }
  $("searchmsg").textContent = name ? `Zona seleccionada: ${name}` : "";
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
// CENTER BUTTON (existing hook)
// ─────────────────────────────────────────────
$("center-btn").addEventListener("click", function () {
  if (!map) return;
  var c = map.getCenter();
  selectPoint(c.lat, c.lng, null, false);
});

// ─────────────────────────────────────────────
// SEARCH
// ─────────────────────────────────────────────
(function () {
  var dl = $("places-list");
  fetch("/api/places")
    .then(function (r) { return r.json(); })
    .then(function (data) {
      dl.innerHTML = "";
      (data.places || []).forEach(function (p) {
        var opt = document.createElement("option");
        opt.value = p.name;
        opt.label = p.note || p.name;
        dl.appendChild(opt);
      });
    })
    .catch(function (e) { console.error(e); });
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

async function refresh() {
  updateSaveButton();
  var p = new URLSearchParams({
    lat: state.lat, lon: state.lon,
    activity: $("activity").value,
    date: $("date").value || new Date().toISOString().slice(0, 10),
    knowledge: new Date().toISOString().slice(0, 10),
  });
  factsFromForm().forEach(function (kv) { var parts = kv.split("="); p.set(parts[0], parts.slice(1).join("=")); });
  try {
    var r = await fetch("/api/resolve?" + p.toString());
    var d = await r.json();
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
  // Coords
  $("coords").textContent = state.lat.toFixed(5) + ", " + state.lon.toFixed(5) + " · " + d.query.activity + " · " + d.query.activity_date;

  // Altitude: prefer dem.value_m, fall back to poi alt
  var altLine = $("altitude-line");
  if (d.dem && typeof d.dem.value_m === "number") {
    altLine.hidden = false;
    altLine.textContent = "Altitud: " + d.dem.value_m + " m · Fuente: " + esc(d.dem.source || "");
  } else if (state.poiAlt != null) {
    altLine.hidden = false;
    altLine.textContent = "Altitud: " + state.poiAlt + " m (observación OSM)";
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
    note: "La altitud ha sido indicada por el usuario; AlRaso todavía no la verifica automáticamente.",
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