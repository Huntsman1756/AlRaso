import { CANONICAL } from '../helpers/constants.mjs';
import { boot, selectCoordinates } from '../helpers/ui.mjs';
import {
  check,
  observedStep,
  readWeatherResponse,
  recordLegalState,
  text,
  visible,
  waitForWeatherResponse
} from './shared.mjs';

function isWeatherUrl(url) {
  try {
    return new URL(url).hostname === 'api.open-meteo.com';
  } catch {
    return false;
  }
}

export const S08_WEATHER_AVAILABLE = {
  id: 'S08_WEATHER_AVAILABLE',
  async run({ page, recorder }) {
    await boot(page);
    const weatherResponse = waitForWeatherResponse(page);
    const complete = await observedStep(recorder, 'weather-available-selection-completes', async () => {
      await selectCoordinates(page, CANONICAL.cares.lat, CANONICAL.cares.lon);
      return true;
    });
    if (!complete) return;

    const response = await weatherResponse;
    const observed = await readWeatherResponse(response);
    const weatherVisible = await visible(page, '#weather-block');
    const weatherHead = await visible(page, '#weather-block .weather-head');
    const weatherText = await text(page, '#weather-block');
    recorder.setField('weather', {
      observed_at: observed?.observed_at || null,
      temperature: observed?.temperature ?? null,
      request_url: observed?.request_url || null,
      http_status: observed?.http_status ?? null,
      ui_structure_valid: weatherVisible && weatherHead && weatherText.includes('Open-Meteo')
    });
    check(recorder, 'weather-response-observed', Boolean(response), {
      actual: { http_status: observed?.http_status ?? null }
    });
    check(recorder, 'weather-http-success', observed?.http_status === 200, { actual: observed?.http_status });
    check(recorder, 'weather-ui-structure-valid', weatherVisible && weatherHead && weatherText.includes('Open-Meteo'));
    const legal = await recordLegalState(page, recorder, 'weather-available-legal');
    check(recorder, 'weather-does-not-hide-legal-result', legal.headline.length > 0);
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
    check(recorder, 'weather-unavailable-copy-visible', weatherText.includes('Sin conexión'));
    const legal = await recordLegalState(page, recorder, 'weather-unavailable-legal');
    check(recorder, 'weather-unavailable-legal-continues', legal.headline.length > 0);
    const failed = observer.snapshot().network.failed_requests.filter((request) => isWeatherUrl(request.url));
    recorder.setField('weather', {
      observed_at: null,
      temperature: null,
      request_url: failed[0]?.url || null,
      http_status: null,
      ui_structure_valid: weatherText.includes('Sin conexión')
    });
    check(recorder, 'weather-abort-observed', failed.some((request) => request.expected && request.expected_fault === 'weather_unavailable'));
  }
};
