import { $ } from "./dom.js";

// Mobile bottom sheet: closed / peek / full. The map resize remains a
// composition callback so this module owns no map implementation details.
var SHEET_STATES = ["closed", "peek", "full"];

export function createSheetController({ onLayoutChange = function () {} } = {}) {
  var sheetState = "closed";
  var card = null;
  var handle = null;

  function isMobileLayout() {
    return window.matchMedia("(max-width: 820px)").matches;
  }

  function setSheetState(next) {
    if (!isMobileLayout() || SHEET_STATES.indexOf(next) === -1) return;
    sheetState = next;
    SHEET_STATES.forEach(function (s) { card.classList.toggle("sheet-" + s, s === next); });
    if (handle) {
      handle.setAttribute("aria-expanded", next === "closed" ? "false" : "true");
      handle.setAttribute("aria-label", next === "full" ? "Recoger la ficha" : "Desplegar la ficha");
    }
    onLayoutChange();
  }

  function openSheetForSelection() {
    if (!isMobileLayout()) return;
    if (sheetState === "closed") setSheetState("peek");
  }

  function bindSheet() {
    if (typeof document === "undefined") return;
    card = $("card");
    handle = $("sheet-handle");
    if (!card || !handle) return;

    handle.addEventListener("click", function () {
      // Explicit cycle: closed -> peek -> full -> closed (drag never required)
      var i = SHEET_STATES.indexOf(sheetState);
      setSheetState(SHEET_STATES[(i + 1) % SHEET_STATES.length]);
    });

    // OPTIONAL drag: simple vertical delta with fixed snap thresholds.
    var dragStartY = null, dragDelta = 0;
    handle.addEventListener("pointerdown", function (ev) {
      if (!isMobileLayout()) return;
      dragStartY = ev.clientY;
      dragDelta = 0;
      card.style.transition = "none";
      handle.setPointerCapture(ev.pointerId);
    });
    handle.addEventListener("pointermove", function (ev) {
      if (dragStartY === null) return;
      dragDelta = ev.clientY - dragStartY;
      var sheetPeekHeight = parseFloat(getComputedStyle(card).getPropertyValue("--sheet-peek-height")) || 440;
      var base = sheetState === "full" ? 0
        : sheetState === "peek" ? card.offsetHeight - sheetPeekHeight : card.offsetHeight - 44;
      card.style.transform = "translateY(" + Math.max(0, base + dragDelta) + "px)";
    });
    function endDrag() {
      if (dragStartY === null) return;
      card.style.transition = "";
      card.style.transform = "";
      dragStartY = null;
      var order = { closed: 0, peek: 1, full: 2 };
      var i = order[sheetState];
      if (dragDelta > 60 && i > 0) setSheetState(SHEET_STATES[i - 1]);
      else if (dragDelta < -60 && i < SHEET_STATES.length - 1) setSheetState(SHEET_STATES[i + 1]);
      else setSheetState(sheetState); // snap back
      dragDelta = 0;
    }
    handle.addEventListener("pointerup", endDrag);
    handle.addEventListener("pointercancel", endDrag);

    // Escape closes things one level at a time: dropdown -> layers panel -> sheet
    document.addEventListener("keydown", function (ev) {
      if (ev.key !== "Escape" || ev.defaultPrevented) return;
      var suggest = $("suggest");
      if (suggest && !suggest.hidden) return; // dropdown owns this Escape
      var layersPanel = $("layers-panel");
      if (layersPanel && !layersPanel.hasAttribute("hidden")) return; // layers owns this Escape
      if (!isMobileLayout()) return;
      var focusInsideSheet = document.activeElement && card.contains(document.activeElement);
      if (sheetState === "full") setSheetState("peek");
      else if (sheetState === "peek") setSheetState("closed");
      if (focusInsideSheet) handle.focus({ preventScroll: true });
    });
  }

  bindSheet();

  return {
    getState: function () { return sheetState; },
    setSheetState,
    openSheetForSelection
  };
}
