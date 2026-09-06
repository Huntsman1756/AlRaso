"use strict";
const $ = (id) => document.getElementById(id);
const state = { lat: null, lon: null, marker: null };
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
      // Reencuadre al contenido útil (Ordesa + Picos) sin dejar el centro en el mar.
      map.fitBounds([[-5.35, 42.45], [0.25, 43.4]], { padding: 30 });
    } catch (e) { console.error(e); }
  });

  map.on("click", (e) => {
    if (Date.now() - poiClickGuard < 150) return; // ya lo ha manejado una capa POI
    selectPoint(e.lngLat.lat, e.lngLat.lng, null, false);
  });
}

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
        minzoom: 9,  // las etiquetas aparecen al acercarse; los puntos siguen visibles antes
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
}

void boot();

function selectPoint(lat, lon, name, fly = true) {
  state.lat = lat;
  state.lon = lon;
  if (map) {
    const ll = [lon, lat];
    if (!state.marker) {
      state.marker = new maplibregl.Marker({ color: "#e11d48" }).setLngLat(ll).addTo(map);
    } else {
      state.marker.setLngLat(ll);
    }
    if (fly) map.flyTo({ center: ll, zoom: Math.max(map.getZoom(), 10) });
  }
  if (!name) $("poi").hidden = true;
  $("searchmsg").textContent = name ? `Zona seleccionada: ${name}` : "";
  refresh();
}

$("date").valueAsDate = new Date();
["activity", "date"].forEach((id) => $(id).addEventListener("change", () => state.lat !== null && refresh()));

$("center-btn").addEventListener("click", () => {
  if (!map) return;
  const c = map.getCenter();
  selectPoint(c.lat, c.lng, null, false);
});

(async () => {
  try {
    const { places } = await (await fetch("/api/places")).json();
    const dl = $("places-list");
    dl.innerHTML = "";
    places.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.name;
      opt.label = p.note || p.name;
      dl.appendChild(opt);
    });
  } catch (e) { console.error(e); }
})();

$("searchform").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const q = $("q").value.trim();
  if (!q) return;
  let f;
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
    // Solo cartografia OSM: mueve el mapa y muestra la tarjeta POI. Nunca
    // suministra hechos al resolver.
    selectPoint(f.lat, f.lon, f.name, true);
    renderPoi(f);
  } else if (f.kind === "ambiguous") {
    $("searchmsg").textContent = "Varias zonas coinciden: " +
      f.matches.map((m) => m.name).join(" · ") + ". Concreta la búsqueda.";
  } else {
    $("searchmsg").textContent =
      "Sin coincidencias. Escribe coordenadas «lat, lon» (ej. 42.6627, 0.0160) " +
      "o elige una zona conocida de la lista.";
  }
});

function factsFromForm() {
  const out = [];
  document.querySelectorAll("#factbox input").forEach((el) => {
    if (el.type === "checkbox") { if (el.checked) out.push(`${el.name}=true`); }
    else if (el.value !== "") out.push(`${el.name}=${el.value}`);
  });
  return out;
}

async function refresh() {
  const p = new URLSearchParams({
    lat: state.lat, lon: state.lon,
    activity: $("activity").value,
    date: $("date").value || new Date().toISOString().slice(0, 10),
    knowledge: new Date().toISOString().slice(0, 10),
  });
  factsFromForm().forEach((kv) => { const [k, v] = kv.split("="); p.set(k, v); });
  const r = await fetch("/api/resolve?" + p.toString());
  render(await r.json());
}

const FACT_LABELS = {
  refuge_capacity_full: "el refugio está sin capacidad",
  nights: "número de noches",
  noches: "número de noches",
  cota_m: "altitud (m)",
  actividad_montana_o_escalada: "actividad montana o escalada",
};
const OP_TEXT = {
  is_true: (l) => l,
  is_false: (l) => `${l} (no)`,
  lte: (l, v) => `${l} ≤ ${v}`,
  gte: (l, v) => `${l} ≥ ${v}`,
  lt: (l, v) => `${l} < ${v}`,
  gt: (l, v) => `${l} > ${v}`,
  eq: (l, v) => `${l} = ${v}`,
};
function conditionText(c) {
  const parts = ((c && c.ast && c.ast.all) || []).map((x) => {
    const label = FACT_LABELS[x.field] || x.field;
    const fn = OP_TEXT[x.op];
    if (fn) return fn(label, x.value);
    return x.value === undefined ? `${label}: ${x.op}` : `${label} ${x.op} ${x.value}`;
  });
  const body = parts.join(" y ");
  if (c && c.holds === false) return `No se cumple: ${body || "—"}.`;
  return `Se cumplen las condiciones: ${body || "—"}.`;
}

const ACT_LABELS = {
  VIVAC_AL_RASO: "dormir al raso (vivac)",
  FUNDA_VIVAC: "pernoctar con funda vivac",
  TIENDA_NOCTURNA: "usar tienda de campaña nocturna",
  ACAMPADA: "acampar",
  PERNOCTA_REFUGIO: "pernoctar en refugio",
};
function whyText(d) {
  const legal = d.determination.legalStatus;
  const act = ACT_LABELS[d.query.activity] || d.query.activity;
  const scope = (d.applicableScope || [])[0];
  const zone = scope ? ` en «${scope.official_name}»` : "";
  if (legal === "PERMITTED")
    return `La normativa verificada permite ${act}${zone} en la fecha consultada` +
      ((d.conditions || []).length ? ", siempre que se cumplan las condiciones indicadas." : ".");
  if (legal === "PROHIBITED") return `La normativa verificada prohíbe ${act}${zone}.`;
  if (legal === "AUTHORIZATION_REQUIRED") return `Para ${act}${zone} hace falta una autorización previa según la normativa verificada.`;
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
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function render(d) {
  $("card-empty").hidden = true;
  $("card-result").hidden = false;
  const ui = d.ui || {};
  $("coords").textContent = `${state.lat.toFixed(5)}, ${state.lon.toFixed(5)} · ${d.query.activity} · ${d.query.activity_date}`;
  $("headline").textContent = ui.headline || d.determination.legalStatus;
  badge($("legal"), d.determination.legalStatus, ui.legal || d.determination.legalStatus);
  badge($("knowledge"), d.determination.knowledgeStatus, ui.knowledge || d.determination.knowledgeStatus);
  badge($("coverage"), d.coverage.status, ui.coverage || d.coverage.status);

  renderFacts(d);

  const cl = $("cond-list");
  cl.innerHTML = "";
  (d.conditions || []).forEach((c) => {
    const li = document.createElement("li");
    li.textContent = conditionText(c);
    cl.appendChild(li);
  });
  $("condiciones").style.display = (d.conditions || []).length ? "" : "none";

  $("decision").textContent = whyText(d);

  const zones = $("region-list");
  zones.innerHTML = "";
  if (!(d.coverage.regions || []).length) {
    zones.innerHTML = '<div class="region">Ninguna región cubierta contiene este punto.<br><span class="meta">AlRaso no tiene corpus aquí y por eso no puede afirmar nada: ni permiso ni prohibición.</span></div>';
  }
  (d.coverage.regions || []).forEach((r) => {
    const div = document.createElement("div");
    div.className = "region";
    const norms = (r.norms || []).map((n) =>
      `<li>${esc(n.title)}${n.canonical_url ? ` — <a target="_blank" rel="noopener" href="${esc(n.canonical_url)}">fuente</a>` : ""}${n.official_status ? ` <i>(${esc(n.official_status)})</i>` : ""}</li>`).join("");
    const notes = (r.notes || []).map((n) => `<li>${esc(n)}</li>`).join("");
    div.innerHTML = `
      <div class="rhead"><span>${esc(r.name)}</span><span class="chip ${r.coverage === "VERIFIED" ? "ok" : "warn"}">${r.coverage === "VERIFIED" ? "completa" : "parcial"}</span></div>
      <div class="meta">verificado ${esc(r.verified_at)} · límite ${r.boundary === "oficial" ? "OFICIAL (geometría del motor)" : "ESQUEMÁTICO (informativo, sin valor legal)"}</div>
      <p>${esc(r.summary)}</p>
      <details><summary>normas y fuentes de la zona</summary><ul>${norms}</ul>${notes ? `<ul>${notes}</ul>` : ""}</details>`;
    zones.appendChild(div);
  });

  const src = $("sources");
  src.innerHTML = "";
  (d.sources || []).forEach((s) => {
    const li = document.createElement("li");
    li.innerHTML = `${esc(s.title)}${s.canonical_url ? ` — <a target="_blank" rel="noopener" href="${esc(s.canonical_url)}">documento</a>` : ""}${s.official_status ? ` <i>(${esc(s.official_status)})</i>` : ""}`;
    src.appendChild(li);
  });
  if (!(d.sources || []).length) src.innerHTML = "<li>Sin fuentes: ninguna norma verificada cubre este punto. Eso no es una prohibición.</li>";

  const tech = $("tech-codes");
  tech.innerHTML = "";
  const codes = [
    `legalStatus=${d.determination.legalStatus}`,
    `knowledgeStatus=${d.determination.knowledgeStatus}`,
    `coverage=${d.coverage.status}`,
    `decisionReason=${d.determination.decisionReason || "—"}`,
    ...(d.determination.reasonCodes || []),
    ...(d.conditions || []).map((c) => `condition=${JSON.stringify(c)}`),
  ];
  codes.forEach((rc) => {
    const li = document.createElement("li");
    li.textContent = rc;
    tech.appendChild(li);
  });

  $("warning").textContent = (d.determination.warnings || [])[0] || "";
}

function renderFacts(d) {
  const box = $("factbox");
  const had = new Set([...box.querySelectorAll("[name]")].map((el) => el.name));
  const wanted = new Map();
  (d.conditions || []).forEach((c) => {
    if (c && c.field) wanted.set(c.field, c);
  });
  ["refuge_capacity_full", "nights"].forEach((f) => wanted.set(f, { field: f }));
  [...wanted.keys()].forEach((f) => {
    if (had.has(f)) return;
    if (f === "refuge_capacity_full") {
      const label = document.createElement("label");
      label.innerHTML = `<input type="checkbox" name="${f}"> el refugio está sin capacidad`;
      box.appendChild(label);
    } else {
      const label = document.createElement("label");
      label.innerHTML = `número de noches <input type="number" name="${f}" min="1" max="30" value="1" style="width:70px">`;
      box.appendChild(label);
    }
    const el = box.querySelector(`[name="${f}"]`);
    el.addEventListener("change", () => state.lat !== null && refresh());
  });
}
