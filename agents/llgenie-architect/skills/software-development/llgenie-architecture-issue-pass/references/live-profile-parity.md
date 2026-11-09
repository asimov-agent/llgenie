# Live-profile parity: measuring drift without destroying it

Depth for the SKILL.md rule on profile sync. The sync is ONE-WAY (tree → live), so on a lane whose live
profile is ahead, the tool's prescribed default action is the destructive one.

## 1. The read-only measurement (two commands)

```bash
make tester-fold-live PROFILE=<p>            # enumerate: same / drifted / live-missing / live-only per file
make sync-agent-profile PROFILE=<p> CHECK=1  # exit 1 names the first differing path and whether it SHRINKS
```

Both are read-only. When the ask is "reload and report the numbers", these two ARE the job — do not proceed to
a write. `CHECK=1`'s exit status is masked if you pipe it; use `> /tmp/out 2>&1; echo $?` and read the real code.

The fold tool prints per-file hashes plus a summary line (`N same, M drifted, K live-missing, L live-only,
0 mid-write`). Quote that line verbatim; it is the reproducible count.

## 2. `COPY=1` / `FORCE=1` are NOT merges

`make tester-fold-live COPY=1` and `make sync-agent-profile FORCE=1` copy file-over-file. Any line present only
on the tree side is silently deleted. Measured: one run overwrote 31 tree files with live content and destroyed
**72 tree-only lines across 12 files** (a SOUL, 35 lines of a skill, and nine-line blocks in two references).
It reported success; the tree was then repaired with `git checkout -- agents/<p>`.

Never run either without a **line-subset proof** that no tree line disappears. And when a sync tool claims
"verified … identical", that claim only says it wrote what it copied — it does not say nothing was lost.
Exercise the destructive path against a COPY of the live data (`cp -a` to scratch, point the destination env at
the copy) and leave the real profile untouched.

## 3. Direction per file — the discriminator is a line subset, not bytes

A lane routinely drifts in BOTH directions at once. Byte counts only hint; compute the two sets and report them
separately:

```python
# tree lines the live file lacks  = would be ADDED by tree->live
ts - ls
# live lines the tree lacks      = would be LOST by tree->live  (the destructive case)
ls - ts
```

Measured on one lane: `SOUL.md` was tree-ahead (`+3, −0` — additive, safe) while a skill was live-ahead (tree
89,035 b vs live 98,101 b, where a sync-down would destroy **35 live-only lines**, two of them entire behaviour
rules absent from the tree). So print a per-file table of tree/live line counts and
"tree→live would ADD n, LOSE m" — never one verdict for the lane. Only the `LOSE > 0` files are why you must
not sync.

Confirm a claimed loss by searching the TREE copy for a phrase unique to the missing rule (`0` hits = the loss
is real, not a whitespace diff):

```bash
search_files pattern="approver != merger" path="<repo>/agents/<p>/"     # 0 in tree, 1 in live ⇒ real loss
```

## 4. The correct reconcile direction

- `live << tree` — a stub awaiting its first sync. `sync-agent-profile` is safe and is the whole fix.
- `live >> tree` — **do not sync down.** Version live→tree as a per-lane PR: commit files byte-identical to the
  live profile under `agents/<p>/`, prove `check_agent_profiles.py check` green with
  `HERMES_PROFILES_HOME=/nonexistent` (CI mode has no live profile), and write the `change->note` row. Made
  identical, any later sync is a no-op.
- A reload directive's wording ("sync any drift") assumes tree→live; take the direction from the measurement,
  not the wording, because the wording does not carry it.
- Keep an addition and a rescue in **separate** vehicles: folding a safe `+3/−0` SOUL change together with a
  35-line rescue lets one review approve the deletion by accident.
