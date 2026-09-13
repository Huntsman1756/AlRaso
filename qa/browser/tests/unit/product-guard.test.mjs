import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

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

test('baseline resolves the repository root from its tests directory', () => {
  const baselineFile = fileURLToPath(new URL('../baseline.spec.mjs', import.meta.url));
  const baselineSource = readFileSync(baselineFile, 'utf8');
  assert.match(baselineSource, /const root = path\.resolve\(here, '\.\.\/\.\.\/\.\.'\);/);

  const repositoryRoot = path.resolve(path.dirname(baselineFile), '../../..');
  for (const directory of ['webapp', 'alraso', 'qa']) {
    assert.equal(existsSync(path.join(repositoryRoot, directory)), true, directory);
  }
});
