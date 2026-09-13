import { $, esc } from "./dom.js";

export const POI_CATS = {
  refuge: { emoji: "🏠", label: "Refugio", anonymousLabel: "Refugio", color: "#b45309" },
  shelter: { emoji: "🛖", label: "Abrigo / cabaña", anonymousLabel: "Abrigo", color: "#f97316" },
  water: { emoji: "💧", label: "Agua", anonymousLabel: "Agua", color: "#0ea5e9" },
  camping: { emoji: "⛺", label: "Camping / bivouac", anonymousLabel: "Camping", color: "#16a34a" },
  protected_area: { emoji: "🌲", label: "Referencia OSM: espacio natural protegido", color: "#0d9488" },
};
// protected_area queda en el snapshot (provenance) pero NO se renderiza ni es
// interactivo: un centroide de relación de parque no es un destino del usuario.
export const POI_ORDER = ["refuge", "shelter", "water", "camping"];

export function normalizePlaceContext(candidate) {
  if (!candidate) return null;
  var raw = candidate.properties || candidate;
  if (typeof raw === "string") return { kind: "Espacio protegido", name: raw };
  var name = raw.name || raw.official_name || raw.label || raw.title;
  if (!name) return null;
  var category = String(raw.category || raw.kind || raw.context_type || "").toLowerCase();
  var kind = category.indexOf("protected") !== -1 || category.indexOf("proteg") !== -1
    ? "Espacio protegido"
    : (raw.kind_label || raw.context_label || "Contexto cartográfico");
  return {
    kind: kind,
    name: name,
    note: raw.note || raw.disclaimer || "Información cartográfica; no determina la legalidad.",
  };
}

export function createPlacePresenter({ state, onLegalQuery = function () {} }) {
  function bindLegalButton(id, lat, lon) {
    var button = $(id);
    if (!button) return;
    button.disabled = false;
    if (Number.isFinite(Number(lat)) && Number.isFinite(Number(lon))) {
      button.setAttribute("data-lat", String(lat));
      button.setAttribute("data-lon", String(lon));
    }
    button.onclick = function () {
      var buttonLat = parseFloat(button.getAttribute("data-lat"));
      var buttonLon = parseFloat(button.getAttribute("data-lon"));
      if (isNaN(buttonLat) || isNaN(buttonLon)) return;
      onLegalQuery(buttonLat, buttonLon, id === "poi-legal-btn" ? state.selectedName : null);
    };
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
    bindLegalButton("poi-legal-btn", p.lat, p.lon);

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
    state.cartographicContext = null;
    renderPlaceHeading();
    renderPlaceContext({});
  }

  function renderPa(p, lat, lon) {
    $("poi").hidden = true;
    $("pa-card").hidden = false;
    $("pa-name").textContent = p.name || "";
    var metaParts = [];
    if (p.region) metaParts.push(p.region);
    metaParts.push("referencia OSM · no ámbito legal");
    $("pa-meta").textContent = metaParts.join(" · ");
    $("pa-note").textContent = p.note || "";
    bindLegalButton("pa-legal-btn", lat === undefined ? p.lat : lat, lon === undefined ? p.lon : lon);

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
    state.cartographicContext = {
      kind: "Espacio protegido",
      name: p.name || "Espacio protegido",
      note: "Información cartográfica; no determina la legalidad.",
    };
    renderPlaceHeading();
    renderPlaceContext({});
  }

  function renderPlaceContext(d) {
    var box = $("place-context");
    if (!box) return;
    var disclosure = $("place-context-disclosure");
    var data = d || {};
    var raw = data.cartographicContext || data.cartographic_context || data.placeContext ||
      data.place_context || data.protectedArea || data.protected_area ||
      ((data.coverage || {}).context) || state.cartographicContext;
    var context = normalizePlaceContext(Array.isArray(raw) ? raw[0] : raw);
    if (!context) {
      box.hidden = true;
      if (disclosure) disclosure.hidden = true;
      $("place-context-value").textContent = "";
      $("place-context-note").textContent = "";
      return;
    }
    box.hidden = false;
    if (disclosure) disclosure.hidden = false;
    $("place-context-kind").textContent = context.kind;
    $("place-context-value").textContent = context.name;
    $("place-context-note").textContent = context.note;
  }

  function renderPlaceHeading() {
    var heading = $("place-heading");
    if (!heading) return;
    var hasCartographicCard =
      ($("poi") && !$("poi").hidden) || ($("pa-card") && !$("pa-card").hidden);
    if (hasCartographicCard) {
      heading.hidden = true;
      heading.textContent = "";
      return;
    }
    heading.textContent = state.selectedName || "Punto seleccionado";
    heading.hidden = false;
  }

  return { renderPoi, renderPa, renderPlaceHeading, renderPlaceContext };
}
