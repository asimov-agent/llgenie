# Gate-red vocabulary: `mergeable` vs `mergeable_state`, and the two most common PR gate reds

## `mergeable` (file-conflict) vs `mergeable_state` (gate matrix) — never conflate
- `mergeable=true` means *only* "no file conflict". A PR can report `mergeable=true` **and** `mergeable_state=blocked` simultaneously.
- `mergeable_state` is the aggregate gate verdict: `blocked` = at least one required check is not green (a red **or** still in_progress/queued); `clean` = all green and passable; `dirty`/`conflicting` = a real merge conflict.
- So "mergeable=true" is NOT a green PR. The green signal is `mergeable_state=clean` (or all check-runs `completed/success` on the head). Don't answer "is the PR green?" with `mergeable=true`.
- `mergeable`/`mergeStateStatus` can both read **`UNKNOWN`** immediately after a push or right as required checks finish — GitHub is still recounting merge state. That is a transient third state, not `blocked`/`dirty` and not evidence the PR is unmergeable. Re-read once a moment later (`gh pr view <n> --json mergeable,mergeStateStatus`) before reporting; it resolves to `MERGEABLE`/`clean` (and to `MERGED` once the owner merges) on the recount. Never read `UNKNOWN` as a red or reopen work over it.

## #845 stale-base red — `BASE:` body text does NOT move the tree
- The guard compares the head's **true merge-base** against the base, not the `BASE:` string in the body. Writing `BASE: <sha>` in the body never changes the tree.
- **Measure the *actual* ancestry**, never trust the body:
  `git fetch origin main` then `git merge-base origin/main <head>`; a `diverged` compare (ahead N / behind M) means the branch forked earlier than the body claims.
- **`origin/main` is the LOCAL tracking ref — a stale shadow until you fetch.** `git show origin/main:<path>`, `git merge-base origin/main`, `git ls-tree origin/main` and `git log origin/main` all read that local ref, NOT the remote. After a merge lands the local `origin/main` still points at the pre-merge base, so an "is my file on main?" check reads the OLD tree and reports the file missing (cost real time this session: 0/2 files, then 4/4 once fetched). Always `git fetch origin '+refs/heads/main:refs/remotes/origin/main'` immediately before any ancestry/content check, print the sha it moved to (`git rev-parse origin/main`), and verify against that — or use `git ls-remote origin refs/heads/main` for the authoritative tip. Confirm the merge commit is an ancestor: `git merge-base --is-ancestor <squash> origin/main`.
- Fix = rebase onto live `origin/main`: `git rebase origin/main` (after `git fetch origin refs/heads/main:refs/remotes/origin/main --no-tags`), so `merge-base == base`. Check `git merge-tree --write-tree origin/main HEAD` first for a clean non-conflict; after rebase the merge-base must equal the base sha.

## #792 check-pr-agents-line red — never hand-write AGENTS:/BASE:
- The guard validates the **literal `make bot-preflight` output**: `<sha> <bytes>b <lines>l` for `AGENTS:` and `<sha> (== origin/main at open)` for `BASE:`.
- Run `make bot-preflight` on the branch and copy its exact two lines into the PR body. A hand-composed `AGENTS: <sha> <sha> census-ok` (or any non-preflight shape) reds the guard.
- The full sha and the `XXXb`/`YYYl` suffixes are mandatory; the preflight output is the single source of truth for the format.

## After the fix: fresh CI is required, and in_progress is not red
- The gate matrix re-evaluates on each push; `mergeable_state=blocked` while required checks are `in_progress`/`queued` is normal, NOT a defect. Wait for all to reach `completed`. Then confirm each conclusion == `success` and `ci-verdict` reads green before calling the PR green.
- Rebase + preflight + amend + push with **plain** `--force-with-lease`; both fork and origin must show the new head (`git ls-remote fork <b>`, `git ls-remote origin <b>`).
- Use the plain `--force-with-lease` form; the explicit `--force-with-lease=<ref>:<expect>` form can reject in this repo even with the correct expected sha — fall back to the plain form rather than debugging the lease.
- Amending an ALREADY-pushed commit (same files, changed tree) can leave `refs/pull/<n>/head` stuck at the previous sha while the fork branch itself advances. Fresh shas reconcile reliably; an amend may not. If the PR head lags after an amend, poll `gh pr view <n> --json headRefOid` a few times, and if it stays stuck add a fresh commit on top instead of re-amending, then re-check. Cross-check the fork with `git ls-remote fork <b>`.

## check-pr-acceptance red on a fix PR — the verdict-gated self-red, NOT your deliverable
- `scripts/check_pr_acceptance.py` (Makefile `check-pr-acceptance`, run inside both `guard` and `scope`) reads the **LIVE issue the PR closes** and reds `claim-unchecked` while that issue's own `## Acceptance criteria` boxes are still `- [ ]`. On a fix PR that closes the issue it fixes, those boxes are unticked by definition until a **reviewer verdict** lands — so this red is BY DESIGN and is not an incomplete implementer step.
- The tick happens ONLY through the verdict-gated write-back seam (the reviewer's COMMENTED verdict writes the boxes back). The implementer must NOT self-tick the issue, must NOT add a fake `## Not covered` deflection, and must NOT edit the issue body to green it — that is fabrication and defeats the gate.
- A PR body that ticks a criterion the issue still leaves unchecked instead trips `claim-exceeds` — worse than the self-red. Keep the PR body's acceptance boxes unticked, mirroring the issue, awaiting the verdict.
- The `scope` failure and the `ci-verdict` / decision-artifact read on the same run are DOWNSTREAM of this one step: `scope` never publishes its artifact because `check-pr-acceptance` failed first, so `ci-verdict` reads a missing artifact. Confirm by reading the `scope` job's step list — its ONLY failed step must be `make check-pr-acceptance`; every implementation step (`ci-lint`, `check-docs`) should show `success`.
- `openspec-image` / `ci-openspec` appearing after the failing step are **skipped (sequenced), not failed** — never report OpenSpec as red when the step was skipped. Verify OpenSpec locally instead: `make ci-openspec` rc=0 (and `openspec-validate` rc=0).
- Correct handling: prove every implementation gate green locally AND on the wire (lint, check-docs, openspec, body gates, holds), then report the ONE designed self-red honestly and hand the PR to the reviewer lane for the verdict. State task-relative verification (the new tests pass, full `make test-unit` count + `EXIT=0`) so "not done" is refuted by evidence — never claim wire-green and never fabricate a tick.

## check-proc-gate red — `# proc-allow:` must share the PHYSICAL line with the call
- `scripts/check_proc_gate.py` (Makefile `check-proc-gate`) flags every `subprocess.run(` in `scripts/` that lacks a `# proc-allow: <reason>` marker **on the same physical line**.
- A call split across lines with the comment on a continuation line is NOT recognised — the gate inspects each physical line containing `subprocess.run(` for the marker. Put the call on one line with the trailing comment: `subprocess.run(cmd, ...)  # proc-allow: <reason>`. Verify locally with `python3 scripts/check_proc_gate.py check` (must exit 0) before pushing, or `linux / unit` reds on the proc gate rather than on pytest.

## Post-merge verification — a merged branch is behind advanced main BY DESIGN
- After a PR merges, `main` advances past the base the branch was cut from. Running `make check-pr-base` on that now-stale branch correctly FAILs ("not cut from `origin/main`", naming the branch's own commits as foreign) — that is the gate working as intended, NOT a defect, and NOT unfinished work. A merged branch is read-only forever; never rebase it or reopen the issue to "fix" that red.
- Verify the merged content instead: fetch live main (explicit refspec), then confirm the files/key lines exist on the fetched `origin/main` (`git ls-tree origin/main -- <paths>`, `git show origin/main:<path> | grep …`). Prove the gate's POSITIVE path with a throwaway local branch off the live tip (`git checkout -b verify-<n> origin/main && make check-pr-base`, expect rc=0), then `git branch -D verify-<n>` — never push that branch.

## A `verdict` red on your merge sha may be judging SOMEONE ELSE's head
- The verdict workflow evaluates the CI **run** it names, not the sha it is triggered on. A
  `verdict` job that failed in the post-merge run at your commit can be reporting on
  `run <other-id>` at a different head — another lane's PR. Read the job log for the two ids
  (`evaluated run`, `head`) before attributing the red to your merge, and name both in the report.
- The failing job's log endpoint often returns empty for guard/verdict jobs while the run is still
  `in_progress`. That is "error line not yet retrievable", never a cause: wait for completion, then
  re-fetch. Do not publish a cause inferred from the step name.
- Your merged commit is green only when its OWN post-merge `push` run (the run whose `head_sha` ==
  your merge sha) is `completed/success` with `linux / unit` success; a verdict run firing before
  that run finishes reads a null/in-flight attempt and is not evidence either way.

## CLI vs REST field names — `mergeStateStatus` ≠ `mergeableState`
- The REST field is `mergeable_state` (via `gh api repos/<o>/<r>/pulls/<n> --jq .mergeable_state`).
- `gh pr view --json` does NOT expose `mergeableState` — it reds `Unknown JSON field: "mergeableState"`. The CLI's camelCase name is **`mergeStateStatus`**; the boolean is **`mergeable`**. Measure with `gh pr view <n> --json mergeable,mergeStateStatus,state,headRefOid`.
- A `gh api … --jq '{…}'` that returns every field `null` (e.g. `headRefOid`, `baseRefName` all null while `state` is populated) is a transient partial read, not an empty PR — re-run the call once before concluding anything; `gh pr view --json` is the fallback that answers in one shot.
