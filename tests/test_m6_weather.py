"""M6 Weather conditions: Open-Meteo as observational outdoor context.

Contract:
- weather is NOT legal evidence: it lives after the legal section, while the
  resolver and legal semantics remain untouched
- direct browser fetch to api.open-meteo.com: no API key, no new endpoint,
  one request per point selection (never per refresh)
- coordinates rounded to 3 decimals (~100 m) for the weather URL only
- monotonic request generation guard + AbortController: a stale response
  can never render
- honest states: loading / no-connection copy; no stale values without
  label; visible CC BY 4.0 attribution linking Open-Meteo
- service worker untouched: api.open-meteo.com stays in the pass-through
  branch; caching weather is forbidden
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))

import server  # noqa: E402

APP = (ROOT / "webapp" / "static" / "app.js").read_text(encoding="utf-8")
HTML = (ROOT / "webapp" / "static" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "webapp" / "static" / "style.css").read_text(encoding="utf-8")
SW = (ROOT / "webapp" / "static" / "sw.js").read_text(encoding="utf-8")
PY = (ROOT / "webapp" / "server.py").read_text(encoding="utf-8")


# ─────────────────────────────────────────────
# F1 — LOCATION IN THE CARD HIERARCHY
# ─────────────────────────────────────────────

class TestWeatherBlockLocation:
    def test_block_exists_hidden_by_default(self):
        assert 'id="weather-block"' in HTML
        match = re.search(r'<div id="weather-block"[^>]*>', HTML)
        assert match and "hidden" in match.group(0)

    def test_block_after_legal_section(self):
        block_idx = HTML.find('id="weather-block"')
        legal_idx = HTML.find('id="legal-section"')
        assert 0 < legal_idx < block_idx, \
            "weather block must follow the legal section"

    def test_altitude_line_still_before_block(self):
        alt_idx = HTML.find('id="altitude-line"')
        block_idx = HTML.find('id="weather-block"')
        assert 0 < alt_idx < block_idx

    def test_css_present(self):
        assert ".weather-block" in CSS
        assert ".weather-unavailable" in CSS


# ─────────────────────────────────────────────
# F2 — FETCH MODEL
# ─────────────────────────────────────────────

class TestWeatherFetchModel:
    def test_direct_open_meteo_url_no_key(self):
        assert "https://api.open-meteo.com/v1/forecast" in APP
        # no API key parameters anywhere in the URL construction
        assert "appid=" not in APP and "&key=" not in APP and "apikey" not in APP.lower()

    def test_coordinates_rounded_to_3_decimals(self):
        # privacy: weather URL uses ~100 m precision only
        assert "lat.toFixed(3)" in APP
        assert "lon.toFixed(3)" in APP

    def test_one_request_per_selection_not_per_refresh(self):
        assert "loadWeather(lat, lon);" in APP
        # selectPoint flow calls it; refresh() must not
        refresh_start = APP.find("function refresh(")
        assert refresh_start != -1
        refresh_body = APP[refresh_start:APP.find("\nfunction ", refresh_start + 10)]
        assert "loadWeather" not in refresh_body, \
            "weather must not be re-fetched on facts/activity changes"
        select_start = APP.find("function selectPoint(")
        select_body = APP[select_start:APP.find("\nfunction ", select_start + 10)]
        assert "loadWeather" in select_body

    def test_monotonic_generation_guard(self):
        assert "weatherRequestId" in APP
        assert "myId !== weatherRequestId" in APP

    def test_abort_previous_request(self):
        assert "weatherAbort" in APP
        assert "weatherAbort.abort()" in APP

    def test_timezone_auto_and_metric(self):
        assert "timezone=auto" in APP
        assert "wind_speed_unit=kmh" in APP


# ─────────────────────────────────────────────
# F1/F3 — CHRONOLOGICAL PERIODS + SW PASS-THROUGH
# ─────────────────────────────────────────────

class TestChronologicalPeriods:
    def test_three_period_buckets(self):
        for h in ("06:00", "12:00", "18:00"):
            assert f'T{h}' in APP

    def test_labels_use_local_chronology(self):
        assert '"Esta "' in APP and '"Mañana "' in APP
        assert "por la mañana" in APP and "por la tarde" in APP and "por la noche" in APP

    def test_utc_offset_used_not_browser_clock(self):
        assert "utc_offset_seconds" in APP
        assert "nowLocal" in APP

    def test_elapsed_periods_skipped(self):
        assert "bEnd <= nowLocal" in APP

    def test_daily_wind_is_not_presented_as_current(self):
        # Ahora block only uses data.current; daily max stays in the daily line
        current_slice = APP[APP.find("var cur = data.current"):APP.find("var daily = data.daily")]
        assert "cur.wind_speed_10m" in current_slice
        assert "wind_speed_10m_max" not in current_slice


# ─────────────────────────────────────────────
# P1 REGRESSIONS — review 2026-09-09 (HEAD b62ff4b)
# ─────────────────────────────────────────────

class TestP1_1_HoyOnlyCurrentLocalDay:
    """Fixture A: today modest, tomorrow/day-after deliberately larger.

    'Hoy' must consume ONLY the daily index of the current local day:
    aggregating the whole daily.* arrays would present tomorrow's extremes
    as today's."""

    def _hoy_slice(self):
        start = APP.find("var daily = data.daily")
        end = APP.find("var periods = computeWeatherPeriods", start)
        assert 0 < start < end
        return APP[start:end]

    def test_current_local_day_located_by_index(self):
        slice_ = self._hoy_slice()
        # index lookup over daily.time, keyed by the location's local date
        # (utc_offset_seconds), never the browser timezone
        assert "(daily.time || []).indexOf(localNow(data).slice(0, 10))" in slice_

    def test_no_whole_array_daily_aggregation(self):
        slice_ = self._hoy_slice()
        for banned in ("minOf(daily.", "maxOf(daily."):
            assert banned not in slice_, \
                f"{banned} aggregates the 3 forecast days into 'Hoy'"

    def test_daily_arrays_indexed_by_current_day(self):
        slice_ = self._hoy_slice()
        for arr in ("temperature_2m_min", "temperature_2m_max",
                    "precipitation_probability_max"):
            assert f"(daily.{arr} || [])[di]" in slice_, arr

    def test_absent_day_is_honest_dash_not_neighbour_values(self):
        # di < 0 (current day missing from daily.time) must yield null -> "–",
        # never a neighbouring day's values
        slice_ = self._hoy_slice()
        assert slice_.count("di >= 0 ?") == 3


class TestP1_2_CurrentSlotExcludesPastHours:
    """Fixture B: an already-elapsed hour with high rain/wind, future hours
    low. The current slot must never absorb past hours: at 17:30 the 12-18
    bucket may only contain hours after 17:30 (before the fix, the whole
    12:00-16:00 range leaked into 'Próximas 24 h')."""

    def _periods_body(self):
        start = APP.find("function computeWeatherPeriods(")
        return APP[start:APP.find("\nfunction ", start + 10)]

    def test_past_hour_guard_present(self):
        assert "if (t <= nowLocal) continue;" in self._periods_body()

    def test_guard_runs_before_hour_accumulation(self):
        body = self._periods_body()
        guard = body.find("if (t <= nowLocal) continue;")
        acc = body.find("buckets[key].temps.push")
        assert 0 <= guard < acc, "past-hour guard must run before accumulation"

    def test_bucket_created_only_from_surviving_hours(self):
        # the guard 'continue's per hour, before the bucket key exists: an
        # hour whose slot is current-but-past can never open a bucket
        body = self._periods_body()
        guard = body.find("if (t <= nowLocal) continue;")
        key = body.find("var key = bDate")
        assert 0 <= guard < key

    def test_elapsed_bucket_skip_kept(self):
        # fully elapsed buckets are still skipped wholesale
        assert "if (bEnd <= nowLocal) continue;" in self._periods_body()


class TestServiceWorkerUntouched:
    def test_sw_has_no_open_meteo_rule(self):
        assert "open-meteo" not in SW, \
            "weather must fall through the existing other-host branch; no SW change expected"

    def test_weather_never_cached_by_shell_precache(self):
        assert "open-meteo" not in SW


# ─────────────────────────────────────────────
# F4 — HONEST STATES + ATTRIBUTION
# ─────────────────────────────────────────────

class TestHonestStates:
    def test_loading_state_cleared_per_selection(self):
        assert '"Cargando condiciones…"' in APP
        assert 'block.removeAttribute("data-lat")' in APP

    def test_no_connection_copy_exact(self):
        assert "No hay datos meteorológicos disponibles ahora." in APP

    def test_stale_response_discarded(self):
        assert "stale response: discarded" in APP

    def test_attribution_visible_with_link(self):
        assert "CC BY 4.0" in APP
        assert 'href="https://open-meteo.com/"' in APP

    def test_no_snow_or_freezing_science(self):
        for banned in ("snow", "freezing", "snowfall"):
            assert banned not in APP.lower(), banned


# ─────────────────────────────────────────────
# F6 — SCOPE
# ─────────────────────────────────────────────

class TestScope:
    def test_no_new_api_routes(self):
        paths = re.findall(r'path == "([^"]+)"', PY)
        api = {p for p in paths if p.startswith("/api/")}
        allowed = {"/api/resolve", "/api/pois", "/api/find",
                   "/api/coverage", "/api/config", "/api/places", "/api/protected-areas"}
        assert api == allowed

    def test_resolver_never_consumes_weather(self):
        # the only weather->something flow is rendering; resolver imports none
        assert "weather" not in (ROOT / "alraso" / "resolver.py").read_text(encoding="utf-8").lower()

    def test_whitelist_includes_m6_test_file(self):
        m2b = (ROOT / "tests" / "test_m2b_official_boundary.py").read_text(encoding="utf-8")
        assert '"tests/test_m6_weather.py"' in m2b

    def test_js_syntax_resources(self):
        # loadWeather/renderWeather are globals callable from the selection flow
        assert "function loadWeather(" in APP
        assert "function renderWeather(" in APP
        assert "function computeWeatherPeriods(" in APP
