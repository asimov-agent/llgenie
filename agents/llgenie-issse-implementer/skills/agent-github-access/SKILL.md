---
name: agent-github-access
category: software-development
description: "Use before admin-scope GitHub steps: acting identity, scope map, audit stamp."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [github, gh-cli, permissions, ghcr, audit]
    related_skills: [llgenie-issue-to-pr, containerized-repo-verification]
---

# The agent's GitHub identity and the access it needs

## When to Use

Any lane that is about to do more than branch/PR/issue work: a GHCR publish or garbage-collect, a
ruleset change, an engine image action, or any step that fails with `Resource protected by
organization SAML/RBAC` or `Must have admin rights`. Also when filing or closing an issue whose
acceptance item is gated on a permission.

## Identity

The acting identity for llgenie agent lanes is **`asimov-agent`** — the repo-owner bot account,
`admin` on `asimov-agent/llgenie`. A worker/collaborator credential (repo permissions
`pull/push/triage`, `admin:false`, no packages-delete scope) is a pairing identity: it may
implement and review, but an acceptance item that needs an admin scope is closed by the bot
identity, not by a human round-trip. Check WHO you are before the step: run `gh auth status`, which
prints only masked tokens, and stop on an identity mismatch.

## Scope map (scope -> the step it unblocks)

| scope | the operation it authorizes |
|---|---|
| `repo` | branches, pushes, PRs and issue writes — every lane's ordinary work |
| `workflow` | `.github/workflows` file changes, via the PR + workflow-validation gates |
| `read:org` | membership checks when a guard job asks who triggered a lane |
| `gist` | scratch notes a session pins; no repo consequence |
| `write:packages` | publishing engine/agent images to GHCR through the post-merge producer lanes; pulling them for verification |
| `delete:packages` | garbage-collect superseded GHCR refs only — the `make registry-cache-gc` sweep #2914 requests; nothing else |

## Rules

- An elevated or destructive step runs **only when an open issue already requested it**: the issue
  body names the operation before a hand touches the registry, a ruleset, or an engine start.
  Engine starts additionally keep their own explicit human-permission gate — this skill changes
  nothing about that.
- Every elevated run is **stamped** on the issue that requested it: what ran, which identity ran
  it, and the replayable commands that re-measure the outcome. An un-audited sweep is a workflow
  defect even when it deleted the right things.
- No credential text, ever, in an issue, comment, PR body, commit message, log line, or this skill.
  `make check-agent-access` reddens token-shaped strings inside the policy artifacts, and the
  transcript redaction seam covers runtime output.

## Procedure

1. `gh auth status` — confirm the active account is the bot identity and the scope the step needs
   is present; the token is printed masked, never echo it yourself.
2. Find the open issue that requests the operation (create it first if none exists — that is the
   audit trail, not a formality).
3. Run the defined target (`make registry-cache-gc`, the publish lane, …) — never an ad-hoc
   hand-built API call when a target exists.
4. Stamp the issue with the run record + proof commands, and re-measure with the tool's read-only
   report (`make registry-cache-orphans`, `make agent-access-report`).

## Precedents

- #2923 — this policy itself: identity + scope roster in AGENTS.md, gated by
  `scripts/check_agent_access.py` (`make check-agent-access`, in the unit battery).
- #2914 — the GC sweep: tooling merged on `main` weeks before any identity carrying
  `delete:packages` could run it; the stamp requirement is why each future sweep lands audited.
