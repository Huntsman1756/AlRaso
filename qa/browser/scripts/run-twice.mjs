import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

import { assertFrozenProductClean } from '../helpers/product-guard.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const browserRoot = path.resolve(here, '..');
const repositoryRoot = path.resolve(browserRoot, '../..');
const runsRoot = path.resolve(process.env.M9_RUNS_ROOT || path.join(browserRoot, '.m9-runs'));

function runOnce(runId) {
  const runDir = path.join(runsRoot, runId);
  const playwrightCli = path.join(browserRoot, 'node_modules', '@playwright', 'test', 'cli.js');
  const result = spawnSync(process.execPath, [playwrightCli, 'test', 'tests/baseline.spec.mjs'], {
    cwd: browserRoot,
    env: {
      ...process.env,
      M9_RUN_ID: runId,
      M9_RUN_DIR: runDir
    },
    stdio: 'inherit'
  });
  if (result.error) throw new Error(`HARNESS_ERROR unable to start Playwright: ${result.error.message}`);
  if (result.status !== 0) throw new Error(`HARNESS_ERROR baseline ${runId} exited with ${result.status}`);
}

function main() {
  assertFrozenProductClean(repositoryRoot);
  runOnce('run-1');
  assertFrozenProductClean(repositoryRoot);
  runOnce('run-2');
  assertFrozenProductClean(repositoryRoot);
  console.log(`M9 two-run evidence written to ${runsRoot}`);
}

try {
  main();
} catch (error) {
  console.error(error.message || error);
  process.exitCode = 1;
}
