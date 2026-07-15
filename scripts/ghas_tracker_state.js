'use strict';

function payloadType(payload) {
  if (payload === null) return 'null';
  if (Array.isArray(payload)) return 'array';
  return typeof payload;
}

function invalidAlertPayload(label, payload) {
  return {
    status: 'invalid',
    alerts: null,
    count: null,
    note: `${label} returned an invalid ${payloadType(payload)} payload; reporting unknown.`,
  };
}

function collectedAlerts(payload, label = 'Alerts') {
  if (!Array.isArray(payload)) {
    return invalidAlertPayload(label, payload);
  }
  return {
    status: 'collected',
    alerts: payload,
    count: payload.length,
    note: null,
  };
}

function unavailableAlerts(label, error) {
  const detail = error && error.message ? error.message : String(error || 'unknown error');
  return {
    status: 'unavailable',
    alerts: null,
    count: null,
    note: `${label} unavailable: ${detail}`,
  };
}

function countOrUnknown(result) {
  if (
    result
    && result.status === 'collected'
    && Number.isInteger(result.count)
  ) {
    return result.count;
  }
  return 'unknown';
}

function metricOrUnknown(result, compute) {
  if (
    !result
    || result.status !== 'collected'
    || !Array.isArray(result.alerts)
  ) {
    return 'unknown';
  }
  return compute(result.alerts);
}

function formatMetric(value) {
  if (value === null || value === undefined || value === 'unknown') {
    return 'unknown';
  }
  return value;
}

function digestAlertMetrics(codeScanning, dependabot, secretScanning) {
  return {
    codeScanning: countOrUnknown(codeScanning),
    dependabot: countOrUnknown(dependabot),
    secretScanning: countOrUnknown(secretScanning),
    pushProtectionBypassed: formatMetric(
      metricOrUnknown(
        secretScanning,
        (alerts) => alerts.filter((alert) => alert.push_protection_bypassed === true).length,
      ),
    ),
  };
}

module.exports = {
  collectedAlerts,
  unavailableAlerts,
  invalidAlertPayload,
  metricOrUnknown,
  countOrUnknown,
  formatMetric,
  digestAlertMetrics,
};
