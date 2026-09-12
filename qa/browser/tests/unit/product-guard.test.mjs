import test from 'node:test';
import assert from 'node:assert/strict';

import { classifyProductDrift } from '../../helpers/product-guard.mjs';

const clean = { diffExit: 0, status: '' };
const trackedDrift = { diffExit: 1, status: ' M webapp/static/app.js' };
const untrackedDrift = { diffExit: 0, status: '?? webapp/tmp.json' };

test('clean frozen roots pass', () => {
  assert.deepEqual(classifyProductDrift(clean), { clean: true, reasons: [] });
});

test('tracked product drift fails', () => {
  assert.equal(classifyProductDrift(trackedDrift).clean, false);
});

test('untracked product drift fails', () => {
  assert.equal(classifyProductDrift(untrackedDrift).clean, false);
});
