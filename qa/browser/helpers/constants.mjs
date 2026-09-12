export const PRODUCT_COMMIT = '2491d7d5e4e90d380b45c4baee3f2d023008b1a4';
export const BASELINE_NOW = '2026-09-12T07:20:00+02:00';
export const LOCALE = 'es-ES';
export const TIMEZONE = 'Europe/Madrid';
export const DEVICE_SCALE_FACTOR = 1;

export const VIEWPORTS = Object.freeze({
  'desktop-1440x900': { width: 1440, height: 900 },
  'mobile-390x844': { width: 390, height: 844 },
  'mobile-360x800': { width: 360, height: 800 }
});

export const CANONICAL = Object.freeze({
  goriz: { id: 'refugio-goriz', query: 'Refugio de Góriz', lat: 42.6627475, lon: 0.0159801 },
  cares: { id: 'cares-picos', query: 'Garganta de la Cares', lat: 43.17068, lon: -4.80299 },
  unknown: { id: 'control-sin-corpus', lat: 41.9, lon: -2.4 },
  namedPoi: { id: 'node/14014082102', query: 'Camping Liébana', lat: 43.121312, lon: -4.568203 },
  unnamedPoi: { id: 'node/12120014839', lat: 43.213375, lon: -4.982078 },
  ordesaPa: { id: 'pa-ordesa', name: 'Parque Nacional de Ordesa y Monte Perdido', lat: 42.64944, lon: 0.02472 },
  picosFacts: { actividad_montana_o_escalada: true, nights: 2, cota_m: 2400 },
  outing: { name: 'M9 baseline Picos', date: '2026-09-13', notes: '' }
});
