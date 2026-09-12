import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { readdirSync, readFileSync } from 'node:fs';
import { isDeepStrictEqual } from 'node:util';

import { writeJson } from '../helpers/evidence.mjs';
import { reproducibilityContract } from '../helpers/normalize.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const browserRoot = path.resolve(here, '..');
const runsRoot = path.resolve(process.env.M9_RUNS_ROOT || path.join(browserRoot, '.m9-runs'));
const expectedCombinationCount = 42;

function walk(dir) {
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) files.push(...walk(full));
    else files.push(full);
  }
  return files;
}

function loadResults(runId) {
  const runDir = path.join(runsRoot, runId);
  const evidenceDir = path.join(runDir, 'evidence');
  const resultFiles = walk(evidenceDir).filter((file) => file.endsWith('.json'));
  const results = new Map();
  const blockers = [];

  for (const file of resultFiles) {
    const result = JSON.parse(readFileSync(file, 'utf8'));
    if (!result.scenario || !result.viewport) continue;
    const key = `${result.scenario}::${result.viewport}`;
    results.set(key, result);
    if (result.execution_status !== 'OK') blockers.push({ key, status: result.execution_status });
  }
  return { results, blockers };
}

function compare() {
  const first = loadResults('run-1');
  const second = loadResults('run-2');
  const keys = [...new Set([...first.results.keys(), ...second.results.keys()])].sort();
  const differences = [];

  if (first.results.size !== expectedCombinationCount) {
    differences.push({ type: 'count', run: 'run-1', actual: first.results.size, expected: expectedCombinationCount });
  }
  if (second.results.size !== expectedCombinationCount) {
    differences.push({ type: 'count', run: 'run-2', actual: second.results.size, expected: expectedCombinationCount });
  }
  for (const blocker of [...first.blockers, ...second.blockers]) {
    differences.push({ type: 'execution_blocker', ...blocker });
  }

  for (const key of keys) {
    const a = first.results.get(key);
    const b = second.results.get(key);
    if (!a || !b) {
      differences.push({ type: 'missing', key, run1: Boolean(a), run2: Boolean(b) });
      continue;
    }
    const normalizedA = reproducibilityContract(a);
    const normalizedB = reproducibilityContract(b);
    if (!isDeepStrictEqual(normalizedA, normalizedB)) {
      differences.push({ key, run1: normalizedA, run2: normalizedB });
    }
  }

  const report = {
    compared_at: new Date().toISOString(),
    expected_combinations: expectedCombinationCount,
    run_1_results: first.results.size,
    run_2_results: second.results.size,
    reproducible: differences.length === 0,
    differences
  };
  const reportPath = path.join(runsRoot, 'reproducibility-diff.json');
  writeJson(reportPath, report);
  if (differences.length) {
    console.error(`NON_REPRODUCIBLE: ${differences.length} difference(s)`);
    for (const difference of differences) console.error(difference.key || difference.type, difference);
    process.exitCode = 1;
    return;
  }
  console.log(`Reproducibility PASS: ${keys.length} stable scenario/viewport contracts match`);
}

try {
  compare();
} catch (error) {
  console.error(`NON_REPRODUCIBLE: ${error.message || error}`);
  process.exitCode = 1;
}

