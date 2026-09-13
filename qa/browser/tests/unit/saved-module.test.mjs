import test from 'node:test';
import assert from 'node:assert/strict';

import { createSavedController, formatDate } from '../../../../webapp/static/modules/saved.js';

test('saved module formats ISO dates for the existing outing rows', () => {
  assert.equal(formatDate('2026-09-13'), '13/09/2026');
});

test('saved controller exposes only the injected storage boundary and UI methods', () => {
  const controller = createSavedController({
    store: {},
    state: { lat: null, lon: null, selectedName: null },
    onSelectPoint() {},
    showTab() {}
  });
  assert.deepEqual(Object.keys(controller).sort(), [
    'initChooser',
    'renderFavorites',
    'renderOutings',
    'updateSaveButton',
    'updateStats'
  ]);
});
