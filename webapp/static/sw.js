// AlRaso service worker (M5) — no dependencies, no build step.
//
// Strategy contract (M5_GATE):
//   - shell (same-origin static): precached on install, stale-while-revalidate
//   - /api/*: NETWORK_ONLY — never stored, never served from storage
//     (fail-closed; the legal server runs locally and keeps working offline)
//   - OpenFreeMap style/sprite/glyph (visited by normal navigation):
//     stale-while-revalidate in MAP_UI_CACHE
//   - OpenFreeMap tiles (visited by normal navigation):
//     cache-first in MAP_TILES_CACHE with an explicit FIFO cap
//   - NO prefetch or mass download of any provider resource (OpenFreeMap ToS)
var SHELL_CACHE = "alraso-shell-v1";
var MAP_UI_CACHE = "alraso-map-ui-v1";
var MAP_TILES_CACHE = "alraso-map-tiles-v1";
var MAX_MAP_UI_ENTRIES = 400;
var MAX_MAP_CACHE_ENTRIES = 600; // explicit operational cap for tiles

var SHELL_URLS = [
  "/", "/index.html", "/style.css", "/app.js", "/store.js",
  "/vendor/maplibre-gl.js", "/vendor/maplibre-gl.css",
  "/manifest.webmanifest", "/icon-192.png", "/icon-512.png"
];

self.addEventListener("install", function (ev) {
  ev.waitUntil(
    caches.open(SHELL_CACHE).then(function (cache) { return cache.addAll(SHELL_URLS); })
  );
});

self.addEventListener("activate", function (ev) {
  var keep = [SHELL_CACHE, MAP_UI_CACHE, MAP_TILES_CACHE];
  ev.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) {
        return keep.indexOf(k) === -1 ? caches.delete(k) : null;
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

function isApi(url) {
  return url.origin === self.location.origin && url.pathname.indexOf("/api/") === 0;
}

// Classify OpenFreeMap resources already requested by normal navigation.
function mapResourceKind(url) {
  if (url.host.indexOf("openfreemap.org") === -1) return null;
  var p = url.pathname;
  if (p.indexOf("/styles/") !== -1) return "style";
  if (p.indexOf("sprite") !== -1) return "sprite";
  if (p.indexOf("/fonts/") !== -1) return "glyph";
  return "tile";
}

function trimCache(cacheName, max) {
  return caches.open(cacheName).then(function (cache) {
    return cache.keys().then(function (keys) {
      var excess = keys.length - max;
      var jobs = [];
      for (var i = 0; i < excess; i++) jobs.push(cache.delete(keys[i])); // FIFO
      return Promise.all(jobs);
    });
  });
}

function staleWhileRevalidate(ev, cacheName, max) {
  return caches.open(cacheName).then(function (cache) {
    return cache.match(ev.request).then(function (hit) {
      var network = fetch(ev.request).then(function (res) {
        if (res && res.ok) {
          return Promise.all([
            cache.put(ev.request, res.clone()),
            max ? trimCache(cacheName, max) : Promise.resolve()
          ]).then(function () { return res; });
        }
        return res;
      }).catch(function () { return null; });
      if (hit) return hit; // serve the stored copy now, refresh in background
      return network.then(function (res) { return res || Response.error(); });
    });
  });
}

function cacheFirst(ev, cacheName, max) {
  return caches.open(cacheName).then(function (cache) {
    return cache.match(ev.request).then(function (hit) {
      if (hit) return hit;
      return fetch(ev.request).then(function (res) {
        if (res && res.ok) {
          cache.put(ev.request, res.clone())
            .then(function () { return trimCache(cacheName, max); });
        }
        return res;
      });
    });
  });
}

self.addEventListener("fetch", function (ev) {
  var req = ev.request;
  if (req.method !== "GET") return; // non-GET: network only
  var url = new URL(req.url);

  // 1) /api/* → NETWORK_ONLY, sin excepción: una determinación jurídica rancia
  //    sería una conclusión incorrecta. Nunca se sirve desde almacenamiento.
  if (isApi(url)) return;

  // 2) Same-origin shell/static → stale-while-revalidate
  if (url.origin === self.location.origin) {
    ev.respondWith(staleWhileRevalidate(ev, SHELL_CACHE, null));
    return;
  }

  // 3) OpenFreeMap resources already requested by normal navigation (no prefetch)
  var kind = mapResourceKind(url);
  if (kind === "tile") {
    ev.respondWith(cacheFirst(ev, MAP_TILES_CACHE, MAX_MAP_CACHE_ENTRIES));
    return;
  }
  if (kind) {
    ev.respondWith(staleWhileRevalidate(ev, MAP_UI_CACHE, MAX_MAP_UI_ENTRIES));
    return;
  }

  // 4) Any other host: pass through untouched
});
