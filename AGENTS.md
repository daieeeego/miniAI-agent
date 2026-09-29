# Development guidance

This repository is a teaching agent: Jev classifies, GPT handles ambiguous classifications,
and Python chooses from a fixed set of dummy tools. Do not describe dummy dispatch as a real
cloud operation or describe Mock scores as measured model confidence.

Run `python -m pytest -q`, `python -m ruff check .`, `python -m ruff format --check .`,
and `node --test .github/scripts/merge-readiness.test.cjs` when changing relevant behavior.
Never use production credentials or external model calls in unit tests.

## Code Review Rules

- Flag any route that executes a tool after an invalid model response, a provider failure,
  or an unavailable fallback. Such cases must require human review; model output must remain
  restricted to the supported route allowlist.
- Flag storage or disclosure of API keys or user messages in application logs or responses.
  Keys must come from Secret Manager in memory through ADC or workload identity; do not
  introduce `.env` secrets or service-account JSON keys.
- Flag a merge check that treats failed, cancelled, skipped, missing, or invalid PR reviews
  as successful. Tests must pass, review must complete, and P0/P1 findings must block the PR.
