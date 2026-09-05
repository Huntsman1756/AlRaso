#!/bin/bash
# F2.1B benchmark: compile (x2), artifact size, fast x3, explain x3, baseline.
BIN=/work/axiom-rules-engine/target/release/axiom-rules-engine
N=$1
R=/work/rulespec-es/es/policies/vivac/ruleset-bench-$N.yaml
A=/work/f2/artifact_$N.json

echo "===== N=$N ====="
echo "-- baseline (capabilities, process startup only)"
{ time $BIN capabilities > /dev/null ; } 2>&1 | grep real
echo "-- compile cold"
{ time $BIN compile --program $R --rulespec-root /work/rulespec-es --output $A ; } 2>&1 | grep -E 'real|error' | tail -2
echo "-- compile warm (same input, 2nd run)"
{ time $BIN compile --program $R --rulespec-root /work/rulespec-es --output ${A%.json}_warm.json ; } 2>&1 | grep -E 'real|error' | tail -2
echo "-- artifact size"
ls -la $A | awk '{print $5" bytes"}'
sha256sum $R | awk '{print "knowledge-state hash (yaml): "$1}'
echo "-- run fast x3"
for i in 1 2 3; do { time $BIN run-compiled --artifact $A < /work/f2/req_fast_$N.json > /work/f2/out_fast_${N}_$i.json ; } 2>&1 | grep real; done
echo "-- run explain x3"
for i in 1 2 3; do { time $BIN run-compiled --artifact $A < /work/f2/req_explain_$N.json > /work/f2/out_expl_${N}_$i.json ; } 2>&1 | grep real; done
echo "-- explain output size"
ls -la /work/f2/out_expl_${N}_1.json | awk '{print $5" bytes"}'
