import { CANONICAL } from './constants.mjs';

const DEFAULT_TIMEOUT = 15_000;

function isPath(response, pathname) {
  try {
    return new URL(response.url()).pathname === pathname;
  } catch {
    return false;
  }
}

async function waitForResolve(page) {
  await page.waitForResponse((response) => isPath(response, '/api/resolve'), {
    timeout: DEFAULT_TIMEOUT
  });
  await waitForLegalHeadline(page);
}

async function waitForMapIdle(page) {
  await page.waitForFunction(
    () => typeof map !== 'undefined' && map && (!map.isMoving || !map.isMoving()),
    undefined,
    { timeout: DEFAULT_TIMEOUT }
  );
}

export async function boot(page) {
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.locator('#map').waitFor({ state: 'visible', timeout: DEFAULT_TIMEOUT });
  await page.waitForFunction(
    () => typeof map !== 'undefined' && map && map.loaded(),
    undefined,
    { timeout: DEFAULT_TIMEOUT }
  );
  await waitForMapIdle(page);
}

export async function waitForMapLayer(page, layerId) {
  await page.waitForFunction(
    (id) => typeof map !== 'undefined' && map && map.getLayer(id),
    layerId,
    { timeout: DEFAULT_TIMEOUT }
  );
}

export async function searchPlace(page, query) {
  const input = page.locator('#q');
  await input.fill(query);
  const resolveResponse = page.waitForResponse(
    (response) => isPath(response, '/api/resolve'),
    { timeout: DEFAULT_TIMEOUT }
  );
  await page.locator('#search-btn').click();
  await resolveResponse;
  await page.locator('#card-result').waitFor({ state: 'visible', timeout: DEFAULT_TIMEOUT });
  await waitForLegalHeadline(page);
  await waitForMapIdle(page);
}

export async function selectCoordinates(page, lat, lon) {
  await searchPlace(page, `${lat}, ${lon}`);
}

export async function waitForLegalHeadline(page) {
  await page.locator('#card-result').waitFor({ state: 'visible', timeout: DEFAULT_TIMEOUT });
  await page.waitForFunction(
    () => Boolean(document.querySelector('#headline')?.textContent?.trim()),
    undefined,
    { timeout: DEFAULT_TIMEOUT }
  );
}

export async function expandSheetFull(page) {
  const handle = page.locator('#sheet-handle');
  if (await handle.isVisible().catch(() => false)) {
    const card = page.locator('#card');
    for (let attempt = 0; attempt < 2; attempt += 1) {
      const classes = await card.getAttribute('class');
      if (classes?.includes('sheet-full')) break;
      await handle.click();
    }
  }
}

export async function openLegalDetail(page) {
  await expandSheetFull(page);
  const detail = page.locator('#detail-box');
  if (!(await detail.evaluate((element) => element.open))) {
    await detail.locator(':scope > summary').click();
  }
  await page.waitForFunction(
    () => document.querySelector('#detail-box')?.open === true,
    undefined,
    { timeout: DEFAULT_TIMEOUT }
  );
}

async function setNumberFact(page, name, value) {
  const input = page.locator(`input[name="${name}"]`);
  await input.waitFor({ state: 'visible', timeout: DEFAULT_TIMEOUT });
  const response = page.waitForResponse(
    (candidate) => isPath(candidate, '/api/resolve'),
    { timeout: DEFAULT_TIMEOUT }
  );
  await input.fill(String(value));
  await input.dispatchEvent('change');
  await response;
  await waitForLegalHeadline(page);
}

export async function enterPicosFacts(page) {
  const activity = page.locator('select#activity');
  await activity.selectOption('VIVAC_AL_RASO');

  const mountain = page.locator('input[name="actividad_montana_o_escalada"]');
  await mountain.waitFor({ state: 'visible', timeout: DEFAULT_TIMEOUT });
  if (!(await mountain.isChecked())) {
    const response = page.waitForResponse(
      (candidate) => isPath(candidate, '/api/resolve'),
      { timeout: DEFAULT_TIMEOUT }
    );
    await mountain.check();
    await response;
    await waitForLegalHeadline(page);
  }

  await setNumberFact(page, 'nights', CANONICAL.picosFacts.nights);
  await setNumberFact(page, 'cota_m', CANONICAL.picosFacts.cota_m);
}

export async function mapClickLngLat(page, lon, lat) {
  const point = await page.evaluate(([longitude, latitude]) => {
    if (typeof map === 'undefined' || !map) {
      throw new Error('HARNESS_ERROR MapLibre map unavailable');
    }
    const pixel = map.project([longitude, latitude]);
    return { x: pixel.x, y: pixel.y };
  }, [lon, lat]);
  const box = await page.locator('#map').boundingBox();
  if (!box) throw new Error('HARNESS_ERROR map bounding box unavailable');
  if (point.x < 0 || point.y < 0 || point.x > box.width || point.y > box.height) {
    throw new Error(`HARNESS_ERROR target outside map viewport: ${lon},${lat}`);
  }
  await page.mouse.click(box.x + point.x, box.y + point.y);
}

export async function saveFavorite(page) {
  await expandSheetFull(page);
  const save = page.locator('#save-btn');
  await save.click();
  await page.waitForFunction(
    () => document.querySelector('#save-btn')?.textContent?.includes('Guardado'),
    undefined,
    { timeout: DEFAULT_TIMEOUT }
  );
}

export async function openSaved(page) {
  await page.locator('[data-tab="saved"]').click();
  await page.locator('#view-saved').waitFor({ state: 'visible', timeout: DEFAULT_TIMEOUT });
}

export async function openOutings(page) {
  await page.locator('[data-tab="outings"]').click();
  await page.locator('#view-outings').waitFor({ state: 'visible', timeout: DEFAULT_TIMEOUT });
}

export async function createOutingFromSelectedPoint(page, { name, date, notes = '' }) {
  await expandSheetFull(page);
  await page.locator('#plan-add-btn').click();
  const overlay = page.locator('#chooser-overlay');
  await overlay.waitFor({ state: 'visible', timeout: DEFAULT_TIMEOUT });
  await page.locator('#chooser-new-name').fill(name);
  await page.locator('#chooser-new-date').fill(date);
  if (notes) {
    // The chooser intentionally has no notes field; notes belong to the full
    // outings form. Keep the argument explicit for scenario readability.
  }
  await page.locator('#chooser-ok-btn').click();
  await overlay.waitFor({ state: 'hidden', timeout: DEFAULT_TIMEOUT });
}

export async function addSelectedPointToExistingOuting(page, { name, date }) {
  await expandSheetFull(page);
  await page.locator('#plan-add-btn').click();
  const overlay = page.locator('#chooser-overlay');
  await overlay.waitFor({ state: 'visible', timeout: DEFAULT_TIMEOUT });
  await page.locator('#chooser-select').selectOption({ label: `${name} (${date})` });
  await page.locator('#chooser-ok-btn').click();
  await overlay.waitFor({ state: 'hidden', timeout: DEFAULT_TIMEOUT });
}

export async function expandOuting(page, name) {
  const row = page.locator('.outing-row').filter({ hasText: name });
  await row.locator('.outing-toggle-btn').click();
  await row.locator('.outing-places').waitFor({ state: 'visible', timeout: DEFAULT_TIMEOUT });
}

export async function selectTab(page, tab) {
  await page.locator(`[data-tab="${tab}"]`).click();
  await page.locator(`#view-${tab}`).waitFor({ state: 'visible', timeout: DEFAULT_TIMEOUT });
}

export { DEFAULT_TIMEOUT };
