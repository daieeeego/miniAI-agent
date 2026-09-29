const { test } = require('node:test');
const assert = require('node:assert/strict');
const { evaluate } = require('./merge-readiness.cjs');
const base = { event: 'pull_request', tests: 'success', codex: 'success' };
const finding = { priority: 'P1', title: 'Bug', detail: 'Evidence', path: 'app/main.py', line: 1 };
const report = findings => JSON.stringify({ summary: 'Review complete', findings });

test('successful tests and an empty review permit merge', () => {
  assert.equal(evaluate({ ...base, report: report([]) }).ok, true);
});
test('failed, skipped and cancelled tests never permit merge', () => {
  for (const tests of ['failure', 'skipped', 'cancelled']) {
    assert.equal(evaluate({ ...base, tests, report: report([]) }).ok, false);
  }
});
test('failed, skipped and cancelled reviews never permit a PR merge', () => {
  for (const codex of ['failure', 'skipped', 'cancelled']) {
    assert.equal(evaluate({ ...base, codex, report: report([]) }).ok, false);
  }
});
test('missing or malformed model output cannot be treated as approval', () => {
  for (const input of ['', '{}', 'Looks good', '{"summary":"ok","findings":null}', report([{}])]) {
    assert.equal(evaluate({ ...base, report: input }).ok, false);
  }
});
test('P0/P1 block merging while P2/P3 remain advisory', () => {
  for (const priority of ['P0', 'P1', 'P2', 'P3']) {
    assert.equal(evaluate({ ...base, report: report([{ ...finding, priority }]) }).ok,
      ['P2', 'P3'].includes(priority));
  }
});
test('push and merge queue runs still require tests', () => {
  for (const event of ['push', 'merge_group']) {
    assert.equal(evaluate({ ...base, event, codex: 'skipped' }).ok, true);
    assert.equal(evaluate({ ...base, event, tests: 'failure' }).ok, false);
  }
});
test('unknown events and invalid severity or line fail closed', () => {
  assert.equal(evaluate({ ...base, event: 'unknown' }).ok, false);
  for (const invalid of [{ ...finding, priority: 'unknown' }, { ...finding, line: 0 }]) {
    assert.equal(evaluate({ ...base, report: report([invalid]) }).ok, false);
  }
});
