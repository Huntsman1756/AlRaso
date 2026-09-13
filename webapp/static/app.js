import { $, esc } from "./modules/dom.js";
import { createAppState } from "./modules/state.js";
import { resolveLegal } from "./modules/api-legal.js";
import { createPlacePresenter, POI_CATS, POI_ORDER } from "./modules/place.js";
import { createSavedController } from "./modules/saved.js";
import { createWeatherController } from "./modules/weather.js";
import { createConnectivityController } from "./modules/connectivity.js";
import { createSearchController } from "./modules/search.js";
import { createMapController } from "./modules/map.js";

"use strict";
const state = createAppState();
const weather = createWeatherController();
const connectivity = createConnectivityController();
const place = createPlacePresenter({
  state,
  onLegalQuery: function (lat, lon, name) { selectPoint(lat, lon, name, true, true); }
});
const mapController = createMapController({
  state,
  poiCats: POI_CATS,
  poiOrder: POI_ORDER,
  onPointSelected: function (lat, lon, name, fly) { selectPoint(lat, lon, name, fly); },
  onPoiClick: function (p, lat, lon) {
    selectPoint(lat, lon, p.name, false);
    place.renderPoi(p);
  },
  onPaClick: function (p, lat, lon) {
    selectPoint(lat, lon, null, false);
    place.renderPa(p, lat, lon);
  }
});
const store = window.AlRasoStore;
const search = createSearchController({
  state,
  onSelectPoint: function (lat, lon, name, fly) { selectPoint(lat, lon, name, fly); },
  onRenderPoi: function (poi) { place.renderPoi(poi); }
});
const saved = createSavedController({
  store,
  state,
  onSelectPoint: function (lat, lon, name, fly) { selectPoint(lat, lon, name, fly); },
  showTab,
  onFeedback: function (message) { $("searchmsg").textContent = message; },
  onStatsDirty: function () { saved.updateStats(); }
});

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
  var mapHandle = mapController.handle();
  if (name === "explore" && mapHandle) {
    setTimeout(function () { mapHandle.resize(); }, 50);
  }

  // Update UI for specific views
  if (name === "saved") saved.renderFavorites();
  if (name === "outings") saved.renderOutings();
  if (name === "profile") saved.updateStats();
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
  return mapController.boot();
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
  if (handle) {
    handle.setAttribute("aria-expanded", next === "closed" ? "false" : "true");
    handle.setAttribute("aria-label", next === "full" ? "Recoger la ficha" : "Desplegar la ficha");
  }
  // MapLibre may need a resize pass after the layout settles (grey/misaligned canvas guard)
  var mapHandle = mapController.handle();
  if (mapHandle) setTimeout(function () { mapHandle.resize(); }, 60);
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
    var sheetPeekHeight = parseFloat(getComputedStyle(card).getPropertyValue("--sheet-peek-height")) || 440;
    var base = sheetState === "full" ? 0
      : sheetState === "peek" ? card.offsetHeight - sheetPeekHeight : card.offsetHeight - 44;
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
    var focusInsideSheet = document.activeElement && card.contains(document.activeElement);
    if (sheetState === "full") setSheetState("peek");
    else if (sheetState === "peek") setSheetState("closed");
    if (focusInsideSheet) handle.focus({ preventScroll: true });
  });
})();

// Search, suggestions and onboarding CTA: initialize before the remaining
// synchronous controls, matching the original end-of-body order.
search.init();

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
// SELECT POINT & FRESH RESOLVE
// ─────────────────────────────────────────────
function selectPoint(lat, lon, name, fly, preserveContext) {
  if (fly === undefined) fly = true;
  var map = mapController.handle();
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
    if (fly) {
      var camera = { center: ll, zoom: Math.max(map.getZoom(), 10) };
      if (isMobileLayout()) {
        var sheet = $("card");
        var peekHeight = sheet
          ? parseFloat(getComputedStyle(sheet).getPropertyValue("--sheet-peek-height"))
          : 0;
        if (Number.isFinite(peekHeight) && peekHeight > 0) {
          camera.padding = { top: 0, right: 0, bottom: peekHeight, left: 0 };
        }
      }
      map.flyTo(camera);
    }
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
    state.cartographicContext = null;
    var contextBox = $("place-context");
    if (contextBox) contextBox.hidden = true;
    var contextDisclosure = $("place-context-disclosure");
    if (contextDisclosure) contextDisclosure.hidden = true;
    var paLegalBtn = $("pa-legal-btn");
    if (paLegalBtn) {
      paLegalBtn.disabled = true;
      paLegalBtn.removeAttribute("data-lat");
      paLegalBtn.removeAttribute("data-lon");
    }
  }
  // The selected place is already the primary heading; avoid a redundant
  // map toast covering the mobile sheet. Error/save feedback still uses this
  // live region elsewhere.
  $("searchmsg").textContent = "";
  document.body.classList.toggle("has-selection", state.lat !== null);
  openSheetForSelection();
  weather.load(lat, lon);
  refresh();
}

// ─────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────
saved.initChooser();
// CENTER BUTTON (existing hook, now inside #detail-box)
// ─────────────────────────────────────────────
$("center-btn").addEventListener("click", function () {
  var map = mapController.handle();
  if (!map) return;
  var c = map.getCenter();
  selectPoint(c.lat, c.lng, null, false);
});

// ─────────────────────────────────────────────
// POI LEGAL CTA — reuse existing selectPoint/refresh (coordinates only)
// ─────────────────────────────────────────────
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

function resetLegalResultForPending() {
  $("card-empty").hidden = true;
  $("card-result").hidden = false;
  if (state.lat !== null && state.lon !== null) {
    var actLabel = ACT_LABELS[$("activity").value] || $("activity").value;
    var date = $("date").value || new Date().toISOString().slice(0, 10);
    $("coords").textContent = state.lat.toFixed(5) + ", " + state.lon.toFixed(5) + " · " + actLabel + " · " + date;
  }
  place.renderPlaceHeading();
  $("legal-emoji").textContent = "";
  $("headline").textContent = "Consultando…";
  $("answer-explanation").textContent = "Verificando la normativa para este punto.";
  $("legal-result").className = "legal-result legal-status--undetermined";
  $("legal-result").style.borderLeftColor = "#93a1b0";
  $("plain-conds").innerHTML = "";
  $("plain-conds").hidden = true;
  $("conditions-summary").hidden = true;
  $("condiciones").style.display = "none";
  $("decision").textContent = "Esperando una nueva determinación.";
  $("corpus-status").textContent = "";
  $("coverage-status").textContent = "";
  $("region-list").innerHTML = "";
  $("sources").innerHTML = "";
  $("tech-codes").innerHTML = "";
  $("warning").textContent = "";
  $("dem-info").hidden = true;
  $("dem-info").innerHTML = "";
  $("altitude-line").hidden = true;
  $("altitude-line").textContent = "";
  ["legal", "knowledge", "coverage"].forEach(function (id) {
    var badgeEl = $(id);
    badgeEl.textContent = "—";
    badgeEl.removeAttribute("data-code");
    badgeEl.className = "badge";
  });
}

function renderLegalResolveFailure() {
  resetLegalResultForPending();
  $("legal-emoji").textContent = "⚠️";
  $("headline").textContent = "No se pudo obtener la determinación";
  $("answer-explanation").textContent = "No se pudo obtener una nueva determinación. Inténtalo de nuevo.";
  $("decision").textContent = "No hay una determinación nueva para este punto.";
}

async function refresh() {
  saved.updateSaveButton();
  var p = new URLSearchParams({
    lat: state.lat, lon: state.lon,
    activity: $("activity").value,
    date: $("date").value || new Date().toISOString().slice(0, 10),
    knowledge: new Date().toISOString().slice(0, 10),
  });
  factsFromForm().forEach(function (kv) { var parts = kv.split("="); p.set(parts[0], parts.slice(1).join("=")); });
  resolveRequestId += 1;
  var myId = resolveRequestId;
  resetLegalResultForPending();
  try {
    var d = await resolveLegal(p);
    if (myId !== resolveRequestId) return; // stale response: discarded
    render(d);
  } catch (e) {
    if (myId !== resolveRequestId) return;
    console.error("resolve error", e);
    renderLegalResolveFailure();
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

const PRIMARY_LEGAL_LABELS = {
  PERMITTED: "Permitido",
  PROHIBITED: "Prohibido",
  AUTHORIZATION_REQUIRED: "Solo con autorización previa",
  UNDETERMINED: "No lo podemos determinar",
};

const CORPUS_STATUS_LABELS = {
  CURRENT: "vigente según los datos disponibles",
  INCOMPLETE: "incompleto según los datos disponibles",
  CONFLICTING: "con fuentes en conflicto",
};

function hasReason(d, code) {
  return ((d.determination && d.determination.reasonCodes) || []).indexOf(code) !== -1;
}

function primaryLegalLabel(d) {
  var legal = d.determination.legalStatus;
  return PRIMARY_LEGAL_LABELS[legal] || ((d.ui || {}).legal || legal);
}

function undeterminedExplanation(d) {
  var coverage = (d.coverage || {}).status;
  var notPermission = "Esto no significa que esté prohibido ni que esté permitido.";
  if (hasReason(d, "NO_PUBLISHABLE_RULE_COVERAGE")) {
    return "La zona está delimitada, pero falta una condición verificable para aplicar una regla concreta. " + notPermission;
  }
  if (hasReason(d, "NO_APPLICABLE_SCOPE")) {
    if (coverage === "PARTIAL") {
      return "Tenemos normativa de la zona, pero la comprobación espacial de este punto no está cerrada. " + notPermission;
    }
    if (coverage === "UNKNOWN") {
      return "No tenemos una zona normativa verificada para este punto. " + notPermission;
    }
  }
  if (coverage === "UNKNOWN") {
    return "Aún no tenemos normativa verificada para este punto. " + notPermission;
  }
  if (coverage === "PARTIAL") {
    return "La cobertura normativa de esta zona todavía no permite resolver este punto. " + notPermission;
  }
  return "Faltan datos para completar esta consulta. " + notPermission;
}

function answerExplanation(d) {
  var legal = d.determination.legalStatus;
  if (legal === "UNDETERMINED") {
    return undeterminedExplanation(d);
  }
  if (legal === "PERMITTED") return "La normativa verificada permite esta actividad.";
  if (legal === "PROHIBITED") return "La normativa verificada prohíbe esta actividad.";
  if (legal === "AUTHORIZATION_REQUIRED") return "Esta actividad requiere una autorización previa.";
  return "No podemos mostrar una conclusión para este estado.";
}

function corpusStatusText(d) {
  var knowledge = d.determination.knowledgeStatus;
  return "Estado del corpus consultado: " +
    (CORPUS_STATUS_LABELS[knowledge] || knowledge || "no disponible");
}

function coverageStatusText(d) {
  var coverage = (d.coverage || {}).status;
  if (coverage === "UNKNOWN") return "Cobertura normativa del punto: ninguna";
  if (coverage === "PARTIAL") return "Cobertura normativa del punto: parcial";
  if (coverage === "VERIFIED") return "Cobertura normativa del punto: geometría y norma verificadas";
  return "Cobertura normativa del punto: " + (coverage || "no disponible");
}

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
  if (hasReason(d, "NO_PUBLISHABLE_RULE_COVERAGE")) return "La zona está delimitada, pero falta una condición verificable para aplicar una regla concreta.";
  if (hasReason(d, "NO_APPLICABLE_SCOPE") && (d.coverage || {}).status === "PARTIAL") {
    return "Tenemos normativa de la zona, pero la comprobación espacial de este punto no está cerrada.";
  }
  if (hasReason(d, "NO_APPLICABLE_SCOPE") && (d.coverage || {}).status === "UNKNOWN") {
    return "No tenemos una zona normativa verificada para este punto.";
  }
  if ((d.coverage || {}).status === "UNKNOWN") return "Aún no tenemos normativa verificada para este punto.";
  if ((d.coverage || {}).status === "PARTIAL") return "La cobertura de esta zona todavía no permite resolver este punto.";
  return "Faltan datos en la consulta para completar la evaluación.";
}

function badge(el, value, plain) {
  el.textContent = plain;
  el.dataset.code = value;
  el.className = "badge " + (
    { PERMITTED: "ok", PROHIBITED: "bad", AUTHORIZATION_REQUIRED: "warn", UNDETERMINED: "unk",
      CURRENT: "ok", INCOMPLETE: "warn", CONFLICTING: "bad",
      VERIFIED: "ok", PARTIAL: "warn", UNKNOWN: "unk" }[value] || "unk");
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
  place.renderPlaceHeading();

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
  $("headline").textContent = primaryLegalLabel(d);
  $("answer-explanation").textContent = answerExplanation(d);
  var resultEl = $("legal-result");
  var statusClass = {
    PERMITTED: "permitted",
    PROHIBITED: "prohibited",
    AUTHORIZATION_REQUIRED: "authorization",
    UNDETERMINED: "undetermined",
  }[legalStatus] || "undetermined";
  resultEl.className = "legal-result legal-status--" + statusClass;
  resultEl.style.borderLeftColor = LEGAL_BORDER_COLOR[legalStatus] || "#999";

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

  var conditionsSummary = $("conditions-summary");
  if (conditionsSummary) conditionsSummary.hidden = !(legalStatus !== "UNDETERMINED" && conds.length > 0);
  place.renderPlaceContext(d);

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
  $("corpus-status").textContent = corpusStatusText(d);
  $("coverage-status").textContent = coverageStatusText(d);

  var zones = $("region-list");
  zones.innerHTML = "";
  if (!(d.coverage.regions || []).length) {
    zones.innerHTML = '<div class="region region-empty">Zona todavía no cubierta</div>';
  }
  (d.coverage.regions || []).forEach(function (r) {
    var div = document.createElement("div");
    div.className = "region";
    var norms = (r.norms || []).map(function (n) {
      return '<li>' + esc(n.title) + (n.canonical_url ? ' — <a target="_blank" rel="noopener" href="' + esc(n.canonical_url) + '">fuente</a>' : '') + (n.official_status ? ' <i>(' + esc(n.official_status) + ')</i>' : '') + '</li>';
    }).join("");
    var notes = (r.notes || []).map(function (n) { return '<li>' + esc(n) + '</li>'; }).join("");
    div.innerHTML =
      '<div class="rhead"><span>' + esc(r.name) + '</span><span class="chip ' + (r.coverage === "VERIFIED" ? "ok" : "warn") + '">' + (r.coverage === "VERIFIED" ? "verificada" : "parcial") + '</span></div>' +
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
  if (!(d.sources || []).length) src.innerHTML = "<li>No hay fuentes normativas vinculadas a este punto.</li>";

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

  badge($("legal"), d.determination.legalStatus, d.determination.legalStatus);
  badge($("knowledge"), d.determination.knowledgeStatus, d.determination.knowledgeStatus);
  badge($("coverage"), d.coverage.status, d.coverage.status);

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
saved.updateStats();
// BOOT
// ─────────────────────────────────────────────
void boot();

// ─────────────────────────────────────────────
// M5: PWA + OFFLINE RESILIENCE
// ─────────────────────────────────────────────
connectivity.init();
