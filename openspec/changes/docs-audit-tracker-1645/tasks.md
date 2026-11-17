# tasks — docs-audit-tracker-1645

## 1. Playbook: name the durable home

- [x] 1.1 `references/own-domain-audit.md`: replace the conditional "Deliverable and the missing
      tracker" opening with the pinned #1645 contract (record home, routing, umbrella citation,
      closed-#1645-only DM fallback).
- [x] 1.2 `SKILL.md`: add the pointer line + bump `version:` (1.0.23 -> 1.0.24)

## 2. Prove the contract live

- [x] 2.1 Run the bounded audit at the freshly fetched tip in a detached worktree: check 1
      (docs alignment claim read against the code path), check 2 (skill freshness via the
      live-vs-tree `cmp` measurement, umbrella-cited), check 3 (`make check-docs` at the tip).
- [x] 2.2 Post the record comment on #1645 (bare sha, gate rcs, routing) and verify by read-back
      (`contains` query returns >= 1).

## 3. Docs triad + gates

- [x] 3.1 Note trio: agent-wiki entry + changes.d fragment + CHANGES.md row
      (`make changes-index` rc=0, `make check-docs` rc=0).
- [x] 3.2 `make openspec-validate NAME=docs-audit-tracker-1645` rc=0, `make check-wiring` rc=0,
      `make lint` rc=0; `make bot-preflight ISSUE=1645` printed the paste line
      `SYNC: llgenie-documentation-maintainer make sync-agent-profile PROFILE=llgenie-documentation-maintainer`
      and that sync ran rc=0 (28 files, 2 content changes); `make issue-bot-gates` re-run at the
      amended head rc=0.

## 4. Ship verification

- [x] 4.1 The final head carries the four ticked AC mirrors (tracker #1645 is referenced as prose
      only — a never-closing tracker, precedent #2652); #1645 stays OPEN (`gh api
      repos/asimov-agent/llgenie/issues/1645 --jq .state` -> OPEN) and its body passes the
      six-section shape read (missing() -> none, rc=0).
