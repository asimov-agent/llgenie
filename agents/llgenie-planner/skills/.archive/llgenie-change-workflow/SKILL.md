---
name: llgenie-change-workflow
description: "Use when making a change in the llgenie repo."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [llgenie, openspec, makefile, github-actions, security-pipeline]
    related_skills: [pr-landing-on-moving-master, worktree-branch-hygiene, derived-document-generators]
---

# Changing the llgenie repo

## When to Use

The work is a change in `/home/asimov/repository/git/llgenie` (or a worktree cut from it): a feature, a
fix, a pipeline edit, a make target. The repo's `AGENTS.md` is the CONTRACT (issue-first, OpenSpec
change before code, one worktree per agent/branch, `make loop`, docs note + `CHANGES.md` row, PR closes
its issue). This skill is the operational half: what actually fails while doing that, in the order it
bites.

## Sequence (short — AGENTS.md owns the rules)

1. `gh issue create` the work item FIRST (or confirm the existing issue), then
   `make openspec-new NAME=<kebab>` and write `proposal.md`, `specs/<cap>/spec.md` (Given/When/Then,
   each scenario carrying a `- **Test:**` line), `tasks.md` BEFORE any code.
2. `git fetch origin main && git worktree add -b feat/<kebab> ../llgenie-wt/<kebab> origin/main`; do
   all edits, gates and pushes in that worktree. Never `git switch` in the user's checkout.
3. Implement, then run the gate set cheapest-first (below).
4. Commit with the three-part body (`Issue:` / `Fix:` / `Benefit:` + `Technical:`), push to the
   **fork** remote, open the PR against `asimov-agent/llgenie:main` with
   `--head andyholst:<branch>` and a `closes #<issue>` line.
5. **Re-read the branch state immediately before the push, and look for an existing PR first.**
   `git log --oneline -3 && git status --short` (a helper, a rebase bot or an earlier turn may have
   committed or amended on top of you — the head CI runs is whatever is at HEAD), then
   `gh pr list --repo asimov-agent/llgenie --head feat/<kebab> --state all`: an existing PR is updated
   by the push, and a second `gh pr create` is a defect. After the PR is up, `gh pr checks <n>` is the
   only evidence that counts; a lowercase `pending` can also be a stale row from a superseded run, so
   confirm against `gh run view <run> --json jobs` (`status`/`conclusion`) before deciding a job is
   still running.
6. **A worktree and a PR from an earlier session are the normal starting point, not an empty one.**
   `git worktree list` shows the branch's worktree; `git log --oneline origin/main..HEAD` says whether it
   already carries work. Reuse that worktree (never cut a second one for the same branch), `git status`
   first: uncommitted work makes `git rebase origin/main` refuse with "cannot rebase: You have unstaged
   changes" — commit it with a real three-part message, then rebase and re-run the cheap gates on the
   result.

## Pitfalls that cost the most time

**Never round-trip a large tracked file through `read_file` → `write_file`.** `read_file` returns
line-number-prefixed text and truncates (2000 lines / ~100 KB). Stripping the prefixes and writing the
result back silently DELETES the tail — a 1600-line `Makefile` came back 487 lines short and the loss
was only visible in `git diff --stat`. Edit with `patch` (unique anchor snippet), or rewrite whole
files with a python heredoc that reads raw text (`Path(p).read_text()`), never through the formatted
view. Recovery: `git checkout -- <path>` and re-apply.

**A whole-file rewrite of a file you already touched must go through python, not `write_file`.**
`write_file` refuses ("modified since you last read it" / "last read with offset/limit") once a file
has been partially viewed or edited, and that guard fires exactly when you are legitimately replacing
a 200-line function you just patched. Do the replacement in `execute_code` with
`Path(p).read_text()` → string surgery → `Path(p).write_text()`, then `python3 -c "import ast;
ast.parse(...)"` (or the file's own gate) to prove it still parses.

**`make openspec-new` leaves a root-owned change directory.** The CLI runs in a container as root, so
`openspec/changes/<name>/` is owned by uid 0 and `write_file` fails with EACCES. `sudo chown -R
"$USER":"$USER" openspec/changes/<name>` immediately after creating it, before writing anything.

**Paste a generated doc table with `make -s <report-target>`.** Without `-s`, make echoes the recipe
line (`python3 scripts/check_dispatch_forms.py report`) as the first line and it is pasted INTO the
doc, so the gate still reports the table stale after a byte-perfect copy. Same for any report target
whose stdout you redirect into a file.

**A new dispatchable workflow must satisfy `check-dispatch-forms` in one go:** a `name:` of the shape
`<identifier> — <what it does>`, the header keys `# Trigger surface:` / `# Flow:` / `# Never:` in the
leading comment block, any `HH:MM UTC` it claims must equal the workflow's own cron, every
`workflow_dispatch` input needs a `description:` plus `default:`/`required:`, and a bare dispatch needs
`# dispatch: no inputs — <reason>`. Then regenerate the table with `make -s dispatch-forms-report` into
the `docs/BOTS.md` markers.

**But the dispatch form is only 1 of 5 contracts a workflow must meet — read
`references/adding-a-workflow.md` before writing one.** The other four live in *different* unit-suite
files and none of them is covered by a make gate: the byte-identical `guard` job plus `needs: [guard]`
(`test_workflow_guards.py`), a cron minute no other bot owns and no every-hour bot reserves
(`test_bot_pipeline_isolation.py`), no `python3 scripts/<x>.py` in any `run:` — reach it through a make
target such as `make require-env KEYS=…` (`test_code_review.py`), and only `secrets.<NAME>` values that
are in `scripts/check_secret_output.py::SECRET_VARS` (`test_secret_output.py`). Run those four files
after every workflow edit; a green cheap-gate batch does NOT mean the workflow is legal.

**An authorship gate reads SOURCE TEXT, so write the identity as inline quoted literals.** A static
check scans the producers for `user.name`/`user.email`; a module constant fails as "authors commits as
`{AUTHOR[0]}`", and an unquoted `user.name=Asimov Agent` parses as `Asimov`. Use
`["git", "-c", 'user.name="Asimov Agent"', "-c", 'user.email="support@docondee.com"', "commit", …]`,
add no `Co-authored-by:` trailer naming anyone else, and run `make check-pr-authors` before pushing.

**`scripts/issue_bot_gates.py::FAST_GATES` is PINNED at exactly six by a unit test — never widen it.**
A new `make ci-unit` gate must be classified in `DEFERRED` with a reason ("a producer/rule change moves
it, ci-unit already catches it on the bot's own PR") and wired into `ci-unit`; adding it to `FAST_GATES`
reds `tests/test_issue_bot_gates.py` ("widening it is a different issue"), and the finding arrives only
after a full `make test-unit` round trip. When a change wants a gate re-checked before the bot pushes,
that is its own issue — not a one-line edit here. Never "fix" a red gate by editing the test that pins
the list.

**An OpenSpec spec file needs delta headers or `make openspec-validate` refuses it.** The shape is
`## ADDED Requirements` (also `MODIFIED`/`REMOVED`/`RENAMED`), then `### Requirement: <name>` with a
MUST/MUST NOT paragraph, then one `#### Scenario:` per behaviour with `Given`/`When`/`Then` on separate
lines and a `- **Test:** \`tests/…::test_…\`` line. A file of `## Requirement:` headings alone parses
as zero deltas: "Change must have at least one delta". Validate before writing the implementation, not
after — the error costs a container round trip.

**A shared module whose name equals a producer's own function needs an import alias, not a rename.**
`code_review`, `run_failure_reactor` and `engine_skill_gap` each export a function called `issue_body`, so
`import issue_body` is shadowed by the local `def` and the call resolves to the function ("Module is not
callable"). Use `from issue_body import render as render_body`, keep the published function name, and
update no caller. The same collision hits any new `scripts/<topic>.py` whose stem is already a function
name in the file that imports it.

**A source-text gate must match a BUILT shape, never a mention in prose.** A first cut that flagged any
`## Technical` literal in a producer fired on every docstring that said "the `## Technical` detail".
Match a quoted, standalone heading (`"## Problem"` as a list item or string) and let backticked prose
through — otherwise the gate is red on a clean tree and gets deleted instead of fixed.

**A renderer that bullet-prefixes every item mangles a fenced or multi-line one.** `issue_body.render`
emits `- ` per technical fact, so a caller that passes a fenced report as three items (`"```"`, the
body, `"```"`) gets `- ``` ` lines and a fence that collides with itself; and wrapping a block the
caller already fenced puts one fence inside another. Emit multi-line items verbatim (one bullet per
fact, blocks left as blocks), pass an already-fenced report as ONE item, and assert the produced
body (`issue_body.headings(...)` out of the recorded `gh` argv) rather than trusting the call.

**Run a targeted test file from the repo venv, not from PATH.** There is no `pytest` on PATH;
`~/llama-gguf-tools/.venv/bin/pytest -q tests/test_<x>.py` is the fast loop, and `make test-unit` (in
the test container, discovered suite) is the gate that counts. Gates need a container engine: use
`NERDCTL=docker` when `nerdctl` is absent, e.g. `make -C tools generate-requirements NERDCTL=docker`.

**`gh pr edit --body-file` can land a body that does NOT contain the phrase you wrote — re-read and assert it.** A body edit races the workflow run that reads it, and a silent no-op leaves the old body in place. After every body edit, `gh pr view <n> --json body --jq .body` and grep for a distinctive required phrase AND for `closes #<n>`; a count of 0 means the edit did not take — retry the edit before reporting the PR ready. The same read-back applies to a cross-link added to an issue.

**Then verify the body's CLAIMS against the tree — an edit that took can still be wrong.** A body that named an `agent-wiki/…` file the branch does not create, and a `make test-unit` count from a superseded run, both read as verified because the write succeeded. For every path the body names, `git ls-tree -r --name-only HEAD` it (or `search_files` target='files' in the worktree); for every number it quotes, take it from the log you actually have (`grep passed /tmp/<unit>.log`), and rewrite the line when it differs. A PR body is what a reviewer checks the diff against.

**A request to make a scanner "less sensitive", or to add a daily bump/self-correction loop, is the four-owner model — never move enforcement.** Route it to `references/security-pipeline.md`: the scan stays schedule/dispatch-only (`enforce_events` in `data/security-policy.json`), findings become FLOORS in `tools/security-floors.in` (max of the minimums) and pins are regenerated, freshness belongs to Renovate with NO `automerge` key (the repo's `auto-merge` job is the only merge authority). Putting a scanner or a bump loop on `pull_request:`/`push:` — or "fixing" noise by adding `automerge: true` — is the regression `make check-security-scan` exists to refuse.

**Push to `fork`, not `origin`.** `origin` is `asimov-agent/llgenie` (upstream); the personal fork is
`fork` (`git remote -v` first). `git push -u origin feat/<name>` creates a stray branch on the base
repo; the PR head must be `andyholst:<branch>`.

**A push rejected with "the tip of your current branch is behind its remote counterpart" means the
branch already has commits you do not.** That is an earlier session's work on the same PR branch, not
a reason to force: `git fetch fork <branch>`, `git diff FETCH_HEAD HEAD --stat` (usually a handful of
lines), then `git reset --hard FETCH_HEAD`, `git apply` that diff and commit it as a NEW commit — the
push is then a fast-forward and the PR's history grows instead of being rewritten. Reserve
`--force-with-lease` for the case the rebase rules allow (your own branch, after you rebased it), and
never for appending a fix to an open PR that already has review history.

**Never change the worktree while `make test-unit` is running in it.** Committing, rebasing or
`git reset --hard` under a live suite makes its result un-attributable: the tests read the tree at the
moment each test runs, so a mid-run reset can mix two revisions. Finalize the tree (commit the fix,
rebase, re-run the cheap gates) BEFORE starting the long suite; if you must edit after it started, kill
it, edit, and rerun — and treat the CI run on the pushed head as the authoritative pass.

**A FORK-head PR cannot publish anything to this organization's GHCR packages, so keep the test
image's inputs UNCHANGED on a fork branch.** The test/openspec/agent image tag is a content hash of
`containers/test/Dockerfile` + `tools/requirements*.txt`, so a lockfile or pin bump changes the tag and
`ci-images` must push it — which the fork's `pull_request` token cannot (`denied: installation not
allowed to Write organization package`), and then `install-published-*` fails too because it runs
inside the tag that was never published. `publish-ci-images` has no fork skip (only the engine images
do), so the whole run is red and unmergeable. Ship the MECHANISM on the fork branch with an empty
floor/unchanged lockfile, and let a same-repo branch (`security-bumps`/`fix-bot` run with
`BUMP_TOKEN`) carry the actual pin move — its PR can publish. `make -s ci-image-refs` shows the test
image hash; if it differs from `origin/main`'s, you are about to trip this.

**Rebase conflicts on this repo always land in the same three places:** the `.PHONY:` continuation
block, the newest `CHANGES.md` table row, and the `README.md` docs-reference table. Resolve as a
UNION (keep both sides' rows/targets), strip duplicate lines the union produced, and re-run
`make check-wiring check-docs lint` — the doc gate reds on a duplicated or dropped row, and `lint`
reds on a markdown heading with no blank line before it.

`scripts/resolve_union_conflicts.py` (this skill) drives that whole loop for a rebase: it keeps both
sides of every conflicted block, puts the BRANCH's row above the base's in `CHANGES.md` (the index is
newest-first, and during a rebase "theirs" is your commit), refuses to continue while any
non-`CHANGES.md` file is still conflicted, and stops when the rebase finishes. Read its output rather
than trusting it: a stray `<<<<<<<` is invisible to git and only a syntax/gate run catches it.

**After a rebase onto a base that added a workflow job, re-pin the Actions.** The rebase drags the
new job's `uses:` refs into the branch, so a pin gate that was green now names them unpinned. Run the
repo's documented update path (`make update-actions` — it writes the full SHA plus the readable tag
comment) and commit it as its own `ci(actions): …` commit; never hand-write a SHA and never relax the
gate. The same shape applies to any derived artifact the base's new jobs move.

**"The registry sync did not implement / does not regenerate the trending list" is a four-leg question — read `references/registry-sync-pipeline.md` before diagnosing it.** The weekly `registry-sync` writes data and derived tables only (`data/models.json`, the quant catalog, the per-`(arch, vram, ram)` trend list with its fastest fitting server, `data/engine-skill-gap.json`); `registry-sync-review` files ONE `agent:implement` issue about a green sync PR; `issue-bot` is the leg that writes code; and `check-engine-skill-gap` in `ci-unit` keeps the sync PR red until a new engine ships a skill or a dated decision. Nothing in the sync chain implements a contract, by design — say that instead of hunting for a missing step. A red run is usually that job's OWN step 9 (`test-unit`), not a broken sync: the four data steps pass, then 2-4 families of goldens red — and because the spawn-issues and PR steps carry only `if: steps.diff.outputs.changed` (no `always()`), a red week files no engine issues and opens no PR. Read the families and the worktree reproduction recipe in the reference before blaming the sync.

**Prove the committed artifacts with the read-only `check-*` targets, in the user's checkout, before touching any run.** `make check-trend-list-matrix check-registry check-engine-skill-gap` plus the `generated_utc` of `data/models.json`, `data/engine-skill-gap.json` and `tests/fixtures/trend-list-matrix.json` separate "the artifacts are stale" (stamps differ) from "the code is broken" (stamps agree, a check still red) — and they mutate nothing, so no worktree is needed for a diagnosis. A check that is red while the stamps agree is a code/generator bug: reproduce the chain in CI order in a worktree (`sync-registry` → `sync-quant-catalog` → `render-trend-list-matrix` → `render-engine-skill-gap`), because every render reads the catalog and rendering the matrix out of order invents dozens of fixture-mismatch failures that look like regressions.

## Gate set, cheapest first

```bash
make -s lint check-wiring check-docs check-workflows check-dispatch-forms \
     check-issue-bodies check-agent-skills check-pr-hygiene check-pr-authors check-actions \
     check-security-scan check-security-bumps issue-bot-gates-check
make openspec-validate NAME=<kebab>          # must exit 0 before "done"
make test-unit                                # background(true, notify) — 9-13 min
```

Long containerized stages print nothing until they finish: run them as a background terminal with a
log, never a foreground call that dies on its timeout. A foreground `timeout=600` is still cut off
around 7 minutes, so polling a CI run with a `for … sleep 25` loop in the foreground dies mid-wait —
poll with a short loop and simply re-issue the call, or run the wait in the background.

`gh run view <id> --log` serves nothing until the run COMPLETES (it exits non-zero with an empty
body), so on a live run read progress from `--json jobs … .steps[]` instead of the log. A run parked
in the sync job's `test-unit` step for 20-40 minutes is normal.

`make test-unit` is not optional when the change touches `.github/workflows/**`, a `scripts/*.py` a
workflow reads, or a generated `requirements*.txt`: those edits are checked only by contract tests in
the discovered suite, so the cheap batch above says nothing about them. Read the tail of its log — the
pass/fail line names the file, and the fix is usually one of the pitfalls here. It takes ~9 minutes and
prints nothing until it ends, so start it in the background with a log file and keep working; when it
comes back red on a workflow you added, fix the contract (guard / cron slot / make seam / secret
roster) and re-run the four contract files plus `make test-unit` again — a green cheap batch after the
fix proves nothing about the suite.

## Filing an issue is a deliverable of its own

An issue is the root of the pipeline (issue → branch → OpenSpec → code → PR → `closes #n`), so its body
is read by someone who was not in the run that filed it. Write **six** sections, in this order, every
time (AGENTS.md carries the same rule; `scripts/issue_body.py` is the one renderer and
`make check-issue-bodies` is the gate):

```markdown
## Problem              the measured symptom (observed, with numbers), not the ticket title
## Why it matters       the consequence of leaving it: what breaks, what it costs, what it blocks
## How we fix it        numbered, plain language; no file paths yet
## Benefit              what the reader gets once fixed / what stops happening
## Acceptance criteria  one `- [ ]` item per provable outcome — "done" as a list, not an adjective
## Technical            LAST and only here: files, make targets, tests, gates, measured numbers
```

`## Not covered` is optional and sits between the acceptance criteria and `## Technical`.

- **Acceptance criteria are a section, not a brainstorm.** Every line is a `- [ ]` a reviewer can
tick; prose in that section fails `make check-issue-bodies` exactly as a missing section does. Keep the
same six sections when restating an existing issue (the triage/refiner legs do).
- **Measure before you write.** `gh run view <id> --json jobs --jq '.jobs[]|select(.name|test("x"))|\"\(.name) \(.startedAt) \(.completedAt)\"'` gives real durations; "this wastes 3 minutes" is only a claim with a run number beside it.
- **Out-of-scope items get their OWN issue, linked BOTH ways** — the filed issue's `Not covered` names
the side issue's number, and the side issue states which issue it came from. A "Not covered" bullet
with no number is the defect. Filing 2 requested issues can legitimately produce 3.
- **Never edit the user's checkout to record the filing.** The issue is the artifact; AGENTS.md / skill / code edits belong to the implementing PR on a worktree.
- **Write against the branch that will land, and say so.** If the issue is based on an open PR, read it (`git fetch origin pull/<n>/head:pr<n>`, `git show pr<n>:<path>`), quote what that branch's file actually says, and add a line stating the dependency plus what follows it if the PR changes shape.
- `gh issue edit <n> --body-file <file>` is how a cross-link gets added after the numbers exist; verify with `gh issue view <n> --json body` and assert the section headings and order in code, not by eye.

## Security pipeline invariant (do not re-derive it)

Before touching anything under `.github/workflows/security-*`, `scripts/security_*`, `renovate.json` or
`tools/requirements*.in`, read `references/security-pipeline.md`. The rule that matters most: the scan
is its own daily pipeline and must never gate a pull request or a push.
