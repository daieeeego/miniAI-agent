// Keep the deterministic merge policy separate from model-generated review text.
function evaluate({ event, tests, codex, report }) {
  if (tests !== 'success') {
    return { ok: false, reason: `Tests did not succeed: ${tests}` };
  }
  if (event === 'push' || event === 'merge_group') {
    return { ok: true, reason: 'Tests passed. Codex review is evaluated on pull requests.' };
  }
  if (event !== 'pull_request') {
    return { ok: false, reason: `Unsupported event: ${event}` };
  }
  if (codex !== 'success') {
    return { ok: false, reason: `Codex review did not succeed: ${codex}. Check authentication and PR origin.` };
  }
  let review;
  try {
    review = JSON.parse(report);
    if (!review || typeof review.summary !== 'string' || !Array.isArray(review.findings)) {
      throw new Error('Invalid report');
    }
    for (const finding of review.findings) {
      if (!finding || !['P0', 'P1', 'P2', 'P3'].includes(finding.priority) ||
          !['title', 'detail', 'path'].every(key => typeof finding[key] === 'string') ||
          !Number.isInteger(finding.line) || finding.line < 1) {
        throw new Error('Invalid finding');
      }
    }
  } catch {
    return { ok: false, reason: 'Codex returned a missing or invalid JSON review.' };
  }
  const blocking = review.findings.filter(finding => ['P0', 'P1'].includes(finding.priority));
  return {
    ok: blocking.length === 0,
    reason: blocking.length ? `${blocking.length} blocking Codex finding(s): P0/P1.` : 'Tests and Codex review passed. No P0/P1 findings.',
    review
  };
}

module.exports = { evaluate };
