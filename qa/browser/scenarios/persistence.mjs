import { CANONICAL } from '../helpers/constants.mjs';
import {
  boot,
  createOutingFromSelectedPoint,
  addSelectedPointToExistingOuting,
  expandOuting,
  openOutings,
  openSaved,
  saveFavorite,
  searchPlace
} from '../helpers/ui.mjs';
import { check, observedStep, text, visible } from './shared.mjs';

export const S10_SAVE_FAVORITE = {
  id: 'S10_SAVE_FAVORITE',
  async run({ page, recorder }) {
    await boot(page);
    const complete = await observedStep(recorder, 'favorite-selection-completes', async () => {
      await searchPlace(page, CANONICAL.goriz.query);
      return true;
    });
    if (!complete) return;

    const saved = await observedStep(recorder, 'favorite-save-completes', async () => {
      await saveFavorite(page);
      await openSaved(page);
      return true;
    });
    if (!saved) return;

    const list = await text(page, '#favorites-list');
    const rows = await page.locator('#favorites-list .fav-row').count();
    check(recorder, 'saved-view-visible', await visible(page, '#view-saved'));
    check(recorder, 'favorite-persisted', list.includes('Refugio de Góriz'), { actual: list });
    check(recorder, 'favorite-count-is-one', rows === 1, { actual: rows });
    recorder.setField('favorite', { name: 'Refugio de Góriz', rows });
  }
};

export const S11_OUTING_FLOW = {
  id: 'S11_OUTING_FLOW',
  async run({ page, recorder }) {
    await boot(page);
    const created = await observedStep(recorder, 'outing-first-point-selection-completes', async () => {
      await searchPlace(page, CANONICAL.cares.query);
      await createOutingFromSelectedPoint(page, CANONICAL.outing);
      return true;
    });
    if (!created) return;

    const added = await observedStep(recorder, 'outing-existing-chooser-add-completes', async () => {
      await searchPlace(page, CANONICAL.goriz.query);
      await addSelectedPointToExistingOuting(page, CANONICAL.outing);
      await openOutings(page);
      await expandOuting(page, CANONICAL.outing.name);
      return true;
    });
    if (!added) return;

    const row = page.locator('.outing-row').filter({ hasText: CANONICAL.outing.name });
    const rowText = await row.textContent();
    const places = row.locator('.outing-place-item');
    const placeText = await places.allTextContents();
    check(recorder, 'outings-view-visible', await visible(page, '#view-outings'));
    check(recorder, 'outing-name-visible', rowText.includes(CANONICAL.outing.name), { actual: rowText });
    check(recorder, 'outing-date-visible', rowText.includes('13/09/2026'), { actual: rowText });
    check(recorder, 'outing-has-two-places', placeText.length === 2, { actual: placeText });
    check(recorder, 'outing-contains-first-place', placeText.some((item) => item.includes('Garganta de la Cares')));
    check(recorder, 'outing-contains-added-place', placeText.some((item) => item.includes('Refugio de Góriz')));
    recorder.setField('outing', { name: CANONICAL.outing.name, date: CANONICAL.outing.date, places: placeText });
  }
};
