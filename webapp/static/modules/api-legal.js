function getJson(path) {
  return fetch(path).then((response) => response.json());
}

export function resolveLegal(params) {
  return getJson(`/api/resolve?${params.toString()}`);
}

export function fetchCoverage() {
  return getJson('/api/coverage');
}

export function findPlaces(query) {
  return getJson(`/api/find?q=${encodeURIComponent(query)}`);
}

export function fetchPlaces() {
  return getJson('/api/places');
}
