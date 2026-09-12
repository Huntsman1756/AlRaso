function nowMs() {
  return Number(process.hrtime.bigint()) / 1_000_000;
}

function matches(matcher, request) {
  const url = request.url();
  if (typeof matcher === 'string') return url.includes(matcher);
  if (matcher instanceof RegExp) {
    matcher.lastIndex = 0;
    return matcher.test(url);
  }
  if (typeof matcher === 'function') return Boolean(matcher(request));
  return false;
}

function compactError(error) {
  return {
    name: error?.name || 'Error',
    message: error?.message || String(error),
    stack: error?.stack || null
  };
}

export function observePage(page, { expectedAbortMatchers = [] } = {}) {
  const requests = [];
  const requestRecords = new Map();
  const responses = [];
  const failedRequests = [];
  const consoleErrors = [];
  const consoleWarnings = [];
  const pageErrors = [];
  const expectedRules = [];
  const declaredFaults = new Set();
  const observedFaults = new Set();

  function addExpectedAbort(name, matcher) {
    declaredFaults.add(name);
    expectedRules.push({ name, matcher });
  }

  for (const entry of expectedAbortMatchers) {
    if (typeof entry === 'object' && entry !== null && 'matcher' in entry) {
      addExpectedAbort(entry.name, entry.matcher);
    } else {
      addExpectedAbort(String(entry), entry);
    }
  }

  page.on('console', (message) => {
    const record = {
      type: message.type(),
      text: message.text(),
      location: message.location()?.url || null
    };
    if (message.type() === 'error') consoleErrors.push(record);
    if (message.type() === 'warning') consoleWarnings.push(record);
  });

  page.on('pageerror', (error) => {
    pageErrors.push(compactError(error));
  });

  page.on('request', (request) => {
    const record = {
      url: request.url(),
      method: request.method(),
      resource_type: request.resourceType(),
      status: null,
      failed: false,
      failure_text: null,
      duration_ms: null,
      expected_fault: null,
      started_at_ms: nowMs()
    };
    requests.push(record);
    requestRecords.set(request, record);
  });

  page.on('response', (response) => {
    const request = response.request();
    const record = requestRecords.get(request);
    if (record) {
      record.status = response.status();
      record.duration_ms = Math.max(0, Math.round(nowMs() - record.started_at_ms));
    }
    responses.push({
      url: response.url(),
      status: response.status(),
      resource_type: request.resourceType()
    });
  });

  page.on('requestfailed', (request) => {
    const record = requestRecords.get(request);
    const rule = expectedRules.find((candidate) => matches(candidate.matcher, request));
    const failureText = request.failure()?.errorText || null;
    const browserCancelled = failureText === 'net::ERR_ABORTED';
    const failure = {
      url: request.url(),
      method: request.method(),
      resource_type: request.resourceType(),
      failure_text: failureText,
      expected: Boolean(rule) || browserCancelled,
      browser_cancelled: browserCancelled,
      expected_fault: rule?.name || null
    };
    failedRequests.push(failure);
    if (record) {
      record.failed = true;
      record.failure_text = failure.failure_text;
      record.expected_fault = failure.expected_fault;
      record.duration_ms = Math.max(0, Math.round(nowMs() - record.started_at_ms));
    }
    if (rule) observedFaults.add(rule.name);
  });

  return {
    addExpectedAbort,
    declareExpectedFault(name) {
      declaredFaults.add(name);
    },
    observedFault(name) {
      return observedFaults.has(name);
    },
    snapshot() {
      const unexpectedFailures = failedRequests.filter((failure) => !failure.expected);
      return {
        console: {
          unexpected_errors: consoleErrors.length,
          warnings: consoleWarnings.length,
          errors: [...consoleErrors],
          warning_records: [...consoleWarnings]
        },
        page_errors: [...pageErrors],
        network: {
          requests: requests.map(({ started_at_ms, ...record }) => record),
          responses: [...responses],
          failed_requests: [...failedRequests],
          unexpected_failures: [...unexpectedFailures]
        },
        expected_faults: [...new Set([...declaredFaults, ...observedFaults])].sort(),
        observed_expected_faults: [...observedFaults].sort()
      };
    }
  };
}
