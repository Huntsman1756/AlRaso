function getJson(path) {
  return fetch(path).then((response) => response.json());
}

export function fetchPois() {
  return getJson('/api/pois');
}

export function fetchProtectedAreas() {
  return getJson('/api/protected-areas');
}
