# The acceptance write-back seam (ticking an issue's proven boxes)

`scripts/acceptance_writeback.py` (landed for the acceptance-writeback issue) is the sanctioned way to
flip a closed/settled issue's `- [ ]` acceptance boxes to `- [x]` with a `proven:` marker and a verdict
reference — never a manual body edit. It has three subcommands:

```
acceptance_writeback.py writeback --issue N --proven 1,3 --verdict-ref '<...>' [--dry]
acceptance_writeback.py apply    --body-file BODY --proven 1,3 --verdict-ref '<...>'
acceptance_writeback.py check    --body-file BODY --proven 1,3 --verdict-ref '<...>'
```

## The pitfall that costs a turn: the heading match is EXACT

The tool finds the section with `issue_body.section_body(body, "Acceptance criteria")`, which matches a
`##` heading whose text (`.strip()`) equals **`Acceptance criteria`** exactly. An issue authored with a
suffix — e.g. `## Acceptance criteria (what closing means)` — is NOT found, and the seam refuses:

```
BodyError: the body has no `## Acceptance criteria` section   (rc 1)
```

This reds even when every acceptance item is genuinely proven on `main`: the issue then sits
closed-but-0/5, verified-in-a-comment instead of ticked, and a reader trusts `0/5` over prose. The
root defect is the **issue's own heading spelling**, authored at filing time — not the PR body, not the
merge. So when writing any six-section issue, the acceptance heading is bare `## Acceptance criteria`,
no parenthetical, no subtitle. This is the same class as the "one canonical heading" rule elsewhere: a
section the seam greps for is found only under its exact canonical name.

## Run it `--dry` first, from a clean worktree at the tip

- `--dry` applies the identical heading match and writes nothing: a non-zero rc there names a body-form
defect **before** any wire write, so always dry-run first (`--dry` exits 0 on success and prints the
plan).
- Run the tool from a **clean detached worktree at the fetched `origin/main` tip**
  (`git worktree add --detach /tmp/wt origin/main`), never the repo's moving main checkout: the tool's
  behavior is `main`'s bytes, and a stale checkout can carry an older seam. Remove the scratch worktree
  after (`git worktree remove /tmp/wt --force`) — it is a `/tmp` throwaway, which the never-prune rule
  lets you delete yourself; a lane's vehicle is not.
- `--verdict-ref` carries the proof a reader can re-run: the merge sha plus the verified blob ids or the
  CI run id. It is the origin of the tick, so it must be a measured value, never "reviewed".

## When the seam refuses because of the heading

You cannot make the boxes tick without the canonical heading, and editing a **closed** issue's body to
satisfy the seam is a wire edit that must not be done on silence (no-consent-by-silence; "not manual").
The honest sequence:

1. Post the refusal durably on the issue: the exact command, the `BodyError`, rc, and the fact that the
   items ARE proven (the blob/run ids). A stranger must see the proof even at 0/5.
2. Ask the routing lane for one of: (A) explicit authorization to canonicalize the heading (a precise
   `gh issue edit`/body PATCH to bare `## Acceptance criteria`), then immediately re-run the seam — the
   ticking stays in the seam, only the heading gate is repaired; or (B) file it as a form-gate finding
   (the seam should lenient-match, or a canary should catch a non-canonical heading) routed
   `agent:implement`, leaving the issue documented-proven at 0/5 until the gate is fixed.
3. Never fabricate a "5/5 proven" read-back: the wire still shows 0/5 until one of the above runs.

## Don't reconstruct a merged fold's boxes by eye

If a dispatch says "tick the boxes via the seam", the deliverable is the seam's output (the issue
body's `- [x] … (proven: …)` lines, read back with `gh issue view N --json body`), not a claim that the
work is proven. Re-read the body after the run and quote the checked count — the seam's own write is
the fact.
