# agents/ — the host agents' behaviour, versioned

An agent's instructions live with the agent, so a change to them is reviewable (issue #791). This tree is
the source of truth for the profiles listed in [`manifest.json`](manifest.json); `make sync-agent-profile
PROFILE=<name>` copies `agents/<name>/` into that profile's Hermes home, and `make check-agent-profiles`
gates the tree in CI.

```
manifest.json                     # which profiles this tree owns, and the rules each SOUL must state
standing-rules.md                 # the ONE copy of the canonical fleet block (issue #873)
fleet-block-exemptions.json       # profiles that do not state the block yet - each with a reason and an owner
<profile>/
  SOUL.md                         # the role it runs under
  skills/<skill>/SKILL.md         # + references/ that skill names
```

## Joining the tree

1. Add `agents/<your-profile>/SOUL.md` with `# <Name>`, a `**Role:**` line, the canonical block from
   [`standing-rules.md`](standing-rules.md) **verbatim** under its heading, and your lane's own rules below
   a second heading.
2. Add `{"name": "<your-profile>", "rules": [...]}` to `manifest.json`. The rule names are the ones in
   `STANDING_RULES` inside `scripts/check_agent_profiles.py`; a name that is not there is a manifest defect,
   not a silent pass. `never-merge` must be declared by at least one profile.
3. Run `make check-agent-profiles`.

## The two things the gate will not let slide

**The canonical block is compared, not trusted.** `check-agent-profiles` extracts the block from
`standing-rules.md` and fails naming the profile and the **first missing bullet**. Thirteen paraphrases of
one rule are thirteen chances for it to stop being the rule; the single copy is what makes a drift a diff.
Deleting the copy while a SOUL still states the heading is a finding, not a skip — the check cannot pass by
not looking.

**An exemption is a debt, not an amnesty.** If your lane's block is not yet verbatim, add an entry to
`fleet-block-exemptions.json` with a `reason` and an `owner`. The gate stays green, but `make
check-agent-profiles report` lists the debt, and the moment your profile states the block the entry is
reported **stale** and must be deleted. An entry with no written reason is a finding.

The same shape is used for the `workflow_run` roster in `tests/fixtures/workflow-run-exemptions.json`
(issue #349): a hand-kept list that the guard itself audits.

## Syncing is a write into a running agent — so it refuses to shrink

`make sync-agent-profile PROFILE=<name>` copies this tree into that profile's Hermes home. The live files
are what the agent actually loads, so the script compares sizes before writing and **refuses** to replace a
live file with a shorter in-tree copy, printing both sizes and naming the file:

```
[agent-profile] REFUSED: SOUL.md — the tree copy is 5149 b and the live file is 7509 b;
                syncing would replace 2360 b of live behaviour with a shorter file
[agent-profile] FAIL: 1 file(s) would SHRINK llgenie-planner's live profile — a truncated in-tree
                copy is not a sync. Re-copy the file from the live profile, or pass --force …
```

Measured on this host: an in-tree planner seed was 20,297 b against a live 100,031 b, and 5,149 b against
7,509 b — either would have overwritten live behaviour with a fraction of itself, silently and with a green
exit code. `--force` is the explicit way to say the shrink is intended.
