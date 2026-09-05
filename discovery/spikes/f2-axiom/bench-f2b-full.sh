#!/bin/bash
# F2.1B full benchmark: cold/warm compile, determinism, artifact size, fast/explain runs, invalidation.
B=/work/axiom-rules-engine/target/release/axiom-rules-engine
R=/work/rulespec-es/es/policies/vivac
for N in 10 100 500 1000; do
  echo "===== N=$N ====="
  echo "-- baseline (capabilities, process startup only)"
  { time $B capabilities > /dev/null ; } 2>&1 | grep real
  echo "-- compile cold"
  { time $B compile --program $R/ruleset-bench-$N.yaml --rulespec-root /work/rulespec-es --output /work/f2/b_$N.json ; } 2>&1 | grep -E 'real|error' | tail -2
  echo "-- compile warm (same input, 2nd run)"
  { time $B compile --program $R/ruleset-bench-$N.yaml --rulespec-root /work/rulespec-es --output /work/f2/b_${N}_warm.json ; } 2>&1 | grep -E 'real|error' | tail -2
  echo "-- artifact size"
  ls -la /work/f2/b_$N.json | awk '{print $5" bytes"}'
  echo "-- knowledge-state hash (ruleset yaml sha256)"
  sha256sum $R/ruleset-bench-$N.yaml | awk '{print $1}'
  echo "-- determinism (sha artifact cold vs warm)"
  sha256sum /work/f2/b_$N.json /work/f2/b_${N}_warm.json | awk '{print $1}'
  echo "-- run fast x3 (warm artifact load + exec)"
  for i in 1 2 3; do { time $B run-compiled --artifact /work/f2/b_$N.json < /work/f2/req_fast_$N.json > /dev/null ; } 2>&1 | grep real; done
  echo "-- run explain x3"
  for i in 1 2 3; do { time $B run-compiled --artifact /work/f2/b_$N.json < /work/f2/req_explain_$N.json > /work/f2/be_${N}_$i.json ; } 2>&1 | grep real; done
  echo "-- explain output size"
  ls -la /work/f2/be_${N}_1.json | awk '{print $5" bytes"}'
done
echo "===== invalidation probe (knowledge-state change) ====="
sed 's/formula: '"'"'1600'"'"'/formula: '"'"'1610'"'"'/' $R/ruleset-bench-10.yaml > $R/ruleset-bench-10v2.yaml
sha256sum $R/ruleset-bench-10.yaml $R/ruleset-bench-10v2.yaml | awk '{print $1"  "substr($2,length($2)-30)}'
$B compile --program $R/ruleset-bench-10v2.yaml --rulespec-root /work/rulespec-es --output /work/f2/b_10v2.json 2>&1 | tail -1
sha256sum /work/f2/b_10.json /work/f2/b_10v2.json | awk '{print $1"  "substr($2,length($2)-30)}'
echo "-- artifact reuse across separate processes (cache-hit semantics): run same artifact again"
{ time $B run-compiled --artifact /work/f2/b_10.json < /work/f2/req_fast_10.json > /dev/null ; } 2>&1 | grep real
rm -f $R/ruleset-bench-10v2.yaml
