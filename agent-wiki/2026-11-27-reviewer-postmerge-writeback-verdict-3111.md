# Reviewer: version the post-merge write-back verdict reference (issue #3111)

Claimed and landed on branch `fix/3111-pr-reviewer-postmerge-ref-tree`, cut from freshly
fetched `origin/main@4b1fcb2bbee47b57d697b96e8737089a00cde952` (local ref == GitHub API).
This is this lane's row of the docs-lane audit at `4b1fcb2bb`: one file, one lane-owned PR
(#3112), no other lane's row touched.

## What changed

`agents/llgenie-pr-reviever/skills/software-development/llgenie-pr-review/references/postmerge-writeback-verdict.md`
is added to the versioned tree at 1513 bytes, byte-identical (sha256 `1879b2f1fc5d…`) to the
live-only copy the audit found in the host profile. The audit classified it `absent-from-tree`:
the live file carried the working behaviour but the tree had no counterpart, so the next
`make sync-agent-profile PROFILE=llgenie-pr-reviever` would have erased it. The direction of the
fix is tree -> live — the tree was the stale side; no live bytes were folded over the tree copy.

## Why it is versioned

The reference encodes the lane's post-merge verdict + write-back shape, verified on #3088/#3080:
a PR already merged at first check still owes a COMMENTED verdict (state=closed/merged is the
normal post-merge #1644 write-back shape, not an open-PR review); a `github-actions[bot]` APPROVED
review is the auto-merge mechanism, not this lane's verdict; a trusted bot-verdict APPROVE cannot
be manufactured from `asimov-agent` when it is author and `MERGER_LOGIN` (SOUL line 21, no
credential switching); each provable box is verified at the exact head before
`acceptance_writeback.py writeback --issue N --proven K --verdict-ref` with a provable
`reviewer <login> review <id> command <cmd> rc=0 head <40hex>` ref (no bare `#N`, no parens);
genuinely post-merge boxes are left open with unblock conditions; and the final on-wire state is
recorded in an evidence file and read back because external gh writes alone are not
session-observable to the Nerve guard. Without a tree home, all of that would vanish on sync.

## Key decisions

- Behaviour versioned as a reference under this lane's own profile only; no SOUL, gate,
  workflow, standing-rule or other lane's file changed.
- No `/home/<user>` literal — paths use `$HOME` per the owner instruction (issue #2145).
- This note and its one-row `docs/changes.d` fragment are the #1123 companions for the
  behavioural change; the `CHANGES.md` index row is regenerated with `make changes-index`.
- No self-tick (#1644), no hand-merge or arm (#1088), no second vehicle. Sync tree -> live is run
  by this lane after the tree change; the merge decision stays with the owner.
