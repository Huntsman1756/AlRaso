import { $ } from "./dom.js";

// M5: PWA + OFFLINE RESILIENCE (installable shell, two-signal connectivity UI)
// Two different failures must never be conflated:
//   - no internet/map tiles (remote cartography unreachable)
//   - local legal server down (no NEW determination can be computed: fail-closed)
// The probe reuses the existing /api/config endpoint; no extra health route is added.

export function createConnectivityController() {
  var banner = null;
  var apiOk = null; // null = unknown yet, true/false = last probe result

  function setBanner() {
    if (!banner) return;
    if (apiOk === false) {
      banner.textContent = "Servidor de verificación no disponible — no podemos calcular una determinación nueva.";
      banner.className = "conn-banner api-down";
      banner.hidden = false;
    } else if (navigator.onLine === false) {
      banner.textContent = "Sin internet — se muestran recursos cartográficos guardados; la verificación jurídica sigue disponible mientras el servidor local responda.";
      banner.className = "conn-banner offline";
      banner.hidden = false;
    } else {
      banner.hidden = true;
    }
  }

  function probeApi() {
    if (typeof AbortController === "undefined") return;
    var ctl = new AbortController();
    var timer = setTimeout(function () { ctl.abort(); }, 4000);
    fetch("/api/config", { cache: "no-store", signal: ctl.signal })
      .then(function (r) { apiOk = r.ok; })
      .catch(function () { apiOk = false; })
      .then(function () { clearTimeout(timer); setBanner(); });
  }

  function init() {
    banner = $("conn-banner");
    var swSupported = "serviceWorker" in navigator && window.isSecureContext === true;
    document.body.setAttribute("data-sw-supported", swSupported ? "1" : "0");

    if (swSupported) {
      navigator.serviceWorker.register("/sw.js").then(function () {
        document.body.setAttribute("data-sw-registered", "1");
      }).catch(function () {
        document.body.setAttribute("data-sw-registered", "0");
      });
    } else {
      document.body.setAttribute("data-sw-registered", "0");
    }

    window.addEventListener("online", probeApi);
    window.addEventListener("offline", setBanner);
    probeApi();
    setInterval(probeApi, 30000);
  }

  return { init };
}
