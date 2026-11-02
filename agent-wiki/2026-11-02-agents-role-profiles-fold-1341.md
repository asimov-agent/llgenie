# 2026-11-02 — the three host role profiles fold into the tree

**Issue:** [#1341](https://github.com/asimov-agent/llgenie/issues/1341) — add business-analyst /
product-manager / status-keeper profiles to the tree + manifest, extended to three profiles by
[#1245](https://github.com/asimov-agent/llgenie/issues/1245)'s record.
**Home:** `agents/<profile>/` (issue #791).
**PR:** the branch carrying this note, `agents/issue-1341-profiles-manifest`, opened against `main`.

## What this change does

The three host role profiles created 2026-10-31 under `~/.hermes/profiles/` — `llgenie-business-analyst`,
`llgenie-product-manager`, `llgenie-status-keeper` — were not in this tree: no `agents/<profile>/`
directory, no `agents/manifest.json` row, live SOULs absent from the tree (measured at
main@33d11fa3: `agents/` listed 11 profiles, none of the three).

This PR folds each profile's behaviour into the tree by **byte-identical copy from the live profile**
(`scripts` / `git diff --no-index` verified byte-equality after the copy — never a private rewrite):
`agents/<profile>/SOUL.md` and the lane's own skill directory `agents/<profile>/skills/<profile>/`
(the one skill each profile runs under that is not part of the shared library Hermes installs; every
other live skill is `_skill_dirs`-excluded via `installed_library_names()`, verified by the probe that
enumerated 116 skill dirs per profile and found exactly one lane skill apiece).

`agents/manifest.json` gains all three rows. Each SOUL states both standing rules in its own voice —
analyst line 10 (`**You never implement.**`) and line 12 (`**You never merge.**`), product-manager same,
status-keeper lines 4/10/12 — so each entry declares `["never-implement", "never-merge"]`, verified
against the live SOULs and the canonical fleet block in `agents/standing-rules.md`. All three SOULs
carry the canonical fleet block verbatim (5867 bytes each, matched byte-for-byte), so no
`fleet-block-exemptions.json` entry is needed.

## Gates

- `make check-agent-profiles` in CI mode (`HERMES_PROFILES_HOME=/nonexistent`): **OK, 13 profiles,
  GATE_EXIT=0**.
- Local live-profile comparison (`check --only absent-from-tree,live-longer,...`): the 168 findings it
  reports are all pre-existing live drift on OTHER lanes (planner, security, ci-pipelines, engine,
  pr-*-lanes); **zero findings name any of the three new profiles** (grepped the full output).

## Out of scope

Renaming `llgenie-issse-implementer` / `llgenie-pr-reviever`, changing who merges or approves, and the
parked initiatives #1343 / #1345 / #1346 stay untouched (tree sync direction only).
