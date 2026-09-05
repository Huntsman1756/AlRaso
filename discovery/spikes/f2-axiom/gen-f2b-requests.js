// F2.1B — request generator for fast and explain runs against ruleset_N.
const N = parseInt(process.argv[2], 10);
const fs = require("fs");
// outputs: last 10 rules of the generated ruleset (durable ids)
const idx = [];
for (let i = N - 10; i < N; i++) idx.push(String(i).padStart(5, "0"));
const OUT = idx.map(r => `es:policies/vivac/ruleset-bench-${N}#rule_${r}`);
function fact(name, kind, value) {
  return { name: `es:policies/vivac/ruleset-bench-${N}#input.${name}`, entity: "Location", entity_id: "loc:p1",
    interval: { start: "2023-07-15", end: "2023-07-16" }, value: { kind, value } };
}
const inputs = [
  fact("activity_name", "text", "VIVAC_AL_RASO"),
  fact("inside_park", "bool", true),
  fact("inside_zona_servicios", "bool", false),
  fact("altitude_m", "decimal", "1742"),
  fact("party_size", "integer", 2),
];
const q = { entity_id: "loc:p1", period: { period_kind: "custom", name: "day", start: "2023-07-15", end: "2023-07-16" }, outputs: OUT };
for (const mode of ["fast", "explain"]) {
  fs.writeFileSync(`/work/f2/req_${mode}_${N}.json`, JSON.stringify({ mode, dataset: { inputs }, queries: [q] }, null, 1));
}
console.log(`requests for N=${N} written`);
