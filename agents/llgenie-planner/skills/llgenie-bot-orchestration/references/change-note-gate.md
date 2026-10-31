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

## Dispatch wording that fixes it in one round

Send back: the exact error line, the two artefacts (note stem + `docs/changes.d/<stem>.md`),
`make check-docs` / `make docs-report` as local proof, "push to the SAME branch", "do NOT open a
second PR", and the two things to report (new head sha + check-docs output). The reflex on a red gate
is a fresh branch; say no explicitly.

## The one false-red case

Note present at the head but the gate reads a stale base: `git cat-file -e <head>:agent-wiki/<stem>.md`
and the same for the fragment. Both present ⇒ rebase onto freshly fetched `main` (the gate shipped
after the PR's base). Either absent ⇒ the lane owes the artefacts.
