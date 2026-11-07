# LLGenie Implementer: acceptance-criteria form contract in the versioned SOUL (owner 2026-11-05, #1796, #1812)

Per-lane fold of the universal form rule (#1796 #1, owner directive 2026-11-05) for this lane. The
reviewer's #1804 verdict (comment 6669030076, #1796 = 5/6) left #1 honestly UNTICKED because the per-lane
#791 fleet rollout had not landed here — `agents/llgenie-issse-implementer/SOUL.md` carried the #791
versioning path but no form contract.

## What changed

- `agents/llgenie-issse-implementer/skills/software-development/llgenie-issue-to-pr/SKILL.md` — the lane's
  active implementing skill, folded live→tree via #1060 (it was live-only, unversioned — the root of the
  #1812 gap), with a new "Acceptance-criteria form contract" section stating the contract verbatim from
  #1796 #1: every issue this lane files AND every PR body it opens has a `## Acceptance criteria`
  `- [ ]` checkbox list — one per provable outcome; a criterion a reviewer cannot tick is not one (#745).
  The checklist must be the canonical `## ` heading, never a bare `**Acceptance criteria:**` bold line
  (that defeats `issue_body.missing()` and the verdict-gated ticking in `acceptance_writeback`, #1644).
  Versioned via #791, announced with `make sync-agent-profile PROFILE=llgenie-issse-implementer` (#1724).
- `openspec/changes/implementer-acceptance-form-contract/` — change-first OpenSpec (proposal + spec +
  tasks), the PR's own diff satisfying the #1807/#1810 presence gate.

## Verification

- `make openspec-validate NAME=implementer-acceptance-form-contract` + `make ci-openspec` green.
- `make check-docs` + `make lint` green at the PR head; change-note trio (#1123) + `make changes-index`.
- `make check-pr-openspec-change` passes (the diff adds its own change dir — exemption 1 of #1807).
- `make check-pr-hygiene` / `check-pr-closing` / `check-pr-agents-line` green; `AGENTS:`/`BASE:` per
  #792/#845 (fresh origin/main), `SYNC:` per #1724. No gate code, no peer-lane files touched (#1644 intact).
- PR authored by this lane, closes #1812 (#1796 #1 gap); merge owner-gated (#1088).
