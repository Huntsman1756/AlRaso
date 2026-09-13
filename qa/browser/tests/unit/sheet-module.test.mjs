import test from 'node:test';
import assert from 'node:assert/strict';

import { createSheetController } from '../../../../webapp/static/modules/sheet.js';

test('sheet module is inert without a browser DOM and exposes its controller API', () => {
  const controller = createSheetController({ onLayoutChange() {} });
  assert.deepEqual(Object.keys(controller), [
    'getState',
    'setSheetState',
    'openSheetForSelection'
  ]);
  assert.equal(controller.getState(), 'closed');
  assert.equal(typeof controller.setSheetState, 'function');
  assert.equal(typeof controller.openSheetForSelection, 'function');
});
