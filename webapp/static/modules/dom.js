export const $ = (id) => document.getElementById(id);

export function esc(value) {
  return String(value ?? '').replace(/[&<>\"]/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;'
  })[character]);
}
