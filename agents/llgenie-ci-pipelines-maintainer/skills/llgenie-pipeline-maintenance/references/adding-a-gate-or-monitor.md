# Adding a new gate or monitor to the llgenie pipeline

Every new monitor touches the same six surfaces. Do them in this order — each one is a
gate that reds if skipped.

1. **Script** `scripts/check_<name>.py`: exit `0` clean, `1` violation, `2` read-failure.
   `FILE=1` delivery files ONE issue per subject, idempotent by a marker string written
   into the body — grep the OPEN issues for the marker before creating (a second file of
   the same subject is the bug the dedupe exists to prevent).
2. **Make target** with a `##` help line, and register it in `.PHONY` — `check-wiring`
   enforces PHONY hygiene and an unregistered target reds.
3. **Workflow** `.github/workflows/<name>.yml` must end with a trailing newline —
   `check-workflows` reds a file whose last byte is not `\n`.
4. **Consumer roster**: register the workflow in `run-failure-reactor.yml`'s
   `workflow_run.workflows:` list. GitHub matches a workflow's `name:` **verbatim, no
   wildcard**, and `check-workflows` reds a workflow absent from the roster ("must be
   routed to a consumer"). Copy the `name:` string exactly.
5. **Dispatch table**: splice the regenerated table into `docs/BOTS.md` between its
   BEGIN/END markers. Generate it with the bare reporter (`make dispatch-forms-report`),
   NOT `make check-dispatch-forms report` — `make` echoes the executed command line to
   stdout, and splicing that echoed line breaks the byte-identical comparison the gate
   does.
6. **Docs**: document the new `make <target>` in `docs/BOTS.md` — `check-docs` flags any
   `##`-help target not documented.
7. **Change-note pair**: `docs/changes.d/<date>-<slug>.md` (ends with a trailing newline
   and a `|`) plus `agent-wiki/<date>-<slug>.md`; then `make changes-index` to regenerate
   `CHANGES.md`.

## Verification battery

Run all of these on the tree before committing: `check-workflows`, `check-wiring`,
`check-dispatch-forms`, `check-docs`, `changes-index`, plus the new tests through the
pinned image. `make lint` needs nested docker and cannot run inside the container — the
newline checks it would do are already covered by `check-workflows`.

## Pitfalls

- **`make changes-index` regenerates the WHOLE index** from every fragment under
  `docs/changes.d/`. If main carried a fragment whose `CHANGES.md` row was never
  generated, your regen adds that row too. Verify each extra row traces to a fragment
  that already exists on main — a legitimate repair from regeneration is not scope
  creep, but an extra row you cannot trace is a diff you should not ship.
- **Test-stub JSON object keys are strings.** A stub writing `{"jobs_total": {"999": 5}}`
  read with `.get(rid)` where `rid` is an int silently misses and returns the default —
  the test then passes for the wrong reason. Look the key up as `str(rid)`. When a
  detector test contradicts a standalone run of the same logic, suspect this first.
- **A classifier that reads a field must ADD it to the real `gh ... --json` field list.** The
  fake-`gh` test stub answers from the scenario fixture whatever keys that fixture holds, so a
  new discriminator reading `run.get("status")` passes every test while production gets `None`
  because `gh run list --json databaseId,workflowName,...` never requested `status` (the API
  returns only requested fields). When you extend a detector to branch on a new field, edit the
  `--json` string in the same change and confirm the stub path is not the only thing carrying it.
- **A fake `gh` must honour the same `--jq` selector the code passes, or the caller's parse fails on the
  wrong shape.** Production does `gh pr view <n> --json statusCheckRollup --jq '.statusCheckRollup | length'`
  and `int(stdout)`; a stub that prints the raw `{"statusCheckRollup": []}` JSON (ignoring `--jq`) makes
  `int('{...}')` raise and the counter reads `-1` instead of `0` — the test then asserts a value real `gh`
  never produces. Emulate the flag: when `--jq` appears in argv, apply the selector and print its result
  (the length for a `| length`, the raw JSON for a bare field), else the payload — a stub that answers only
  the happy path is not a faithful stand-in.
- **A hermetic preflight that surfaces an EXISTING CI gate's obligation must IMPORT that gate's finding
  function, never restate its regex/contract.** `bot_preflight.py` verifies the same `AGENTS:`/`BASE:` pair
  the CI `check-pr-agents-line` gate does, so it calls `from check_pr_hygiene import
  pr_agents_line_findings` and renders that function's own detail strings — it does not re-implement the
  pattern or the `BASE == AGENTS` equality. A restated contract drifts the moment the gate changes (a second
  copy of the regex is the #792 class again); importing keeps the preflight byte-identical to what CI
  enforces and lets it cite the gate's real `file:line`. Gate the verdict on the same PR-kind condition the
  gate uses (`is_bot_pr`) so the preflight never enforces more than CI does on a human range.
- **Wiring a new BODY-obligation verdict into `main()` makes existing sibling tests whose "complete body"
  fixture predates the obligation FAIL — that is the new contract working, so ENRICH the fixture, do not
  weaken the verdict.** When `bot_preflight` gained the AGENTS/BASE verdict, a test from the prior SYNC-line
  work fed a bot body carrying only a `SYNC:` line and asserted a pass; under the new contract that body is
  rightly refused (missing AGENTS/BASE), so the test reds. The fix is to give the fixture a real
  `AGENTS:`/`BASE:` pair (preserving the test's original point), never to downgrade the new refusal to a
  warning or skip it. This is the body-obligation form of "a shape change has a spelling; find who asserted
  it" — grep the suite for tests that build a "complete" body before you wire the verdict in.
- **Prove the guard on the OLD tree: a brand-new function reds as `AttributeError`, and a WARN-asserting test
  reds as `AssertionError` — confirm BOTH shapes are red before green-on-fixed.** Running the new tests
  against the pre-fix script, `agents_base_verdict` is absent (`AttributeError`) and the test asserting a WARN
  naming a specific issue number reds because the old output lacks the number. A rule only ever run on the
  fixed tree has demonstrated nothing; capture both failure shapes as the proof.
- **A semantics change to a shared helper invalidates the existing fixture-based tests — preserve
  their INTENT, never weaken their assertion.** When the new discriminator suppresses some inputs,
  a pre-existing test that fed two cases into one condition may encode the OLD semantics (e.g. two
  zero-job runs expected to BOTH flag, now one is legitimately suppressed). Do not delete or loosen
  that assertion; reshape the fixture so it still proves its original point (give the two runs
  distinct branches so both remain independent stalls) and prove the new behaviour in a NEW test.
- **A fixture value on the wrong side of the threshold you are asserting about proves nothing.**
  Asserting that a run is flagged while its age/`createdAt` sits UNDER `--minutes` asserts a clean
  result against a fragment built to be dirty — set every fixture the assertion depends on past the
  boundary (e.g. the in_progress holder must be > `--minutes` old to be the flagged stall).
- **To prove a detector's VERDICT end-to-end, a fake `gh` must answer EVERY `gh api` path the script calls, and setup+invoke must run in ONE container.** A `docker run --rm` is a fresh filesystem, so a stub written to `/tmp/ghbin` in one invocation is gone in the next — put the `mkdir`, the stub heredoc, `export GH=<stub>`, and the script invocation all in a single `bash -lc` block. Enumerate the call sites in the module and cover each path the tool actually requests (the run/jobs/artifacts reads AND any auxiliary listing such as `superseding_run`'s `/actions/runs?branch=…`), because a stub that answers only the happy path returns exit `2` with `could not reach a verdict — … failed`. The pass condition is the script's OWN exit code (`0` for a neutral verdict, `2` for a reachable-verdict read failure) plus the conclusion it writes to `--check-run-out`, not just that pytest is green.
- **Prove the guard catches the bug** on the OLD tree: the fake-`gh` test must show the
  violation NAMED on the buggy input and zero violations on the clean input. A rule
  only ever run on the fixed tree has demonstrated nothing.
- **Amend the commit message before the FIRST push** if it has a typo. A branch never
  pushed is safe to `git commit --amend`; after it is pushed it is not.
- **`openspec validate` checks STRUCTURE, not that a `**Test:**` id RESOLVES — a change's `spec.md`
  can cite tests that do not exist and still validate green, and the suite stays green because
  nothing executes the citation.** After authoring (or auditing) an openspec change, script-verify
  every named id against the tree (`grep -rn 'def <id>' tests/` for each `**Test:**` line) and ADD
  the missing test rather than trimming the spec. A dangling spec link is a documentation defect
  the validator cannot see — treat it exactly like a red run, and re-amend the commit after fixing.
- **A test that locates a workflow step by a bare target name COLLIDES when one target is another's
  PREFIX** — `"make check-pr-acceptance"` is a prefix of `"make check-pr-acceptance-form"`, so
  `text.index("make check-pr-acceptance", form_idx)` lands on the same position and the ordering
  assertion compares a string to itself (a vacuous pass, or `15817 ≯ 15817`). Anchor on the
  unambiguous full step line (`name: make check-pr-acceptance-form`) or a trailing sentinel; grep
  the workflow for every sibling target before writing a positional assertion.
- **Never cite a CI run id as green before the head-instance run concludes success.** A
  just-opened PR is `BLOCKED` with checks in flight — report the PR number and head sha,
  and say the run id follows when it lands. Citing a cancelled or in-flight run as the
  verdict is the exact error this lane exists to catch.
