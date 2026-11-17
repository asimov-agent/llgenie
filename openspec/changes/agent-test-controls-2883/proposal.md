# Proposal: agent-test-controls-2883

## Why

Issue #2883 (filed 2026-11-17 from the LIVE-ONLY classification in #2880, rows 12-13; census head
`585b03dd740c121564190f86987f9bac89f4e796` of PR #2882). The lane tree ships
`agents/llgenie-pr-merge-conflict/scripts/dirty-detector.py` and `scripts/tally-delta.py`, but the
positive/negative controls that prove those detectors fire and stay quiet — `test-dirty-detector.py`
and `test-tally-delta.py` — exist only in the live profile's `scripts/` dir.
`make provision-agent-profiles` therefore ships two untested detectors on every rebuild.

## What Changes

- Copy `test-dirty-detector.py` (sha256 `5f281cb5…`) and `test-tally-delta.py` (sha256 `e26f04cd…`)
  from the live profile root `scripts/` into `agents/llgenie-pr-merge-conflict/scripts/`, byte-identical
  (the #2878/#2882 fold contract: live -> tree, live side never written).
- The controls stay host-runnable scripts: hyphenated names keep them out of pytest collection, and
  both read their subjects via `HERE / <subject>` so they work from the lane tree directory.
- No detector behaviour changes; nothing added to the CI gate roster in this change.

## Goals

Ship the controls beside the subjects so census/provision parity proves the detectors are testable
wherever the lane is provisioned. Out of scope: wiring the controls into a CI job (tracked nowhere
yet; the controls need no GitHub state — they stub `gh`), and the remaining host-state/dead rows of
#2880's table, which need no tree home by that classification.
