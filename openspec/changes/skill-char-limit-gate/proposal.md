# Gate the 100,000-character skill-writer cap (issue #2084)

## Why

`skill_manage` refuses any write to a `SKILL.md` above 100,000 characters and rolls back the whole
batch. A lane whose skill is over the cap cannot record a single lesson — it runs, learns, and
silently loses every correction. No gate measured it, so four tree skills were over the limit at
once and only one had been reported.

## What changes

- `scripts/check_agent_skills.py` gains a `skill-over-char-limit` finding over every
  `agents/*/skills/*/SKILL.md`, naming the file, the character count, the overflow, and the remedy
  (move whole sections into `references/`, leave a pointer).
- An unreadable skill is `skill-size-unreadable`: a length that cannot be measured is not a pass.
- The gate counts characters, matching the tool; a byte rule would false-red a file the tool saves.
- The four over-limit skills are slimmed by moving whole sections into `references/`, zero-loss.

## Impact

`make check-agent-skills` (already in `ci-unit`) now fails on an over-limit skill. No behaviour
changes for a skill under the cap.
