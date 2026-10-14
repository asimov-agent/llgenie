# The issue bot decides on the whole thread before it implements

## Why

The implementer read the issue body only. The comment thread is where issues are actually
specified, so the bot implemented the wrong thing when a comment narrowed the request; it also
spent a daily PR slot on issues that were already done, superseded, or ambiguous.

## What changes

- `dispatch` fetches the body **and every comment** and hands the agent the thread plus a
  decision instruction whose verdict format is machine-read.
- Three verdicts: **implement** (unchanged path), **refine** (one comment with an implementable
  restatement + `agent:refined`, no PR), **close** (reason **with cited evidence** + `agent:closed`;
  refused without evidence).
- `apply-verdict` is the deterministic applier; the workflow runs it between triage and the
  implement/push/PR steps, which now require the `implement` verdict.
- An issue already carrying `agent:refined`/`agent:closed` is never picked again (no loops), and
  refine/close open no PR, so the 3/day PR cap is untouched in meaning.

## Impact

A reviewer stops seeing PRs for issues the thread had already answered, and stops seeing wrong
implementations of ambiguous issues. Refusing an evidence-free close is deliberate: closing is for
"already done / superseded / duplicate / not a code change", never for "hard".
