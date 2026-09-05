// F2.1B — synthetic ruleset generator v2: N condition-equivalent rules.
// Shape learned from engine limits: match stays scalar (Integer flag per
// modality), the condition-equivalent rule is a Judgment referencing the flag
// with `== 1` plus comparisons — mirrors our domain shape.
const fs = require("fs");
const N = parseInt(process.argv[2], 10);
const modalities = ["VIVAC_AL_RASO", "FUNDA_VIVAC", "TIENDA_NOCTURNA", "TARP", "ACAMPADA", "PERNOCTA_REFUGIO", "VEHICULO"];

let rules = [];
rules.push(`  - name: altitude_base
    kind: parameter
    dtype: Integer
    versions:
      - effective_from: '2020-01-01'
        formula: '1600'
      - effective_from: '2022-02-09'
        formula: '1800'`);

for (let i = 0; i < N; i++) {
  const threshold = 1600 + (i % 400);
  const modality = modalities[i % modalities.length];
  rules.push(`  - name: match_${String(i).padStart(5, "0")}\n    kind: derived\n    entity: Location\n    dtype: Integer\n    period: Day\n    versions:\n      - effective_from: '2020-01-01'\n        formula: |-\n          match activity_name:\n              "${modality}" => 1\n              _ => 0`);
  const versions = [
    `      - effective_from: '2020-01-01'\n        formula: match_${String(i).padStart(5, "0")} == 1 and altitude_m >= ${threshold} + altitude_base and inside_park and not inside_zona_servicios`,
  ];
  if (i % 2 === 0) {
    versions.push(`      - effective_from: '2022-02-09'\n        formula: match_${String(i).padStart(5, "0")} == 1 and altitude_m >= ${threshold} and inside_park and party_size <= 10`);
  }
  rules.push(`  - name: rule_${String(i).padStart(5, "0")}\n    kind: derived\n    entity: Location\n    dtype: Judgment\n    period: Day\n    versions:\n${versions.join("\n")}`);
}

const yaml = `format: rulespec/v1
module:
  summary: F2.1B synthetic knowledge-state with ${N} rules
rules:
${rules.join("\n")}
`;
fs.writeFileSync(`/work/rulespec-es/es/policies/vivac/ruleset-bench-${N}.yaml`, yaml);
console.log(`ruleset-bench-${N}.yaml written`);
