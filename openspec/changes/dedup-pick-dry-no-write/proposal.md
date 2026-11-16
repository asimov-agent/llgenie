# Fix: `make issue-dedup-pick DRY=1` previews the pair and writes nothing

## Why

`bots.mk` wires `issue-dedup-pick` with a preview mode — `DRY=1` appends `--dry` — and the
`scripts/issue_dedup.py` module docstring promises "`--dry` prints the decision and mutates
nothing". It does not. Measured on main `28a3d43aa`: `pick(gh, repo)` (line 132) has **no `dry`
parameter**, `Path("dedup-in.md").write_text(body)` (line 154) runs **unconditionally**, and
`main()` (line 249) calls `pick(args.gh, args.repo)` — parsing `--dry` but dropping it. The
dedupe lane's only preview therefore mutates the tree: every dry pick leaves `dedup-in.md` on
disk, and any gate that refuses a dirty tree (`make lane-preflight`) then refuses a tree that
was only previewed. Issue #564.

## What changes

1. `pick(gh, repo, dry=False)`: with `dry=True` it prints the same `action=`/`canonical=`/`copy=`
   protocol and writes nothing; the log line says `would write dedup-in.md` instead of
   `wrote dedup-in.md` (the wording #564 asks for, matching the refiner's #352 fix).
2. `main()` passes the already-parsed `args.dry` into `pick`. No change to `bots.mk` or the
   Makefile wiring — the flag plumbing already exists end-to-end up to the dropped argument.
3. A test proves the dry pick leaves no `dedup-in.md` behind while the real pick still writes it.

## Who

llgenie-issue-bot-maintainer (the dedupe bot leg).
