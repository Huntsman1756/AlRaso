import { $ } from "./dom.js";

// ─────────────────────────────────────────────
// M6: WEATHER CONDITIONS (Open-Meteo, observational outdoor context)
// NOT legal evidence: the resolver never consumes these values.
// - direct browser fetch (CORS), no API key, no new server endpoint
// - one request per point selection (never per refresh)
// - coordinates rounded to 3 decimals (~100 m) for the weather URL only;
//   the legal resolution keeps the original coordinates
// - monotonic request generation guard: a stale response can never render
// - weather is never cached (stale weather is worse than no weather)
// ─────────────────────────────────────────────

export function createWeatherController() {
  var weatherRequestId = 0;
  var weatherAbort = null;

  function load(lat, lon) {
    var block = $("weather-block");
    if (!block || lat === null || lat === undefined) return;
    weatherRequestId += 1;
    var myId = weatherRequestId;
    if (weatherAbort) { try { weatherAbort.abort(); } catch (e) { /* already aborted */ } }
    weatherAbort = typeof AbortController !== "undefined" ? new AbortController() : null;
    // clear previous values immediately: no old data may survive a new selection
    block.hidden = false;
    block.removeAttribute("data-lat");
    block.removeAttribute("data-lon");
    block.innerHTML = "";
    var loading = document.createElement("p");
    loading.className = "weather-loading";
    loading.textContent = "Cargando condiciones…";
    block.appendChild(loading);

    var url = "https://api.open-meteo.com/v1/forecast" +
      "?latitude=" + Number(lat.toFixed(3)) +
      "&longitude=" + Number(lon.toFixed(3)) +
      "&current=temperature_2m,wind_speed_10m,wind_gusts_10m" +
      "&hourly=temperature_2m,precipitation_probability,wind_speed_10m,wind_gusts_10m" +
      "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max" +
      "&timezone=auto&forecast_days=3&wind_speed_unit=kmh";
    fetch(url, { cache: "no-store", signal: weatherAbort ? weatherAbort.signal : undefined })
      .then(function (r) { if (!r.ok) throw new Error("weather_http_" + r.status); return r.json(); })
      .then(function (data) {
        if (myId !== weatherRequestId) return; // stale response: discarded
        renderWeather(block, lat, lon, data);
      })
      .catch(function () {
        if (myId !== weatherRequestId) return; // aborted or superseded
        block.innerHTML = "";
        var p = document.createElement("p");
        p.className = "weather-unavailable";
        p.textContent = "No hay datos meteorológicos disponibles ahora.";
        block.appendChild(p);
      });
  }
  return { load };
}

export function fmtTemp(v) {
  return (v === null || v === undefined) ? "–" : Math.round(v) + "°";
}
export function fmtKmh(v) {
  return (v === null || v === undefined) ? "–" : Math.round(v) + " km/h";
}
export function fmtProb(v) {
  return (v === null || v === undefined) ? "–" : v + "%";
}
export function minOf(arr) {
  var a = (arr || []).filter(function (v) { return v !== null && v !== undefined; });
  return a.length ? Math.min.apply(null, a) : null;
}
export function maxOf(arr) {
  var a = (arr || []).filter(function (v) { return v !== null && v !== undefined; });
  return a.length ? Math.max.apply(null, a) : null;
}
export function nextDayStr(dateStr) {
  var d = new Date(dateStr + "T00:00Z"); d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}
export function prevDayStr(dateStr) {
  var d = new Date(dateStr + "T00:00Z"); d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}
// Current local instant at the location ("YYYY-MM-DDTHH:MM"), string-based
// on utc_offset_seconds - never the browser clock.
export function localNow(data) {
  var off = (data.utc_offset_seconds || 0) * 1000;
  return new Date(Date.now() + off).toISOString().slice(0, 16);
}

// Three following chronological LOCAL periods (06-12, 12-18, 18-06),
// skipping elapsed ones; day shown when the date changes. All time math is
// string-based on the location's local time via utc_offset_seconds.
export function computeWeatherPeriods(data) {
  var hourly = data.hourly || {};
  var times = hourly.time || [];
  if (!times.length) return [];
  var nowLocal = localNow(data);
  var buckets = {}, order = [];
  for (var i = 0; i < times.length; i++) {
    var t = times[i];
    var date = t.slice(0, 10), hh = Number(t.slice(11, 13));
    var bDate, bIdx, bStart, bEnd;
    if (hh >= 6 && hh < 12) {
      bDate = date; bIdx = 0; bStart = date + "T06:00"; bEnd = date + "T12:00";
    } else if (hh >= 12 && hh < 18) {
      bDate = date; bIdx = 1; bStart = date + "T12:00"; bEnd = date + "T18:00";
    } else if (hh >= 18) {
      bDate = date; bIdx = 2; bStart = date + "T18:00"; bEnd = nextDayStr(date) + "T06:00";
    } else {
      bDate = prevDayStr(date); bIdx = 2; bStart = bDate + "T18:00"; bEnd = date + "T06:00";
    }
    if (t <= nowLocal) continue; // past hour: must never enter the current slot
    if (bEnd <= nowLocal) continue; // fully elapsed: skip
    var key = bDate + "#" + bIdx;
    if (!buckets[key]) {
      buckets[key] = { bDate: bDate, bIdx: bIdx, temps: [], rain: [], wind: [], gust: [] };
      order.push(key);
    }
    buckets[key].temps.push(hourly.temperature_2m ? hourly.temperature_2m[i] : null);
    buckets[key].rain.push(hourly.precipitation_probability ? hourly.precipitation_probability[i] : null);
    buckets[key].wind.push(hourly.wind_speed_10m ? hourly.wind_speed_10m[i] : null);
    buckets[key].gust.push(hourly.wind_gusts_10m ? hourly.wind_gusts_10m[i] : null);
  }
  order.sort();
  var today = nowLocal.slice(0, 10);
  var tomorrow = nextDayStr(today);
  return order.slice(0, 3).map(function (key) {
    var b = buckets[key];
    var base = ["por la mañana", "por la tarde", "por la noche"][b.bIdx];
    var label;
    if (b.bDate === today) label = (b.bIdx === 2 ? "Esta " : "") + base;
    else if (b.bDate === tomorrow) label = "Mañana " + base;
    else label = b.bDate.slice(5).replace("-", "/") + " " + base;
    var lo = minOf(b.temps), hi = maxOf(b.temps);
    return {
      label: label,
      temp: fmtTemp(lo) + "/" + fmtTemp(hi),
      rain: fmtProb(maxOf(b.rain)),
      wind: fmtKmh(maxOf(b.wind)) + "/" + fmtKmh(maxOf(b.gust))
    };
  });
}

function renderWeather(block, lat, lon, data) {
  block.innerHTML = "";
  block.setAttribute("data-lat", lat.toFixed(3));
  block.setAttribute("data-lon", lon.toFixed(3));

  var head = document.createElement("p");
  head.className = "weather-head";
  head.innerHTML = '<span class="weather-title"><svg class="ui-icon weather-icon" data-icon="cloud" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6.657 18c-2.572 0 -4.657 -2.007 -4.657 -4.483c0 -2.475 2.085 -4.482 4.657 -4.482c.393 -1.762 1.794 -3.2 3.675 -3.773c1.88 -.572 3.956 -.193 5.444 1c1.488 1.19 2.162 3.007 1.77 4.769h.99c1.913 0 3.464 1.56 3.464 3.486c0 1.927 -1.551 3.487 -3.465 3.487h-11.878"></path></svg><span>Condiciones</span></span><span class="weather-src">Tiempo: ' +
    '<a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a>' +
    ' (CC BY 4.0)</span>';
  block.appendChild(head);

  var cur = data.current || {};
  var now = document.createElement("p");
  now.className = "weather-line";
  now.textContent = "Ahora: " + fmtTemp(cur.temperature_2m) +
    " · viento " + fmtKmh(cur.wind_speed_10m) +
    " · rachas " + fmtKmh(cur.wind_gusts_10m);
  block.appendChild(now);

  var daily = data.daily || {};
  // "Hoy" consumes ONLY the daily index of the current local day: aggregating
  // the whole daily.* arrays would present tomorrow's extremes as today's.
  var di = (daily.time || []).indexOf(localNow(data).slice(0, 10));
  var dailyMin = di >= 0 ? (daily.temperature_2m_min || [])[di] : null;
  var dailyMax = di >= 0 ? (daily.temperature_2m_max || [])[di] : null;
  var dailyProb = di >= 0 ? (daily.precipitation_probability_max || [])[di] : null;
  var today = document.createElement("p");
  today.className = "weather-line";
  today.textContent = "Hoy: " + fmtTemp(dailyMin) +
    " / " + fmtTemp(dailyMax) +
    " · lluvia " + fmtProb(dailyProb);
  block.appendChild(today);

  var forecast = document.createElement("details");
  forecast.id = "weather-forecast";
  forecast.className = "weather-forecast";
  var summary = document.createElement("summary");
  summary.className = "weather-sub";
  summary.textContent = "Próximas 24 h";
  forecast.appendChild(summary);
  block.appendChild(forecast);

  var periods = computeWeatherPeriods(data);
  if (!periods.length) {
    var empty = document.createElement("p");
    empty.className = "weather-line weather-period";
    empty.textContent = "No hay franjas de previsión disponibles.";
    forecast.appendChild(empty);
    return;
  }
  periods.forEach(function (p) {
    var row = document.createElement("p");
    row.className = "weather-line weather-period";
    row.textContent = p.label + ": " + p.temp + " · lluvia " + p.rain +
      " · viento " + p.wind;
    forecast.appendChild(row);
  });
}
