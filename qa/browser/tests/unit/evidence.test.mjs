import test from 'node:test';
import assert from 'node:assert/strict';

import { manifestHashCandidates } from '../../helpers/evidence.mjs';

test('manifest never hashes itself', () => {
  const files = ['manifest.json', 'findings.json', 'desktop-1440x900/S01_BOOT_EMPTY.png'];
  assert.deepEqual(manifestHashCandidates(files), [
    'findings.json',
    'desktop-1440x900/S01_BOOT_EMPTY.png'
  ]);
});

test('hash candidates are stable and deduplicated', () => {
  assert.deepEqual(
    manifestHashCandidates(['z.json', 'manifest.json', 'a.json', 'manifest.json']),
    ['z.json', 'a.json']
  );
});
