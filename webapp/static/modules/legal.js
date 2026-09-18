import { $, esc } from "./dom.js";
import { resolveLegal } from "./api-legal.js";

const FACT_LABELS = {
  refuge_capacity_full: "el refugio está sin capacidad",
  nights: "número de noches",
  noches: "número de noches",
  cota_m: "altitud (m)",
  actividad_montana_o_escalada: "actividad de montaña o escalada",
  activity_date: "la fecha de la actividad",
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
  date_in_range: function (l, v) { return l + " ∈ [" + v[0] + "…" + v[1] + "]"; },
};
export function conditionText(c) {
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
  CONDITIONAL: "Permitido solo con condiciones",
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

export function primaryLegalLabel(d) {
  var legal = d.determination.legalStatus;
  return PRIMARY_LEGAL_LABELS[legal] || ((d.ui || {}).legal || legal);
}

export function undeterminedExplanation(d) {
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

export function answerExplanation(d) {
  var legal = d.determination.legalStatus;
  if (legal === "UNDETERMINED") {
    return undeterminedExplanation(d);
  }
  if (legal === "PERMITTED") return "La normativa verificada permite esta actividad.";
  if (legal === "CONDITIONAL") return "La normativa permite esta actividad solo si se cumplen unas condiciones que no podemos comprobar automáticamente. No es un sí directo.";
  if (legal === "PROHIBITED") return "La normativa verificada prohíbe esta actividad.";
  if (legal === "AUTHORIZATION_REQUIRED") return "Esta actividad requiere una autorización previa.";
  return "No podemos mostrar una conclusión para este estado.";
}

export function corpusStatusText(d) {
  var knowledge = d.determination.knowledgeStatus;
  return "Estado del corpus consultado: " +
    (CORPUS_STATUS_LABELS[knowledge] || knowledge || "no disponible");
}

export function coverageStatusText(d) {
  var coverage = (d.coverage || {}).status;
  if (coverage === "UNKNOWN") return "Cobertura normativa del punto: ninguna";
  if (coverage === "PARTIAL") return "Cobertura normativa del punto: parcial";
  if (coverage === "VERIFIED") return "Cobertura normativa del punto: geometría y norma verificadas";
  return "Cobertura normativa del punto: " + (coverage || "no disponible");
}

export function whyText(d) {
  var legal = d.determination.legalStatus;
  var act = ACT_LABELS[d.query.activity] || d.query.activity;
  var scope = (d.applicableScope || [])[0];
  var zone = scope ? ' en «' + scope.official_name + '»' : '';
  if (legal === "PERMITTED")
    return 'La normativa verificada permite ' + act + zone +
      ((d.conditions || []).length ? ", siempre que se cumplan las condiciones indicadas." : ".");
  if (legal === "CONDITIONAL")
    return 'La normativa permite ' + act + zone +
      ', pero hay condiciones pendientes que no podemos comprobar.';
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


// Emoji mapping per legalStatus (never color-only)
export const LEGAL_EMOJI = {
  PERMITTED: "✅",
  CONDITIONAL: "🟡",
  PROHIBITED: "⛔",
  AUTHORIZATION_REQUIRED: "🟠",
  UNDETERMINED: "⚠️",
};

export const LEGAL_BORDER_COLOR = {
  PERMITTED: "#22c55e",
  CONDITIONAL: "#eab308",
  PROHIBITED: "#ef4444",
  AUTHORIZATION_REQUIRED: "#f59e0b",
  UNDETERMINED: "#93a1b0",
};



export function createLegalController({
  state,
  form,
  onSaveButtonState = function () {},
  onPlaceContext = function () {}
}) {
  function factsFromForm() {
    var out = [];
    form.factbox.querySelectorAll("input").forEach(function (el) {
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
      var actLabel = ACT_LABELS[form.activity.value] || form.activity.value;
      var date = form.date.value || new Date().toISOString().slice(0, 10);
      $("coords").textContent = state.lat.toFixed(5) + ", " + state.lon.toFixed(5) + " · " + actLabel + " · " + date;
    }
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
    onSaveButtonState();
    var p = new URLSearchParams({
      lat: state.lat, lon: state.lon,
      activity: form.activity.value,
      date: form.date.value || new Date().toISOString().slice(0, 10),
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
      onPlaceContext(d);
      return d;
    } catch (e) {
      if (myId !== resolveRequestId) return;
      console.error("resolve error", e);
      renderLegalResolveFailure();
      form.searchMessage.textContent = "No se pudo obtener la determinación. Inténtalo de nuevo.";
    }
  }

  function badge(el, value, plain) {
    el.textContent = plain;
    el.dataset.code = value;
    el.className = "badge " + (
      { PERMITTED: "ok", CONDITIONAL: "warn", PROHIBITED: "bad", AUTHORIZATION_REQUIRED: "warn", UNDETERMINED: "unk",
        CURRENT: "ok", INCOMPLETE: "warn", CONFLICTING: "bad",
        VERIFIED: "ok", PARTIAL: "warn", UNKNOWN: "unk" }[value] || "unk");
  }

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
    $("headline").textContent = primaryLegalLabel(d);
    $("answer-explanation").textContent = answerExplanation(d);
    var resultEl = $("legal-result");
    var statusClass = {
      PERMITTED: "permitted",
      CONDITIONAL: "conditional",
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
        label.innerHTML = '<input type="checkbox" name="' + esc(f) + '"> ' + esc(spec.label);
        box.appendChild(label);
      } else {
        var label = document.createElement("label");
        label.innerHTML = esc(spec.label) + ' <input type="number" name="' + esc(f) + '" min="0" style="width:80px">';
        if (spec.note) {
          var note = document.createElement("span");
          note.className = "fact-note";
          note.textContent = spec.note;
          label.appendChild(note);
        }
        box.appendChild(label);
      }
      var el = box.querySelector('[name="' + CSS.escape(f) + '"]');
      el.addEventListener("change", function () { if (state.lat !== null) refresh(); });
    });
  }

  // ─────────────────────────────────────────────

  return {
    refresh,
    resetLegalResultForPending,
    renderLegalResolveFailure,
    render
  };
}
