# Pitfalls — measured failures and what each one cost

Split out of `SKILL.md` when that file reached the ~100,000-character cap and could
no longer accept new lessons. Content is verbatim.

- **`agents/<profile>/SOUL.md` is a protected agent-instruction file: every edit needs its own interactive approval, which can time out and then refuses a retry.** Batch a lane's SOUL change into ONE write — the fleet block, the lane section and any new rule together — instead of patching the file three times, or you spend three approvals on one file and finish with two of three rules landed (a missing rule is invisible: `check-agent-profiles` only proves the rules the manifest declares). If a write is refused after a timeout, stop and ask the user to approve the prompt; do not route the edit through `terminal`, `execute_code`, or a second path.
- **`make check-agent-profiles` compares the tree against the LIVE profile on this host, so its `live-longer` finding is machine state, not a branch verdict.** It fails when the tree's `SOUL.md`/skill copy is *shorter* than `~/.hermes/profiles/<profile>/…`, which CI cannot see because it has no live profiles — the same tree passes there. Report it as a host-state divergence with both byte counts (tree vs live) and do not call the branch red on it; the deterministic halves are the manifest/rules check and the frontmatter/section checks.
- **Only regenerate the SOUL of the profile THIS branch owns — a blanket fleet-block rewrite across `agents/*/SOUL.md` fails on its second step and trespasses on other lanes.** Regenerating every SOUL so the canonical block matches `agents/standing-rules.md` makes each of those profiles state the block verbatim, which turns its entry in `agents/fleet-block-exemptions.json` `STALE` (`fleet-block-drift` becomes `fleet-exemption-stale`), and the exemption is owned by the lane that has not yet written its rule. Revert the others (`git checkout origin/<base> -- agents/<other>/SOUL.md`) and regenerate only the file the branch adds; the reason a gap exists is another lane's work queue, not a merge conflict.
- **`make sync-agent-profile PROFILE=<p> CHECK=1` fails whenever the tree and the live profile differ, including for a profile the repo has just rewritten.** The sequence is: copy the live file aside (`cp -a ~/.hermes/profiles/<p>/SOUL.md <scratch>/SOUL.md.before-sync`), run `make sync-agent-profile PROFILE=<p>` (repo → profile; it prints `verified: 1 file(s) read back identical`), then re-run with `CHECK=1` and expect `OK: … match … byte for byte`. Running only `CHECK=1` proves nothing about the tree and leaves a red that reads like a branch defect.
- **Attribute a red from the job LOG, not from the check name.** `gh api repos/<owner>/<repo>/commits/<sha>/check-runs --jq '.check_runs[]|select(.conclusion=="failure")|.details_url'` gives the job id; `gh api repos/<owner>/<repo>/actions/jobs/<id>/logs --allow-escape-sequences | sed 's/\x1b\[[0-9;]*m//g'` returns the assertion text (the API refuses some logs without that flag). The file:line in the log is what lets you prove "inherited from a red `main`" against a pristine worktree instead of guessing from job names — a plain read that returns zero bytes is the flag's guard, not an unreadable log.
- **A repo-wide `gh run list --limit N` window is not a per-PR history.** After a capacity sweep the newest runs dominate, so an older PR's retry silently falls out of the window — a stuck-cancellation monitor built that way reported zero for a PR that was provably `attempt=2`. Ask per commit: `gh run list --commit <sha> --limit 1`. If the thing you monitor can scroll off page one, the monitor is blind exactly when it matters.
- **A cancellation that survives a re-run means someone's sweep, not a workflow bug.** Read the run's `attempt` and `triggering_actor` before hunting YAML. `attempt >= 2` cancelled = no verdict is coming; attempt 1 is ordinary `cancel-in-progress` noise.
- **`mergeable_state` is NOT PR state — they are two different keys, and a CLOSED PR reports `mergeable_state=blocked` because its branch still resolves a head.** The raw `gh api pulls/<n>` JSON has `state` (open/closed; the authoritative open/closed field) and `mergeable_state` (computed; GitHub recomputes it on a closed PR whenever the branch's head resolves — `refs/pull/N/head` and the branch ref still return that sha after close). Reading `mergeable_state` as "the PR is open and blocked" turns a closed-and-resolved PR into a phantom open swept item, and a branch ref that resolves a sha is never an open PR. When deciding what is swept work, read `state` or `pull.state`; a PR with `state=closed` is out of the board, the sweep, and any re-push regardless of its `mergeable_state`, `mergeable`, or the fact its branch resolves. Verify the `state` field directly (`gh api repos/<o>/<r>/issues/<n> --jq .state`) instead of arguing from a resolving ref. A fork `main`, a fork head ref, and a surviving branch all resolve long after the PR is closed — resolution is not liveness.
- **Never run parallel tool calls against the same worktree — settle a stacked set one PR at a time, each through one self-logging script.** Issuing several `terminal` commands in one turn that all touch one worktree races them: two rebases on the same branch corrupt the `rebase-merge` state (one command's `--continue` fires while the other's conflict is mid-file), a read taken mid-rebase prints `gitfile does not point to a valid repository` or a contradictory head, and an auto-`--continue` can commit a hunk while a concurrent `git grep` still sees its marker — landing a pushed commit with a residual marker I reported as clean. The user's "you have not resolved the conflicts" was exactly this: a gap that only surfaced once the race was stopped. For each stacked PR run ONE self-logging script that does the whole re-seat and writes its own evidence log (worktree add → `git rebase --onto <new-base> <old-base>` → loop: `CHANGES.md` = take the base then `changes-index`; `docs/ARCHITECTURE.md` = regenerate the census for the re-seated tree; `agent-wiki/*`/`*.py`/`*.json` = strip markers as identical-or-union; `git rebase --continue` → `make changes-index` → amend → lease push → API `mergeable` read-back), and invoke it once, serially, verifying the log before the next. Reuse and extend `scripts/stack-replay.sh` rather than hand-typing the loop per PR; a one-shot script whose stdout is captured to a file also survives the output-render glitches that made mid-sweep reads unreadable this session.
- **`gh pr checks` reports `cancelled` runs as `fail`.** Never quote its fail column as a failure count, and never call a PR red on it: read the conclusions instead — `gh api repos/<owner>/<repo>/commits/<head-sha>/check-runs --jq '[.check_runs[].conclusion // "running"] | group_by(.) | map("\(.[0]):\(length)") | join(" ")'`. `cancelled` means superseded by a newer run (`cancel-in-progress` on PRs) = *not yet*, `failure` means red. Also anchor on the PR's **current head sha**, because `gh pr checks` aggregates across runs and a new push silently invalidates every earlier number, including your own.
- A check whose *name* still contains `${{ matrix.… }}` does **not** prove a YAML defect: a run cancelled before its matrix instantiated keeps the workflow's declared names with no expanded children. Check the conclusion first — if it is `cancelled`, the matrix never expanded because nothing ran. Send someone hunting a workflow fault only when a *completed* run has unexpanded names.
- "All checks green" is not "mergeable": the auto-merge condition is `mergeStateStatus == CLEAN`. A PR can be `MERGEABLE/BLOCKED` with every check successful, and reporting that as green-and-mergeable is how a red board gets called ready. The converse matters as much: that same PR is *owner-ready* — a human's approval is the only missing step — so say which of the two you mean rather than emitting one word that is false for half the audience.
- A sweep that reports success while PRs stay conflicted, or crashes its own decision step, is broken — check the run log, do not trust the green.
- CI `guard` sitting `pending` for many minutes with other runs also queued is a **runner capacity** problem, not something wrong with the PR. Report the run ids and say so; do not re-push.
- Capacity starvation and a crashing automation sweep are different failures: keep them in separate issues. Conflating them hides one behind the other.
- After a long capacity backlog clears, PRs that were `MERGEABLE` are the ones to watch: `main` moved while nothing merged, so they can turn `DIRTY` and need this same rebase.
- Worktree count is a tracked trend under an owner-only prune. Always report the worktree you left and its path; never prune to compensate.
- The `pr<N>-rebase`-style local branch is scratch; the branch that matters is the one on `origin`.
- The knowledge here belongs in the repo, not only in this profile: a host skill is admitted **by name** in `HOST_SKILLS` (`scripts/check_agent_skills.py`) and needs frontmatter plus `## Inputs`/`## Output`/`## Rules`. `.hermes/skills/rebase-conflict` already covers the inner half (resolve, stage, stop, caller continues and pushes) — any in-tree version of this procedure must *point* at it, never restate it, and must say which half runs where: the leg contract stops at `git add` in the CI image, this outer procedure owns survey, worktree, gates, lease and report on the host. Never merge the two contracts: one would then say "stop after staging" and "survey and push" at once.
- When filing an issue whose `## Technical` embeds a whole `SKILL.md`, the body gate (`scripts/issue_body.py::missing`) reads every `^## ` line as an issue section: a verbatim fence yields "unknown sections" and `Technical` stops being last. Demote the embedded headings to `###` and tell the implementer to restore `##` when writing the file.
- **`rerere` is enabled on this clone and its cache can hand you a WRONG `CHANGES.md`.** `git rebase` printed `CONFLICT` then `Staged 'CHANGES.md' using previous resolution`, staging a mangled 3-column row copied from a *different* PR's conflict. Always inspect the staged file and rebuild it (main's file + the branch's own row) instead of trusting a rerere resolution; run `git -c rerere.enabled=false rebase --continue`. Verify the row shape (`line.count('|') == 5` for a 4-column table) and that the row's *text* matches the branch's original row, not just its note name.
- Rebase `--force-with-lease` leases must name the ref actually fetched, else the push is rejected; verify afterwards that `HEAD` == `origin/<branch>` and the parent is `origin/main`.
- **Prove content preservation by added/removed LINES, not by tree diff.** `git diff <old-base> <old-tip>` vs `git diff origin/main HEAD` (after rebase) will *always* differ once main moved; the honest check is `diff <(grep -E '^[+-][^+-]' old.diff) <(grep -E '^[+-][^+-]' new.diff)` plus the `--stat` totals (e.g. `17 files changed, 1836 insertions(+), 2 deletions(-)` on both sides). Diffing a pre-rebase commit against its rebased twin also shows all of main's work and reads like drift when there is none.
4. **one lane, one PR:** before a sweep touches a PR, check bot-claim: and agent/issue-<n>-* branch; a claimed PR is another lane's (issue #994 rule 1).
3. **version-here:** this behaviour is versioned by issue + PR under agents/llgenie-pr-merge-conflict/, then sync-agent-profile PROFILE=llgenie-pr-merge-conflict CHECK=1 comes back byte-identical.
2. **new-PR -> reviewer:** the planner sends new reviewable PRs to @llgenie-pr-reviever; this lane never reviews its own PR.
1. **report-back:** rebase/resolve to done (last push, gates green, head fixed) -> post head sha + PR number + what stands to @llgenie-planner.

## A line number is a property of a SHA, not of a file

A dispatch that says "insert one blank line above line 39" is only actionable against the exact
commit those line numbers were read from. Measured: three separate requests to fix
`agents/<lane>/SOUL.md:39` named a heading that on the current main sat at line **49** — the
referenced commit's copy was **84 lines** and main's was **94**, because other lanes' merges had
added rules to the same file in between. Following the number literally would have inserted a blank
line four rules early, in a file whose real defect was already fixed.

Before acting on any line-numbered instruction:

    git show <the-sha-in-the-request>:<file> | sed -n '<n-1>,<n+1>p'   # does it match the quote?
    git show origin/main:<file>            | sed -n '<n-1>,<n+1>p'     # where is it NOW?
    git rev-parse <sha>:<file> ; git rev-parse origin/main:<file>      # blob identity

If the two blobs are equal, the fix is already in the tree and the request is answered by evidence,
not by an edit. Report the pair of line numbers and the blob ids: that is what lets the asker
retract the request instead of repeating it.

Related, same class: an identifier match is not a record match. `grep architect@llgenie.local` over
a commit range found 2 hits; `grep -i '^co-authored-by'` filtered to that address found 0 — the
hits were PROSE describing the trailer rule inside commits about it. A trailer is a line-anchored
construct, so the only valid check anchors at column 0. An unanchored grep for an identifier finds
documentation about the identifier and reads it as an instance.

## A ratchet red on a rebase is "your new file added roots", not "re-record the baseline"

An import-roots ratchet (#953) records a baseline and refuses any file that raises the count. When
a rebase brings this branch onto a main that carries the gate, a branch-side file written before
the gate landed will red it — measured twice tonight: a branch adding `sys.path.insert(0, …/scripts)`
plus bare `import check_agent_profiles` pushed bare 52→54 and sys-path 32→33, and the same class came
back as a later dispatch.

The two fixes are NOT interchangeable:
  - on `main`, a NEWER file with grandfathered roots, carried in by a REBASE, is the case for
    re-recording the baseline to the new count (the file predates the convention);
  - on a BRANCH, a brand-new file adding its own roots is EXACTLY what the gate exists to refuse
    (#796) — fix the file to use the established seam (`import scripts.<module>`, or the conftest
    root), and re-running the gate must return to the ORIGINAL baseline, never a raised one.

Choosing wrong re-records an inflated baseline and silently disables the ratchet for the next new
file too. After the fix, `make check-import-roots` must print counts at or below the recorded
baseline — not "OK: counts at a new higher baseline". The seam is the fix; the baseline is not.

## A gate's SUBCOMMAND can change its verdict: call the one CI runs, not the one the help names first

`scripts/check_import_roots.py` exposes `{check, report, ratchet}`. On a pristine clean main,
`check` returns rc=1 (84 findings) while `ratchet` returns rc=0 (`OK {sys-path:32, bare:52}`) — the
SAME tree, two verdicts, because `check` is a raw SHAPE scan (any vestige is a finding) and
`ratchet` compares the COUNT to a baseline and fails only when it rose. `make check-import-roots`
calls `ratchet`; CI gates on that. Reported twice tonight as a false green-is-red, and the cause is
the script's own docstring naming the ratchet's behavior "`check` fails when they RISE" — a reader
runs `check` expecting a baseline comparison and concludes the gate is broken.

Two rules:
  - when an assertion or a driver wraps a gate with several subcommands, CALL THE SAME SUBCOMMAND CI
    RUNS. `ratchet` here; anything else either reds a clean tree (and teaches the reader to disarm
    the gate) or silently checks a weaker/different predicate.
  - in a report, name the subcommand with the verdict. "import-roots 84 finding(s)" is unreadable
    until the reader knows whether that is `check` (a scan) or `ratchet` (a rise vs baseline) — the
    same predicate-less-count failure as quoting a number without the branch that produced it.

## A ratchet red is the BRANCH'S defect when main passes the same baseline — do not rebase it

When a PR's `linux/unit` fails `check-import-roots` with a count over the recorded baseline
(`bare: 54 now, 52 recorded`), decide WHOSE defect it is before acting. The decisive measurement is
a clean archive of `main`:

    git archive origin/main | (mkdir -p /tmp/t && cd /tmp/t && tar -xf - && make check-import-roots)

If that returns `OK: counts at or below the recorded baseline`, main is clean, so the two extra
bare sites live on the BRANCH — and a rebase onto clean main leaves them exactly where they are:
still red on the same count. The remedy is converting the branch's over-baseline sites to the
baseline pattern, not rebasing.

An earlier drafting of this lesson said "on a BRANCH, a brand-new file adding roots is refused —
fix the file to the conftest seam." This is the same rule applied to the whole branch, and it must
not be read as an invitation to move main (re-record) to accommodate the branch. Measured on #1128:
the 429 in the same job was a SUCCEEDED retry (a red herring), and the failing step was
`make ci-unit` -> check-import-roots — read the exact failing STEP, not the job name, before
naming a cause.

## When the paths predate the PR, only the PER-FILE CONTENT diff exposes a duplicate vehicle

The duplicate-vehicle pair (`ls-tree` shows the paths on main + `--is-ancestor` says the commit never
merged) is VACUOUS for skill/versioning PRs whose directory shipped long ago (the tester skill
landed via #919): the paths are trivially on main and the commit is trivially not an ancestor — that
says nothing about the CONTENT. Measured #1084 at main `329d9d6c` (2026-10-31): head `6d068af8`
`CONFLICTING` (merge-tree exit 1, 2 conflicts: `SKILL.md` content + `post-merge-verification.md`
add/add), but the same-day sync `f447b471` (#1152, `sync(agents): llgenie-tester live->tree
byte-identical CHECK=1 6/6`, merged 07:22+01:00) had already absorbed the PR's whole #1060 content.

The instrument: for every file in the PR's own stat, `git diff origin/main:<f> <head>:<f>` and count
each side's unique lines (`grep -cE '^\+[^+]'` and `'^-[^-]'`). #1084: SKILL.md branch-unique 3
(only an older rewrite of the hang-band paragraph main already EXTENDS with a newer generation),
`agent-profile-versioning.md` byte-identical (0/0), `post-merge-verification.md` branch-unique 0 with
main a 15-line superset. Branch-unique ≈ 0 or only older rewrites of blocks main extends = superseded.
A live->tree sync landing WHILE a versioning PR sits open supersedes it by design: the sync captures
the live profile, which contains the open PR's work. Correct action: post per-file counts + the sync
sha on the PR, recommend closing as superseded, push nothing, label nothing, leave the branch
untouched — a "correct" rebase here replays an older generation that REGRESSES main's newer
paragraphs or lands an empty PR.
