# Security pipeline skill (#790)

A host agent asked to work a **security leg** now has a contract: `.hermes/skills/security-pipeline/SKILL.md`
(frontmatter `name: security-pipeline`, `## Inputs` / `## Output` / `## Rules`). It is the versioned
behaviour an agent reads before it re-derives the pipeline from source — the four legs, the shape of
the two files that decide each run, and the shared "green or nothing" rule.

## What the skill states

- **The four owners** are the daily scan (`security-scan`), the floor (`security-bumps`),
  tagged issues (`security-issues`) and the remediation bot (`security-bot`). A red scan is only a
  work item because `security-issues` + `security-bot` read it; the routing reactor deliberately does
  not watch the scan (its red is by design until the floors land).
- **`enforce_events` is data, never a literal** — the only events that may fail a run come from
  `data/security-policy.json` (`schedule`, `workflow_dispatch`); `push`/`pull_request` are forbidden
  (`make check-security-scan` refuses them). `pr_fail_on` is empty on purpose (report-only).
- **The floor is the maximum of the minimums** — per package, the lowest fixed version clearing every
  advisory the report lists; only a finding with a fixed version becomes a floor.
- **A compiled `requirements*.txt` is never an edit target** — `requirements.in` / `-dev.in` are
  edited; the compiled files come from the ONE generator.
- **Green or nothing** — a red gate reverts the edit, comments the real output, opens no PR; never
  merge, never push to `main`, never force-push.
- **Never add an `automerge` key to `renovate.json`** — every rule sets `automergeType: pr` and
  `platformAutomerge: false` (#718).
- **The routing invariant** (issue #780/#349) — a gate nobody watches is not a gate; the one
  deliberate exemption is `security-scan`, whose red is owned by `security-issues` + `security-bot`.
- **A merged PR's bare `closes #N` never clears a scan-evidence box** (#1693) — only
  `security-issues-reconcile` may, by naming a genuine completed scan (run id + sha).
- **Refuse what the lane cannot place** — a `component:container` advisory or a package pinned
  nowhere is refused on the issue, never guessed.

## Gate-driven change

`make check-agent-skills` iterates every skill directory and fails (`skill-unused`) on any skill no
leg preloads that is not admitted by name. No workflow/leg preloads a security skill (the pipeline is
its own daily scan), so the skill owes a **one-line `HOST_SKILLS` admission** in
`scripts/check_agent_skills.py` — the only script change, exactly the one the dispatch pre-authorized.
`.hermes/skills/README.md` lists the new leg row (and the HOST-skills paragraph names it).

## Scope

AC#1 of #790 (the `docs/SECURITY.md` routing-invariant page) is already satisfied on `main` via #780
(`a25650938a`); this PR carries AC#2 + AC#3 (skill + README leg row) and, via the HOST_SKILLS
admission, the AC#4 gate set (`make check-workflows check-docs check-agent-skills lint`) green.
