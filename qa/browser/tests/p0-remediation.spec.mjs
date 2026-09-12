import { test, expect } from '@playwright/test';

import { installBaselineClock } from '../helpers/environment.mjs';
import { observePage } from '../helpers/observer.mjs';
import { ScenarioRecorder } from '../helpers/recorder.mjs';
import { S03_COORDS_UNKNOWN, S04_PICOS_PERMITTED } from '../scenarios/core.mjs';
import { S14_LEGAL_SERVER_DOWN } from '../scenarios/resilience.mjs';

async function executeScenario(scenario, page, testInfo) {
  const recorder = new ScenarioRecorder(scenario.id, testInfo.project.name);
  const observer = observePage(page);

  await installBaselineClock(page);
  await scenario.run({
    page,
    recorder,
    observer,
    projectName: testInfo.project.name
  });
  return { result: recorder.finish({ observer, reproducible: true }), page };
}

test('S14 never presents a previous legal determination as current', async ({ page }, testInfo) => {
  const { result } = await executeScenario(S14_LEGAL_SERVER_DOWN, page, testInfo);

  expect(result.assertions.failed, JSON.stringify(result, null, 2)).toBe(0);
  expect(result.findings, JSON.stringify(result, null, 2)).toEqual([]);
  await expect(page.locator('#headline')).toContainText('No se pudo obtener');
  await expect(page.locator('#coords')).toContainText('41.90000');
  await expect(page.locator('#legal')).not.toHaveAttribute('data-code', 'PERMITTED');
});

test('S03 unknown coordinates remains fail-closed', async ({ page }, testInfo) => {
  const { result } = await executeScenario(S03_COORDS_UNKNOWN, page, testInfo);
  expect(result.scenario_status, JSON.stringify(result, null, 2)).toBe('PASS');
  expect(result.assertions.failed, JSON.stringify(result, null, 2)).toBe(0);
});

test('S04 Picos permitted remains available with UI facts', async ({ page }, testInfo) => {
  const { result } = await executeScenario(S04_PICOS_PERMITTED, page, testInfo);
  expect(result.scenario_status, JSON.stringify(result, null, 2)).toBe('PASS');
  expect(result.assertions.failed, JSON.stringify(result, null, 2)).toBe(0);
});
