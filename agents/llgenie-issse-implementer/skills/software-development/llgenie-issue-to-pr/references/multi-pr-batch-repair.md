# Repairing a BATCH of sibling PRs from one tracker issue

A tracker issue asks you to fix N open PRs that a generator (dependency/engine bump workflow, a
codemod job) opened and that all red the SAME gates. One issue, N branches, N PRs — no new PR is
created; each existing PR gets a pushed fix commit.

## Before touching anything

1. `gh pr list --search "<n>" --state all --json number,headRefName,headRefOid,mergeable` and
   cross-check `headRefName` against the branches the issue names. A batch can be half-landed
   already; a PR that is MERGED or CLOSED is out of the batch.
2. `git worktree list --porcelain` + `ls <repo>-wt/<slug>*` — a multi-PR batch usually ALREADY has
   one long-lived worktree per branch from an earlier window. Reuse them (they hold uncommitted or
   unpushed work); do not create a second worktree on the same branch, and never remove one.
   Compare each worktree's `HEAD` against `git ls-remote origin <branch>` — a worktree ahead of the
   remote means the fix was made but never pushed, which is the cheapest case to finish.
3. Find where each branch actually lives: bump/codemod branches are usually on `origin`, agent
   branches on a `fork` remote. `git ls-remote <remote> refs/heads/<b>` decides which one to push to.

## The per-branch loop

Do ONE branch fully (gates green locally, pushed, comment posted) before starting the next — a
half-applied batch leaves the same convention in two states, and an error in the generated
text (a missing newline, a wrong issue number) is then repeated N times.

```
for each branch:
  cd <worktree>; git fetch <remote> <branch>
  # 1 content: add the owed artifacts (trio / docs row) with correct stems
  # 2 message: git commit --amend  (drop the claim line; keep the descriptive body)
  # 3 gates:  make check-pr-closing check-docs changes-index lint   -> rc 0 each
  # 4 push:   git push --force-with-lease --force-if-includes <remote> <branch>
  # 5 record: echo "<branch> $(git rev-parse --short HEAD)"
```

Amending with `--no-edit` after `git add` of new files is correct when only the trios changed; when
the claim line also has to go, amend with an edited message and then verify the TREE still carries
the bump: `git diff <pre-amend-sha> HEAD --name-only` must list only the docs/note files.

### The closed-issue claim lives in the COMMIT MESSAGE too

The squash-text half of `check-pr-closing` reds a bump/codemod PR whose COMMIT MESSAGE cites a
tracker issue that is CLOSED (the body alone is not enough). `gh issue view <n> --json state`
first: if closed, drop the claim from the commit message (`Issue: #<n>` line) AND the PR body,
closing nothing — do not repoint a generated bump at a closed tracker. If a live tracking issue
exists, cite that instead.

## Serving drift: a pin bump must move the BASE IMAGE too

An engine bump that raises a version pin while the served base image (`Dockerfile*`,
`params/<engine>.json`, the engine `SKILL.md`) still points at the old tag is a silently broken
PR — the pin says vX but the container still runs vX-1. After bumping the pin, grep the changed
engine's tree for the OLD version string and move every base-image / fallback reference to the new
tag in the SAME commit. Confirm the new tag really exists before writing it
(`docker manifest inspect <image>:<tag>` rc 0, plus a control `…:<old-tag>` rc 0 to prove the probe
works). Record the base-image move in the change-note so the trio describes what the container will
actually run.

Then prove the committed tree is exactly what the generator emits — this is the `assert==tree`
check the unit gate performs:

```bash
make generate-engine-params        # expect: [engine-params] 0 file(s) changed
```

0 changed means the committed `Dockerfile*`, `params/<engine>.json` and `SKILL.md` already match
the generator output. A mismatch reds
`tests/test_engine_skills.py::test_official_upstream_images_are_used_as_bases`, which reads the
ACTUAL generated Dockerfile (`es.dockerfile_path().read_text()`) and asserts the base
`FROM <image>:<tag>` — so a pin that moved in params/SKILL but lagged in `Dockerfile.cuda` is a
RED unit gate, not a cosmetic diff. Drive the fix through the generator (bump the pin, re-run
`make generate-engine-params`) rather than hand-editing the emitted Dockerfile.

The same `assert==tree` lag also bites the committed GENERATED MANIFEST, not just the Dockerfile:
a pin bump to `0.40.13` with `containers/engines/binaries.json` still naming `0.40.12` reds
`test_engine_skills.py::test_committed_engine_params_match_the_skills` (it regenerates in
check-only mode and asserts nothing differs — the red is the lag, not the bump). `make
generate-engine-params` fixes it across every variant (cuda/rocm/vulkan/cpu). Prove it against
the pushed OBJECT, not the test: `gh api
"repos/<o>/<r>/contents/containers/engines/binaries.json?ref=<sha>" --jq .content | base64 -d |
grep -c '<new-ver>'` (want the variant count) and `grep -c '<old-ver>'` (want 0), and a re-run
of `make generate-engine-params` reporting `0 file(s) changed`. Never edit the test or the
assertion to match a stale manifest.

Not every per-arch Dockerfile carries a raw engine tag: a `Dockerfile.rocm` may build
`FROM rocm/pytorch:...` (no upstream engine tag), so grep will find the old version string only in
the arch that consumes the engine image — do not invent a bump for the arch that never references
it, and say so when asked to bump "both cuda and rocm".

## Verify the batch, not the last branch

- Loop the gate commands over every worktree and print one line per branch (`ok` / `FAIL`), not a
  wall of output; re-run any FAIL in isolation.
- After pushing, `gh pr checks <n> --repo <o>/<r> --json name,state` per PR and grep for
  `guard`/`scope`. A batch is delivered when every PR's `<gate>:SUCCESS`; pending legs
  (`IN_PROGRESS`/`QUEUED` on the linux matrix) are not a defect — say so instead of implying green.
- $? for `gh pr checks` is 8 while anything is pending; never read the exit code as the verdict.
- The `linux / unit` leg runs ~14 minutes. A short poll budget (e.g. 40 x 15s = 10 min) expires
  BEFORE the verdict and reads as "still running", not as a failure. Poll with one generous
  timeout (~600s) or a long budget, and if it still expires, report the leg as in-progress rather
  than re-triggering the whole suite.

### Distinguish an external gate red from a branch-editable one before touching it

A `publish-order` / tag-not-found red on `linux / unit` can be caused by SIBLING PRs whose release
tags are not yet published — it is external to your branch and clears when those siblings merge.
Before "fixing" a red, classify it: an index row that lags the fragment, or a committed manifest
that lags the skill pin, is branch-editable (regenerate it); a tag published by another PR is not
yours to fix by editing your branch. Confirm ownership (does the failing object even exist on your
branch? does the tag's PR predate yours?) and, if external, say so and wait rather than churn.

## Mergeability across the set

Sibling PRs generated at different times sit on different bases. `mergeable`:

- `MERGEABLE` → leave it alone (never rebase a mergeable branch just because main moved).
- `CONFLICTING` → rebase THAT one onto current `origin/main`, then re-render shared-append files
  (CHANGES.md) from the fragments rather than hand-merging the conflict markers.

Rebasing one branch of a batch does not oblige you to rebase the rest.

### Another lane can force-move your branch mid-flight — re-confirm the head and your content

A rebase/merge-conflict maintainer lane may re-stack your branch onto the fleet chain while you
still own it. Your pushed sha is then NOT the merged head, and the merged chain is often NOT a
descendant of your push (identical commit messages, different shas, sitting on current `main`).
After any push you did not control, re-confirm both the head and that YOUR content survived the
re-stack:

```bash
gh pr view <n> --json headRefOid --jq .headRefOid
git ls-remote origin refs/heads/<branch>            # must equal headRefOid
git show <newhead>:containers/engines/binaries.json | grep -c '<new-ver>'   # variant count
git show <newhead>:containers/engines/binaries.json | grep -c '<old-ver>'   # want 0
git show <newhead>:CHANGES.md | grep '<fragment-stem>' | grep -oE '<oldsha>|<newsha>'
```

The deliverable is the content being correct at whatever head merges — not the sha you pushed.
When a re-stack happened without the lane messaging you and its rule requires an all-clear, flag
the un-acknowledged rebase to the planner, but do not rewrite a branch another lane is holding.

After the PR is MERGED, prove the fix landed on main — "state: MERGED" alone is not the proof:

```bash
git fetch origin +refs/heads/main:refs/remotes/origin/main
git show origin/main:<path> | grep -c '<new-ver>'      # want the variant count
```

## Reporting

Post the same finish comment on every PR (head sha, which gates were red, what changed, local rc 0
proof), then ONE summary to the planner listing all N heads and the per-PR gate state. Never claim
"all green" while a leg is still pending — report the pending legs explicitly.
