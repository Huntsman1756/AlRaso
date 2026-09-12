const VOLATILE_KEYS = new Set([
  'generated_at',
  'scenario_duration_ms',
  'duration_ms',
  'request_duration_ms',
  'timing_ms',
  'timings_ms'
]);

const EXTERNAL_WEATHER_OUTCOME_KEYS = new Set([
  'status',
  'response_observed',
  'response_http_status',
  'external_latency_ms',
  'ui_structure_valid',
  'attribution_visible',
  'observed_at',
  'temperature'
]);

const WEATHER_OUTCOME_KEYS = new Set([
  'observed_at',
  'temperature',
  'http_status',
  'ui_structure_valid'
]);

function shouldDrop(path, key) {
  if (VOLATILE_KEYS.has(key)) return true;
  return path[0] === 'weather' && WEATHER_OUTCOME_KEYS.has(key);
}

function sanitize(value, path = []) {
  if (Array.isArray(value)) return value.map((item, index) => sanitize(item, [...path, String(index)]));
  if (value === null || typeof value !== 'object') return value;

  const output = {};
  for (const [key, child] of Object.entries(value)) {
    if (shouldDrop(path, key)) continue;
    output[key] = sanitize(child, [...path, key]);
  }
  return output;
}

export function normalizeResult(result) {
  return sanitize(result);
}

// Reproducibility compares the stable scenario contract, not transport
// inventories or generated artifact locations. Those details remain in the
// raw evidence for diagnosis and performance analysis.
export function reproducibilityContract(result) {
  const normalized = normalizeResult(result);
  const {
    evidence,
    metrics,
    network,
    fatal_error,
    console,
    unexpected_console_errors,
    console_warnings,
    external_observation,
    ...stable
  } = normalized;

  stable.network = {
    unexpected_failures: normalized.network?.unexpected_failures || []
  };
  if (stable.offline && typeof stable.offline === 'object' && !Array.isArray(stable.offline)) {
    const offline = { ...stable.offline };
    delete offline.api_failures;
    stable.offline = offline;
  }
  if (external_observation && typeof external_observation === 'object' && !Array.isArray(external_observation)) {
    stable.external_observation = Object.fromEntries(
      Object.entries(external_observation)
        .filter(([key]) => !EXTERNAL_WEATHER_OUTCOME_KEYS.has(key))
    );
  }
  return stable;
}
