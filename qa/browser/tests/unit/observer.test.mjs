import test from 'node:test';
import assert from 'node:assert/strict';

import { observePage } from '../../helpers/observer.mjs';

test('external weather request failures remain raw evidence without blocking the scenario', () => {
  const listeners = new Map();
  const page = {
    on(event, handler) {
      listeners.set(event, handler);
    }
  };
  const observer = observePage(page);
  observer.addNonBlockingFailure(
    'open_meteo_external',
    (request) => request.url().includes('api.open-meteo.com')
  );

  const request = {
    url: () => 'https://api.open-meteo.com/v1/forecast',
    method: () => 'GET',
    resourceType: () => 'fetch',
    failure: () => ({ errorText: 'net::ERR_NAME_NOT_RESOLVED' })
  };
  listeners.get('request')(request);
  listeners.get('requestfailed')(request);

  const snapshot = observer.snapshot();
  assert.equal(snapshot.network.failed_requests[0].non_blocking, true);
  assert.equal(snapshot.network.failed_requests[0].non_blocking_reason, 'open_meteo_external');
  assert.equal(snapshot.network.non_blocking_failures.length, 1);
  assert.deepEqual(snapshot.network.unexpected_failures, []);
});
