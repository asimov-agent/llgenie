# A non-blocking JEV layer must still be visible in the run (issue #238)

## Why

`agent_jev_preflight.sh` reports whether the JEV decision layer is available and **never stops a
run** — correct for an autonomous bot, but it left one gap: when the layer was unavailable, the only
trace was a warning in a log nobody reads. With the key in place (`TYPESAFE_API_KEY` is a repo
secret) the layer is ON, and the maintainer's question — "is it on?" — should be answerable from the
run page, not from a log grep.

## What changed

- **The preflight annotates the run.** When `GITHUB_ACTIONS=true` it emits
  `::notice title=JEV decision layer::JEV is ON for this run …` (layer ready) or
  `::warning title=JEV decision layer::JEV is INACTIVE for this run …` (layer unavailable, run
  continues), and appends the outcome to `$GITHUB_STEP_SUMMARY`. Locally it stays plain text —
  asserted: no `::notice`/`::warning` markers outside Actions.
- **The two workflow comments were corrected.** Both still said the step "fails the run when the
  key is missing" / "a run without this secret fails loudly instead of repairing a PR
  unsupervised" — the old gate contract, i.e. a lie about an autonomous bot. They now say what the
  layer is for (fewer LLM calls, fewer tokens, fewer mistakes) and that the step reports rather
  than blocks.

## Tests

`tests/test_agent_nerve.py` → **23 passed** (was 20):

- `test_the_run_annotates_whether_jev_is_on_or_off` — the off case carries a warning annotation and
  exits 0; a working layer carries a notice and says JEV is ON; outside Actions there is no
  annotation noise; the step summary is written when Actions offers one.
- `test_the_workflow_comments_describe_the_layer_it_actually_runs` — both workflows say what the
  layer is for and that it never stops a run, and the three stale gate-contract phrases are gone.

## Verified in the published image too

`ghcr.io/asimov-agent/llgenie/agent:273ea56e54f4` (published after #265 merged): plugin enabled at
`pinned@3de7d949`, the sidecar loading as profile **`lean`** through the plugin's own loader
(nervous, receipts, reflex, token_trajectory, work_supervision), every setting read back, and the
preflight with the host's key answering a **real decision call** (`JEV ready`, rc=0).
