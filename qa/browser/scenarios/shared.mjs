import { DEFAULT_TIMEOUT } from '../helpers/ui.mjs';

const WEATHER_TIMEOUT = 30_000;

export async function text(page, selector) {
  return (await page.locator(selector).textContent({ timeout: DEFAULT_TIMEOUT })).trim();
}

export async function visible(page, selector) {
  return page.locator(selector).isVisible().catch(() => false);
}

export async function attr(page, selector, name) {
  return page.locator(selector).getAttribute(name, { timeout: DEFAULT_TIMEOUT });
}

export async function containsText(page, selector, expected) {
  return (await text(page, selector)).includes(expected);
}

export function isTimeout(error) {
  return error?.name === 'TimeoutError' || /timeout/i.test(error?.message || '');
}

export async function observedStep(recorder, label, action, details = {}) {
  try {
    return await action();
  } catch (error) {
    if (!isTimeout(error)) throw error;
    recorder.check(label, false, {
      ...details,
      error: { name: error.name, message: error.message }
    });
    return null;
  }
}

export function check(recorder, label, condition, details = {}) {
  return recorder.check(label, Boolean(condition), details);
}

export async function waitForRequestFailure(page, predicate) {
  return page.waitForEvent('requestfailed', { predicate, timeout: DEFAULT_TIMEOUT });
}

export async function submitSearchWithoutResponseWait(page, query) {
  const requestPromise = page.waitForRequest(
    (request) => new URL(request.url()).pathname === '/api/resolve',
    { timeout: DEFAULT_TIMEOUT }
  );
  await page.locator('#q').fill(query);
  await page.locator('#search-btn').click();
  return requestPromise;
}

export async function openDetails(page, selector = '#detail-box') {
  const detail = page.locator(selector);
  const open = await detail.evaluate((element) => element.open);
  if (!open) await detail.locator(':scope > summary').click();
  await detail.waitFor({ state: 'visible', timeout: DEFAULT_TIMEOUT });
}

export async function recordLegalState(page, recorder, prefix = 'legal') {
  const headline = await text(page, '#headline');
  const technical = await attr(page, '#legal', 'data-code');
  const coverage = await attr(page, '#coverage', 'data-code');
  recorder.setField('legal_observed', { headline, legal_status: technical, coverage });
  check(recorder, `${prefix}-headline-visible`, headline.length > 0, { actual: headline });
  check(recorder, `${prefix}-technical-status-visible`, Boolean(technical), { actual: technical });
  return { headline, technical, coverage };
}

export async function inspectServiceWorker(page) {
  return page.evaluate(async () => {
    const registration = await navigator.serviceWorker.getRegistration();
    return {
      supported: 'serviceWorker' in navigator,
      registered: Boolean(registration),
      controller: Boolean(navigator.serviceWorker.controller)
    };
  });
}

export async function waitForWeatherResponse(page) {
  try {
    return await page.waitForResponse(
      (response) => new URL(response.url()).hostname === 'api.open-meteo.com',
      { timeout: WEATHER_TIMEOUT }
    );
  } catch {
    return null;
  }
}

export async function readWeatherResponse(response) {
  if (!response) return null;
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  return {
    observed_at: body?.current?.time || null,
    temperature: body?.current?.temperature_2m ?? null,
    request_url: response.url(),
    http_status: response.status()
  };
}
