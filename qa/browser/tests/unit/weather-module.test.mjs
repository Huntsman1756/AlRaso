import test from 'node:test';
import assert from 'node:assert/strict';

import {
  computeWeatherPeriods,
  createWeatherController,
  fmtKmh,
  fmtProb,
  fmtTemp,
  localNow,
  maxOf,
  minOf,
  nextDayStr,
  prevDayStr
} from '../../../../webapp/static/modules/weather.js';

test('weather controller exposes the selection loader without leaking request state', () => {
  const controller = createWeatherController();
  assert.equal(typeof controller.load, 'function');
  assert.equal(Object.prototype.hasOwnProperty.call(controller, 'weatherRequestId'), false);
  assert.equal(Object.prototype.hasOwnProperty.call(controller, 'weatherAbort'), false);
});

test('weather formatting helpers preserve honest empty values and metric units', () => {
  assert.equal(fmtTemp(null), '–');
  assert.equal(fmtTemp(12.6), '13°');
  assert.equal(fmtKmh(undefined), '–');
  assert.equal(fmtKmh(3.6), '4 km/h');
  assert.equal(fmtProb(null), '–');
  assert.equal(fmtProb(40), '40%');
  assert.equal(minOf([null, 8, undefined, 3]), 3);
  assert.equal(maxOf([null, 8, undefined, 3]), 8);
  assert.equal(minOf([]), null);
  assert.equal(maxOf([]), null);
});

test('weather date helpers move by one UTC calendar day', () => {
  assert.equal(nextDayStr('2026-09-13'), '2026-09-14');
  assert.equal(prevDayStr('2026-09-13'), '2026-09-12');
});

test('localNow uses the forecast location offset', () => {
  const originalNow = Date.now;
  Date.now = () => Date.parse('2026-09-13T22:30:00Z');
  try {
    assert.equal(localNow({ utc_offset_seconds: 7200 }), '2026-09-14T00:30');
  } finally {
    Date.now = originalNow;
  }
});

test('period helper skips elapsed hours and returns the next three local buckets', () => {
  const originalNow = Date.now;
  Date.now = () => Date.parse('2026-09-13T10:30:00Z');
  try {
    const data = {
      utc_offset_seconds: 0,
      hourly: {
        time: [
          '2026-09-13T10:00',
          '2026-09-13T11:00',
          '2026-09-13T12:00',
          '2026-09-13T18:00',
          '2026-09-14T06:00'
        ],
        temperature_2m: [1, 2, 3, 4, 5],
        precipitation_probability: [10, 20, 30, 40, 50],
        wind_speed_10m: [1, 2, 3, 4, 5],
        wind_gusts_10m: [2, 3, 4, 5, 6]
      }
    };
    const periods = computeWeatherPeriods(data);
    assert.equal(periods.length, 3);
    assert.equal(periods[0].label, 'por la mañana');
    assert.equal(periods[0].temp, '2°/2°');
    assert.equal(periods[1].label, 'por la tarde');
    assert.equal(periods[2].label, 'Esta por la noche');
  } finally {
    Date.now = originalNow;
  }
});
