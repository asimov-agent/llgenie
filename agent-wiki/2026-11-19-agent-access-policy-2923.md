# 2026-11-19 — name the agent's GitHub identity and gate its access policy (issue #2923, PR #<TBD>)

The agent lanes' acting identity and token-scope roster move from session memory into two versioned
artifacts — the AGENTS.md section `## The agent's GitHub identity and required access (MANDATORY,
durable)` and the host agent skill `agents/llgenie-issse-implementer/skills/agent-github-access/` —
and a new gate `scripts/check_agent_access.py` (`make check-agent-access`, in the unit battery)
enforces both, including a secret scan that refuses token-shaped strings inside the policy
documents themselves.

## What was verified

- **Why it was needed** (measured 2026-11-19, main `c564764c5645`): `make registry-cache-orphans`
  lists 8 superseded fixed `:buildcache` tags while the worker identity that shipped #2914 holds
  repo permissions `admin:false` and no `delete:packages` scope; #2837/#2254/#880 wait on the same
  unnamed-identity question. The policy now answers it in the open: act as `asimov-agent`, each
  scope mapped to the step it unblocks.
- **Gate** (`scripts/check_agent_access.py`): reddens a deleted section, a missing acting identity,
  a scope that stops sharing its line with the operation word it maps to, a missing skill, a stripped
  audit-rule phrase (`open issue`, `stamped`, `gh auth status`), and any `gh[pousr]_…` /
  `github_pat_…` string in the section or the skill — the finding names kind + location only, never
  the value. `make agent-access-report` prints the identity, the six scope mappings, the rule
  phrases, and the verdict.
- **Wiring**: targets in `mk/gates.mk` (documented help lines), added to the Makefile target roster,
  and `make check-agent-access` added to the `scripts/ci_unit.py` battery next to
  `make check-issue-bodies`; `make check-wiring` green.
- **Tests**: `tests/test_check_agent_access.py` — 10 hermetic cases (real tree green; deleted
  section red; scope-mapping break red while the other five scopes pass; identity rename red;
  missing skill red; stripped `stamped` rule red; planted `gho_` token in the section and
  `github_pat_` token in the skill both red **with the value never echoed**; battery step-list
  assertion; report exits 0 on findings).
- **Sync**: the skill joins the host-agent tree and reaches the live profile through
  `make sync-agent-profile PROFILE=llgenie-issse-implementer`, never by hand.

## Decision

- The skill lives in `agents/llgenie-issse-implementer/skills/` (host-agent behaviour tree, gated by
  `make check-agent-profiles`), NOT `.hermes/skills/` — `.hermes/skills/` is reserved for CI legs
  preloaded with `hermes -s <name>`, and this policy is host-agent behaviour.
- The elevated-run audit (an open issue requests it first; the run is stamped on that issue) does
  not weaken the engine-start rule: starting inference servers still requires explicit human
  permission, stated verbatim in the new section.
- The scope roster is deliberately narrow; `delete:packages` is authorized for exactly the #2914 GC
  sweep and nothing else, so a future destructive use needs its own issue before the scope earns a
  second meaning.

## Current status

Issue #2923 open; the PR implements this change and closes it. Executing the GHCR orphan sweep
remains #2914's work item (its ACs are re-measured after the sweep runs); the agent-image dispatch
(#2837) and the ruleset decisions (#2254, #880) stay their own issues.
