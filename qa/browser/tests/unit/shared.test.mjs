import test from 'node:test';
import assert from 'node:assert/strict';

import { waitForWeatherResponse } from '../../scenarios/shared.mjs';

test('weather response wait uses a dedicated 30-second external timeout', async () => {
  let receivedOptions;
  const page = {
    waitForResponse(_predicate, options) {
      receivedOptions = options;
      return Promise.resolve({
        url: () => 'https://api.open-meteo.com/v1/forecast',
        status: () => 200
      });
    }
  };

  await waitForWeatherResponse(page);

  assert.equal(receivedOptions.timeout, 30_000);
});
