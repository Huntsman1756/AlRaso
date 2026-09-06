"use strict";
const $ = (id) => document.getElementById(id);
const state = { lat: null, lon: null, marker: null };

const style = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

const map = new maplibregl.Map({
  container: "map",
  style,
  center: [-1.6, 42.95],
  zoom: 6.6,
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
    map.addLayer({
      id: "cov-line", type: "line", source: "coverage",
      paint: {
        "line-color": ["match", ["get", "coverage"], "VERIFIED", "#22c55e", "PARTIAL", "#f59e0b", "#94a3b8"],
        "line-width": 1.4,
        "line-dasharray": ["case", ["==", ["get", "boundary"], "esquematico"], ["literal", [3, 3]], ["literal", [1]]],
      },
    });
    map.fitBounds([[-5.3, 42.55], [0.3, 43.45]], { padding: 30 });
  } catch (e) { console.error(e); }
});

map.on("click", (e) => {
  state.lat = e.lngLat.lat;
  state.lon = e.lngLat.lng;
  if (!state.marker) {
    state.marker = new maplibregl.Marker({ color: "#e11d48" }).setLngLat(e.lngLat).addTo(map);
  } else {
    state.marker.setLngLat(e.lngLat);
  }
  refresh();
});

$("date").valueAsDate = new Date();
["activity", "date"].forEach((id) => $(id).addEventListener("change", () => state.lat !== null && refresh()));

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

function badge(el, value) {
  el.textContent = value;
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
  $("coords").textContent = `${state.lat.toFixed(5)}, ${state.lon.toFixed(5)} · ${d.query.activity} · ${d.query.activity_date}`;
  badge($("legal"), d.determination.legalStatus);
  badge($("knowledge"), d.determination.knowledgeStatus);
  badge($("coverage"), d.coverage.status);

  renderFacts(d);

  const cl = $("cond-list");
  cl.innerHTML = "";
  (d.conditions || []).forEach((c) => {
    const li = document.createElement("li");
    li.textContent = JSON.stringify(c);
    cl.appendChild(li);
  });
  $("condiciones").style.display = (d.conditions || []).length ? "" : "none";

  $("decision").textContent = d.determination.decisionReason || "—";
  const rl = $("reasons");
  rl.innerHTML = "";
  (d.determination.reasonCodes || []).forEach((rc) => {
    const li = document.createElement("li");
    li.textContent = rc;
    rl.appendChild(li);
  });

  const zones = $("region-list");
  zones.innerHTML = "";
  if (!(d.coverage.regions || []).length) {
    zones.innerHTML = '<div class="region">Ninguna región cubierta contiene este punto.<br><span class="meta">coverage=UNKNOWN: AlRaso no tiene corpus aquí y por eso la determinación legal es UNDETERMINED (nunca un permiso por ausencia).</span></div>';
  }
  (d.coverage.regions || []).forEach((r) => {
    const div = document.createElement("div");
    div.className = "region";
    const norms = (r.norms || []).map((n) =>
      `<li>${esc(n.title)}${n.canonical_url ? ` — <a target="_blank" rel="noopener" href="${esc(n.canonical_url)}">fuente</a>` : ""}${n.official_status ? ` <i>(${esc(n.official_status)})</i>` : ""}</li>`).join("");
    const notes = (r.notes || []).map((n) => `<li>${esc(n)}</li>`).join("");
    div.innerHTML = `
      <div class="rhead"><span>${esc(r.name)}</span><span class="chip ${r.coverage === "VERIFIED" ? "ok" : "warn"}">${r.coverage}</span></div>
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
  if (!(d.sources || []).length) src.innerHTML = "<li>Sin fuentes: la resolución no llegó a materializarse en norma publicable (fail-closed).</li>";

  $("warning").textContent = (d.determination.warnings || [])[0] || "";
}

function renderFacts(d) {
  const box = $("factbox");
  const had = new Set([...box.querySelectorAll("[name]")].map((el) => el.name));
  const wanted = new Map();
  (d.conditions || []).forEach((c) => {
    if (c && c.field) wanted.set(c.field, c);
  });
  (d.applicableScope || []).forEach(() => {});
  // hechos típicos del corpus vigente para que el usuario pueda jugar con ellos
  ["refuge_capacity_full", "nights"].forEach((f) => wanted.set(f, { field: f }));
  [...wanted.keys()].forEach((f) => {
    if (had.has(f)) return;
    if (f === "refuge_capacity_full") {
      const label = document.createElement("label");
      label.innerHTML = `<input type="checkbox" name="${f}"> refugio sin capacidad`;
      box.appendChild(label);
    } else {
      const label = document.createElement("label");
      label.innerHTML = `${f} <input type="number" name="${f}" min="1" max="30" value="1" style="width:70px">`;
      box.appendChild(label);
    }
    const el = box.querySelector(`[name="${f}"]`);
    el.addEventListener("change", () => state.lat !== null && refresh());
  });
}
