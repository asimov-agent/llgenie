# Docs-maintainer lane: version the post-#1083 live lessons back into the tree

Versions live→tree drift for the `llgenie-documentation-maintainer` lane that appeared **after** #1083
merged (issue #1165; does **not** close #961 / #1060 — those are closed for this lane and not reopened).

`#1083` (merge `a653cdc`, 09:26Z) shipped the lane's `SOUL.md` + `skills/llgenie-docs-maintainer/`
(v1.0.7) and cleared its drift rows. The live profile then kept absorbing lessons post-merge, all
genuine and forward-only:

- **v1.0.8** (11:29Z): the `~1h ci-unit` cancellation fingerprint — two identical
  `Timeout (0:05:00)!` cancellations with sibling jobs green mean a starved runner, not the diff;
  stop rerun-looping and wait for a quiet window.
- **v1.0.9** (11:38Z): two rules the lane itself proved — a live→tree skill sync *edits*
  `agents/*/skills/**` and therefore owes its own change-record note shipped in the **same** PR; and
  "the gate that will police you may live in an unmerged PR — prove your head green under THAT
  version before it lands, or the race reds you".
- **v1.0.10** (12:0xZ): the `check-import-roots` ratchet red (issue #796) — a branch of yours that
  reds it is usually your **own** new test bootstrapping `sys.path` / importing a `scripts/` module
  bare; fix the import via the conftest seam (`from scripts import check_docs`), never bump the
  baseline, and read the ratchet's exit with `${PIPESTATUS[0]}`, not `$?` after a pipe.

`references/ci-triage-for-docs-prs.md` grew with it (8,683 b), gaining the ratchet section
alongside the cancellation fingerprint, and SKILL.md reached **v1.0.12** (51,128 b) with five more
lessons the lane earned while landing this PR: the `--force-with-lease` lease expects a **literal sha,
not a ref path** (`:refs/heads/x` → `stale info`; fetch then push plain
`--force-with-lease`); a PR body that names a "final head" must be written **after the last push**,
never before; `gh pr checks` is the only safe way to resolve the **matrix run id** from the
guard/holds duplicates at one sha; a heartbeat-coalesced watcher line can quote a **stale head** —
re-read the PR directly, timestamped, before acting on a poll; and a `pull_request` run evaluates the
workflow at its **merge ref**, so the 120-min ceiling raised on main (#1175) does not apply to an
unrebased PR — its ~60-min `completed/cancelled` is the **old-ceiling fingerprint**, fixed by a rebase,
never by rerunning the doomed run. Because `make sync-agent-profile` is
one-way (tree→live), a live write can never return to the tree on its own, so
`check_agent_profiles.py` re-reports the files `live-longer` until this PR lands. Verified live is a
clean superset of the tree for all five files (no tree line is dropped — a pure union).
Real change→note gate probe (the un-merged #1133
`check_docs.py --base origin/main`) re-run at the final head `60aee889` (measured 13:10Z):
**exit 0** — the note is exactly what keeps this PR green under the gate once #1133 merges.

The recurrence (a live skill that keeps absorbing lessons between clearing PRs) is the subject of
#1156, whose landed rule (#1168) now says lessons land as issue + tree PR **under the lane's own
directory** — never as live-profile patches — and pins the drift gate to catch live writes; a
subsequent live bump would then be a fresh issue, not a touch of a merged branch.
