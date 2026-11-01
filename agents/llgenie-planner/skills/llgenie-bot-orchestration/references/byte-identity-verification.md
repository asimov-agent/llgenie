# Verifying a "byte-identical copy" / md5 fold claim

When a lane (or a fold task) says it committed a file **byte-identical to the live source** and
quotes an md5, treat that as a claim like any other. The failure this catches: the copy was made
wrong (e.g. the final newline dropped), so tree != live, and the quoted md5 is the hash of the
*broken* copy — not the source. Trusting it propagates the wrong hash into an acceptance anchor.

## 1. Diff content, don't trust the quoted md5

A single md5 proves nothing on its own — the lane can quote the hash of the wrong side, or of a
copy it re-generated after you read it. Diff the two objects directly:

```bash
# live file vs the committed blob at the head you were handed
diff <(cat /path/to/live/file) <(git -C /path/to/repo cat-file blob <head-sha>:<repo-relative-path>)
```

- Empty diff = genuinely byte-identical; the claim holds.
- Any hunk = NOT identical; read it. The common one-line hunk with
  `\ No newline at end of file` on the committed side is the trailing-newline trap (below).

Compute md5 of *both* sides yourself and compare; never repeat a hash the lane handed you:

```bash
md5sum /path/to/live/file
git -C <repo> cat-file blob <head-sha>:<path> | md5sum
```

## 2. The trailing-newline trap

The very common fold defect: the committed copy lacks the final `\n` the live source has. It
fails **two** ways at once — (a) it breaks byte-identity (`tree != live`), and (b) it trips a lint
gate (`files missing a trailing newline`). So a red lint job on a `files-missing-trailing-newline`
check is direct evidence the fold was done by hand, not by a verbatim copy.

Confirm the byte that matters:

```bash
tail -c 5 /path/to/live/file | od -c      # last byte should be \n for a text file
git cat-file blob <head-sha>:<path> | tail -c 5 | od -c
```

`diff` also prints `\ No newline at end of file` on whichever side is short — read that line, do
not skim the hunk.

## 3. The correct fix direction

Regenerate the committed copy **verbatim** from the live source (a `cp`-style full write, not a
partial re-write or a hand re-typed tail) so it keeps the trailing newline. After the fix the
committed md5 must equal the **live** md5 — which is the *with-newline* hash, i.e. NOT the hash
the broken copy had. Re-diff to close: empty diff between live and the new committed blob.

## 4. The acceptance anchor is part of the mutation

When you put an md5 into an issue body, dispatch, or acceptance criterion, that anchor must be the
**byte-correct live hash**. If the fold was done wrong, the anchor you set points at the broken
copy and is itself a defect: PATCH the issue body to the live hash in the same pass you correct
the lane (replace the old string, then re-read the body to confirm the old hash is gone and the new
one present). An anchor left at the broken hash will make a correct fix look like a failure.

## 5. When your own guidance was the wrong one

If fresh measurement refutes guidance **you** posted, post a superseding comment that names the
comment id it replaces (per `references/board-state-and-holds.md`) and states the corrected hash
and byte facts — do not silently post a second, contradictory instruction.

## 6. Editing the live source invalidates a pending fold's anchor

Folding live profile files into the tree is versioned work, so the live file can move *before* the
fold lands: you add a section, a lane rewrites it, and the acceptance anchor quoted in the issuing
issue is now the hash of a file that no longer exists.

- **Any edit to a live profile file that a pending issue/fold names by md5 owes an anchor update in
  the same pass.** Re-`md5sum` the file, PATCH the issue's line, and read back (old hash gone, new
  hash present, plus the new line/byte count). An anchor left at the pre-edit hash makes a correct
  fold look like a failure and invites the lane to "restore" the older content.
- Record in the issue why the anchor moved ("strengthened with rule X") so the new fingerprint is
  not read as an unexplained drift.
- Conversely, when the fold lands, verify the **committed** md5 against the live file at that
  moment — not against the hash quoted at filing time.
- Keep the writing to the topical reference files, not `SKILL.md`: a bloated `SKILL.md` can exceed the
  skill tool's size cap and become un-patchable, so new depth belongs in `references/` with a
  one-line pointer, and `SKILL.md` stays a compact rules-and-index file.

## 7. The cap trap is on the LIVE file, not the tree copy

The skill tool's patch is refused when the **live** `SKILL.md` exceeds the size cap — check the *live*
profile's character count (`wc -c` / `python3 -c "print(len(open(...,encoding='utf-8').read()))"`),
never the tree copy's byte size. These two can disagree badly: on 2026-11-01 the TREE copy was
112,550 bytes while the LIVE file had been trimmed to 99,885 bytes (99,734 chars) — under the cap and
patchable. A claim "SKILL.md is over the cap / un-patchable" that was measured from the tree (or from a
stale snapshot quoted in an earlier error) is a phantom: re-measure the live file by char count before
filing a slimming issue, and if it is under cap, make the change directly.

## Fold byte-identity: the trailing-newline case (verified 2026-11-01)

A live-to-tree fold that claims "byte-identical" can silently drop the file's final newline, breaking BOTH the fold md5 anchor AND the lint gate — two apparently unrelated reds. Measured on #1447: the submitted dead-workflow-and-trigger-proof.md was `222606522ed7692d426ebe0805df3481` (no trailing newline, `od -c` shows `\ No newline at end of file`), while the live source was `cec492a9ff15371dee70381c2404ccf3` ending `\n`.

Prove byte-identity against the committed blob, never the lane's claim:

```bash
git cat-file blob <head>:agents/<lane>/skills/<skill>/references/<file>.md | md5sum   # committed copy
md5sum <live profile path>                                                            # live source
git cat-file blob <head>:.../<file>.md | tail -c 20 | od -c                          # final byte: newline or absent
```

`git diff` between the two must be EMPTY; if they differ only by a final newline, the fold dropped it. The correct fix is to regenerate the committed copy VERBATIM from the live source (`cp`, never a partial re-write) so the committed md5 equals live. Ten "stay byte-identical to md5 Z" instructions are wrong when Z is the broken no-newline hash — update the issue/PR md5 anchor to the byte-correct live hash at the same time (this pass: #1445 anchor `222606522e` -> `cec492a9`, #1452 anchor `bc85c482` -> `56788e9d`). A merged fold whose file differs from live re-opens the #1402/#1421 class: the acceptance criterion is "the file in-tree IS the live file", measured by md5, not by existence.
