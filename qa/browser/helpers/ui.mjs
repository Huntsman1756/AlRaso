import { CANONICAL } from './constants.mjs';

const DEFAULT_TIMEOUT = 15_000;
const mapHookedPages = new WeakSet();

async function installMapCapture(page) {
  if (mapHookedPages.has(page)) return;
  await page.addInitScript(() => {
    let currentMapLibre = null;

    function wrapMapConstructor(value) {
      if (!value || typeof value.Map !== 'function' || value.Map.__m9HarnessWrapped) {
        return value;
      }
      const OriginalMap = value.Map;
      const WrappedMap = new Proxy(OriginalMap, {
        construct(target, args, newTarget) {
          const instance = Reflect.construct(target, args, newTarget);
          window.__m9HarnessMap = instance;
          return instance;
        }
      });
      Object.defineProperty(WrappedMap, '__m9HarnessWrapped', { value: true });
      value.Map = WrappedMap;
      return value;
    }

    Object.defineProperty(window, 'maplibregl', {
      configurable: true,
      get() { return currentMapLibre; },
      set(value) { currentMapLibre = wrapMapConstructor(value); }
    });
  });
  mapHookedPages.add(page);
}

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
    () => {
      const map = window.__m9HarnessMap;
      return map && (!map.isMoving || !map.isMoving());
    },
    undefined,
    { timeout: DEFAULT_TIMEOUT }
  );
}

export async function boot(page) {
  await installMapCapture(page);
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.locator('#map').waitFor({ state: 'visible', timeout: DEFAULT_TIMEOUT });
  await page.waitForFunction(
    () => {
      const map = window.__m9HarnessMap;
      return Boolean(map && typeof map.loaded === 'function' && map.loaded());
    },
    undefined,
    { timeout: DEFAULT_TIMEOUT }
  );
  await waitForMapIdle(page);
}

export async function waitForMapLayer(page, layerId) {
  await page.waitForFunction(
    (id) => window.__m9HarnessMap?.getLayer(id),
    layerId,
    { timeout: DEFAULT_TIMEOUT }
  );
}

export async function waitForMapLayoutProperty(page, layerId, property, expected) {
  await page.waitForFunction(
    ([id, name, value]) => window.__m9HarnessMap?.getLayoutProperty(id, name) === value,
    [layerId, property, expected],
    { timeout: DEFAULT_TIMEOUT }
  );
}

export async function queryMapRenderedFeatures(page, options) {
  return page.evaluate((query) => window.__m9HarnessMap?.queryRenderedFeatures(query) || [], options);
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
  const query = page.locator('#query-disclosure');
  if (await query.count() && !(await query.evaluate((element) => element.open))) {
    await query.locator(':scope > summary').click();
  }
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
    const map = window.__m9HarnessMap;
    if (!map) {
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
