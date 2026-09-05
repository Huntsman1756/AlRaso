// F2.1A request generator — 6 probes over the closed activity vocabulary.
const P = "es:policies/vivac/activity-spike";
const OUT = ["resolucion_unica", "caso_permitida", "caso_autorizacion", "caso_prohibida", "modalidad_conocida"].map(n => `${P}#${n}`);

function fact(name, kind, value, start, end) {
  return { name: `${P}#input.${name}`, entity: "Location", entity_id: "loc:p1",
    interval: { start, end }, value: { kind, value } };
}
function req({ facts, omit = [] } = {}) {
  const base = [
    fact("activity_name", "text", "VIVAC_AL_RASO", "2023-07-15", "2023-07-16"),
    fact("inside_park", "bool", true, "2023-07-15", "2023-07-16"),
    fact("inside_refugio_zone", "bool", false, "2023-07-15", "2023-07-16"),
    fact("inside_zona_servicios", "bool", false, "2023-07-15", "2023-07-16"),
    fact("altitude_m", "decimal", "1850", "2023-07-15", "2023-07-16"),
  ].filter(f => !omit.includes(f.name.split("#input.")[1]));
  const inputs = facts ? base.map(f => { const k = f.name.split("#input.")[1]; return facts[k] ? { ...f, value: { kind: facts[k].kind, value: facts[k].value } } : f; }) : base;
  return { mode: "explain", dataset: { inputs },
    queries: [{ entity_id: "loc:p1", period: { period_kind: "custom", name: "day", start: "2023-07-15", end: "2023-07-16" }, outputs: OUT }] };
}

const cases = {
  a1_known_activity: req({}),
  a2_unknown_activity: req({ facts: { activity_name: { kind: "text", value: "CAMPING_LIBRE" } } }),
  a3_lowercase_unmatched: req({ facts: { activity_name: { kind: "text", value: "vivac_al_raso" } } }),
  a4_missing_activity_input: req({ omit: ["activity_name"] }),
  a5_refuge_activity: req({ facts: { activity_name: { kind: "text", value: "PERNOCTA_REFUGIO" }, inside_refugio_zone: { kind: "bool", value: true } } }),
  a6_tent_activity: req({ facts: { activity_name: { kind: "text", value: "TIENDA_NOCTURNA" }, altitude_m: { kind: "decimal", value: "1850" } } }),
};
const fs = require("fs");
for (const [name, r] of Object.entries(cases)) fs.writeFileSync(`/work/f2/f2a-${name}.json`, JSON.stringify(r, null, 1));
console.log("wrote", Object.keys(cases).length, "F2.1A requests");
