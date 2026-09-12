import { CANONICAL } from '../helpers/constants.mjs';
import { boot, selectCoordinates } from '../helpers/ui.mjs';
import {
  check,
  classifyWeatherObservation,
  isWeatherUrl,
  matchesCanonicalWeatherCoordinates,
  observedStep,
  readWeatherResponse,
  recordLegalState,
  text,
  visible,
  weatherProbeAssertions,
  waitForWeatherRequest,
  waitForWeatherResponse
} from './shared.mjs';

export const S08_WEATHER_AVAILABLE = {
  id: 'S08_WEATHER_AVAILABLE',
  async run({ page, recorder, observer }) {
    observer.addNonBlockingFailure('open_meteo_external', (request) => isWeatherUrl(request.url()));
    await boot(page);
    const weatherRequest = waitForWeatherRequest(page);
    const weatherResponse = waitForWeatherResponse(page);
    const complete = await observedStep(recorder, 'weather-available-selection-completes', async () => {
      await selectCoordinates(page, CANONICAL.cares.lat, CANONICAL.cares.lon);
      return true;
    });
    if (!complete) return;

    const [request, response] = await Promise.all([weatherRequest, weatherResponse]);
    const network = observer.snapshot().network;
    const failedRequest = network.failed_requests.find((candidate) => isWeatherUrl(candidate.url));
    const requestObserved = Boolean(request || failedRequest);
    const requestUrl = request?.url?.() || failedRequest?.url || null;
    const responseObserved = Boolean(response);
    const responseStatus = response?.status?.() ?? null;
    const status = classifyWeatherObservation({
      requestObserved,
      responseObserved,
      responseStatus,
      requestFailed: Boolean(failedRequest)
    });
    const observed = await readWeatherResponse(response);
    const weatherVisible = await visible(page, '#weather-block');
    const weatherHead = await visible(page, '#weather-block .weather-head');
    const weatherText = await text(page, '#weather-block');
    const weatherUiValid = weatherVisible && weatherHead && weatherText.includes('Open-Meteo');
    const forecast = page.locator('#weather-forecast');
    const forecastExists = await forecast.count() === 1;
    const forecastClosed = forecastExists && !(await forecast.evaluate((element) => element.open));
    check(recorder, 'weather-forecast-collapsed-by-default', forecastClosed);
    if (forecastExists) {
      await forecast.locator(':scope > summary').click();
      check(recorder, 'weather-forecast-expands', await forecast.evaluate((element) => element.open));
      await forecast.locator(':scope > summary').click();
    }
    const canonicalCoordinates = matchesCanonicalWeatherCoordinates(requestUrl, CANONICAL.cares);
    const externalObservation = {
      provider: 'open-meteo',
      request_observed: requestObserved,
      request_url: requestUrl,
      response_observed: responseObserved,
      status,
      response_http_status: responseStatus,
      external_latency_ms: network.responses.find((candidate) => candidate.url === requestUrl)?.duration_ms ?? null,
      ui_structure_valid: weatherUiValid,
      attribution_visible: weatherText.includes('Open-Meteo')
    };
    recorder.setField('external_observation', externalObservation);
    recorder.setField('weather', {
      observed_at: observed?.observed_at || null,
      temperature: observed?.temperature ?? null,
      request_url: requestUrl,
      http_status: responseStatus,
      ui_structure_valid: weatherUiValid
    });
    const legal = await recordLegalState(page, recorder, 'weather-available-legal');
    const assertions = weatherProbeAssertions({
      requestObserved,
      canonicalCoordinates,
      status,
      weatherUiValid,
      legalAvailable: legal.headline.length > 0
    });
    check(recorder, 'weather-request-observed', assertions.request_observed);
    check(recorder, 'weather-canonical-coordinates', assertions.canonical_coordinates);
    check(recorder, 'weather-live-integration-valid', assertions.live_integration_valid);
    check(recorder, 'weather-does-not-hide-legal-result', assertions.legal_result_available);
  }
};

export const S09_WEATHER_UNAVAILABLE = {
  id: 'S09_WEATHER_UNAVAILABLE',
  async run({ page, recorder, observer }) {
    await page.route('https://api.open-meteo.com/**', (route) => route.abort('failed'));
    observer.addExpectedAbort('weather_unavailable', (request) => isWeatherUrl(request.url()));
    recorder.expectedFault('weather_unavailable');
    await boot(page);
    const complete = await observedStep(recorder, 'weather-unavailable-selection-completes', async () => {
      await selectCoordinates(page, CANONICAL.cares.lat, CANONICAL.cares.lon);
      return true;
    });
    if (!complete) return;

    await page.locator('#weather-block .weather-unavailable').waitFor({ state: 'visible', timeout: 15_000 }).catch((error) => {
      if (error?.name === 'TimeoutError') recorder.check('weather-unavailable-copy-visible', false, { error: error.message });
      else throw error;
    });
    const weatherText = await text(page, '#weather-block');
    check(recorder, 'weather-unavailable-copy-visible', weatherText.includes('No hay datos meteorológicos disponibles ahora.'));
    const legal = await recordLegalState(page, recorder, 'weather-unavailable-legal');
    check(recorder, 'weather-unavailable-legal-continues', legal.headline.length > 0);
    const failed = observer.snapshot().network.failed_requests.filter((request) => isWeatherUrl(request.url));
    recorder.setField('weather', {
      observed_at: null,
      temperature: null,
      request_url: failed[0]?.url || null,
      http_status: null,
      ui_structure_valid: weatherText.includes('No hay datos meteorológicos disponibles ahora.')
    });
    check(recorder, 'weather-abort-observed', failed.some((request) => request.expected && request.expected_fault === 'weather_unavailable'));
  }
};
