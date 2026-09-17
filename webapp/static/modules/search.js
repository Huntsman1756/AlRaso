import { $, esc } from "./dom.js";
import { fetchPlaces, findPlaces } from "./api-legal.js";

// Search ownership: suggestions, manual/coordinate submit, and onboarding CTA.
// Product selection and POI presentation remain callbacks owned by app.js.
export function createSearchController({ state, onSelectPoint, onRenderPoi }) {
  function relocateExploreCta() {
    var cta = $("explore-cta");
    if (!cta || !window.matchMedia("(max-width: 820px)").matches) return;
    $("map-container").appendChild(cta);
  }

  function initExploreCta() {
    var cta = $("explore-cta");
    if (!cta) return;

    // Notes come from /api/places (single source of truth) — no stale claims here
    var zones = [
      { id: "cares-picos", label: "⛰ Picos de Europa · Cares" },
      { id: "refugio-goriz", label: "🏔 Refugio de Góriz" },
      { id: "pradera-ordesa", label: "🌲 Pradera de Ordesa" },
    ];

    // Fetch /api/places to use real data (no new endpoint)
    fetchPlaces()
      .then(function (data) {
        // Build a lookup from the places API by id
        var placeMap = {};
        (data.places || []).forEach(function (p) {
          placeMap[p.id] = p;
        });

        cta.innerHTML = "";
        zones.forEach(function (z) {
          var place = placeMap[z.id];
          var note = place && place.note ? place.note : "";
          var btn = document.createElement("button");
          btn.type = "button";
          btn.className = "cta-btn";
          btn.innerHTML = '<span class="cta-label">' + esc(z.label) + '</span>' +
            (note ? '<span class="cta-note">' + esc(note) + '</span>' : '');
          btn.setAttribute("aria-label", "Explorar " + z.label);
          btn.addEventListener("click", function () {
            if (place) {
              onSelectPoint(place.lat, place.lon, place.name, true);
            } else {
              // Fresh resolve — use /api/find to look up the zone
              findPlaces(z.label)
                .then(function (f) {
                  if (f.kind === "place" || f.kind === "coords") {
                    onSelectPoint(f.lat, f.lon, f.name || null, true);
                  }
                })
                .catch(function () {});
            }
          });
          // Ensure minimum 44px hit target on mobile (enforced by CSS min-height:44px)
          cta.appendChild(btn);
        });
        cta.removeAttribute("hidden");
      })
      .catch(function () {
        // If fetch fails, keep CTA empty (no crash)
      });
  }

  function initSuggest() {
    var input = $("q");
    var box = $("suggest");
    if (!input || !box) return;
    var places = [];
    var matches = [];
    var active = -1;

    fetchPlaces()
      .then(function (data) { places = (data.places || []).slice(); })
      .catch(function (e) { console.error("places", e); });

    function close() {
      box.hidden = true;
      box.innerHTML = "";
      active = -1;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
    }
    function render(q) {
      var ql = q.trim().toLowerCase();
      matches = places.filter(function (p) {
        var name = typeof p.name === "string" ? p.name : "";
        var note = typeof p.note === "string" ? p.note : "";
        return !ql || name.toLowerCase().indexOf(ql) !== -1 || note.toLowerCase().indexOf(ql) !== -1;
      });
      box.innerHTML = "";
      active = -1;
      matches.forEach(function (p, i) {
        var opt = document.createElement("button");
        opt.type = "button";
        opt.className = "suggest-opt";
        opt.id = "suggest-opt-" + i;
        opt.setAttribute("role", "option");
        opt.setAttribute("aria-selected", "false");
        opt.innerHTML = '<span class="suggest-name">' + esc(p.name) + '</span>' +
          (p.note ? '<span class="suggest-note">' + esc(p.note) + '</span>' : '');
        opt.addEventListener("click", function () { choose(p); });
        box.appendChild(opt);
      });
    }
    function open() {
      render(input.value);
      if (!matches.length) { close(); return; }
      box.hidden = false;
      input.setAttribute("aria-expanded", "true");
    }
    function choose(p) {
      input.value = p.name;
      close();
      onSelectPoint(p.lat, p.lon, p.name, true);
    }
    input.addEventListener("focus", open);
    input.addEventListener("input", open);
    input.addEventListener("keydown", function (ev) {
      var opts = box.querySelectorAll(".suggest-opt");
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        if (box.hidden || !opts.length) return;
        ev.preventDefault();
        var dir = ev.key === "ArrowDown" ? 1 : -1;
        active = (active + dir + opts.length) % opts.length;
        Array.prototype.forEach.call(opts, function (o, i) {
          o.setAttribute("aria-selected", i === active ? "true" : "false");
        });
        input.setAttribute("aria-activedescendant", opts[active].id);
      } else if (ev.key === "Enter") {
        if (!box.hidden && active >= 0 && matches[active]) {
          ev.preventDefault();
          choose(matches[active]);
        }
        // Enter sin opcion activa: submit normal (búsqueda manual o coordenadas)
      } else if (ev.key === "Escape") {
        if (!box.hidden) { ev.preventDefault(); ev.stopPropagation(); close(); }
      }
    });
    document.addEventListener("click", function (ev) {
      if (ev.target.closest && !ev.target.closest("#searchform")) close();
    });
    $("searchform").addEventListener("submit", close);
  }

  function initSubmit() {
    $("searchform").addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var q = $("q").value.trim();
      if (!q) return;
      var f;
      try {
        f = await findPlaces(q);
      } catch (e) {
        $("searchmsg").textContent = "No se pudo consultar la búsqueda.";
        return;
      }
      if (f.kind === "coords") {
        onSelectPoint(f.lat, f.lon, null);
      } else if (f.kind === "place") {
        onSelectPoint(f.lat, f.lon, f.name);
      } else if (f.kind === "poi") {
        onSelectPoint(f.lat, f.lon, f.name, true);
        onRenderPoi(f);
      } else if (f.kind === "ambiguous") {
        $("searchmsg").textContent = "Varias zonas coinciden: " +
          f.matches.map(function (m) { return m.name; }).join(" · ") + ". Concreta la búsqueda.";
      } else {
        $("searchmsg").textContent =
          "Sin coincidencias. Escribe coordenadas «lat, lon» (ej. 42.6627, 0.0160) " +
          "o elige una zona conocida de la lista.";
      }
    });
  }

  function init() {
    relocateExploreCta();
    initExploreCta();
    initSuggest();
    initSubmit();
  }

  return { init };
}
