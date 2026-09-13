import test from 'node:test';
import assert from 'node:assert/strict';

import { createSearchController } from '../../../../webapp/static/modules/search.js';

test('search module has no browser effects until init and exposes its controller API', () => {
  const controller = createSearchController({
    state: {},
    onSelectPoint() {},
    onRenderPoi() {}
  });
  assert.deepEqual(Object.keys(controller), ['init']);
  assert.equal(typeof controller.init, 'function');
});
