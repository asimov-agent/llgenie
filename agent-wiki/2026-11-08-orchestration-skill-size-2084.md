# llgenie-bot-orchestration SKILL.md back under the skill-writer cap, tree-based and zero-loss (#2084)

The tree copy of the planner's orchestration skill was 102,432 bytes — 1,977 characters past what
`skill_manage` will write — so **every** patch to the versioned rulebook was refused and rolled back,
and four support references written to carry the overflow existed only in the live profile. A
`make sync-agent-profile` would therefore have replaced the corrected live copy with the un-patchable
tree body and dropped those references.

## What was verified

- **Tree-based, zero-loss.** The base is the TREE copy at `origin/main` `c3f3b2ac` —
  **not** the live profile's 99,575-byte copy, which lacks 81 distinct lines the tree carries
  (merge-over-red verification, ci-verdict re-judge/expiry, push-and-rerun discipline, the
  loop-escape/deflection lesson). A straight live→tree copy would have destroyed all 81 silently.
- **The section move.** `## When to Use` (L81–147, 6,659 bytes, 64 lines) went **verbatim** into
  `references/when-to-use-and-pass-shape.md`; the body now carries a summary plus the pointer.
- **Subset proof (the mandated check).** Distinct lines of the pre-change tree body against the slim
  body ∪ the new reference:

  ```
  tree distinct lines: 719
  LOST: 0
  tree lines preserved: 719 / 719
  ```

- **Size.** `SKILL.md` 102,432 b / 101,977 chars → **97,962 b / 97,537 chars**, 2,463 characters of
  headroom under the 100,000 cap.
- **The five references**, each linked from the always-on pointer block: the four the issue names
  (`orchestrator-tick-contract.md`, `pass-contract-and-sweep.md`, `host-lane-precedence-over-ci.md`,
  `lane-gap-audit.md`) plus `fleet-quiet-diagnosis.md`, which `host-lane-precedence-over-ci.md` cites
  — committing that one verbatim without its pointer target would have red `skill-reference-missing`.
- **The gate, proven by a negative control first.** `skill-size` in `scripts/check_agent_profiles.py`
  (`make check-agent-profiles`, inside `make ci-unit`) refuses any `agents/*/skills/*/SKILL.md` past
  `SKILL_MAX_CHARS = 100_000` **and names the remedy** (`move sections into references/ … never raise
  the cap`), because a bare character count teaches nobody what to do. Planted against the pre-change
  tree body it reports:

  ```
  FAIL skill-size: agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md: is 101,977
  characters (102,432 bytes), 1,977 over the 100,000-character skill-writer limit — `skill_manage`
  refuses every patch … move sections into `references/` … until it fits, never raise the cap
  ```

  Restoring the slim body prints `OK … its body is under the 100,000-character skill-writer cap`.
- **The gate immediately found three more instances** it was not written for:
  `llgenie-pipeline-maintenance` (103,203 chars), `llgenie-engine-improver` (106,407) and
  `llgenie-pr-rebase` (103,927). They are recorded as dated exemptions in
  `tests/fixtures/skill-size-exceptions.json`, each naming its own slimming issue **#2114**, and the
  gate reports the record as a note and reds the moment an entry goes stale (file back under the cap).
  An exemption is a decision with a tracking issue, never a pass.

## Decisions taken

- **`host-lane-precedence-over-ci.md` is committed verbatim, beside `host-lane-precedence.md`.** The
  issue predates #2073, which landed the canonical tree write-up of the same rule; the live twin's
  unique sections (measuring a lane before calling it stalled, and the whole-fleet-quiet diagnostic
  order) exist nowhere in the tree, so both stay and the file carries a two-line header stating which
  is canonical and what the other adds.
- **`fleet-quiet-diagnosis.md` came with it** — it is the pointer target `host-lane-precedence-over-ci.md`
  cites, and a live-only reference is exactly what #2084 is about.
- **No live profile was written.** `make sync-agent-profile` and `tester-fold-live … COPY=1` were not
  run: 56 of the 114 tree files would shrink the live profile.

## Not covered

- `make sync-agent-profile PROFILE=llgenie-planner CHECK=1` still reports `SKILL.md` as differing:
  tree 97,962 b against live 99,575 b, and the live copy is missing the tree's 81 unique lines. Making
  them byte-equal needs the tree's unique lines written **into** the live profile, which is a separate
  change (#928/#1079/#2062 own that drift class) — see #2084's comment for the measurement.
- The three other over-limit skills are #2114.

## Status

OpenSpec change: not applicable (agent profile content + a gate, no new capability spec). The gate's
tests are `tests/test_agent_profiles.py::test_a_skill_past_the_writer_cap_is_a_finding_that_names_the_remedy`
and the three exemption tests beside it; `make test-unit` runs them.
