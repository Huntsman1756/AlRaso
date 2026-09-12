import test from 'node:test';
import assert from 'node:assert/strict';

import { ScenarioRecorder } from '../../helpers/recorder.mjs';

test('product assertion failure becomes FAIL, not HARNESS_ERROR', () => {
  const recorder = new ScenarioRecorder('S14_LEGAL_SERVER_DOWN', 'mobile-390x844');
  recorder.check('no-stale-result', false, { actual: 'PERMITTED', expected: 'not stale' });
  const result = recorder.finish();

  assert.equal(result.scenario_status, 'FAIL');
  assert.equal(result.assertions.failed, 1);
});

test('not applicable is explicit', () => {
  const recorder = new ScenarioRecorder('S12_MOBILE_SHEET', 'desktop-1440x900');
  recorder.notApplicable('mobile-sheet-state');

  assert.equal(recorder.finish().assertions.not_applicable, 1);
});

test('observer errors make a product result FAIL without changing its status class', () => {
  const recorder = new ScenarioRecorder('S01_BOOT_EMPTY', 'desktop-1440x900');
  const result = recorder.finish({
    observer: {
      snapshot: () => ({
        console: { unexpected_errors: 1, warnings: 0 },
        page_errors: [{ message: 'boom' }],
        network: { unexpected_failures: [] },
        expected_faults: []
      })
    }
  });

  assert.equal(result.scenario_status, 'FAIL');
  assert.equal(result.unexpected_console_errors, 1);
  assert.equal(result.page_errors, 1);
});

test('console.error remains evidence without failing the scenario by itself', () => {
  const recorder = new ScenarioRecorder('S14_LEGAL_SERVER_DOWN', 'mobile-390x844');
  const result = recorder.finish({
    observer: {
      snapshot: () => ({
        console: { unexpected_errors: 1, warnings: 0, errors: [{ text: 'expected transport error' }] },
        page_errors: [],
        network: { unexpected_failures: [] },
        expected_faults: ['resolve_request_aborted']
      })
    }
  });

  assert.equal(result.scenario_status, 'PASS');
  assert.equal(result.unexpected_console_errors, 1);
  assert.deepEqual(result.expected_faults, ['resolve_request_aborted']);
});
