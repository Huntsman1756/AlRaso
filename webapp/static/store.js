"use strict";
/**
 * AlRasoStore — almacenamiento local para favoritos y salidas.
 * Módulo lógico puro (sin DOM), para que pueda ser inspeccionado offline.
 */
(function (root) {

  var STORAGE_FAVS_KEY = "alraso.favorites.v1";
  var STORAGE_OUTINGS_KEY = "alraso.outings.v1";

  // Shim para localStorage: si no está disponible (private mode), usar en memoria.
  var _storage = (function () {
    try {
      var testKey = "__lr_check__";
      localStorage.setItem(testKey, "1");
      localStorage.removeItem(testKey);
      return localStorage;
    } catch (e) {
      var _mem = {};
      return {
        getItem: function (k) { return _mem[k] !== undefined ? _mem[k] : null; },
        setItem: function (k, v) { _mem[k] = String(v); },
        removeItem: function (k) { delete _mem[k]; },
      };
    }
  })();

  function readJson(key) {
    try {
      var raw = _storage.getItem(key);
      if (raw === null || raw === undefined) return [];
      var parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed;
    } catch (e) {
      return [];
    }
  }

  function writeJson(key, arr) {
    try {
      _storage.setItem(key, JSON.stringify(arr));
      return true;
    } catch (e) {
      return false;
    }
  }

  function _favValid(f) {
    if (!f || typeof f !== "object") return false;
    if (typeof f.id !== "string" || !f.id) return false;
    if (typeof f.name !== "string" || !f.name) return false;
    if (typeof f.lat !== "number" || !isFinite(f.lat) || f.lat < -90 || f.lat > 90) return false;
    if (typeof f.lon !== "number" || !isFinite(f.lon) || f.lon < -180 || f.lon > 180) return false;
    if (f.category !== undefined && typeof f.category !== "string") return false;
    if (f.created_at !== undefined && typeof f.created_at !== "string") return false;
    return true;
  }

  function _outingValid(o) {
    if (!o || typeof o !== "object") return false;
    if (typeof o.id !== "string" || !o.id) return false;
    if (typeof o.name !== "string" || !o.name) return false;
    if (typeof o.date !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(o.date)) return false;
    if (o.status && o.status !== "PLANNED" && o.status !== "COMPLETED") return false;
    if (o.places !== undefined) {
      if (!Array.isArray(o.places)) return false;
    }
    return true;
  }

  function _nowISO() { return new Date().toISOString(); }
  function _uid(prefix) { return prefix + Date.now().toString(36) + Math.random().toString(36).slice(2, 8); }

  var AlRasoStore = {
    // ── Favoritos ──
    favorites: function () {
      return readJson(STORAGE_FAVS_KEY).filter(_favValid);
    },
    addFavorite: function (opts) {
      var fav = {
        id: _uid("fav-"),
        name: opts.name || "Sin nombre",
        lat: Number(opts.lat),
        lon: Number(opts.lon),
        created_at: _nowISO(),
      };
      if (opts.category) fav.category = opts.category;
      var list = AlRasoStore.favorites();
      list.push(fav);
      writeJson(STORAGE_FAVS_KEY, list);
      return fav;
    },
    removeFavorite: function (id) {
      var list = AlRasoStore.favorites().filter(function (f) { return f.id !== id; });
      writeJson(STORAGE_FAVS_KEY, list);
    },
    findFavoriteByPoint: function (lat, lon) {
      var r = 1e-6;
      var list = AlRasoStore.favorites();
      for (var i = 0; i < list.length; i++) {
        var f = list[i];
        if (Math.abs(f.lat - lat) < r && Math.abs(f.lon - lon) < r) return f;
      }
      return null;
    },

    // ── Salidas ──
    outings: function () {
      return readJson(STORAGE_OUTINGS_KEY).filter(_outingValid);
    },
    addOuting: function (opts) {
      var o = {
        id: _uid("out-"),
        name: opts.name || "Nueva salida",
        date: opts.date || new Date().toISOString().slice(0, 10),
        notes: opts.notes || "",
        status: "PLANNED",
        places: [],
        created_at: _nowISO(),
        completed_at: null,
      };
      var list = AlRasoStore.outings();
      list.push(o);
      writeJson(STORAGE_OUTINGS_KEY, list);
      return o;
    },
    addPlaceToOuting: function (outingId, place) {
      var list = AlRasoStore.outings();
      for (var i = 0; i < list.length; i++) {
        if (list[i].id === outingId) {
          // Guard against malformed legacy data missing places array
          if (!Array.isArray(list[i].places)) list[i].places = [];
          // No duplicates por lat/lon redondeado + nombre
          var r = 1e-6;
          var dup = false;
          for (var j = 0; j < list[i].places.length; j++) {
            var p = list[i].places[j];
            if (Math.abs(p.lat - Number(place.lat)) < r &&
                Math.abs(p.lon - Number(place.lon)) < r &&
                p.name === (place.name || "")) {
              dup = true; break;
            }
          }
          if (!dup) {
            list[i].places.push({ lat: Number(place.lat), lon: Number(place.lon), name: place.name || "" });
          }
          writeJson(STORAGE_OUTINGS_KEY, list);
          return list[i];
        }
      }
      return null;
    },
    completeOuting: function (id) {
      var list = AlRasoStore.outings();
      for (var i = 0; i < list.length; i++) {
        if (list[i].id === id) {
          list[i].status = "COMPLETED";
          list[i].completed_at = _nowISO();
          break;
        }
      }
      writeJson(STORAGE_OUTINGS_KEY, list);
    },
    removeOuting: function (id) {
      var list = AlRasoStore.outings().filter(function (o) { return o.id !== id; });
      writeJson(STORAGE_OUTINGS_KEY, list);
    },

    // ── Estadísticas ──
    stats: function () {
      var outings = AlRasoStore.outings();
      return {
        favorites: AlRasoStore.favorites().length,
        planned: outings.filter(function (o) { return o.status === "PLANNED"; }).length,
        completed: outings.filter(function (o) { return o.status === "COMPLETED"; }).length,
      };
    },
  };

  if (typeof window !== "undefined") { window.AlRasoStore = AlRasoStore; }
  if (typeof module !== "undefined" && module.exports) { module.exports = AlRasoStore; }

})(typeof window !== "undefined" ? window : this);