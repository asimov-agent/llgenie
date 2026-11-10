# force-push-lease-rule-1960

## Why

The fleet force-push rule (issue #1960) was worded so that a rebased branch could not be pushed at
all: it demanded `--force-with-lease` semantics but left the natural post-rebase push ambiguous, and
lanes responded either by skipping the mandatory freshness rebase or by force-pushing blindly. The
rule text lives in `agents/standing-rules.md` and in every lane's `SOUL.md`, so the ambiguity was
fleet-wide.

## What Changes

- Reword the rule once, everywhere it appears: after a fresh fetch of remote+head, a REBASE of your
  own branch pushes with plain `--force-with-lease`; the `--force-if-includes` twin is for
  non-rebase force pushes; a branch another lane repaired stays read-only.
- Applied to `agents/standing-rules.md`, the pr-rebase skill's copy, and the 13 lane SOUL.md copies
  in the same commit, with the agent-wiki note and its `docs/changes.d` fragment.
- No code changes: this is fleet instruction text (issue #1960, PR #2449).

## Impact

- Affected: every lane's push discipline; `agents/standing-rules.md` is the canonical copy the
  hygiene gates read.
- Closes GitHub issue #1960.
