# An orphan agent branch (commits, no PR) → open the PR, do not re-implement

(NOTE: this reference is not yet linked from SKILL.md — SKILL.md sits at its 100,000-char ceiling;
linking it needs a trim elsewhere first.)

A dispatch that says "branch `<b>` @ `<sha>` exists with N files and NO PR" is the #770 class: the
in-repo implement leg committed and died before `gh pr create`. Recover it; never cut a second
branch and never rewrite the vehicle.

1. `git fetch origin '+refs/heads/<b>:refs/remotes/origin/<b>' '+refs/heads/main:refs/remotes/origin/main'`,
   then `git reset --hard <remote sha>` in the workspace worktree. A freshly created worktree whose
   local branch reads an OLD `main` tip while the remote branch holds the work is normal — the local
   ref was made from main; reset it to the remote sha first, or the first push looks like a delete.
2. `git rebase origin/main`. Expect a `CHANGES.md` row-list conflict only; keep BOTH rows (the peer's
   and yours), then re-run `make bot-preflight` and rewrite the body's `AGENTS:`/`BASE:` pair.
3. **Audit every `#N` the orphan committed.** A lane that died mid-flight can credit the WRONG issue
   on its docs surfaces (measured: the note, its filename, the `docs/changes.d/` fragment, the
   CHANGES.md row and three docstrings all said `#2059` — an unrelated OPEN issue — for a vehicle
   closing `#2068`). `git grep -n '<number>'` the tree; rename note+fragment to the real number and
   re-point the row and docstrings in their own commit. `check-docs` does NOT catch this: it only
   asks for *an* issue or PR reference, so a wrong number passes.
4. Run the gates the branch never ran: `make lane-preflight`, then `check-proc-gate`,
   `check-architecture-census`, `check-module-names`, `check-import-roots ratchet`, `check-pr-base`,
   `check-pr-closing`. A new `scripts/` file with a bare `subprocess.run`/`Popen` reds
   `check-proc-gate` — route probes through `scripts/proc.py` (`run_ok` where the caller inspects rc)
   and put an on-record `# proc-allow: <reason>` only on a call the seam cannot host (a detached
   long-lived daemon spawn).
5. `check-pr-closing` holds the SQUASH TEXT too: a commit body with `Issue: #N`, or a subject ending
   `(#N)`, is a claim, so at least one commit in the range needs an adjacent `closes #N` — the PR
   body alone reds `squash-mismatch` (see `pr-close-mismatch-recovery.md` §143).
6. `check-pr-acceptance` will red on the linked issue's own unticked `## Acceptance criteria`. That is
   the #1644 verdict write-back lane's job: report the red with its run ids and tick nothing you did
   not measure (a criterion needing a live host daemon cannot be ticked from CI).

Timing: push only when no run at the head is `in_progress`, and re-`fetch` immediately before any
`--force-with-lease`. A peer merge between a rebase and its push makes `check-pr-base` read `STALE`
and owes a second rebase — that is the #1015-justified case, and the body's `BASE:`/`AGENTS:` pair
must be regenerated to the new tip.
