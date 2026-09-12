import { CANONICAL } from '../helpers/constants.mjs';
import {
  boot,
  mapClickLngLat,
  openLegalDetail,
  searchPlace,
  selectCoordinates,
  waitForMapLayer
} from '../helpers/ui.mjs';
import {
  check,
  containsText,
  observedStep,
  recordLegalState,
  text,
  visible
} from './shared.mjs';

function isResolve(response) {
  try {
    return new URL(response.url()).pathname === '/api/resolve';
  } catch {
    return false;
  }
}

async function clickMapFeature(page, lon, lat, selector) {
  const response = page.waitForResponse(isResolve, { timeout: 15_000 });
  await mapClickLngLat(page, lon, lat);
  await response;
  await page.locator(selector).waitFor({ state: 'visible', timeout: 15_000 });
}

export const S05_POI_NAMED = {
  id: 'S05_POI_NAMED',
  async run({ page, recorder }) {
    await boot(page);
    const complete = await observedStep(recorder, 'named-poi-search-completes', async () => {
      await searchPlace(page, CANONICAL.namedPoi.query);
      return true;
    });
    if (!complete) return;

    check(recorder, 'named-poi-card-visible', await visible(page, '#poi'));
    const title = await text(page, '#poi-name');
    const meta = await text(page, '#poi-meta');
    check(recorder, 'named-poi-title', title === 'Camping Liébana', { actual: title });
    check(recorder, 'named-poi-icon-visible', (await text(page, '#poi-emoji')).length > 0);
    check(recorder, 'named-poi-id-not-main-ui', !`${title} ${meta}`.includes(CANONICAL.namedPoi.id));

    await observedStep(recorder, 'named-poi-provenance-opens', async () => {
      await page.locator('#poi-srcbox > summary').click();
      await page.locator('#poi-src-details').waitFor({ state: 'visible', timeout: 15_000 });
      return true;
    });
    const provenance = await text(page, '#poi-src-details');
    check(recorder, 'named-poi-source-ref-in-provenance', provenance.includes(CANONICAL.namedPoi.id));
    check(recorder, 'named-poi-legal-cta-enabled', !(await page.locator('#poi-legal-btn').isDisabled()));
  }
};

export const S06_POI_UNNAMED = {
  id: 'S06_POI_UNNAMED',
  async run({ page, recorder }) {
    await boot(page);
    const complete = await observedStep(recorder, 'unnamed-poi-map-centering-completes', async () => {
      await selectCoordinates(page, CANONICAL.unnamedPoi.lat, CANONICAL.unnamedPoi.lon);
      await waitForMapLayer(page, 'poi-icons-camping');
      return true;
    });
    if (!complete) return;

    // The canonical coordinate is inside the protected-area polygon too. Use
    // the real layer toggle so the subsequent pointer click targets the POI
    // symbol rather than the polygon underneath it.
    const protectedToggle = page.locator('#lg-protected');
    if (await protectedToggle.isChecked()) {
      await page.locator('#layers-btn').click();
      await protectedToggle.click();
      await page.waitForFunction(
        () => map.getLayoutProperty('pa-fill', 'visibility') === 'none',
        undefined,
        { timeout: 15_000 }
      );
      await page.locator('#layers-btn').click();
      await page.waitForFunction(
        () => document.querySelector('#layers-panel')?.hasAttribute('hidden'),
        undefined,
        { timeout: 15_000 }
      );
    }

    const clicked = await observedStep(recorder, 'unnamed-poi-click-completes', async () => {
      await clickMapFeature(page, CANONICAL.unnamedPoi.lon, CANONICAL.unnamedPoi.lat, '#poi');
      return true;
    });
    if (!clicked) return;

    const title = await text(page, '#poi-name');
    const meta = await text(page, '#poi-meta');
    const labelFeatures = await page.evaluate((id) => {
      const features = map.queryRenderedFeatures({ layers: ['poi-labels-camping'] });
      return features.filter((feature) => feature.properties?.id === id).map((feature) => feature.properties?.name || null);
    }, CANONICAL.unnamedPoi.id);
    check(recorder, 'unnamed-poi-card-visible', await visible(page, '#poi'));
    check(recorder, 'unnamed-poi-category-title', title === 'Camping sin nombre', { actual: title });
    check(recorder, 'unnamed-poi-source-ref-not-title', !`${title} ${meta}`.includes(CANONICAL.unnamedPoi.id));
    check(recorder, 'unnamed-poi-icon-only-map-label', labelFeatures.length === 0 || labelFeatures.every((name) => !name));

    await observedStep(recorder, 'unnamed-poi-provenance-opens', async () => {
      await page.locator('#poi-srcbox > summary').click();
      await page.locator('#poi-src-details').waitFor({ state: 'visible', timeout: 15_000 });
      return true;
    });
    const provenance = await text(page, '#poi-src-details');
    check(recorder, 'unnamed-poi-source-ref-in-provenance', provenance.includes(CANONICAL.unnamedPoi.id));
  }
};

export const S07_PROTECTED_AREA = {
  id: 'S07_PROTECTED_AREA',
  async run({ page, recorder }) {
    await boot(page);
    const complete = await observedStep(recorder, 'protected-area-map-centering-completes', async () => {
      await selectCoordinates(page, CANONICAL.ordesaPa.lat, CANONICAL.ordesaPa.lon);
      await waitForMapLayer(page, 'pa-fill');
      return true;
    });
    if (!complete) return;

    const clicked = await observedStep(recorder, 'protected-area-click-completes', async () => {
      await clickMapFeature(page, CANONICAL.ordesaPa.lon, CANONICAL.ordesaPa.lat, '#pa-card');
      return true;
    });
    if (!clicked) return;

    const name = await text(page, '#pa-name');
    const note = await text(page, '#pa-note');
    const button = page.locator('#pa-legal-btn');
    const dataLat = Number(await button.getAttribute('data-lat'));
    const dataLon = Number(await button.getAttribute('data-lon'));
    check(recorder, 'protected-area-card-visible', await visible(page, '#pa-card'));
    check(recorder, 'protected-area-name', name === CANONICAL.ordesaPa.name, { actual: name });
    check(recorder, 'protected-area-non-legal-disclaimer', note === 'Referencia cartográfica de OpenStreetMap para contexto visual; el límite mostrado NO es la delimitación legal oficial; no determina el ámbito jurídico de AlRaso.', { actual: note });
    check(recorder, 'protected-area-cta-enabled', !(await button.isDisabled()));
    check(recorder, 'protected-area-cta-coordinates-only', Number.isFinite(dataLat) && Number.isFinite(dataLon));
    recorder.setField('protected_area_cta', { data_lat: dataLat, data_lon: dataLon, name_attribute: await button.getAttribute('data-name') });

    const ctaResolve = await observedStep(recorder, 'protected-area-cta-resolves-coordinates', async () => {
      const response = page.waitForResponse(isResolve, { timeout: 15_000 });
      await button.click();
      return response;
    });
    check(recorder, 'protected-area-cta-no-name-attribute', !(await button.getAttribute('data-name')));
    if (ctaResolve) {
      const url = ctaResolve.url();
      check(recorder, 'protected-area-cta-request-has-coordinates', url.includes('lat=') && url.includes('lon='), { actual: url });
    }
    await openLegalDetail(page).catch(() => {});
    await recordLegalState(page, recorder, 'protected-area-cta-result');
  }
};
