import { $ } from "./dom.js";
import { fetchCoverage } from "./api-legal.js";
import { fetchPois, fetchProtectedAreas } from "./api-cartography.js";

const FALLBACK_STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
const PA_FILL_COLOR = "#0d9488";

export function validPaPosition(position) {
  return Array.isArray(position) && position.length >= 2 &&
    Number.isFinite(position[0]) && Number.isFinite(position[1]) &&
    position[0] >= -180 && position[0] <= 180 &&
    position[1] >= -90 && position[1] <= 90;
}

export function validPaRing(ring) {
  return Array.isArray(ring) && ring.length >= 4 && ring.every(validPaPosition) &&
    ring[0][0] === ring[ring.length - 1][0] &&
    ring[0][1] === ring[ring.length - 1][1];
}

export function validPaGeometry(geometry) {
  if (!geometry || (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon")) return false;
  if (geometry.type === "Polygon") return Array.isArray(geometry.coordinates) && geometry.coordinates.length > 0 && geometry.coordinates.every(validPaRing);
  return Array.isArray(geometry.coordinates) && geometry.coordinates.length > 0 && geometry.coordinates.every(
    (polygon) => Array.isArray(polygon) && polygon.length > 0 && polygon.every(validPaRing));
}

export function validPaFeatureCollection(fc) {
  return !!fc && fc.type === "FeatureCollection" && Array.isArray(fc.features) &&
    fc.features.every((feature) => feature && feature.type === "Feature" && validPaGeometry(feature.geometry));
}

export function createMapController({
  state,
  poiCats = {},
  poiOrder = [],
  onPointSelected,
  onPoiClick,
  onPaClick
}) {
  var map = null;
  var poiClickGuard = 0;

  function makePoiIconDataUrl(cat) {
    var c = poiCats[cat];
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
    try { fc = await fetchPois(); }
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

    await Promise.all(poiOrder.map(function (cat) {
      return loadPoiIcon(cat).then(function (ok) { if (ok) loadedIcons[cat] = true; });
    }));

    poiOrder.forEach(function (cat) {
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
        map.on("click", "poi-icons-" + cat, function (e) { handlePoiClick(e); });
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

  async function loadProtectedAreas() {
    var fc;
    try { fc = await fetchProtectedAreas(); }
    catch (e) { console.error("protected-areas", e); return; }
    // A failed or malformed geometry is a missing context layer, never a reason
    // to invent a polygon or let MapLibre break the rest of the map.
    if (!validPaFeatureCollection(fc)) {
      console.warn("protected-areas: invalid geometry payload; layer skipped");
      return;
    }
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
    map.on("click", "pa-fill", function (e) { handlePaClick(e); });
    map.on("click", "pa-line", function (e) { handlePaClick(e); });
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

  function handlePoiClick(e) {
    const f = e.features && e.features[0];
    if (!f) return;
    const p = f.properties;
    poiClickGuard = Date.now();
    onPoiClick(p, f.geometry.coordinates[1], f.geometry.coordinates[0]);
  }

  function handlePaClick(e) {
    const f = e.features && e.features[0];
    if (!f) return;
    const p = f.properties;
    poiClickGuard = Date.now();
    // Use the exact clicked coordinates for the CTA (coords-only invariant).
    onPaClick(p, e.lngLat.lat, e.lngLat.lng);
  }

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
        const fc = await fetchCoverage();
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
      onPointSelected(e.lngLat.lat, e.lngLat.lng, null, false);
    });
  }

  function handle() {
    return map;
  }

  return { boot, handle };
}
