const VOLATILE_KEYS = new Set([
  'generated_at',
  'scenario_duration_ms',
  'duration_ms',
  'request_duration_ms',
  'timing_ms',
  'timings_ms'
]);

function shouldDrop(path, key) {
  if (VOLATILE_KEYS.has(key)) return true;
  return path[0] === 'weather' && (key === 'temperature' || key === 'observed_at');
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
    ...stable
  } = normalized;

  stable.network = {
    unexpected_failures: normalized.network?.unexpected_failures || []
  };
  return stable;
}
