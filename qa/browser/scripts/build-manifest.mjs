import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';

import { BASELINE_NOW, DEVICE_SCALE_FACTOR, LOCALE, PRODUCT_COMMIT, TIMEZONE, VIEWPORTS } from '../helpers/constants.mjs';
import { manifestHashCandidates, sha256File, writeJson } from '../helpers/evidence.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const browserRoot = path.resolve(here, '..');
const repositoryRoot = path.resolve(browserRoot, '../..');
const runDir = path.resolve(process.env.M9_RUN_DIR || path.join(browserRoot, '.m9-runs', 'run-2'));
const evidenceRoot = path.resolve(process.env.M9_EVIDENCE_ROOT || path.join(runDir, 'evidence'));
const manifestPath = path.resolve(process.env.M9_MANIFEST_OUT || path.join(runDir, 'manifest.json'));
const expectedVersions = {
  node_version: 'v24.19.0',
  playwright_version: '1.63.0',
  chromium_version: '153.0.8010.12'
};

const scenarioIds = [
  'S01_BOOT_EMPTY',
  'S02_SEARCH_KNOWN_PLACE',
  'S03_COORDS_UNKNOWN',
  'S04_PICOS_PERMITTED',
  'S05_POI_NAMED',
  'S06_POI_UNNAMED',
  'S07_PROTECTED_AREA',
  'S08_WEATHER_AVAILABLE',
  'S09_WEATHER_UNAVAILABLE',
  'S10_SAVE_FAVORITE',
  'S11_OUTING_FLOW',
  'S12_MOBILE_SHEET',
  'S13_OFFLINE_VISITED',
  'S14_LEGAL_SERVER_DOWN'
];

function walk(dir) {
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) files.push(...walk(full));
    else files.push(full);
  }
  return files;
}

function readEnvironment() {
  const environmentFile = path.resolve(process.env.M9_ENVIRONMENT_FILE || path.join(runDir, 'environment.json'));
  if (!existsSync(environmentFile)) throw new Error(`ENVIRONMENT_ERROR missing ${environmentFile}`);
  return JSON.parse(readFileSync(environmentFile, 'utf8'));
}

function assertCanonicalTooling(environment) {
  for (const [key, expected] of Object.entries(expectedVersions)) {
    if (environment[key] !== expected) {
      throw new Error(`ENVIRONMENT_ERROR ${key}=${environment[key]} expected ${expected}`);
    }
  }
  if (environment.dem?.rasterio_installed !== false) {
    throw new Error('ENVIRONMENT_ERROR rasterio_installed must be false');
  }
}

function buildManifest() {
  const environment = readEnvironment();
  assertCanonicalTooling(environment);
  if (!existsSync(evidenceRoot)) throw new Error(`ENVIRONMENT_ERROR missing evidence root ${evidenceRoot}`);

  const relativeFiles = walk(evidenceRoot)
    .map((file) => path.relative(evidenceRoot, file).split(path.sep).join('/'))
    .sort();
  const hashableFiles = manifestHashCandidates(relativeFiles);
  const evidence = hashableFiles.map((relative) => ({
    path: relative,
    sha256: sha256File(path.join(evidenceRoot, relative))
  }));
  const qaHarnessCommit = process.env.M9_HARNESS_SHA || execFileSync('git', ['rev-parse', 'HEAD'], {
    cwd: repositoryRoot,
    encoding: 'utf8'
  }).trim();

  const manifest = {
    product_commit: PRODUCT_COMMIT,
    qa_harness_commit: qaHarnessCommit,
    generated_at: new Date().toISOString(),
    baseline_now: BASELINE_NOW,
    node_version: environment.node_version,
    python_version: environment.python_version,
    playwright_version: environment.playwright_version,
    chromium_version: environment.chromium_version,
    platform: environment.platform,
    dem: environment.dem,
    locale: LOCALE,
    timezone: TIMEZONE,
    device_scale_factor: DEVICE_SCALE_FACTOR,
    viewports: Object.entries(VIEWPORTS).map(([id, viewport]) => ({ id, ...viewport })),
    scenarios: scenarioIds,
    volatile_fields: ['weather.temperature', 'weather.observed_at'],
    evidence
  };
  writeJson(manifestPath, manifest);
  console.log(`Manifest written to ${manifestPath}`);
  console.log(`Evidence hashes: ${evidence.length}; manifest self-hash: excluded`);
}

try {
  buildManifest();
} catch (error) {
  console.error(error.message || error);
  process.exitCode = 1;
}
