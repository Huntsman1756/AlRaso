function asBoolean(value) {
  return Boolean(value);
}

export class ScenarioRecorder {
  constructor(scenario, viewport) {
    this.scenario = scenario;
    this.viewport = viewport;
    this.assertionRecords = [];
    this.findings = [];
    this.expectedFaults = new Set();
  }

  check(label, condition, details = {}) {
    const passed = asBoolean(condition);
    this.assertionRecords.push({ label, passed, ...details });
    return passed;
  }

  notApplicable(label, details = {}) {
    this.assertionRecords.push({ label, passed: null, not_applicable: true, ...details });
  }

  expectedFault(name) {
    this.expectedFaults.add(name);
  }

  addFinding(finding) {
    this.findings.push(finding);
  }

  finish({ observer = null, metrics = {}, reproducible = null } = {}) {
    const observed = observer?.snapshot?.() || {};
    const assertionRecords = [...this.assertionRecords];
    const assertionFailed = assertionRecords.filter((record) => record.passed === false).length;
    const assertionPassed = assertionRecords.filter((record) => record.passed === true).length;
    const notApplicable = assertionRecords.filter((record) => record.not_applicable === true).length;
    const unexpectedConsoleErrors = observed.console?.unexpected_errors || 0;
    const pageErrors = observed.page_errors?.length || 0;
    const unexpectedNetworkFailures = observed.network?.unexpected_failures || [];
    const failed = assertionFailed + unexpectedConsoleErrors + pageErrors + unexpectedNetworkFailures.length;

    return {
      scenario: this.scenario,
      viewport: this.viewport,
      scenario_status: failed === 0 ? 'PASS' : 'FAIL',
      reproducible,
      assertions: {
        passed: assertionPassed,
        failed,
        not_applicable: notApplicable
      },
      assertion_details: assertionRecords,
      console: observed.console || { unexpected_errors: 0, warnings: 0, errors: [], warning_records: [] },
      unexpected_console_errors: unexpectedConsoleErrors,
      console_warnings: observed.console?.warnings || 0,
      page_errors: pageErrors,
      network: observed.network || { requests: [], responses: [], failed_requests: [], unexpected_failures: [] },
      expected_faults: [...new Set([
        ...this.expectedFaults,
        ...(observed.expected_faults || [])
      ])].sort(),
      unexpected_network_failures: unexpectedNetworkFailures,
      timings_ms: metrics.timings_ms || {},
      metrics,
      findings: [...this.findings]
    };
  }
}
