import test from 'node:test';
import assert from 'node:assert/strict';

const MODULES = [
  'dom.js',
  'state.js',
  'api-legal.js',
  'api-cartography.js',
  'map.js',
  'place.js',
  'legal.js',
  'search.js',
  'weather.js',
  'sheet.js',
  'saved.js',
  'connectivity.js'
];

test('every frontend module loads in Node without browser side effects', async () => {
  for (const moduleName of MODULES) {
    const namespace = await import(`../../../../webapp/static/modules/${moduleName}`);
    assert.ok(Object.keys(namespace).length > 0, moduleName);
  }
});
