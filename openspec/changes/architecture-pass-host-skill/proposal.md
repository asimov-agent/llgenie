# A host agent's procedure is gated, diffable and in the tree

## Why

The measurement rule that this repository paid for once — an issue's numbers are taken from
`origin/main`, never from the checkout you happen to be standing in — existed only in a **host profile**,
`~/.hermes/profiles/llgenie-architect/skills/software-development/llgenie-architecture-issue-pass/SKILL.md`.
It cannot reach the CI implementer (which runs in the agent image with no host profile), a reviewer
cannot diff it between two passes, and a profile reinstall loses it.

Measured on `origin/main@17cdcf3`:

- `git ls-tree -r --name-only origin/main -- agents` -> 0 paths (that home is #791, still open).
- `.hermes/skills/` -> 12 entries: 11 bot-leg skills plus `README.md`, and **no host skill**. Its README
  stated the rule as "One Hermes **project skill** per agent leg".
- `grep -c 'commits/main' AGENTS.md` -> 0: nothing in the rulebook says which commit an issue's numbers
  are measured against.

Six issues (#795–#800) were filed in one pass against a PR tip (`19e2ff3`, PR #793's branch) while
claiming `main`; three of them needed rescoping after an independent re-measure. The procedure that
would have prevented that was, and remained, the least reviewable thing in the tree.

## What changes

1. `.hermes/skills/llgenie-architecture-pass/SKILL.md` — the architecture-pass contract in the repo's
   skill shape (frontmatter plus `Inputs` / `Output` / `Rules`), carrying the sha rule, the counting
   rules, the audit checks and the correction discipline.
2. `scripts/check_agent_skills.py` — `HOST_SKILLS`, a frozenset admitted **by name** (never detected from
   the body), exempt from the unused-skill rule only; still owing frontmatter and the three sections.
   The `report` prints a ` host-skill` marker. This is the mechanism PR #793 introduces for
   `llgenie-engine-improver`, applied to its second instance.
3. The same gate stops matching a section name as a **substring**: `if section not in body` became an
   exact `^## Rules$` heading match, so `## Rules for reviewers` no longer satisfies the contract. All
   twelve committed skills already use exact headings, so nothing else moves.
4. `.hermes/skills/README.md` — the HOST-skill row and paragraph; `docs/ARCHITECTURE.md` — the
   `.hermes/skills/` row now says the directory carries a host skill no leg preloads.

5. `AGENTS.md` gains the `(MANDATORY, durable)` section **an issue's numbers name the commit they were
   measured on** — the sha from `gh api …/commits/main`, a detached worktree, the counting method, and
   "correct the body, not just the comment". It is the rule the skill enforces, stated in the referee file
   the legs are required to read; applied here with the owner's explicit approval (it is their file).

## Impact

- No leg changes: no Makefile prompt, no workflow and no bot behaviour moves.
- The gate gains one admission and one stricter comparison; a skill no leg preloads is still refused
  unless it is named.
- `make check-agent-skills`, `make check-wiring`, `make check-docs` and the agent-skills suite are green.
