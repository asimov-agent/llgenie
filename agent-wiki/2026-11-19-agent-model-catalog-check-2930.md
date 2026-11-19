# 2026-11-19 — The weekly registry lane checks the Hermes model chain against the live catalog (issue #2930)

Implements issue #2930 (OpenSpec change `agent-model-catalog-check`): the model chain pinned by
issue #2929 (`agents/hermes-base-config.yaml`) is now proven against the live Nous catalog every
week, instead of rotting silently when a synthesized `:free` variant is removed upstream.

## What was verified against the spec

- **Chain read** — `scripts/check_agent_model_catalog.py::chain_members` reads the config itself:
  the `model:` default, every `model.aliases.<name>.model` (with its budget copied down from the
  parent when the alias itself declares no `context_window`), and every `fallback_providers[]`
  entry. A config declaring no models exits loudly — the check can never pass vacuously. A model
  id with conflicting budgets is a finding, never a silent first-wins.
- **Hermetic fetch** — `GET https://inference-api.nousresearch.com/v1/models` measured 2026-11-19:
  HTTP 200 **without any auth header** (413 model objects, each carrying `id` + `context_length`;
  exactly 5 `:free` entries, all 5 chain `:free` ids among them). The script sends a User-Agent and
  nothing else, reads no credential, and a test asserts no `Authorization` header reaches the
  request and no `environ` read exists in the code path.
- **Comparison** — exit 0 only when every declared id is listed AND its committed budget equals the
  published `context_length`. A missing member names its declaration sites and lists the current
  `:free` candidates; a budget divergence names both numbers. A transport failure exits 3 and files
  nothing: an unreadable catalog is not news.
- **One deduped issue** — findings file exactly one issue through the one renderer
  (`issue_body.render`, marker first line `<!-- agent-model-catalog-check: chain-membership -->`),
  labeled `agent:implement` with a live `labels --jq` proof (never 422-blind), deduped by a body
  SEARCH of open issues (#2848) — a later week PATCHes the open issue's body over REST and reads it
  back (#2673), never filing a second issue; a failed dedupe search files nothing blind.
- **Wiring** — `make check-agent-model-catalog` (help text, `DRY`/`CATALOG`/`REPO` variables,
  `--repo "$(GH_REPO)"`) is the **last** step of the `registry-sync` sync job: a red finding must
  not forfeit the sync PR the job just opened (the #775 lesson). The weekly cron survives untouched
  (`19 5 * * 1`). `scripts/issue_body.py::PRODUCERS` gained the module;
  `scripts/package-layers.json` registers it in "Bots and automation" with the `proc` subprocess-seam
  edge (#797); `scripts/check_ci_discipline.py` names the new weekly duty in the registry-sync
  rationale it must keep describing.

## Key decisions

- The check reads the config as the single source (it is the file #2929's referee and the image
  build already read) instead of a second declaration.
- Public endpoint, no secret: the CI step carries only `secrets.GITHUB_TOKEN` (the job already
  holds `issues: write`); `NOUS_PORTAL_API_TOKEN` is NOT forwarded.
- The step sits after "Open / update the sync PR" on purpose, pinned by a test that asserts last-step
  position.

## Current status

- Live proofs on the branch: `make check-agent-model-catalog` against a saved live catalog exits 0;
  a doctored catalog with one member removed prints the FINDING and `--dry-run` exits 1 with the
  six-section body (marker first line) and touches no `gh`.
- 16 tests in `tests/test_check_agent_model_catalog.py` cover the chain read, comparison, dedupe
  update path, no-credential promise, and the workflow/target/PRODUCERS/layers wiring.
- Issue: #2930 (closes via the PR for this change).
