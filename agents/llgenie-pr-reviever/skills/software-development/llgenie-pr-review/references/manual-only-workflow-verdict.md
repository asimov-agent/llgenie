# Manual-only workflow verdicts: 5-AC pattern, measured not assumed (#2307/#2293)

Reviewing a PR that makes run-failure-reactor / fix-bot (or any auto-reaction bot) manual-only follows
one repeating shape. Re-measure every criterion from the artifact — a verdict that quotes another bot's
evidence is the #745 self-tick class.

## The five ACs and their cheapest honest proof
1. **file is dispatch-only with the input** — read the file's `on:` block end-to-end
   (`sed -n '/^on:/,/^permissions:/p' <file>.yml`). One trigger key, `workflow_dispatch`; the required
   input present. Run `scripts/check_workflows.py check` and `scripts/check_wiring.py check` for rc=0.
2. **the sibling keeps its manual inputs** — same read of the second file; assert the input list is intact.
3. **no remaining auto trigger** — grep both `on:` blocks for `schedule`/`workflow_run`/`push`/`pull_request`;
   expect zero.
4. **the gate pins manual-only** — `MANUAL_ONLY_WORKFLOWS` in `scripts/check_workflows.py` names the exact
   workflow filenames, and the gate's own OK line drives the enforcement.
5. **a re-added trigger reds the gate** — this is a MUTATION proof, run it yourself: append
   `workflow_run: [CI]` to the file's `on:`, `check` must exit non-zero naming the file and "Remove
   workflow_run", then restore byte-identical (verify with `cmp`) and check rc=0 again.

## Gate names that trip together are often the SAME seam
`check-pr-acceptance` red in guard + scope + ci-verdict at once is one verdict-gated seam (#1644), not
three unrelated joins. A `check-pr-sync-line` red is a SEPARATE, author-side defect: the body changed an
`agents/<lane>/` file without the `SYNC:` re-sync line (issue #1724) — that is the owning lane's fix, not
a tick.

## Write the `proven:` ref in one reproducible form
`pytest|check rc<N>|<run id> <head>` — never a bare "tests pass". Canadian here: the negative control
(AC5) is the strongest evidence for a manual-only claim; a `proven: check_workflows.py check rc=0 then
mutation rc=1 then restore rc=0 head=<sha>` ref is replayable.
