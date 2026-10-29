# Implementer rebase-only-on-conflict rule (issue #1015, 2026-10-29)

Owner rule extending #994 + #1010: **do not rebase a PR onto every `main` move — rebase only when it is
actually `CONFLICTING`, or its base merges.** Let `main` advance under an armed branch until a merge
actually needs a rebase; a branch that is `MERGEABLE` but slightly behind is not broken, and chasing every
`main` move is churn that rewrites shas under stacked children and forfeits the arm's verdict.

- **Fetch before any work** via the explicit refspec `+refs/heads/main:refs/remotes/origin/main` or the API
  — never the local `refs/heads/origin/main` short-ref, which is a stale shadow (measured `6d9fef1d` when
  real main was `238dcd2c`, then `6b8fafcf`). Pull-to-friendly if not conflicting.
- **Verify the trigger** with `gh pr view <n> --json mergeable` before touching a branch: `CONFLICTING` —
  rebase; `MERGEABLE` — leave it and report.

Landed in this lane's SOUL (via the #919 tree + `make sync-agent-profile PROFILE=llgenie-issse-implementer
CHECK=1` byte-identical). While taking it, this lane's `containerized-repo-verification/SKILL.md` was found
live-ahead (8 lines) and re-taken live→tree — including the wall-refusal discipline: a protected-agent-
instruction wall refuses even your own lane's file; do not route around it by terminal/`git`/`execute_code`,
document the intent via a non-gated ledger/`agent-wiki`/test pin, and report the SOUL line as awaiting the
owner's approval, not silently dropped. A contract that only lives in a DM is lost.

Referenced: `agents/llgenie-issse-implementer/SOUL.md`,
`agents/llgenie-issse-implementer/skills/containerized-repo-verification/SKILL.md`. Issue #1015, #994.
