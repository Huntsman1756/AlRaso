import { $ } from "./modules/dom.js";
import { createAppState } from "./modules/state.js";
import { createLegalController } from "./modules/legal.js";
import { createPlacePresenter, POI_CATS, POI_ORDER } from "./modules/place.js";
import { createSavedController } from "./modules/saved.js";
import { createWeatherController } from "./modules/weather.js";
import { createConnectivityController } from "./modules/connectivity.js";
import { createSearchController } from "./modules/search.js";
import { createMapController } from "./modules/map.js";
import { createSheetController } from "./modules/sheet.js";

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
const legal = createLegalController({
  state,
  form: {
    activity: $("activity"),
    date: $("date"),
    factbox: $("factbox"),
    searchMessage: $("searchmsg")
  },
  onSaveButtonState: function () { saved.updateSaveButton(); },
  onPlaceContext: function (d) { place.renderPlaceContext(d); }
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
// BOTTOM SHEET (R2, mobile <=820px) — the controller owns state, pointer input,
// Escape arbitration and accessibility attributes. Map resize is injected.
const sheet = createSheetController({
  onLayoutChange: function () {
    var mapHandle = mapController.handle();
    if (mapHandle) setTimeout(function () { mapHandle.resize(); }, 60);
  }
});

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
      if (window.matchMedia("(max-width: 820px)").matches) {
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
  place.renderPlaceHeading();
  // The selected place is already the primary heading; avoid a redundant
  // map toast covering the mobile sheet. Error/save feedback still uses this
  // live region elsewhere.
  $("searchmsg").textContent = "";
  document.body.classList.toggle("has-selection", state.lat !== null);
  sheet.openSheetForSelection();
  weather.load(lat, lon);
  legal.refresh();
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

// FRESH RESOLVE (api/resolve)
// ─────────────────────────────────────────────
$("date").valueAsDate = new Date();
["activity", "date"].forEach(function (id) {
  $(id).addEventListener("change", function () {
    if (state.lat !== null) legal.refresh();
  });
});

// ─────────────────────────────────────────────
// RENDER — full card restructure
// ─────────────────────────────────────────────
saved.updateStats();
// BOOT
// ─────────────────────────────────────────────
void boot();

// ─────────────────────────────────────────────
// M5: PWA + OFFLINE RESILIENCE
// ─────────────────────────────────────────────
connectivity.init();
