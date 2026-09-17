import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

// node:test runs without a real localStorage; store.js probes it once at load
// time, so the shim must exist BEFORE the module is required.
const mem = new Map();
globalThis.localStorage = {
  getItem: (k) => (mem.has(k) ? mem.get(k) : null),
  setItem: (k, v) => mem.set(k, String(v)),
  removeItem: (k) => mem.delete(k),
};

// store.js is a CJS-style IIFE (window.AlRasoStore / module.exports).
const require = createRequire(import.meta.url);
const AlRasoStore = require('../../../../webapp/static/store.js');

function seedOuting(outing) {
  // Corrupt or hostile stored data is filtered at the read boundary.
  localStorage.setItem('alraso.outings.v1', JSON.stringify([outing]));
}

test('outings with malformed place entries are dropped at the read boundary', () => {
  seedOuting({
    id: 'out-1', name: 'Salida', date: '2026-09-13', status: 'PLANNED',
    places: [{ lat: '"><script>x</script>', lon: 0.5, name: 'x' }],
  });
  assert.equal(AlRasoStore.outings().length, 0);
});

test('outings with non-finite or out-of-range place coords are dropped', () => {
  for (const badLat of [NaN, Infinity, 91, -91, '42.6']) {
    seedOuting({
      id: 'out-1', name: 'Salida', date: '2026-09-13', status: 'PLANNED',
      places: [{ lat: badLat, lon: 0.5, name: 'x' }],
    });
    assert.equal(AlRasoStore.outings().length, 0, `lat=${badLat}`);
  }
});

test('a valid outing with valid places survives validation', () => {
  seedOuting({
    id: 'out-1', name: 'Salida', date: '2026-09-13', status: 'PLANNED',
    places: [{ lat: 42.6627, lon: 0.016, name: 'Góriz' }],
  });
  const outings = AlRasoStore.outings();
  assert.equal(outings.length, 1);
  assert.equal(outings[0].places[0].name, 'Góriz');
});
