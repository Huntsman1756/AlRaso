import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';

import { writeJson } from '../helpers/evidence.mjs';
import { PRODUCT_COMMIT } from '../helpers/constants.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const browserRoot = path.resolve(here, '..');
const repositoryRoot = path.resolve(browserRoot, '../..');
const runsRoot = path.resolve(process.env.M9_RUNS_ROOT || path.join(browserRoot, '.m9-runs'));
const activeRun = path.resolve(process.env.M9_RUN_DIR || path.join(runsRoot, 'run-2'));
const analysisRoot = path.join(activeRun, 'analysis');

function read(relative) {
  return readFileSync(path.join(repositoryRoot, relative), 'utf8');
}

function count(text, expression) {
  return [...text.matchAll(expression)].length;
}

function lineCount(text) {
  return text.split(/\r?\n/).length - (text.endsWith('\n') || text.endsWith('\r') ? 1 : 0);
}

function nonEmptyLineCount(text) {
  return text.split(/\r?\n/).filter((line) => line.trim()).length;
}

function sourceMetrics(relative) {
  const text = read(relative);
  const isPython = relative.endsWith('.py');
  const isJavaScript = relative.endsWith('.js');
  const isServer = relative === 'webapp/server.py';
  return {
    file: relative,
    bytes: Buffer.byteLength(text, 'utf8'),
    loc: lineCount(text),
    non_empty_loc: nonEmptyLineCount(text),
    function_or_def_count: isPython
      ? count(text, /^\s*(?:async\s+)?def\s+[A-Za-z_]\w*\s*\(/gm)
      : count(text, /(?:^|\n)\s*(?:async\s+)?function\s+[A-Za-z_$][\w$]*\s*\(/g)
        + (isJavaScript ? count(text, /(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*(?:async\s*)?\([^)]*\)\s*=>/g) : 0),
    fetch_sites: count(text, /\bfetch\s*\(/g) + count(text, /\burlopen\s*\(/g),
    add_event_listener_sites: count(text, /\.addEventListener\s*\(/g),
    dom_lookup_sites: count(text, /\$\s*\(/g) + count(text, /\bquerySelector(?:All)?\s*\(/g),
    try_catch_or_except_boundaries: count(text, /\btry\s*\{|\btry\s*:/g) + count(text, /\bcatch\s*\(|\bexcept\b/g),
    route_comparisons: isServer
      ? count(text, /(?:path|route|request_path|parsed)\s*(?:==|!=|\.startswith\(|\bin\s+)/g)
      : 0
  };
}

function markerInventory(relative, labels) {
  const text = read(relative);
  return labels.map(({ label, markers }) => {
    const hits = markers.filter((marker) => text.includes(marker));
    return {
      label,
      status: hits.length ? 'present' : 'not assessed',
      evidence: [relative],
      marker_hits: hits
    };
  });
}

const frontendResponsibilities = [
  { label: 'map/layers', markers: ['new maplibregl.Map', 'bindLayerToggles', 'loadCoverage'] },
  { label: 'POIs', markers: ['loadPois', 'renderPoi', 'poiLegalBtn'] },
  { label: 'protected areas', markers: ['loadProtectedAreas', 'renderPa', 'paLegalBtn'] },
  { label: 'bottom sheet', markers: ['SHEET_STATES', 'setSheetState', 'sheet-handle'] },
  { label: 'geolocation', markers: ['navigator.geolocation', 'initGeo'] },
  { label: 'search/suggestions', markers: ['initSuggest', 'searchform', '/api/find'] },
  { label: 'legal resolve rendering', markers: ['async function refresh', 'primaryLegalLabel', 'render(d)'] },
  { label: 'favorites', markers: ['renderFavorites', 'AlRasoStore.addFavorite'] },
  { label: 'outings', markers: ['renderOutings', 'openChooser', 'AlRasoStore.addOuting'] },
  { label: 'connectivity/PWA', markers: ['initPwa', 'serviceWorker.register', 'conn-banner'] },
  { label: 'weather', markers: ['loadWeather', 'renderWeather', 'api.open-meteo.com'] }
];

const backendResponsibilities = [
  { label: 'HTTP/static serving', markers: ['BaseHTTPRequestHandler', 'STATIC_DIR', 'send_head'] },
  { label: 'routing', markers: ['def do_GET', 'def do_OPTIONS', 'path =='] },
  { label: 'configuration', markers: ['/api/config', 'config_payload'] },
  { label: 'search', markers: ['/api/find', 'find_place'] },
  { label: 'POI/protected-area APIs', markers: ['/api/pois', '/api/protected-areas'] },
  { label: 'coverage', markers: ['/api/coverage', 'coverage_geojson'] },
  { label: 'resolver adapter', markers: ['/api/resolve', 'service.resolve'] },
  { label: 'serialization/presentation', markers: ['json.dumps', 'def _json'] },
  { label: 'input validation', markers: ['parse_coords', 'float(', 'HTTPStatus.BAD_REQUEST'] },
  { label: 'error handling', markers: ['except Exception', 'HTTPStatus.INTERNAL_SERVER_ERROR'] }
];

function qualityMatrix() {
  const packageJson = JSON.parse(readFileSync(path.join(browserRoot, 'package.json'), 'utf8'));
  const packageText = readFileSync(path.join(browserRoot, 'package.json'), 'utf8');
  const has = (relative) => existsSync(path.join(repositoryRoot, relative));
  const hasText = (relative, marker) => has(relative) && read(relative).includes(marker);
  const hasAxe = packageText.includes('axe') || existsSync(path.join(browserRoot, 'node_modules', 'axe-core'));
  const hasSnapshots = existsSync(path.join(browserRoot, 'tests', '__snapshots__'));
  return [
    { area: 'unit/integration Python', status: has('tests/test_engine_contract.py') ? 'present' : 'absent', evidence: ['tests/', '.github/workflows/gates.yml'] },
    { area: 'clean-wheel', status: has('tooling/clean_wheel.ps1') ? 'present' : 'absent', evidence: ['tooling/clean_wheel.ps1', '.github/workflows/gates.yml'] },
    { area: 'pre-commit', status: has('.pre-commit-config.yaml') ? 'present' : 'absent', evidence: ['.pre-commit-config.yaml'] },
    { area: 'schema validation', status: has('.pre-commit-config.yaml') && has('schemas/alraso-m2-coverage-v1.schema.json') ? 'present' : 'absent', evidence: ['.pre-commit-config.yaml', 'schemas/'] },
    { area: 'cross-Python CI', status: hasText('.github/workflows/gates.yml', 'python: ["3.11", "3.12"]') ? 'present' : 'absent', evidence: ['.github/workflows/gates.yml'] },
    { area: 'E2E browser automated', status: has('qa/browser/tests/baseline.spec.mjs') ? 'present' : 'absent', evidence: ['qa/browser/tests/baseline.spec.mjs'] },
    { area: 'a11y automated', status: hasAxe ? 'present' : (has('tests/test_m31_product_ux.py') ? 'partial' : 'absent'), evidence: ['tests/test_m31_product_ux.py', 'qa/browser/package.json'] },
    { area: 'visual regression', status: hasSnapshots ? 'present' : 'absent', evidence: ['qa/browser/tests/baseline.spec.mjs', 'qa/browser/package.json'] },
    { area: 'JS lint', status: has('eslint.config.js') || has('.eslintrc.json') ? 'present' : 'absent', evidence: ['qa/browser/package.json'] },
    { area: 'frontend unit tests', status: existsSync(path.join(browserRoot, 'tests', 'frontend')) ? 'present' : 'absent', evidence: ['qa/browser/tests/unit/'] },
    { area: 'API contract tests', status: has('tests/test_m2_webapp.py') ? 'partial' : 'absent', evidence: ['tests/test_m2_webapp.py', 'webapp/server.py'] },
    { area: 'performance baseline', status: has('qa/browser/helpers/observer.mjs') ? 'present' : 'absent', evidence: ['qa/browser/helpers/observer.mjs', 'qa/browser/scripts/analyze-repo.mjs'] },
    { area: 'security headers baseline', status: hasText('webapp/server.py', 'Cache-Control') ? 'partial' : 'absent', evidence: ['webapp/server.py'] },
    { area: 'browser harness unit tests', status: packageJson.scripts?.unit ? 'present' : 'absent', evidence: ['qa/browser/tests/unit/'] }
  ];
}

function resultFiles(runId) {
  const root = path.join(runsRoot, runId, 'evidence');
  if (!existsSync(root)) return [];
  const output = [];
  const visit = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const file = path.join(dir, entry.name);
      if (entry.isDirectory()) visit(file);
      else if (entry.name.endsWith('.json')) output.push(file);
    }
  };
  visit(root);
  return output;
}

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function summary(values) {
  return values.length ? {
    count: values.length,
    min_ms: Math.min(...values),
    median_ms: median(values),
    max_ms: Math.max(...values)
  } : { count: 0, min_ms: null, median_ms: null, max_ms: null };
}

function performanceSummary() {
  const endpointNames = ['/api/config', '/api/places', '/api/pois', '/api/protected-areas', '/api/coverage', '/api/find', '/api/resolve'];
  const endpoints = Object.fromEntries(endpointNames.map((endpoint) => [endpoint, {
    durations_ms: [],
    request_count: 0,
    response_count: 0,
    failed_count: 0,
    bytes_observed: []
  }]));
  const scenarios = [];

  for (const runId of ['run-1', 'run-2']) {
    for (const file of resultFiles(runId)) {
      const result = JSON.parse(readFileSync(file, 'utf8'));
      if (!result.scenario || !result.viewport) continue;
      scenarios.push({
        scenario: result.scenario,
        viewport: result.viewport,
        run: runId,
        duration_ms: result.metrics?.timings_ms?.scenario ?? null,
        requests: result.network?.requests?.length ?? 0,
        responses: result.network?.responses?.length ?? 0,
        failed_requests: result.network?.failed_requests?.length ?? 0
      });
      for (const request of result.network?.requests || []) {
        let endpoint;
        try { endpoint = new URL(request.url).pathname; } catch { endpoint = null; }
        if (!endpoints[endpoint]) continue;
        endpoints[endpoint].request_count += 1;
        if (request.failed) endpoints[endpoint].failed_count += 1;
        if (typeof request.duration_ms === 'number') endpoints[endpoint].durations_ms.push(request.duration_ms);
      }
      for (const response of result.network?.responses || []) {
        let endpoint;
        try { endpoint = new URL(response.url).pathname; } catch { endpoint = null; }
        if (!endpoints[endpoint]) continue;
        endpoints[endpoint].response_count += 1;
        if (typeof response.transferred_bytes === 'number') endpoints[endpoint].bytes_observed.push(response.transferred_bytes);
      }
    }
  }

  const endpointReport = Object.fromEntries(Object.entries(endpoints).map(([endpoint, data]) => [endpoint, {
    ...summary(data.durations_ms),
    request_count: data.request_count,
    response_count: data.response_count,
    failed_count: data.failed_count,
    bytes_observed: data.bytes_observed.length ? {
      count: data.bytes_observed.length,
      total: data.bytes_observed.reduce((sum, value) => sum + value, 0)
    } : null
  }]));
  return {
    source_runs: ['run-1', 'run-2'],
    endpoints: endpointReport,
    scenarios,
    performance_budget_verdict: 'not assessed in M9.0'
  };
}

function analyze() {
  const frontendFiles = ['webapp/static/app.js', 'webapp/static/store.js', 'webapp/static/sw.js', 'webapp/static/index.html', 'webapp/static/style.css'];
  const backendFiles = ['webapp/server.py', 'webapp/dem.py', ...readdirSync(path.join(repositoryRoot, 'alraso'))
    .filter((file) => file.endsWith('.py'))
    .sort()
    .map((file) => path.join('alraso', file))];
  const allFiles = [...new Set([...frontendFiles, ...backendFiles])];
  const architecture = {
    product_commit: PRODUCT_COMMIT,
    files: allFiles.map(sourceMetrics),
    frontend_responsibilities: markerInventory('webapp/static/app.js', frontendResponsibilities),
    backend_responsibilities: markerInventory('webapp/server.py', backendResponsibilities),
    server_routes: [...new Set([...read('webapp/server.py').matchAll(/['"](\/api\/[A-Za-z0-9_-]+)['"]/g)].map((match) => match[1]))].sort()
  };
  const quality = {
    product_commit: PRODUCT_COMMIT,
    areas: qualityMatrix(),
    note: 'Statuses record observed M9.0 capability, not a quality verdict.'
  };
  writeJson(path.join(analysisRoot, 'architecture.json'), architecture);
  writeJson(path.join(analysisRoot, 'quality.json'), quality);
  writeJson(path.join(analysisRoot, 'performance-summary.json'), performanceSummary());
  console.log(`Analysis written to ${analysisRoot}`);
}

try {
  analyze();
} catch (error) {
  console.error(error.message || error);
  process.exitCode = 1;
}
