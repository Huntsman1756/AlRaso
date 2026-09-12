import test from 'node:test';
import assert from 'node:assert/strict';

import { waitForWeatherRequest, waitForWeatherResponse } from '../../scenarios/shared.mjs';

test('weather request and response waits use a dedicated 30-second external timeout', async () => {
  const receivedOptions = [];
  const page = {
    waitForRequest(_predicate, options) {
      receivedOptions.push(options);
      return Promise.resolve({ url: () => 'https://api.open-meteo.com/v1/forecast' });
    },
    waitForResponse(_predicate, options) {
      receivedOptions.push(options);
      return Promise.resolve({
        url: () => 'https://api.open-meteo.com/v1/forecast',
        status: () => 200
      });
    }
  };

  await waitForWeatherRequest(page);
  await waitForWeatherResponse(page);

  assert.deepEqual(receivedOptions, [{ timeout: 30_000 }, { timeout: 30_000 }]);
});
