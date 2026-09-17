import test from 'node:test';
import assert from 'node:assert/strict';

import { esc } from '../../../../webapp/static/modules/dom.js';

test('esc neutralizes markup metacharacters', () => {
  assert.equal(
    esc('<img src=x onerror="alert(1)">'),
    '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;'
  );
});

test('esc escapes single quotes for single-quoted attribute contexts', () => {
  assert.equal(esc("a'b"), 'a&#39;b');
});

test('esc escapes ampersands before other entities', () => {
  assert.equal(esc('a & "b"'), 'a &amp; &quot;b&quot;');
});

test('esc tolerates nullish and non-string input', () => {
  assert.equal(esc(null), '');
  assert.equal(esc(undefined), '');
  assert.equal(esc(42), '42');
});
