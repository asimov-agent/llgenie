# Fleet rule 15: fresh base, bookended work (implementer lane)

The implementer lane's copy of fleet rule 15 (#873), landed through the #791 process on
`feat/agent-profile-implementer-skill`:

- **SOUL** already carried the rule verbatim (via #972).
- **Skill** (`references/queue-and-pr-mechanics.md`) now carries the operative half: fetch `origin main`
  and branch at the sha just fetched; never a sha from a chat; the fork-named-`origin` trap; the stacked
  exception (name both the stack head and the fetched `origin/main`); start comment → finish comment →
  report both lines to the planner; and the measured hook — a branch sat at `798cbee` while main moved to
  `5017128e`, and the rebase then found a stale ratchet baseline, a dead index row, and a lint rule that
  did not exist at cut.
- **Tests** pin both the SOUL's rule and the skill's procedure (negative controls run: removing each
  section makes the test fail).

Bookend for the whole pass: base main at plan `7db4ac99`, started from `73cbe680`, finished `3c2d2242`
(local == remote == PR head). The fence-quote test (#956/#944 delta) was verified against the live gate
before being added, rather than chasing a fabricated defect.

Referenced in: `agents/llgenie-issse-implementer/SOUL.md`,
`agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/queue-and-pr-mechanics.md`,
`tests/test_agent_profiles.py`.
