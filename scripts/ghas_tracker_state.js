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

function slaAlertMetrics(codeScanning, dependabot, secretScanning, ageDays) {
  const countAtLeast = (result, days) => metricOrUnknown(
    result,
    (alerts) => alerts.filter((alert) => ageDays(alert) >= days).length,
  );
  const highSeverityCodeAged = metricOrUnknown(
    codeScanning,
    (alerts) => alerts.filter((alert) => {
      const severity = alert.rule?.security_severity_level || alert.rule?.severity || 'unknown';
      return ['critical', 'high'].includes(String(severity).toLowerCase()) && ageDays(alert) >= 14;
    }).length,
  );
  const criticalDependabotAged = metricOrUnknown(
    dependabot,
    (alerts) => alerts.filter((alert) => {
      const severity = alert.security_vulnerability?.severity || alert.severity || 'unknown';
      return ['critical', 'high'].includes(String(severity).toLowerCase()) && ageDays(alert) >= 14;
    }).length,
  );

  return {
    codeScanning: countOrUnknown(codeScanning),
    dependabot: countOrUnknown(dependabot),
    secretScanning: countOrUnknown(secretScanning),
    codeAged7: countAtLeast(codeScanning, 7),
    codeAged14: countAtLeast(codeScanning, 14),
    codeAged30: countAtLeast(codeScanning, 30),
    highSeverityCodeAged,
    dependabotAged7: countAtLeast(dependabot, 7),
    dependabotAged14: countAtLeast(dependabot, 14),
    dependabotAged30: countAtLeast(dependabot, 30),
    criticalDependabotAged,
    secretAged7: countAtLeast(secretScanning, 7),
    secretAged14: countAtLeast(secretScanning, 14),
    secretAged30: countAtLeast(secretScanning, 30),
    secretBypassed: metricOrUnknown(
      secretScanning,
      (alerts) => alerts.filter((alert) => alert.push_protection_bypassed === true).length,
    ),
    secretBypassedAged: metricOrUnknown(
      secretScanning,
      (alerts) => alerts.filter(
        (alert) => alert.push_protection_bypassed === true && ageDays(alert) >= 7,
      ).length,
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
  slaAlertMetrics,
};
