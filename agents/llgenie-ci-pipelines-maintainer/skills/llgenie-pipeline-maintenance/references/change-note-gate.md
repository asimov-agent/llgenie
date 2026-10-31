# The change->note gate (#1123) and a branch cut before the gate existed

## What the gate checks

`make check-docs` -> `scripts/check_docs.py check` runs a change->note leg ONLY when a base ref
is available (`--base` or `CHECK_DOCS_BASE`; default resolves `origin/main`). It diffs
`git diff <base>...HEAD` and fails when the diff touches a *behavioural surface*
(`agents/<lane>/skills/`, `scripts/`, `Makefile`, workflows, `docs/*.md`, `data/`, ...) but adds no
`agent-wiki/<stem>.md` note. The note must also have a `docs/changes.d/<stem>.md` index row
(enforced by `problems()`), and both must be **committed** — the gate reads committed paths, an
untracked note is invisible to it.

It runs in the **`scope` workflow (`ci.yml` docs-class), against CURRENT `origin/main`** — not against
the branch's own cut point. So a branch cut before the #1133 gate landed is red on that head even
though locally `check_docs.py check` passes (no base, gate skipped with a printed note).

## The failure shape and the fix

Symptoms: `scope` job fails `make check-docs` with `change->note: this branch changes
agents/<lane>/skills/... (+N more) but adds no agent-wiki/<stem>.md note` while local
`check_docs.py check` (plain) says ok.

Root cause is almost always a **stale cut**: the branch is based on main *before* the change->note
gate merged, so its version of `check_docs.py` has no gate and CI (diffing against newer main) flags it.

Fix (one vehicle, atomically):
1. Rebase the single atomic commit onto current `upstream/main` (the canonical `asimov-agent/llgenie`,
   NOT the fork `origin`) so the branch carries the gate.
2. Add `agent-wiki/<date>-<stem>.md` (note, references its issue/PR with `#<n>`) and
   `docs/changes.d/<date>-<stem>.md` (one index row), folded into the SAME commit as the change.
3. Verify with the real base, not a plain run:
   `python3 scripts/check_docs.py check --base upstream/main` — expect ok AND no
   "change->note skipped" note; confirm the note path appears in `git diff --name-only <base>...HEAD`.
4. Force-push your own branch with `--force-with-lease` (lease = the current remote head); read the
   remote head back; re-arm auto-merge only after scope+guard+unit green at the new head.

## Rules that keep it honest

- The surface set is ADDITIVE — never weaken the gate, never pin an exact file list, never move the
docs gates to `push`/`pull_request` to dodge them.
- A note for a test-only/fixture/rendered change is a filler note, not compliance; the gate already
  exempts `tests/`, `agent-wiki/`, `docs/changes.d/`, `CHANGES.md`.
- Add the note in the same commit as the behaviour; a follow-up commit that adds it after CI already
  reddened is just the red passing and the fix — the gate wants the pair on the diff.
- When a branch predates the gate, the remedy is REBASE onto current main + note, never a rerun of the
  old green branch (a rerun replays the stale base and stays red).
