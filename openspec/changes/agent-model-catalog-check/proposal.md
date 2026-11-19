# Proposal: agent-model-catalog-check

## Why

Issue #2930. The five `:free` members of the Hermes model chain (issue #2929,
`agents/hermes-base-config.yaml`) are synthesized free variants in the Nous
catalog. Nothing in the repo checks that `meituan/longcat-2.5:free`,
`tencent/hy4-flash:free`, `stepfun/step-3.7-flash:free`, `qwen/qwen4-max:free`
and `upstage/solar-mini4:free` are still listed, or that the committed
`context_window` budgets still match the catalog's published
`context_length`. Measured 2026-11-19: `GET https://inference-api.nousresearch.com/v1/models`
answers 200 WITHOUT auth (413 models; exactly these five carry `:free`), so the
check needs no secret anywhere.

## What Changes

- ADDED `scripts/check_agent_model_catalog.py`: reads the chain (primary
  `model:` block + `fallback_providers`) from `agents/hermes-base-config.yaml`,
  fetches the public catalog list, and reports (a) any chain id missing from the
  catalog, (b) any `context_window` that diverges from the catalog
  `context_length`. Exit 0 while everything agrees; non-zero findings name every
  member. `--catalog <file>` reads a saved catalog (fixture/offline mode);
  `--dry-run` prints the would-be issue body instead of filing it.
- ADDED issue filing: findings collapse to ONE deduped issue (marker first
  line, `scripts/issue_body.py::render`, labelled `agent:implement`, naming the
  current `:free` catalog ids as replacement candidates); a later run re-reads
  its marker and UPDATES the open issue instead of filing a second one
  (`registry_change_issue.py` idiom). The producer joins `issue_body.PRODUCERS`.
- ADDED make target `check-agent-model-catalog` (mk/bots.mk, documented).
- MODIFIED `.github/workflows/registry-sync.yml`: the weekly allow-listed lane
  gains one step running the checker (GH_TOKEN already job-scoped). No new
  schedule, no agent job — `make check-ci-discipline` stays green; the lane's
  SCHEDULE_ALLOW rationale is updated to describe reality.

## Out of Scope (→ issues)

- None beyond the issue's own `Not covered` (the chain install itself, #2929).
