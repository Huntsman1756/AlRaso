import { CANONICAL } from '../helpers/constants.mjs';
import {
  boot,
  enterPicosFacts,
  openLegalDetail,
  searchPlace,
  selectCoordinates
} from '../helpers/ui.mjs';
import {
  attr,
  check,
  containsText,
  observedStep,
  recordLegalState,
  text,
  visible
} from './shared.mjs';

export const S01_BOOT_EMPTY = {
  id: 'S01_BOOT_EMPTY',
  async run({ page, recorder }) {
    await boot(page);
    check(recorder, 'map-visible', await visible(page, '#map'));
    check(recorder, 'empty-card-visible', await visible(page, '#card-empty'));
    check(recorder, 'result-card-hidden', !(await visible(page, '#card-result')));
    check(recorder, 'no-selected-headline', (await text(page, '#headline')) === '');
    check(recorder, 'body-has-no-selection', !(await page.locator('body').getAttribute('class') || '').includes('has-selection'));
  }
};

export const S02_SEARCH_KNOWN_PLACE = {
  id: 'S02_SEARCH_KNOWN_PLACE',
  async run({ page, recorder }) {
    await boot(page);
    const complete = await observedStep(recorder, 'known-place-search-completes', async () => {
      await searchPlace(page, CANONICAL.goriz.query);
      await openLegalDetail(page);
      return true;
    });
    if (!complete) return;

    const state = await recordLegalState(page, recorder, 'known-place');
    check(recorder, 'known-place-query-retained', (await page.locator('#q').inputValue()) === CANONICAL.goriz.query);
    check(recorder, 'known-place-coordinates-visible', (await text(page, '#coords')).includes('42.66275'));
    check(recorder, 'known-place-result-legal-visible', state.headline.length > 0);
  }
};

export const S03_COORDS_UNKNOWN = {
  id: 'S03_COORDS_UNKNOWN',
  async run({ page, recorder }) {
    await boot(page);
    const complete = await observedStep(recorder, 'unknown-coordinates-search-completes', async () => {
      await selectCoordinates(page, CANONICAL.unknown.lat, CANONICAL.unknown.lon);
      await openLegalDetail(page);
      return true;
    });
    if (!complete) return;

    const state = await recordLegalState(page, recorder, 'unknown-coordinates');
    await observedStep(recorder, 'technical-detail-opens', async () => {
      const tech = page.locator('#tech');
      if (!(await tech.evaluate((element) => element.open))) await tech.locator(':scope > summary').click();
      return true;
    });
    const technicalText = await text(page, '#tech-codes');
    check(recorder, 'unknown-legal-status', state.technical === 'UNDETERMINED', { actual: state.technical });
    check(recorder, 'unknown-coverage-status', state.coverage === 'UNKNOWN', { actual: state.coverage });
    check(recorder, 'unknown-copy-compact', (await text(page, '#answer-explanation')).length > 0);
    check(recorder, 'unknown-technical-coverage', technicalText.includes('coverage=UNKNOWN'));
    recorder.setField('unknown', { legal_status: state.technical, coverage: state.coverage });
  }
};

export const S04_PICOS_PERMITTED = {
  id: 'S04_PICOS_PERMITTED',
  async run({ page, recorder }) {
    await boot(page);
    const complete = await observedStep(recorder, 'picos-initial-search-completes', async () => {
      await selectCoordinates(page, CANONICAL.cares.lat, CANONICAL.cares.lon);
      await openLegalDetail(page);
      return true;
    });
    if (!complete) return;

    const factsComplete = await observedStep(recorder, 'picos-facts-entered', async () => {
      await enterPicosFacts(page);
      await openLegalDetail(page);
      return true;
    });
    if (!factsComplete) return;

    const state = await recordLegalState(page, recorder, 'picos');
    const activity = await page.locator('#activity').inputValue();
    const mountain = await page.locator('input[name="actividad_montana_o_escalada"]').isChecked();
    const nights = await page.locator('input[name="nights"]').inputValue();
    const altitude = await page.locator('input[name="cota_m"]').inputValue();
    const demVisible = await visible(page, '#dem-info');
    recorder.setField('facts', {
      activity,
      actividad_montana_o_escalada: mountain,
      nights,
      cota_m: altitude,
      dem_required: false,
      dem_visible: demVisible
    });
    check(recorder, 'picos-permitted-headline', state.headline.includes('Permitido'), { actual: state.headline });
    check(recorder, 'picos-permitted-technical-status', state.technical === 'PERMITTED', { actual: state.technical });
    check(recorder, 'picos-activity-fact', activity === 'VIVAC_AL_RASO');
    check(recorder, 'picos-mountain-fact', mountain);
    check(recorder, 'picos-nights-fact', nights === String(CANONICAL.picosFacts.nights));
    check(recorder, 'picos-altitude-fact', altitude === String(CANONICAL.picosFacts.cota_m));
  }
};
