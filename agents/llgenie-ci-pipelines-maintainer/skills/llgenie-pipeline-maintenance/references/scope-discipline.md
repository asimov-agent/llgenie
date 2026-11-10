# Scope discipline on rulings, branch protection, and completion checks

## A terse ruling is never a licence to expand scope

- Translate an ambiguous or few-word owner ruling into a **bounded proposal** and confirm it before touching high-blast-radius files. High blast radius = how merges are gated, how workflow triggers fire, or files that other lanes' tests assert on.
- Offer the **minimal safe option first** in the clarify, and say explicitly what the larger option breaks (resource cost, deadlock, which tests/scripts ripple). One bounded question beats a sprawling refactor built on an inference.
- When the fix would mean reworking a *deliberate* design (e.g. removing a `paths-ignore` that exists to avoid running the full CI matrix on docs), that rework is a **product decision**, not something inferred from a one-line ruling. Record the ruling as a quoted comment on the issue and **hand the implementation decision back** to the queue owner.
- When the user pushes back with frustration ("what are you talking about"), do not defend the plan: stop, restate the assumption you were acting on in one sentence, and ask a single bounded clarify.

## Branch protection: `required_status_checks` deadlock

- GitHub blocks a merge until **every** context listed in `required_status_checks` reports green for that PR. A listed context that a PR *class* never produces is a **permanent block**, not a warning.
- The safe set is the **intersection** of contexts every PR class receives. Measure it from real PR rollups per class (code PR vs docs-only PR) — never assume an enum of job names.
- Anything broader than the intersection requires making every class produce every context (a trigger/workflow change). That is itself a scope decision and must be ruled on, not inferred.

## Completion checks do not override explicit instructions

- A generic integrity/completion nudge ("make and verify a task-relative change") never overrides an explicit instruction that forbids that change. State the verified state, name the tension in one line, and hold.
- **Never fabricate a mutation** (a ruleset write, a code edit) to satisfy a check. A mutation made against an explicit "do not touch X" is worse than an unappeased check.
- Evidence is a **read-back**, never a claim: `gh api "/repos/<owner>/<repo>/rulesets/<id>" --jq '{id,rules:[.rules[].type]}'`, `gh issue view <n> --json comments`, `git rev-list --count <base>..HEAD`, `git status --porcelain`. "I posted it" / "I changed it" must be proven by the API echoing the new state and the *absence* of unintended changes (ruleset still only its original rules; branch still 0 commits).
- Report an abandoned vehicle honestly (an empty worktree/branch created for a fix that was then scoped down) as a measured fact; do not prune it — pruning is the owner's call.
