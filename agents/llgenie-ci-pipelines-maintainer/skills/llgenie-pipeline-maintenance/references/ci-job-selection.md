# Changing WHICH jobs a PR runs (trigger selection, not job `if:`)

Two different levers, never confuse them: **row selection** narrows a matrix that already exists
(`engine-base` collapsing to one placeholder row); **stage selection** decides whether a job family
exists at all. This file is the second one.

## The rule: select at the TRIGGER, because absence is invisible afterwards

A job `if:` that evaluates false leaves a SKIPPED job behind, and a `paths:` filter on the workflow
leaves nothing at all — a reviewer reading the check list cannot tell "not needed" from "not run".
So:

1. **`pull_request.paths` / `paths-ignore` on the workflow** is the only place a stage set is decided.
   A `paths-ignore` clause applies **only when EVERY changed path matches it**: one code file in the
   diff restores the whole matrix, which is exactly the property you want.
2. **Never filter `push`.** A merge to the default branch keeps every job; only PRs are scoped.
3. **Never add a job-level `if:` for path selection.** `tests/test_ci_images.py` permits exactly four
   job shapes (`_PUSH_WAIT`/`needs`, the `matrix.x != 'none'` placeholder row, one push-scoped publish
   condition, `!cancelled()`/`always()`) and five step conditions; a sixth shape turns the repo's
   strongest CI invariant into a list of exceptions. Read that test before designing, not after it reds.
4. **Keep one always-present check.** A separate workflow with NO path filter classifies the diff and
   reports one stable check name (e.g. `scope`): the classes detected, the jobs they select, and the
   reason each skipped family is absent. A path that matches no known class FAILS it — an empty answer
   is not a verdict (a red rollup with nothing in it is the same defect from the other side).

There are **no required status checks** on this repo's default branch (`branches/main/protection`
answers 404; the ruleset carries `deletion` and `non_fast_forward` only), so a skipped stage cannot
deadlock a merge — the always-present check buys *legibility*, and making it required is an owner
decision, never something a change assumes.

## The classifier: stdlib + `git diff`, no third-party action

A path-filter action would add a pinned `uses:` — a SHA, a `docs/SECURITY.md` row, a roster entry — and
hand an external dependency the power to skip the pipeline. Instead:

```bash
python3 scripts/<scope>.py jobs --from origin/<base>     # classes, selected jobs, skipped jobs + why
```

- Paths in, classes/jobs out, so it runs in the test image with no git, no network, no action.
- Wildcard paths select EVERY class: `Makefile`, `.github/**`, `tools/**`, `scripts/ci_*.py`,
  `scripts/engine_*.py`, `scripts/check_*.py`, `pytest.ini`, `.gitleaks.toml`, `renovate.json`,
  `AGENTS.md`. A change that can alter what a gate proves must never slim itself out of its own
  coverage.
- Print, per skipped job, the classes that WOULD have selected it (`skipped: engine-matrix (needs one
  of containers, engines, skills)`) — a bare list of absent names says a job did not run, never whether
  that was right.
- In the workflow, fetch the base by name before diffing (`git fetch --no-tags origin
  +refs/heads/$BASE_REF:refs/remotes/origin/$BASE_REF`); a `pull_request` checkout holds the merge ref,
  not the base branch.

## The moving parts, and what each one must leave green

| Piece | Must exist | Gate that catches a mistake |
|---|---|---|
| classifier script | one make target calls it, declared `.PHONY`, documented with `## help` | `check-wiring` (a target CI never calls), `check-docs` |
| always-present check workflow | its own `name:`, pinned `uses:` only, minimal `permissions`, own `timeout-minutes`, own `concurrency` group | `check-workflows`, `check-actions` (pin gate) |
| path-filtered docs workflow | the gates a docs diff can still break: `ci-lint`, `check-docs`, `check-wiring`, `check-issue-bodies`, `check-workflows`, `check-dispatch-forms`, `ci-openspec` | `check-dispatch-forms` (if it gains a dispatch form), `_job_if_allowed` |
| trigger edit on the main workflow | `paths-ignore` on `pull_request` ONLY | `tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` |

Add a wiring test that pins the three-way agreement — the main workflow filters exactly the class the
classifier calls docs, the always-present workflow has NO filter and runs the classifier through make,
and the docs workflow runs the docs gates. A classifier plus a filter with nothing proving they agree
is the silent drift this design exists to prevent.

## Fail-closed, and the producer's output as the gate

**The classifier must answer "everything" when it cannot read the diff — but the two unreadable shapes
have OPPOSITE exit codes, because the human action differs.** Both print `WIDE: <reason>` and select
EVERY job family (never an empty set):

| input | selection | exit | why |
|---|---|---|---|
| empty diff (no paths at all, or only blank ones) | all N of N | **0** | nothing for an author to fix; a red here is an unfixable red on exactly the refs an always-on reporting check exists for — a merge-queue ref, a `workflow_dispatch`, a force-push that nets to no change |
| a path matching no class | all N of N | **1** | someone must add the glob, so the check must be loud |

A refusal (`exit 2`, with or without a printed selection) turns the always-on check into a source of
unfixable reds; the split is 0 for what nobody can act on and 1 for what a human must act on. Pin all of
it: the printed `N of N`, the `WIDE` line, and the exit code for BOTH shapes (`jobs` and
`jobs --paths ''`), plus the subcommand twins — `classify` must agree with `jobs`, or one caller gets a
different verdict than another.

**A blank path entry is a shell artifact, not a changed path.** `--paths "$CHANGED"` with an empty
variable expands to `[""]`, which classifies as an UNCLASSIFIABLE path and reds the check — the empty
diff's unfixable red reached through a second door. Drop blank/whitespace-only entries BEFORE the
decision, and keep a test that a real unknown path sitting next to them still wins.

**Pin the Makefile seam by RUNNING it — against a genuinely failed decision.** The recipe must not swallow
a failure (a later `|| true` would turn an unreadable diff into a green check), so run the target against
a ref that cannot be diffed and expect non-zero; an empty `BASE=` is the wrong probe now that an empty
diff passes by design.

**A trigger-level filter cannot be verified before it is on the default branch.** GitHub evaluates
`on.pull_request.paths`/`paths-ignore` from the branch a PR targets, so a probe PR cut from `main`
*before* the filter landed runs the full matrix — measured: a docs-only probe queued `guard` plus the
whole job floor, which reads exactly like "the filter is broken". Prove the classifier on any branch;
prove the SELECTION only after the change is on `main`, and say which of the two you are showing.

**The classifier and the trigger must be ONE set, asserted, not described.** `set(CLASSES["docs"])` ==
`set(ci.yml pull_request.paths-ignore)` == `set(docs.yml pull_request.paths)`, all three in one test: if
only the trigger was narrowed, the printed selection still claims a class the trigger ignores, and the
print is the only place a human sees the truth. Negative-control it by putting the old pattern back.

**A family that proves a pushed artefact is selected by the producer's output, never by the diff.**
The matrix owner resolves the fact ONCE and passes it down, because a matrix job cannot aggregate its
legs — `needs.<job>.outputs` takes the LAST leg's value, so a per-leg flag reports one arbitrary row:

```yaml
# caller (the job that resolves the rows)
outputs:
  pushed: ${{ steps.m.outputs.pushed }}                        # echoed by a script, not inline YAML
with:
  pushed: ${{ needs.<matrix-job>.outputs.pushed || 'false' }}   # fail closed for a silent caller
```

```yaml
# callee (the reusable workflow)
matrix:
  backend: ${{ inputs.pushed == 'true' && fromJSON('["cpu","cuda","rocm","vulkan"]') || fromJSON('["none"]') }}
steps:
  - name: Say which row this is, and why        # NO if: — the reason prints on both rows
    run: echo "<family>-none: SKIPPED - no image pushed in this run (pushed=${{ inputs.pushed }})"
  - uses: ...                                    # every work step:
    if: ${{ matrix.backend != 'none' }}          # gate the ROW, never the job
```

Extending `test_no_ci_step_or_job_is_skipped`'s allowlist is legitimate for a new placeholder row — add
the condition **with its reason written at the assertion** (`matrix.backend != 'none'` is the published
twin of `matrix.engine != 'none'`), and say in the PR body that the allowlist changed and why. A
job-level `if:` stays forbidden: it makes the check name disappear.

**The placeholder row must survive its own cleanup.** Gating only the *work* steps leaves the
`if: always()` teardown running on the row that skipped everything it needs — measured: the `none` row
failed in four seconds on `make test-clean` (which wants the docker action the row deliberately skips),
so the row that exists to prove nothing produced a red. Put the row decision in the SHELL, not in a
compound `if:` the allowlist refuses:

```yaml
  - name: Prune orphaned test containers
    if: always()                                   # stays inside the allowlist
    run: |
      if [ "${{ matrix.backend }}" = "none" ]; then
        echo "no containers to prune: the none row started none"
        exit 0
      fi
      make test-clean
```

Pin it (`assert cleanup["if"] == "always()"` and the shell guard is present in the `run:` body). A
placeholder that reds is worse than the wasted runners it replaced, and it will be read as a real
failure of the change.

**Put the decision in a script, not in the YAML.** The value that makes four jobs run or not run can only
be tested while it lives in a `scripts/*.py` with a CLI (`--event`, `--matrix`) printing the exact string
written into `$GITHUB_OUTPUT`; inline, the only possible test is a string match on the workflow file.
Cover it behaviourally: pull_request with real rows → false, push with real rows → true, push with only
the `none` row → false, unreadable matrix → true (fail closed), empty matrix → false (no rows).

## Gate classification (FAST_GATES vs DEFERRED) — verify the gate is REAL first

`scripts/issue_bot_gates.py` splits every `ci-unit` gate into `FAST_GATES` (cheap, run before a push)
and a `DEFERRED` map (with a written reason). A gate that is in neither is a `#475` finding. The one-list
rule: to add a gate, edit `FAST_GATES` (the tuple) — never restate the list at a call site; a target that
IMPORTS the tuple (`make lane-preflight` style) inherits any addition for free.

**Verify the gate exists on `main` before judging whether to widen FAST_GATES.** Measured: a dispatch
cited `check-import-roots` as "(DEFERRED)", but `main` had no make target, no `scripts/check_import_roots.py`,
and no `ci-unit` entry — it lived only on the unmerged `feat/import-roots-guard` branch. So "should
FAST_GATES cover it?" is not answerable until the gate lands.

**A gate almost always lands ALREADY CLASSIFIED as DEFERRED** (the landing PR adds a `DEFERRED` entry
with a written reason, and `issue-bot-gates check` stays green). So promoting it to FAST is a **MOVE,
not an addition**: remove its `DEFERRED` entry AND add it to `FAST_GATES` in the SAME edit — leaving it in
both reds the validator's overlap check. Do not "add to `FAST_GATES` and leave the DEFERRED line".

**The move cannot ride the gate's own landing PR if that PR is armed with a live matrix.** A promotion is
one config line, but pushing it to a PR whose `linux/unit` is mid-run cancels that matrix (same rule as
never cancelling a run for a body-only edit) and buys a 16–33 min re-run with no verdict. Sequence: the
gate's branch merges → a **separate one-line follow-up PR** does the MOVE → any target that IMPORTS the
`FAST_GATES` tuple (`make lane-preflight` style) inherits it for free. Never restate the list at a call
site, and **never widen `FAST_GATES` inside a PR that merely consumes it** — that conflates two issues.

**Classify a static-read gate** (no container/network: `check-wiring`, `check-docs`, `lint`,
`check-import-roots`) **as FAST, not DEFERRED** — it is cheap per push, and a drift it only catches in the
full matrix costs ~16–33 min to surface late. Prove "static read" by reading the script on the gate's
branch before it lands: imports limited to stdlib (`argparse/ast/json/re/sys/pathlib`), no
`subprocess`/`git`/`docker`/`requests`/`urllib`/`socket`, reads via `glob`/`rglob`/`read_text` under a
root — then the classification is a certainty at merge time, not a judgement.

## Verify the classifier's class table is COHERENT, not just that one path maps

A new gate/file is not the only silent-skip risk: the whole class table can have a **dead selector** — a
`CLASSES` entry that no job lists, so a diff of only that class selects nothing and the run goes green
having tested nothing. Prove coherence, not one path:

```bash
# one representative path per class → every class must select a REAL job (not just always-on guard/lint)
for p in docs/X.md .hermes/s/k/SKILL.md .github/workflows/x.yml scripts/foo_model.py \
         tests/test_foo.py data/foo.json containers/Dockerfile \
         containers/engines/x/Dockerfile renovate.json; do
  python3 scripts/ci_scope.py --paths "$p" | grep -E 'run — class'
done
```
Every class must select ≥1 class-driven job; an empty result for a defined class is a dead selector. And a
gate's OWN files must classify: a new `scripts/check_<x>.py` should hit the `scripts/check_*.py` wildcard
(→ WIDE, all classes) or the `scripts` class, and its `tests/**` files the `tests` class (→ the job that
runs the gate). Run this check when adding a gate or a class, and before believing "a diff of that area is
covered." Warning sign to also grep for: a class name the job map references but `CLASSES` never emits
(typo/dead need) — symmetric to the dead selector.

## Pitfalls

- **A PR that mixes docs with anything else runs BOTH workflows.** The docs workflow's `paths:` matches
  if any changed file is markdown, and the main workflow's `paths-ignore` stops applying the moment one
  path is not. Expect two runs, and do not "fix" it — it is the safe direction.
- **The wildcard set makes the feature's own PR look unfiltered.** A diff that touches `.github/**` or
  `Makefile` reports every class and every job (correctly). Do not present that as "the filter did not
  work": show a docs-only path list for the win instead.
- **`paths-ignore` must cover the non-markdown documentation paths too.** `docs/**`, `agent-wiki/**`
  and `openspec/**` carry JSON/YAML/text files as well as `.md`; forgetting one keeps the full job
  floor for a docs edit that touches no markdown at all.
- **Never filter markdown by extension (`**/*.md` / `*.md`).** In this repo markdown is not documentation
  by its suffix: `data/trending-README.md` and `data/MODEL_CONTRACT.md` are read by `sync_registry.py`,
  `.hermes/skills/**/SKILL.md` are the agent legs' contracts, `skills/engines/**/SKILL.md` is what
  `generate-engine-params` reads, and `tests/fixtures/**/*.md` are unit fixtures. A diff containing ONLY
  one of those matches `**/*.md` on every path, so GitHub skips `ci.yml` entirely and the registry/unit
  gates that file needs never run. List the five class paths instead, assert the list is EXACTLY the
  classifier's docs class, and add a repo-wide guard that fails on a `**/*.md` entry in ANY workflow's
  `paths`/`paths-ignore`, so a tidy-up in a second workflow cannot reintroduce it.
- **No `uses:` additions.** Reuse the repo's pinned `actions/checkout` SHA and `./.github/actions/docker`;
  a new orchestrator action fails review even when it is pinned.
