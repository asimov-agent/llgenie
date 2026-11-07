# auto-merge-recheck-stale-head — proposal

Issue: [#1910](https://github.com/asimov-agent/llgenie/issues/1910)

## Why

The `auto-merge` scheduled recheck only re-evaluates PRs whose deferral marker names their
current head (one marker per head, #545). A green head that moved after the last deferral — 
the rebase lane pushed a new commit, or a fresh push landed — has no marker for its new head,
so the recheck prints "not a retry" and skips it forever. If no `workflow_run` CI completion
happens to fire at that head (the `auto-merge-success` group saturated by main-tip churn), the
fleet never evaluates a green, mergeable PR. Measured live on #1817 at head `41e522e4`.

## What changes

`scripts/auto_merge.py::recheck` also sweeps a PR that carries ANY deferral marker (an older
head) when its CURRENT head is green (no red check and a concluded green run): the stale-by-move
marker means the PR is the merger's own backlog, re-evaluated against the current tree. A red
current head is still never approved or merged (the #1386 rule holds). One-comment-per-head
dedupe is unchanged.

## Capabilities / Proposal

- The recheck evaluates a green head whose deferral markers all name older heads.
- A red current head is still skipped by the sweep's red-check, exactly as before.

## Open questions

- None; the acceptance criteria in #1910 define the proof (the mechanism merges, no hand merge).
