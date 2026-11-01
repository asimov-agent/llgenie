# tester profile live→tree versioning round (fleet reload directive)

Versions this test-lane drift into the repo tree after the owner's fleet-wide reload directive
("reload SOUL + skills from main; repo copy is source of truth; version via issue+PR, never private
edits").

The loaded live profile (`~/.hermes/profiles/llgenie-tester/`) is the latest reload and carries
lessons the tree lacked:

- `SOUL.md` — role-artifact banner (test evidence artifact: failing name/job id/sha/run id), and the
  owner directive line on arming auto-merge when done.
- `SKILL.md` (+164) — `## Role artifact (2026-11-01)`; jq `--arg` is handed to `gh` not to its jq;
  `mergeCommit` is an OBJECT not a string; a `pull_request` job's git HEAD is the MERGE ref not the PR
  head; the arm field is `enabledAt`, not `enabled`.
- `references/red-job-triage.md` (+39) — §10 "Verify a census-repoint PR (shared-gate unblocker,
  #1221/#1222)": run the real census gate on the clean merge-tree, keep ancestor+re-measure intact,
  arm state is `ms=BLOCKED`/`autoMergeRequest.enabledAt`, not the command's exit.
- `references/post-merge-verification.md` — compare FILE HASHES for the sync close-out, not one size.
- `references/path-selection-probes.md` — additional control-experiment/probe discipline.

Direction judged by byte-diff, not mtime: every diverging file is live-superset; the tree had no
content live lacked (no tree-larger, no live-missing). Verified `sync-agent-profile CHECK=1` OK for
all files between the branch's `agents/llgenie-tester/` and the live profile.

No other lane touched.
