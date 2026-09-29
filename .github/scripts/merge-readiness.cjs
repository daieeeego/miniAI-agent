// Merge readiness is deterministic: CI tests must complete successfully.
function evaluate({ event, tests }) {
  if (tests !== 'success') {
    return { ok: false, reason: `Tests did not succeed: ${tests}` };
  }
  if (!['pull_request', 'push', 'merge_group'].includes(event)) {
    return { ok: false, reason: `Unsupported event: ${event}` };
  }
  return { ok: true, reason: 'CI tests passed.' };
}

module.exports = { evaluate };
