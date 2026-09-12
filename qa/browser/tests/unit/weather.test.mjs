import test from 'node:test';
import assert from 'node:assert/strict';

import {
  classifyWeatherObservation,
  matchesCanonicalWeatherCoordinates,
  weatherProbeAssertions
} from '../../scenarios/shared.mjs';

function probe({ requestObserved, responseObserved, responseStatus, requestFailed, weatherUiValid }) {
  const status = classifyWeatherObservation({
    requestObserved,
    responseObserved,
    responseStatus,
    requestFailed
  });
  const assertions = weatherProbeAssertions({
    requestObserved,
    canonicalCoordinates: true,
    status,
    weatherUiValid,
    legalAvailable: true
  });
  return { status, assertions };
}

function passes(assertions) {
  return Object.values(assertions).every(Boolean);
}

test('S08 live 200 with valid UI is a passing product probe', () => {
  const result = probe({
    requestObserved: true,
    responseObserved: true,
    responseStatus: 200,
    requestFailed: false,
    weatherUiValid: true
  });

  assert.equal(result.status, 'LIVE_OK');
  assert.equal(passes(result.assertions), true);
});

test('S08 observed request timeout passes without live-provider assertions', () => {
  const result = probe({
    requestObserved: true,
    responseObserved: false,
    responseStatus: null,
    requestFailed: false,
    weatherUiValid: false
  });

  assert.equal(result.status, 'EXTERNAL_TIMEOUT');
  assert.equal(passes(result.assertions), true);
});

test('S08 missing request fails the product probe', () => {
  const result = probe({
    requestObserved: false,
    responseObserved: false,
    responseStatus: null,
    requestFailed: false,
    weatherUiValid: false
  });

  assert.equal(result.status, null);
  assert.equal(passes(result.assertions), false);
  assert.equal(result.assertions.request_observed, false);
});

test('S08 live 200 with invalid UI fails the product probe', () => {
  const result = probe({
    requestObserved: true,
    responseObserved: true,
    responseStatus: 200,
    requestFailed: false,
    weatherUiValid: false
  });

  assert.equal(result.status, 'LIVE_OK');
  assert.equal(passes(result.assertions), false);
  assert.equal(result.assertions.live_integration_valid, false);
});

test('S08 observed network failure is external and non-blocking by itself', () => {
  const result = probe({
    requestObserved: true,
    responseObserved: false,
    responseStatus: null,
    requestFailed: true,
    weatherUiValid: false
  });

  assert.equal(result.status, 'EXTERNAL_NETWORK_ERROR');
  assert.equal(passes(result.assertions), true);
});

test('S08 canonical weather coordinates are read from the real request URL', () => {
  const canonical = { lat: 43.17068, lon: -4.80299 };
  const requestUrl = 'https://api.open-meteo.com/v1/forecast?latitude=43.171&longitude=-4.803';

  assert.equal(matchesCanonicalWeatherCoordinates(requestUrl, canonical), true);
  assert.equal(
    matchesCanonicalWeatherCoordinates(
      'https://api.open-meteo.com/v1/forecast?latitude=41.9&longitude=-2.4',
      canonical
    ),
    false
  );
});
