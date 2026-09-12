import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { test } from '@playwright/test';

import { assertCanonicalEnvironment, captureEnvironment, installBaselineClock } from '../helpers/environment.mjs';
import { writeJson, writeScreenshot } from '../helpers/evidence.mjs';
import { observePage } from '../helpers/observer.mjs';
import { assertFrozenProductClean } from '../helpers/product-guard.mjs';
import { ScenarioRecorder } from '../helpers/recorder.mjs';
import {
  S01_BOOT_EMPTY,
  S02_SEARCH_KNOWN_PLACE,
  S03_COORDS_UNKNOWN,
  S04_PICOS_PERMITTED
} from '../scenarios/core.mjs';
import { S05_POI_NAMED, S06_POI_UNNAMED, S07_PROTECTED_AREA } from '../scenarios/map.mjs';
import { S08_WEATHER_AVAILABLE, S09_WEATHER_UNAVAILABLE } from '../scenarios/weather.mjs';
import { S10_SAVE_FAVORITE, S11_OUTING_FLOW } from '../scenarios/persistence.mjs';
import { S12_MOBILE_SHEET, S13_OFFLINE_VISITED, S14_LEGAL_SERVER_DOWN } from '../scenarios/resilience.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const runDir = path.resolve(process.env.M9_RUN_DIR || path.join(here, '..', '.m9-runs', 'manual'));

const scenarios = [
  S01_BOOT_EMPTY,
  S02_SEARCH_KNOWN_PLACE,
  S03_COORDS_UNKNOWN,
  S04_PICOS_PERMITTED,
  S05_POI_NAMED,
  S06_POI_UNNAMED,
  S07_PROTECTED_AREA,
  S08_WEATHER_AVAILABLE,
  S09_WEATHER_UNAVAILABLE,
  S10_SAVE_FAVORITE,
  S11_OUTING_FLOW,
  S12_MOBILE_SHEET,
  S13_OFFLINE_VISITED,
  S14_LEGAL_SERVER_DOWN
];

function errorRecord(error) {
  if (!error) return null;
  return { name: error.name || 'Error', message: error.message || String(error), stack: error.stack || null };
}

function errorClass(error) {
  if (!error) return null;
  const message = `${error.name || ''} ${error.message || ''}`;
  if (message.includes('ENVIRONMENT_ERROR')) return 'ENVIRONMENT_ERROR';
  if (message.includes('NON_REPRODUCIBLE')) return 'NON_REPRODUCIBLE';
  return 'HARNESS_ERROR';
}

function evidencePath(projectName, scenarioId, suffix) {
  return path.join(runDir, 'evidence', projectName, `${scenarioId}${suffix}`);
}

test.beforeAll(async ({ browser }) => {
  assertFrozenProductClean(root);
  const environment = captureEnvironment(browser, root);
  assertCanonicalEnvironment(environment);
  writeJson(path.join(runDir, 'environment.json'), environment);
});

test.afterAll(() => {
  assertFrozenProductClean(root);
});

for (const scenario of scenarios) {
  test(scenario.id, async ({ page }, testInfo) => {
    const projectName = testInfo.project.name;
    const recorder = new ScenarioRecorder(scenario.id, projectName);
    const observer = observePage(page);
    const started = performance.now();
    let fatalError = null;
    let screenshotError = null;
    const resultFile = evidencePath(projectName, scenario.id, '.json');
    const screenshotFile = evidencePath(projectName, scenario.id, '.png');

    try {
      await installBaselineClock(page);
      await scenario.run({ page, recorder, observer, projectName, runDir });
    } catch (error) {
      fatalError = error;
    } finally {
      try {
        await writeScreenshot(page, screenshotFile, { fullPage: true });
      } catch (error) {
        screenshotError = error;
      }

      const executionError = fatalError || screenshotError;
      const result = recorder.finish({
        observer,
        metrics: {
          timings_ms: { scenario: Math.round(performance.now() - started) }
        },
        reproducible: executionError ? false : true
      });
      result.execution_status = errorClass(executionError) || 'OK';
      result.fatal_error = errorRecord(executionError);
      result.evidence = {
        screenshot: path.relative(runDir, screenshotFile).replaceAll(path.sep, '/'),
        result: path.relative(runDir, resultFile).replaceAll(path.sep, '/')
      };
      if (executionError) result.scenario_status = 'FAIL';
      writeJson(resultFile, result);
    }

    if (fatalError) throw fatalError;
    if (screenshotError) throw screenshotError;
  });
}
