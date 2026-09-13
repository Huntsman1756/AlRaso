import test from 'node:test';
import assert from 'node:assert/strict';

import {
  conditionText,
  createLegalController,
  undeterminedExplanation,
  whyText
} from '../../../../webapp/static/modules/legal.js';

const form = {
  activity: { value: 'VIVAC_AL_RASO' },
  date: { value: '2026-09-13' },
  factbox: { querySelectorAll() { return []; } },
  searchMessage: { textContent: '' }
};

test('legal controller has no browser effects until its methods are called', () => {
  const controller = createLegalController({ state: {}, form });
  assert.deepEqual(Object.keys(controller), [
    'refresh',
    'resetLegalResultForPending',
    'renderLegalResolveFailure',
    'render'
  ]);
});

test('legal copy helpers preserve condition and undetermined paths', () => {
  assert.equal(
    conditionText({ ast: { all: [{ field: 'nights', op: 'lte', value: 2 }] }, holds: true }),
    'Se cumplen las condiciones: número de noches ≤ 2.'
  );
  const unknown = {
    determination: { legalStatus: 'UNDETERMINED', reasonCodes: ['NO_APPLICABLE_SCOPE'] },
    coverage: { status: 'UNKNOWN' }
  };
  assert.match(undeterminedExplanation(unknown), /No tenemos una zona normativa verificada/);
  assert.match(whyText({
    determination: { legalStatus: 'PERMITTED', reasonCodes: [] },
    query: { activity: 'VIVAC_AL_RASO' },
    conditions: [],
    applicableScope: []
  }), /permite dormir al raso/);
});
