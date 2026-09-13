import { $, esc } from "./dom.js";
import { POI_CATS } from "./place.js";

export function formatDate(ds) {
  var parts = ds.split("-");
  return parts[2] + "/" + parts[1] + "/" + parts[0];
}

export function createSavedController({
  store,
  state,
  onSelectPoint,
  showTab,
  onFeedback = function () {},
  onStatsDirty = function () {}
}) {
  function currentPlaceName() {
    return state.selectedName || (state.lat !== null ? "Punto " + state.lat.toFixed(5) + ", " + state.lon.toFixed(5) : "");
  }

  // ─────────────────────────────────────────────
  const selectPoint = onSelectPoint;

  function updateSaveButton() {
    var saveBtn = $("save-btn");
    var planBtn = $("plan-add-btn");
    var hasPoint = state.lat !== null;
    saveBtn.disabled = !hasPoint;
    planBtn.disabled = !hasPoint;
    var saveLabel = saveBtn.querySelector(".button-label");
    if (!hasPoint) {
      if (saveLabel) saveLabel.textContent = "Guardar";
      else saveBtn.textContent = "Guardar";
      return;
    }
    var fav = store.findFavoriteByPoint(state.lat, state.lon);
    if (saveLabel) saveLabel.textContent = fav ? "Guardado" : "Guardar";
    else saveBtn.textContent = fav ? "Guardado" : "Guardar";
  }

  function openChooser() {
    var overlay = $("chooser-overlay");
    overlay.hidden = false;

    if (state.lat === null) {
      $("chooser-no-point").hidden = false;
      $("chooser-content").hidden = true;
    } else {
      $("chooser-no-point").hidden = true;
      $("chooser-content").hidden = false;

      // Populate select with PLANNED outings
      var sel = $("chooser-select");
      sel.innerHTML = "";
      var outings = store.outings().filter(function (o) { return o.status === "PLANNED"; });
      if (outings.length === 0) {
        // No outings, show new form
        $("chooser-new").hidden = false;
        $("chooser-new-name").value = "";
        $("chooser-new-date").value = new Date().toISOString().slice(0, 10);
        sel.parentElement.style.display = "none";
        $("chooser-ok-btn").textContent = "Crear y añadir";
      } else {
        var optDefault = document.createElement("option");
        optDefault.value = "__new__";
        optDefault.textContent = "Crear nueva salida…";
        sel.appendChild(optDefault);
        outings.forEach(function (o) {
          var opt = document.createElement("option");
          opt.value = o.id;
          opt.textContent = o.name + " (" + o.date + ")";
          sel.appendChild(opt);
        });
        sel.style.display = "";
        sel.parentElement.style.display = "";
        // Initialize visibility from current select value (default is "__new__")
        if (sel.value === "__new__") {
          $("chooser-new").hidden = false;
          $("chooser-new-name").value = "";
          $("chooser-new-date").value = new Date().toISOString().slice(0, 10);
        } else {
          $("chooser-new").hidden = true;
        }
        $("chooser-ok-btn").textContent = "Añadir";
      }
    }

    // Focus into dialog
    overlay.querySelector("button, input, select").focus();

    // Add keydown handler for Escape
    overlay._keyHandler = function (ev) {
      if (ev.key === "Escape") { closeChooser(); }
    };
    document.addEventListener("keydown", overlay._keyHandler);

    // Close on backdrop click
    overlay._clickHandler = function (ev) {
      if (ev.target === overlay) closeChooser();
    };
    overlay.addEventListener("click", overlay._clickHandler);
  }

  function closeChooser() {
    var overlay = $("chooser-overlay");
    if (overlay._keyHandler) document.removeEventListener("keydown", overlay._keyHandler);
    if (overlay._clickHandler) overlay.removeEventListener("click", overlay._clickHandler);
    overlay.hidden = true;
  }

  function renderFavorites() {
    var listEl = $("favorites-list");
    var favs = store.favorites();
    if (favs.length === 0) {
      listEl.innerHTML = '<p class="empty-state">Todavía no has guardado ningún sitio.</p>' +
        '<p class="hint">Explora el mapa y pulsa ♡ Guardar en la ficha de un lugar.</p>';
      return;
    }
    listEl.innerHTML = "";
    favs.forEach(function (fav) {
      var row = document.createElement("div");
      row.className = "fav-row";
      var subtitle = fav.category ? POI_CATS[fav.category] ? POI_CATS[fav.category].label : fav.category : fav.lat.toFixed(5) + ", " + fav.lon.toFixed(5);
      row.innerHTML =
        '<div class="fav-info"><span class="fav-name">♥ ' + esc(fav.name) + '</span><span class="fav-sub">' + esc(subtitle) + '</span></div>' +
        '<div class="fav-actions">' +
          '<button class="view-on-map-btn" data-lat="' + fav.lat + '" data-lon="' + fav.lon + '" data-name="' + esc(fav.name) + '">Ver en mapa</button>' +
          '<button class="del-fav-btn" data-id="' + esc(fav.id) + '">Eliminar</button>' +
        '</div>';
      listEl.appendChild(row);
    });

    // Attach events
    listEl.querySelectorAll(".view-on-map-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var lat = parseFloat(btn.dataset.lat);
        var lon = parseFloat(btn.dataset.lon);
        var name = btn.dataset.name;
        showTab("explore");
        selectPoint(lat, lon, name, true);
      });
    });
    listEl.querySelectorAll(".del-fav-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        store.removeFavorite(btn.dataset.id);
        renderFavorites();
        updateSaveButton();
        onStatsDirty();
      });
    });
  }

  // ─────────────────────────────────────────────
  // OUTINGS VIEW RENDER
  // ─────────────────────────────────────────────
  function renderOutings() {
    var listEl = $("outings-list");
    var outings = store.outings();

    if (outings.length === 0) {
      listEl.innerHTML = '<p class="empty-state">Todavía no has preparado ninguna salida.</p>' +
        '<p class="hint">Desde la ficha de un lugar, pulsa "Añadir a una salida" o crea una aquí.</p>';
      return;
    }

    var planned = outings.filter(function (o) { return o.status === "PLANNED"; }).sort(function (a, b) { return a.date.localeCompare(b.date); });
    var completed = outings.filter(function (o) { return o.status === "COMPLETED"; });

    var html = "";

    if (planned.length > 0) {
      html += '<h3>Próximas</h3>';
      planned.forEach(function (o) { html += outingRow(o); });
    }

    if (completed.length > 0) {
      html += '<h3>Realizadas</h3>';
      completed.forEach(function (o) { html += outingRow(o); });
    }

    listEl.innerHTML = html;

    // Attach events
    listEl.querySelectorAll(".outing-toggle-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.dataset.id;
        var row = btn.closest(".outing-row");
        var placesDiv = row.querySelector(".outing-places");
        if (placesDiv.style.display === "block") {
          placesDiv.style.display = "none";
          btn.textContent = "Ver";
        } else {
          renderOutingPlaces(row, id);
          placesDiv.style.display = "block";
          btn.textContent = "Ocultar";
        }
      });
    });
    listEl.querySelectorAll(".outing-view-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var lat = parseFloat(btn.dataset.lat);
        var lon = parseFloat(btn.dataset.lon);
        var name = btn.dataset.name;
        showTab("explore");
        selectPoint(lat, lon, name, true);
      });
    });
    listEl.querySelectorAll(".outing-complete-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        store.completeOuting(btn.dataset.id);
        renderOutings();
        onStatsDirty();
      });
    });
    listEl.querySelectorAll(".outing-del-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        store.removeOuting(btn.dataset.id);
        renderOutings();
        onStatsDirty();
      });
    });
  }

  function outingRow(o) {
    var statusLabel = o.status === "COMPLETED" ? " · realizada ✓" : "";
    var placeCount = (o.places || []).length;
    var notesHtml = o.notes ? '<span class="outing-notes">' + esc(o.notes) + '</span>' : '';
    return '<div class="outing-row" data-outing-id="' + esc(o.id) + '">' +
      '<div class="outing-info">' +
        '<span class="outing-name">' + esc(o.name) + '</span>' +
        ' · ' + formatDate(o.date) +
        ' · ' + placeCount + ' lugar' + (placeCount !== 1 ? 'es' : '') +
        statusLabel +
        notesHtml +
      '</div>' +
      '<div class="outing-actions">' +
        '<button class="outing-toggle-btn" data-id="' + esc(o.id) + '">Ver</button>' +
        (o.status === "PLANNED" ? '<button class="outing-complete-btn" data-id="' + esc(o.id) + '">Marcar realizada</button>' : '') +
        '<button class="outing-del-btn" data-id="' + esc(o.id) + '">Eliminar</button>' +
      '</div>' +
      '<div class="outing-places" style="display:none"></div>' +
    '</div>';
  }

  function renderOutingPlaces(row, outingId) {
    var placesDiv = row.querySelector(".outing-places");
    var outings = store.outings();
    var outing = null;
    for (var i = 0; i < outings.length; i++) {
      if (outings[i].id === outingId) { outing = outings[i]; break; }
    }
    if (!outing || !outing.places || outing.places.length === 0) {
      placesDiv.innerHTML = '<p class="empty-state">Sin lugares en esta salida.</p>';
      return;
    }
    placesDiv.innerHTML = "";
    outing.places.forEach(function (p) {
      var div = document.createElement("div");
      div.className = "outing-place-item";
      div.innerHTML = '<span>' + esc(p.name || p.lat.toFixed(5) + ", " + p.lon.toFixed(5)) + '</span>' +
        '<button class="outing-view-btn" data-lat="' + p.lat + '" data-lon="' + p.lon + '" data-name="' + esc(p.name || '') + '">Ver en mapa</button>';
      placesDiv.appendChild(div);
    });
  }

  // ─────────────────────────────────────────────

  function updateStats() {
    var s = store.stats();
    $("stat-favorites").textContent = s.favorites;
    $("stat-planned").textContent = s.planned;
    $("stat-completed").textContent = s.completed;
  }

  function initChooser() {
  $("save-btn").addEventListener("click", function () {
    if (state.lat === null) return;
    var name = state.selectedName || "Punto guardado";
    var fav = store.findFavoriteByPoint(state.lat, state.lon);
    if (fav) {
      store.removeFavorite(fav.id);
      onFeedback("Lugar eliminado de Guardados.");
    } else {
      store.addFavorite({ name: name, lat: state.lat, lon: state.lon, category: state.poiCategory || undefined });
      onFeedback("Lugar guardado en Guardados.");
    }
    updateSaveButton();
    onStatsDirty();
  });

  // ─────────────────────────────────────────────
  // PLAN ADD BUTTON + CHOOSER MODAL
  // ─────────────────────────────────────────────

  var _planAddTrigger = null;

  $("plan-add-btn").addEventListener("click", function () {
    if (state.lat === null) return;
    openChooser();
  });

  $("chooser-close").addEventListener("click", closeChooser);

  $("chooser-select").addEventListener("change", function () {
    if (this.value === "__new__") {
      $("chooser-new").hidden = false;
      $("chooser-new-name").value = "";
      $("chooser-new-date").value = new Date().toISOString().slice(0, 10);
    } else {
      $("chooser-new").hidden = true;
    }
  });

  $("chooser-ok-btn").addEventListener("click", function () {
    if (state.lat === null) return;
    var sel = $("chooser-select");
    var val = sel.value;

    if (val === "__new__" || $("chooser-new").hidden === false) {
      // Create new outing then add place
      var oName = $("chooser-new-name").value.trim() || "Nueva salida";
      var date = $("chooser-new-date").value || new Date().toISOString().slice(0, 10);
      var outing = store.addOuting({ name: oName, date: date });
      store.addPlaceToOuting(outing.id, { lat: state.lat, lon: state.lon, name: currentPlaceName() });
      onFeedback("Lugar añadido a la salida «" + esc(oName) + "».");
    } else if (val && val !== "__new__") {
      // Add to existing outing
      var outings = store.outings();
      var chosen = null;
      for (var i = 0; i < outings.length; i++) { if (outings[i].id === val) { chosen = outings[i]; break; } }
      store.addPlaceToOuting(val, { lat: state.lat, lon: state.lon, name: currentPlaceName() });
      onFeedback(chosen ? "Lugar añadido a la salida «" + esc(chosen.name) + "»." : "Lugar añadido a la salida.");
    }
    closeChooser();
  });

  // ─────────────────────────────────────────────

  // NEW OUTING FORM
  // ─────────────────────────────────────────────
  $("new-outing-btn").addEventListener("click", function () {
    $("outing-form").hidden = false;
    $("outing-name").value = "";
    $("outing-date").value = new Date().toISOString().slice(0, 10);
    $("outing-notes").value = "";
    $("outing-name").focus();
  });

  $("outing-cancel-btn").addEventListener("click", function () {
    $("outing-form").hidden = true;
  });

  $("outing-confirm-btn").addEventListener("click", function () {
    var name = $("outing-name").value.trim();
    var date = $("outing-date").value;
    var notes = $("outing-notes").value.trim();
    if (!name) { $("outing-name").focus(); return; }
    store.addOuting({ name: name, date: date, notes: notes });
    $("outing-form").hidden = true;
    onFeedback("Salida creada.");
    renderOutings();
    onStatsDirty();
  });

  // ─────────────────────────────────────────────
  // PROFILE STATS
  // ─────────────────────────────────────────────
  }

  return { renderFavorites, renderOutings, updateStats, updateSaveButton, initChooser };
}
