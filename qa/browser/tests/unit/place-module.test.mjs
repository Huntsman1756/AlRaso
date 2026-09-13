import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createPlacePresenter,
  normalizePlaceContext,
  POI_CATS,
  POI_ORDER
} from '../../../../webapp/static/modules/place.js';

test('place presenter is inert until a render method is called', () => {
  const presenter = createPlacePresenter({ state: {} });
  assert.deepEqual(Object.keys(presenter), [
    'renderPoi',
    'renderPa',
    'renderPlaceHeading',
    'renderPlaceContext'
  ]);
  assert.equal(typeof presenter.renderPoi, 'function');
  assert.equal(typeof presenter.renderPa, 'function');
  assert.equal(typeof presenter.renderPlaceHeading, 'function');
  assert.equal(typeof presenter.renderPlaceContext, 'function');
});

test('place context normalization keeps cartographic labels and disclaimer', () => {
  assert.deepEqual(normalizePlaceContext({
    properties: {
      name: 'Parque de prueba',
      category: 'protected_area',
      disclaimer: 'Solo contexto cartográfico'
    }
  }), {
    kind: 'Espacio protegido',
    name: 'Parque de prueba',
    note: 'Solo contexto cartográfico'
  });
  assert.equal(normalizePlaceContext({ properties: {} }), null);
});

test('place category constants keep the established presentation order', () => {
  assert.deepEqual(POI_ORDER, ['refuge', 'shelter', 'water', 'camping']);
  assert.equal(POI_CATS.refuge.label, 'Refugio');
  assert.equal(POI_CATS.protected_area.emoji, '🌲');
});
