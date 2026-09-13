import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createMapController,
  validPaFeatureCollection,
  validPaGeometry,
  validPaPosition,
  validPaRing
} from '../../../../webapp/static/modules/map.js';

test('map controller has no browser effects until boot and exposes its handle API', () => {
  const controller = createMapController({
    state: {},
    poiCats: {},
    poiOrder: [],
    onPointSelected() {},
    onPoiClick() {},
    onPaClick() {}
  });
  assert.deepEqual(Object.keys(controller), ['boot', 'handle']);
  assert.equal(typeof controller.boot, 'function');
  assert.equal(controller.handle(), null);
});

test('protected-area validators keep closed coordinate rings and feature collections strict', () => {
  const ring = [[0, 0], [1, 0], [1, 1], [0, 0]];
  const geometry = { type: 'Polygon', coordinates: [ring] };
  const featureCollection = {
    type: 'FeatureCollection',
    features: [{ type: 'Feature', geometry }]
  };
  assert.equal(validPaPosition([0, 0]), true);
  assert.equal(validPaPosition([181, 0]), false);
  assert.equal(validPaRing(ring), true);
  assert.equal(validPaRing([[0, 0], [1, 0], [1, 1], [0, 1]]), false);
  assert.equal(validPaGeometry(geometry), true);
  assert.equal(validPaFeatureCollection(featureCollection), true);
  assert.equal(validPaFeatureCollection({ ...featureCollection, features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: [0, 0] } }] }), false);
});
