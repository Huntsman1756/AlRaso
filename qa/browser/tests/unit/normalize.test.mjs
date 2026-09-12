import test from 'node:test';
import assert from 'node:assert/strict';

import { normalizeResult, reproducibilityContract } from '../../helpers/normalize.mjs';

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

test('reproducibility contract ignores transport inventory but keeps stable outcomes', () => {
  const a = reproducibilityContract({
    scenario: 'S01_BOOT_EMPTY',
    scenario_status: 'PASS',
    expected_faults: [],
    network: {
      requests: [{ url: 'https://tiles.example/a', duration_ms: 4 }],
      failed_requests: [],
      unexpected_failures: []
    },
    evidence: { screenshot: 'one.png' }
  });
  const b = reproducibilityContract({
    scenario: 'S01_BOOT_EMPTY',
    scenario_status: 'PASS',
    expected_faults: [],
    network: {
      requests: [{ url: 'https://tiles.example/b', duration_ms: 9 }],
      failed_requests: [{ url: 'https://tiles.example/c' }],
      unexpected_failures: []
    },
    evidence: { screenshot: 'two.png' }
  });

  assert.deepEqual(a, b);
});

test('offline transport failure count stays in normalized raw evidence', () => {
  const result = normalizeResult({
    scenario: 'S13_OFFLINE_VISITED',
    offline: {
      controller_before: true,
      controller_after: true,
      api_failures: 5,
      stale_weather_visible: false
    }
  });

  assert.equal(result.offline.api_failures, 5);
});

test('reproducibility contract ignores offline transport failure count', () => {
  const makeResult = (apiFailures) => ({
    scenario: 'S13_OFFLINE_VISITED',
    scenario_status: 'PASS',
    expected_faults: ['offline_transport'],
    offline: {
      controller_before: true,
      controller_after: true,
      api_failures: apiFailures,
      stale_weather_visible: false
    }
  });

  assert.deepEqual(
    reproducibilityContract(makeResult(5)),
    reproducibilityContract(makeResult(4))
  );
});

test('S08 external outcome is raw evidence but not stable reproducibility state', () => {
  const makeResult = (observation) => ({
    scenario: 'S08_WEATHER_AVAILABLE',
    viewport: 'desktop-1440x900',
    scenario_status: 'PASS',
    assertions: { passed: 4, failed: 0, not_applicable: 0 },
    legal_observed: {
      headline: 'No lo podemos determinar',
      legal_status: 'UNDETERMINED',
      coverage: 'PARTIAL'
    },
    weather: {
      observed_at: observation.observed_at,
      temperature: observation.temperature,
      request_url: observation.request_url,
      http_status: observation.response_http_status,
      ui_structure_valid: observation.ui_structure_valid
    },
    external_observation: observation
  });

  const live = {
    provider: 'open-meteo',
    request_observed: true,
    request_url: 'https://api.open-meteo.com/v1/forecast?latitude=43.171&longitude=-4.803',
    response_observed: true,
    status: 'LIVE_OK',
    response_http_status: 200,
    external_latency_ms: 120,
    observed_at: '2026-09-12T07:20',
    temperature: 12,
    ui_structure_valid: true
  };
  const timeout = {
    ...live,
    response_observed: false,
    status: 'EXTERNAL_TIMEOUT',
    response_http_status: null,
    external_latency_ms: null,
    observed_at: null,
    temperature: null,
    ui_structure_valid: false
  };

  assert.equal(normalizeResult(makeResult(timeout)).external_observation.status, 'EXTERNAL_TIMEOUT');
  assert.deepEqual(reproducibilityContract(makeResult(live)), reproducibilityContract(makeResult(timeout)));
  assert.notDeepEqual(
    reproducibilityContract(makeResult(live)),
    reproducibilityContract(makeResult({ ...live, request_observed: false, request_url: null }))
  );
});
