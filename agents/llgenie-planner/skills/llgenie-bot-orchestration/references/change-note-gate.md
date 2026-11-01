# The change→note gate on a behavioural PR

`ci-scope` runs the docs gates even for a non-docs PR. A diff that changes behaviour — a workflow
under `.github/workflows/`, a Make target, a script under `scripts/` — and adds no
`agent-wiki/<stem>.md` note plus its `docs/changes.d/<stem>.md` row fails with:

```
[check-docs] ERROR: change->note: this branch changes <file> (+N more) but adds no
agent-wiki/<stem>.md note — a behavioural change owes a note (and its docs/changes.d/<stem>.md
row)
[check-docs] 1 problem(s); see `make docs-report`
```

## Reading it correctly

- This red is REAL — not a flake, not a stale-base artifact. Do not rerun it away, and do not accept
  a lane's "all gates green locally": the lane ran a narrower target.
- The note belongs to the *same* branch and vehicle. Never let the lane open a second PR for it, and
  never add it yourself to another lane's branch.
- `make check-docs` also runs `scripts/changes_index.py check`, which asserts every `agent-wiki/`
  note has a fragment and every fragment points at an existing note. Note without fragment just moves
  the red one step along.
- Anything touching workflows, Make targets or `scripts/` is behavioural for this gate — check for both
  artefacts before routing a reviewer, or the reviewer's whole pass is wasted on an unmergeable PR.
- **A change to an agent's own rules is behavioural too.** A diff to `agents/<lane>/SOUL.md` or
  `agents/<lane>/skills/**` reds the same gate ("this branch changes agents/<lane>/SOUL.md (+N more)
  but adds no agent-wiki/<stem>.md note"), so a live→tree versioning fold must ship the note and the
  `docs/changes.d/` row **in the same PR**. A fold that only bumps the profile files is an unmergeable
  vehicle — verify the note at the fold's head (`git cat-file -e <head>:agent-wiki/<stem>.md`) before
  you call the sync aligned.
- **A lane's "change-note duty included" is still a claim.** A same-topic note from an *earlier* issue
  (a prior `*-install-leg-container.md` for a different ticket) does not satisfy the gate for this
  change: the error names the changed files, so confirm the note you find is the one whose stem covers
  *this* branch's change, not a look-alike. `git ls-tree -r <head> -- agent-wiki/ | grep -i <topic>`
  and `git diff --name-only origin/main <head> -- agent-wiki/` — if neither shows a new note for this
  change, the duty was not paid and the gate is red for real.

## Dispatch wording that fixes it in one round

Send back: the exact error line, the two artefacts (note stem + `docs/changes.d/<stem>.md`),
`make check-docs` / `make docs-report` as local proof, "push to the SAME branch", "do NOT open a
second PR", and the two things to report (new head sha + check-docs output). The reflex on a red gate
is a fresh branch; say no explicitly.

## The one false-red case

Note present at the head but the gate reads a stale base: `git cat-file -e <head>:agent-wiki/<stem>.md`
and the same for the fragment. Both present ⇒ rebase onto freshly fetched `main` (the gate shipped
after the PR's base). Either absent ⇒ the lane owes the artefacts.
