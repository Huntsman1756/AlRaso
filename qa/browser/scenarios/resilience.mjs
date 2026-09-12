import { CANONICAL } from '../helpers/constants.mjs';
import {
  boot,
  enterPicosFacts,
  openLegalDetail,
  searchPlace,
  selectCoordinates
} from '../helpers/ui.mjs';
import {
  check,
  inspectServiceWorker,
  observedStep,
  recordLegalState,
  submitSearchWithoutResponseWait,
  text,
  visible,
  waitForRequestFailure
} from './shared.mjs';

function isResolveRequest(request) {
  try {
    return new URL(request.url()).pathname === '/api/resolve';
  } catch {
    return false;
  }
}

function isUnknownResolveRequest(request) {
  try {
    const url = new URL(request.url());
    return isResolveRequest(request)
      && Math.abs(Number(url.searchParams.get('lat')) - CANONICAL.unknown.lat) < 0.000001
      && Math.abs(Number(url.searchParams.get('lon')) - CANONICAL.unknown.lon) < 0.000001;
  } catch {
    return false;
  }
}

export const S12_MOBILE_SHEET = {
  id: 'S12_MOBILE_SHEET',
  async run({ page, recorder, projectName }) {
    await boot(page);
    check(recorder, 'mobile-sheet-map-usable', await visible(page, '#map'));
    check(recorder, 'mobile-sheet-card-usable', await visible(page, '#card'));

    if (projectName === 'desktop-1440x900') {
      recorder.notApplicable('mobile-sheet-states', { reason: 'desktop viewport' });
      return;
    }

    const selected = await observedStep(recorder, 'mobile-sheet-selection-completes', async () => {
      await searchPlace(page, CANONICAL.goriz.query);
      return true;
    });
    if (!selected) return;

    const card = page.locator('#card');
    check(recorder, 'mobile-sheet-starts-peek', (await card.getAttribute('class')).includes('sheet-peek'));
    await page.locator('#sheet-handle').click();
    check(recorder, 'mobile-sheet-reaches-full', (await card.getAttribute('class')).includes('sheet-full'));
    await page.locator('#sheet-handle').click();
    check(recorder, 'mobile-sheet-reaches-closed', (await card.getAttribute('class')).includes('sheet-closed'));
    const box = await page.locator('#map').boundingBox();
    check(recorder, 'mobile-sheet-map-remains-sized', Boolean(box && box.width > 0 && box.height > 0), { actual: box });
  }
};

export const S13_OFFLINE_VISITED = {
  id: 'S13_OFFLINE_VISITED',
  async run({ page, recorder, observer }) {
    await boot(page);
    const prepared = await observedStep(recorder, 'offline-service-worker-preparation', async () => {
      await page.waitForFunction(() => navigator.serviceWorker.ready, undefined, { timeout: 15_000 });
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.waitForFunction(() => navigator.serviceWorker.controller !== null, undefined, { timeout: 15_000 });
      return true;
    });
    if (!prepared) return;

    const beforeOffline = await inspectServiceWorker(page);
    observer.addExpectedAbort('offline_transport', () => true);
    recorder.expectedFault('offline_transport');
    await page.context().setOffline(true);

    const reloaded = await observedStep(recorder, 'offline-shell-reload-completes', async () => {
      await page.reload({ waitUntil: 'domcontentloaded', timeout: 15_000 });
      await page.locator('#map').waitFor({ state: 'visible', timeout: 15_000 });
      return true;
    });
    if (!reloaded) return;

    const afterOffline = await inspectServiceWorker(page);
    const staleWeather = await visible(page, '#weather-block .weather-head');
    const shellText = await text(page, 'body');
    const apiFailures = observer.snapshot().network.failed_requests.filter((request) => request.url.includes('/api/'));
    recorder.setField('offline', {
      controller_before: beforeOffline.controller,
      controller_after: afterOffline.controller,
      api_failures: apiFailures.length,
      stale_weather_visible: staleWeather
    });
    check(recorder, 'offline-service-worker-controls-page', beforeOffline.controller && afterOffline.controller);
    check(recorder, 'offline-shell-visible', shellText.includes('Explorar') && shellText.includes('Buscar'));
    check(recorder, 'offline-api-is-not-presented-as-cached', apiFailures.length > 0);
    check(recorder, 'offline-no-stale-weather', !staleWeather);
  }
};

export const S14_LEGAL_SERVER_DOWN = {
  id: 'S14_LEGAL_SERVER_DOWN',
  async run({ page, recorder, observer }) {
    let abortNextResolve = false;
    await page.route('**/api/resolve?**', async (route) => {
      if (abortNextResolve && isUnknownResolveRequest(route.request())) {
        abortNextResolve = false;
        await route.abort('failed');
        return;
      }
      await route.continue();
    });
    observer.addExpectedAbort('resolve_request_aborted', isResolveRequest);
    recorder.expectedFault('resolve_request_aborted');

    await boot(page);
    const prepared = await observedStep(recorder, 'legal-server-down-previous-result-prepares', async () => {
      await selectCoordinates(page, CANONICAL.cares.lat, CANONICAL.cares.lon);
      await openLegalDetail(page);
      await enterPicosFacts(page);
      await openLegalDetail(page);
      const state = await recordLegalState(page, recorder, 'legal-server-down-previous');
      check(recorder, 'legal-server-down-previous-is-permitted', state.technical === 'PERMITTED', { actual: state.technical });
      return state;
    });
    if (!prepared) return;

    // Allow any UI-triggered refresh from the final fact change to settle
    // before arming the transport fault. The target guard below ensures that
    // only the new unknown-coordinate resolve is interrupted.
    await page.waitForTimeout(500);
    abortNextResolve = true;
    const failedRequest = waitForRequestFailure(page, isResolveRequest);
    await submitSearchWithoutResponseWait(page, `${CANONICAL.unknown.lat}, ${CANONICAL.unknown.lon}`);
    const failed = await observedStep(recorder, 'legal-server-down-transport-aborts', async () => failedRequest);
    await page.waitForTimeout(250);

    const currentHeadline = await text(page, '#headline');
    const currentLegal = await page.locator('#legal').getAttribute('data-code');
    const currentCoords = await text(page, '#coords');
    const newCoordinatesVisible = currentCoords.includes('41.90000') && currentCoords.includes('-2.40000');
    const staleResult = currentLegal === 'PERMITTED' && currentHeadline.includes('Permitido') && !newCoordinatesVisible;
    recorder.setField('legal_server_down', {
      request_failed: Boolean(failed),
      current_headline: currentHeadline,
      current_legal_status: currentLegal,
      current_coordinates: currentCoords,
      stale_result: staleResult
    });
    check(recorder, 'legal-server-down-fault-observed', Boolean(failed));
    check(recorder, 'legal-server-down-does-not-present-stale-result', !staleResult, {
      actual: { headline: currentHeadline, legal_status: currentLegal, coordinates: currentCoords }
    });
    if (staleResult) {
      recorder.addFinding({
        id: 'M9-LEGAL-BOUNDARY-001',
        severity: 'P0',
        area: 'LEGAL_BOUNDARY',
        finding_type: 'DATA_INTEGRITY',
        scenario: 'S14_LEGAL_SERVER_DOWN',
        summary: 'La determinación PERMITTED anterior permanece visible tras fallar el nuevo resolve.',
        evidence: [],
        reproduction: [
          'Resolver Picos con los hechos canónicos hasta obtener PERMITTED.',
          'Armar el aborto del siguiente /api/resolve.',
          'Buscar 41.9, -2.4 y observar la ficha legal.'
        ],
        expected: 'No presentar una determinación anterior como resultado de la nueva coordenada.',
        actual: { headline: currentHeadline, legal_status: currentLegal, coordinates: currentCoords },
        proposed_milestone: 'M9.3',
        blocking_p0: true
      });
      recorder.setField('blocking_p0', true);
    } else {
      recorder.setField('blocking_p0', false);
    }
  }
};
