import test from 'node:test';
import assert from 'node:assert/strict';

import { normalizeResult } from '../../helpers/normalize.mjs';

test('weather volatile values do not participate in reproducibility comparison', () => {
  const a = normalizeResult({
    scenario: 'S08_WEATHER_AVAILABLE',
    weather: { temperature: 4, observed_at: 'a', status: 200 }
  });
  const b = normalizeResult({
    scenario: 'S08_WEATHER_AVAILABLE',
    weather: { temperature: 8, observed_at: 'b', status: 200 }
  });

  assert.deepEqual(a, b);
});

test('stable status and expected faults remain comparable', () => {
  assert.notDeepEqual(
    normalizeResult({ scenario_status: 'PASS', expected_faults: [] }),
    normalizeResult({ scenario_status: 'FAIL', expected_faults: [] })
  );
  assert.notDeepEqual(
    normalizeResult({ scenario_status: 'PASS', expected_faults: [] }),
    normalizeResult({ scenario_status: 'PASS', expected_faults: ['weather_unavailable'] })
  );
});

test('timing and generation fields are removed without changing assertions', () => {
  const result = normalizeResult({
    generated_at: 'a',
    scenario_duration_ms: 10,
    assertions: { passed: 2, failed: 0 },
    network: { request_duration_ms: 20, status: 200 }
  });

  assert.deepEqual(result, {
    assertions: { passed: 2, failed: 0 },
    network: { status: 200 }
  });
});
