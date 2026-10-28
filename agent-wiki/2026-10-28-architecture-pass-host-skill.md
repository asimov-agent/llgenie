# 2026-10-28 — the architecture pass is a gated host skill, not a profile file

**Issue:** [#805](https://github.com/asimov-agent/llgenie/issues/805) · **PR:** [#811](https://github.com/asimov-agent/llgenie/pull/811) · **OpenSpec:** `architecture-pass-host-skill`

## What was wrong

The rule this repo paid for once — **an issue's numbers are measured on `origin/main`, never on the
checkout you happen to be standing in** — lived only in a host profile:

```
~/.hermes/profiles/llgenie-architect/skills/software-development/llgenie-architecture-issue-pass/SKILL.md
```

Three readers were exposed. The CI implementer runs in the agent image and cannot see a host profile, so
the procedure that decides whether an issue's numbers are true never reached the leg that acts on them. A
reviewer could not diff the procedure between two passes, which is exactly the audit trail #791 exists to
create for `SOUL.md`. And a profile reinstall, a `hermes` upgrade or a second machine loses it silently.

The cost was already paid in this session: six issues (#795–#800) were filed against `19e2ff3` — the tip
of PR #793's branch — while claiming `main`, and three needed rescoping after the planner re-measured on
`origin/main@17cdcf3`.

## What changed

| file | change |
|---|---|
| `.hermes/skills/llgenie-architecture-pass/SKILL.md` | **new** — the pass as a contract: frontmatter + `## Inputs` / `## Output` / `## Rules`, the audit-check table, the delta-table rule |
| `scripts/check_agent_skills.py` | `HOST_SKILLS = frozenset({"llgenie-architecture-pass"})`, exempt from the unused-skill rule **only**; `report()` marks it ` host-skill`; the docstring states the admission rule |
| `scripts/check_agent_skills.py` | a required section is now an **exact heading** (`^## Rules$`), never a substring — `## Rules for reviewers` no longer satisfies the contract |
| `tests/test_agent_skills.py` | four cases: admitted host skill is not `skill-unused`; an admitted one missing `## Rules` is still refused; a decorated heading is a missing section; this tree reports the skill and its sha rule |
| `.hermes/skills/llgenie-architecture-pass/references/host-skill-merge.md` | **new** — the merge recipe for two PRs that both add a host skill: measure with `git merge-tree --write-tree`, the README keep-both trap (two paragraphs + a false "the one HOST skill"), the `HOST_SKILLS` union, and "prove it on the merged tree" |
| `AGENTS.md` | the `(MANDATORY, durable)` measurement section (owner-approved) — the rule this skill enforces, in the referee file the legs read |
| `.hermes/skills/README.md`, `docs/ARCHITECTURE.md` | the HOST-skill row/paragraph, and the `.hermes/skills/` row that now says a host skill lives there |

## Decisions

- **`HOST_SKILLS` is by name, never detected from the body.** PR #793 introduced the mechanism for
  `llgenie-engine-improver`; this is its second instance. Whichever lands first, the other gains one line
  in the frozenset — the same shape, no second design.
- **The directory is `.hermes/skills/`, not `agents/`.** `agents/<profile>/skills/` is #791's layout and
  is not in the tree yet; when it lands, this skill moves and #805 says so.
- **`AGENTS.md` edited — with the owner's explicit approval, asked for and given before the edit.** It gains
  one `(MANDATORY, durable)` section stating the measurement rule (sha from `gh api …/commits/main`, a
  detached worktree, the counting method, and correct-the-body-not-the-comment). A bot that edits the
  referee file on its own is the behaviour #791 exists to prevent, so the approval is recorded here rather
  than implied: the question offered "#811 now / separate PR / leave it OWED" and the owner chose in-place.
- **The exact-heading match is in scope, not drive-by.** Without it, the acceptance criterion "removing
  `## Rules` turns the gate red" was only true for a deletion; a rename passed. Measured first: all 12
  committed skills already use exact headings, so nothing else moved.

## Verification (real output)

```
python3 scripts/check_agent_skills.py check
[check-agent-skills] OK: 10 agent leg(s) preload a project skill, 12 skill(s) carry
Inputs/Output/Rules, prompts within 400 characters           # exit 0

python3 scripts/check_agent_skills.py report | grep architecture-pass
  llgenie-architecture-pass: host-skill name='llgenie-architecture-pass' description=yes

pytest tests/test_agent_skills.py -q                          # 24 passed
python3 scripts/check_wiring.py check                          # exit 0 (235 docs, 258 targets)
python3 scripts/check_docs.py check                            # exit 0
python3 scripts/lint_linefeeds.py                              # LINT OK
make openspec-validate NAME=architecture-pass-host-skill       # Change is valid
```

Negative controls, each restored afterwards:

| what was broken | expected | measured |
|---|---|---|
| `HOST_SKILLS` emptied | `skill-unused` for the new skill | exit 1, `FAIL skill-unused: .hermes/skills/llgenie-architecture-pass/SKILL.md` |
| `## Rules` renamed to `## Rules for reviewers` | `skill-section` | exit 1, `missing '## Rules'` |

## Found on the way (not fixed here)

`scripts/module_name_guard.py check` is **red on clean `origin/main`** — it refuses
`tests/test_rename_llgenie_serve.py`, a test whose subject is the retired name — and it is wired to **no
make target** (`grep module_name_guard Makefile` -> 0 hits), so the guard `docs/ARCHITECTURE.md` calls the
renamed-module guard never runs in CI and would fail if it did. Out of scope for this change; it is the
"gate nothing enforces" class the architecture pass files as its own issue.

`make openspec-new` leaves the change directory **root-owned** (`-u root` into a `rw` mount), so the next
write needs `sudo chown` — the same class as #433, met head-on here.
