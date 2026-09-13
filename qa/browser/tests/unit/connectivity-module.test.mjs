import test from 'node:test';
import assert from 'node:assert/strict';

import { createConnectivityController } from '../../../../webapp/static/modules/connectivity.js';

test('connectivity module has no browser effects until init and exposes its controller API', () => {
  const controller = createConnectivityController();
  assert.deepEqual(Object.keys(controller), ['init']);
  assert.equal(typeof controller.init, 'function');
});
