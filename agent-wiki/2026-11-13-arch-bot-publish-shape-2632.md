# 2026-11-13 — architecture-bot publish shape: commit text closes, mirrors ticked (#2632)

OpenSpec change `arch-bot-publish-shape` (issue #2632). Verified against the issue's goal: the
publish leg of `scripts/architecture_bot.py` no longer dumps the draft issue body into the commit
and no longer leaves the three mirrors (issue body / commit text / PR body) contradicting each
other. Measured root cause on PR #2629: `git commit -m <title> -m <issue body>` produced commit
text with unticked `- [ ]` criteria and no `closes` line (`check-pr-closing`: "The joined commit
messages close (none)"), and `render_pr` emitted no `AGENTS:`/`BASE:` pair.

Decisions:
- One source for the criteria: `acceptance_items(doc, head)` feeds `render_issue`,
  `render_commit_body` and the PR mirror, so the mirrors cannot drift in wording (the referee
  rule of the three-mirror contract).
- Commit body = marker + completion line + ticked mirrors (plain) + `closes #<issue>`. Proven
  strings live on the issue body and the PR body only.
- Order: draft issue → branch + pair + commit → `gh api PATCH repos/<repo>/issues/<n>
  -F body=@-` with ticked, sha-naming proven → push → `pr create` with PR body carrying the AC
  mirror + `AGENTS: <base-tip> <bytes>b <lines>l` + `BASE: <base-tip> (== origin/main at open)`
  + `closes #<issue>` last. Dry previews the FINAL body shapes, not the draft.
- `tick_issue_acceptance` raises when a criterion is missing from the body it must tick — a
  silent half-tick is a loud error.
- Seam defect found while proving it: `run_ok` in `scripts/proc.py` swallowed the `input=` kwarg
  (`**_`), so the piped issue body never reached `gh`. The seam now forwards `input` to
  `subprocess.run` in `run_ok`/`run_text`/`run_checked`; a call without `input` is unchanged
  (inherited stdin). Spec delta: MODIFIED "The subprocess policy seam forwards a piped stdin".

Status: `tests/test_architecture_bot.py` (fake gh now serves `api` calls and parks the final
issue body; fixture seeds `AGENTS.md`) + `tests/test_proc.py` + `tests/test_proc_seam_gate.py`
green: 41 passed, rc=0 through the container test gate.
