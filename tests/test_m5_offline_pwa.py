"""M5 Offline PWA: installable shell + resilience of visited resources.

Contract:
- /api/* is NETWORK_ONLY in the service worker (fail-closed legal discipline:
  no stale determination may ever be served from storage)
- provider map resources only from normal navigation (no prefetch/mass
  download: OpenFreeMap ToS)
- explicit bounded, versioned caches (600 tiles / 400 style+sprite+glyph)
- two-signal connectivity banner: no internet != local legal server down
- probe uses the existing /api/config endpoint (no /api/health)
- valid manifest, valid PNG icons, correct MIME types, no new API routes
"""
from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))

import server  # noqa: E402

SW = (ROOT / "webapp" / "static" / "sw.js").read_text(encoding="utf-8")
APP = (ROOT / "webapp" / "static" / "app.js").read_text(encoding="utf-8")
HTML = (ROOT / "webapp" / "static" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "webapp" / "static" / "style.css").read_text(encoding="utf-8")
PY = (ROOT / "webapp" / "server.py").read_text(encoding="utf-8")
MANIFEST = json.loads(
    (ROOT / "webapp" / "static" / "manifest.webmanifest").read_text(encoding="utf-8"))


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"not a PNG: {path}"
    assert data[12:16] == b"IHDR", f"missing IHDR: {path}"
    w, h = struct.unpack(">II", data[16:24])
    return w, h


# ─────────────────────────────────────────────
# P1 — INSTALLABLE
# ─────────────────────────────────────────────

class TestInstallable:
    def test_manifest_fields(self):
        assert MANIFEST["short_name"] == "AlRaso"
        assert MANIFEST["display"] == "standalone"
        assert MANIFEST["start_url"] == "."
        assert MANIFEST["theme_color"] == "#101418"
        assert MANIFEST["background_color"] == "#101418"

    def test_manifest_icons_192_and_512_with_maskable(self):
        sizes = {i["sizes"] for i in MANIFEST["icons"]}
        assert "192x192" in sizes and "512x512" in sizes
        assert any("maskable" in i["purpose"] for i in MANIFEST["icons"])

    def test_html_links_manifest_and_theme_color(self):
        assert 'rel="manifest"' in HTML and "/manifest.webmanifest" in HTML
        assert 'name="theme-color"' in HTML and "content=\"#101418\"" in HTML

    def test_icon_192_valid_png(self):
        assert _png_size(ROOT / "webapp" / "static" / "icon-192.png") == (192, 192)

    def test_icon_512_valid_png(self):
        assert _png_size(ROOT / "webapp" / "static" / "icon-512.png") == (512, 512)

    def test_sw_registration_secure_context_only(self):
        assert "serviceWorker" in APP
        assert "window.isSecureContext" in APP
        assert "data-sw-registered" in APP


# ─────────────────────────────────────────────
# P2 — SERVICE WORKER STRATEGIES
# ─────────────────────────────────────────────

class TestServiceWorkerStrategies:
    def test_api_branch_is_pure_network_only(self):
        # The /api/* branch must return before any storage access exists in it.
        start = SW.find("// 1)")
        end = SW.find("// 2)")
        assert start != -1 and end != -1 and start < end
        branch = SW[start:end]
        assert "if (isApi(url)) return;" in branch
        assert "cache" not in branch.lower(), "the /api branch must not touch any cache"

    def test_no_api_url_is_ever_listed_for_caching(self):
        assert "addAll" in SW
        shell_section = SW[SW.find("var SHELL_URLS"):SW.find("self.addEventListener")]
        assert "/api/" not in shell_section, "shell precache list must not contain API paths"

    def test_no_provider_prefetch_or_hardcoded_tile_urls(self):
        # Only host-based classification; the SW never constructs provider URLs.
        assert "tiles.openfreemap.org" not in SW
        assert "openfreemap.org" in SW  # host classification only
        assert "new Request(" not in SW
        # "prefetch" may appear in explanatory comments, never in executable code
        code_only = "\n".join(l for l in SW.splitlines()
                              if not l.strip().startswith("//"))
        assert "prefetch" not in code_only.lower()

    def test_explicit_bounded_caches(self):
        assert "MAX_MAP_CACHE_ENTRIES = 600" in SW
        assert "MAX_MAP_UI_ENTRIES = 400" in SW
        assert "function trimCache" in SW

    def test_trim_cache_never_runs_without_cap(self):
        # Regression: SWR for the shell passes max=null; a missing guard
        # would make `keys.length - null === keys.length` and wipe the
        # whole shell cache on every refresh (caught by the CDP gate).
        start = SW.find("function trimCache")
        end = SW.find("function staleWhileRevalidate")
        body = SW[start:end]
        assert "if (!max) return Promise.resolve();" in body
        assert body.index("if (!max)") < body.index("caches.open")

    def test_versioned_caches_and_purge_on_activate(self):
        for name in ("alraso-shell-v1", "alraso-map-ui-v1", "alraso-map-tiles-v1"):
            assert name in SW
        assert "caches.delete(k)" in SW

    def test_strategies_present(self):
        assert "function cacheFirst" in SW
        assert "function staleWhileRevalidate" in SW
        assert "mapResourceKind" in SW

    def test_swr_binds_refresh_to_event_lifetime(self):
        # P1 fix: storage mutations must be bound to the FetchEvent lifetime
        # (workbox StaleWhileRevalidate registers fetchAndCache via waitUntil).
        assert "ev.waitUntil(update.catch(function () {}));" in SW
        start = SW.find("function staleWhileRevalidate")
        end = SW.find("function cacheFirst")
        body = SW[start:end]
        assert "ev.waitUntil" in body
        assert body.index("ev.waitUntil") < body.index("return caches.open(cacheName)")

    def test_cachefirst_chains_storage_before_resolving(self):
        # P1 fix: on a miss, cache.put + trim must be part of the promise
        # that resolves the Response (covered by respondWith), never an
        # orphaned fire-and-forget statement.
        start = SW.find("function cacheFirst")
        end = SW.find('self.addEventListener("fetch"')
        assert start != -1 and end != -1 and start < end
        body = SW[start:end]
        assert "return cache.put(ev.request, res.clone())" in body
        put_lines = [l for l in body.splitlines() if "cache.put(ev.request" in l]
        assert put_lines and all("return" in l for l in put_lines), \
            "every cache.put in cacheFirst must be chained into the returned promise"


# ─────────────────────────────────────────────
# P4 — CONNECTIVITY BANNER (two signals, fail-closed)
# ─────────────────────────────────────────────

class TestConnectivityBanner:
    def test_banner_element(self):
        assert 'id="conn-banner"' in HTML
        assert 'role="status"' in HTML

    def test_offline_copy_is_honest(self):
        assert "Sin internet — se muestran recursos cartográficos guardados" in APP
        assert "la verificación jurídica sigue disponible" in APP

    def test_api_down_copy_fail_closed(self):
        assert "Servidor de verificación no disponible" in APP
        assert "no podemos calcular una determinación nueva" in APP

    def test_probe_uses_existing_config_endpoint_and_no_health_route(self):
        assert '"/api/config"' in APP
        assert 'cache: "no-store"' in APP
        assert "/api/health" not in APP + SW + HTML + PY

    def test_online_offline_listeners(self):
        assert 'addEventListener("online"' in APP
        assert 'addEventListener("offline"' in APP

    def test_banner_css_states(self):
        assert ".conn-banner" in CSS
        assert ".conn-banner.offline" in CSS
        assert ".conn-banner.api-down" in CSS


# ─────────────────────────────────────────────
# P6/P7 — SERVER ASSETS + SCOPE
# ─────────────────────────────────────────────

class TestServerServesAssets:
    def test_static_files_registered(self):
        sf = server.STATIC_FILES
        for p in ("/sw.js", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png"):
            assert p in sf, p

    def test_mime_types_correct(self):
        sf = server.STATIC_FILES
        assert "manifest+json" in sf["/manifest.webmanifest"][1]
        assert sf["/sw.js"][1].startswith("text/javascript")
        assert sf["/icon-192.png"][1] == "image/png"
        assert sf["/icon-512.png"][1] == "image/png"

    def test_no_new_api_routes(self):
        paths = re.findall(r'path == "([^"]+)"', PY)
        api = {p for p in paths if p.startswith("/api/")}
        allowed = {"/api/resolve", "/api/pois", "/api/find",
                   "/api/coverage", "/api/config", "/api/places", "/api/protected-areas"}
        assert api == allowed
