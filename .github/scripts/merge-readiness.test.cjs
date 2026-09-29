const { test } = require('node:test');
const assert = require('node:assert/strict');
const { evaluate } = require('./merge-readiness.cjs');
const base = { event: 'pull_request', tests: 'success' };

test('successful CI tests permit merge readiness', () => {
  assert.equal(evaluate(base).ok, true);
});
test('failed, skipped, cancelled and missing tests never permit merge', () => {
  for (const tests of ['failure', 'skipped', 'cancelled', '']) {
    assert.equal(evaluate({ ...base, tests }).ok, false);
  }
});
test('PR, push and merge queue all require CI tests', () => {
  for (const event of ['push', 'merge_group']) {
    assert.equal(evaluate({ ...base, event }).ok, true);
    assert.equal(evaluate({ ...base, event, tests: 'failure' }).ok, false);
  }
});
test('unknown events fail closed', () => {
  assert.equal(evaluate({ ...base, event: 'unknown' }).ok, false);
});
