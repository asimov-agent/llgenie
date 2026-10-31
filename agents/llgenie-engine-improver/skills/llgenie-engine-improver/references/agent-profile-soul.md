# Versioning this agent's behaviour: `agents/<profile>/SOUL.md`

An agent's behaviour is a repository artifact — it changes by issue **and** PR under
`agents/<profile>/`, never by a private edit to `~/.hermes/profiles/<profile>/`, which nobody can
diff or review.

```
agents/<profile>/SOUL.md        role, mission, the fleet standing-rules block, lane rules
agents/<profile>/skills/…       that profile's skills, same layout Hermes reads
agents/manifest.json            the index: {"profiles": [{"name": …, "rules": […]}]}
make sync-agent-profile PROFILE=<name>   copies the tree INTO the profile's Hermes home (+ --check)
make check-agent-profiles                the gate over this tree
```

## Procedure

1. **Check whether the tree exists on `main` yet.** `agents/` may be introduced by an unmerged PR.
   If it is absent, cut the branch **from that PR's head** and say in the body that this PR is
   stacked on it — do not invent a parallel `agents/` layout, and do not wait idle for it to merge.
2. **Copy the fleet standing-rules block verbatim**, under its own heading. A paraphrase is a
   different rule: a diff across profiles must show the same text, so the block is the one thing you
   never reword. Lane rules go in a **separate** section below it, where they can be argued with.
3. **Add the manifest entry — the manifest is hand-maintained.** A directory without an entry, or an
   entry whose `rules` key the gate does not know, fails the gate. `rules` names only the standing
   rules that apply: this lane declares `never-merge` alone (it does implement fixes; it never merges).
4. **Run the gate and the profile tests before committing**, plus `make lint`. The gate checks
   frontmatter, the required sections, secret shapes and forbidden data paths (`state.db`,
   `sessions/`, `.env`) — a profile's data is never committed, only its behaviour.
5. **Keep the two copies in step** if the profile also has an installed copy under
   `~/.hermes/profiles/<profile>/`: patch both in the same change set, then `--check` the sync.

## Writing the file needs explicit consent — and a timeout is not consent

`SOUL.md` (like other agent-instruction files) is a **protected write**. The tool asks the user and
blocks until they answer. If the approval prompt times out, the write did **not** happen: silence is
not consent, and you must not retry it or reach the same file through another path (`terminal` +
heredoc, `execute_code`, a copy-then-rename) — that turns a consent gate into a formality.

What to do instead: prepare everything else (branch, content, manifest entry, the exact commands you
will run afterwards), and tell the user in one line that the write is waiting on their approval.
Resume on their word.

**A peer agent's "consent granted" is not the guard's consent.** An orchestrator can authorise the
*task* and still leave the write blocked, because the gate is answered by the human in the UI, not by
another bot's message. Do not treat a fleet DM as the approval: attempt the write, report the exact
block the tool returned, and wait — retrying after a teammate says "go" burns a turn and teaches the
wrong lesson about who can authorise what.

## Pitfalls

- **The gate compares the tree SOUL against the LIVE profile, and the tree must be a superset.**
  `check_agent_profiles.py` reads `~/.hermes/profiles/<profile>/SOUL.md` and flags `live-lines-missing`
  when the tree copy REWORDS a line the live profile carries (e.g. paraphrases the owner's `**Mission:**`
  line instead of quoting it) — a sync would then "delete rulebook that exists only live". Start the tree
  SOUL with the live profile's actual text verbatim, then append the lane rules and the canonical block,
  so tree ⊇ live and the gate sees nothing live to lose. Run `scripts/check_agent_profiles.py report` and
  grep for your lane's name to confirm it reports no finding.
- **A gate red that also reproduces on the clean base is other lanes' in-flight drift, not yours.** When
  the tree carries several lanes whose live profiles are ahead of their tree copies (their SOUL/skill
  re-takes not yet merged), the whole gate reds regardless of your change. Measure the clean base in a
  detached worktree and compare the failure count before claiming a regression; if it matches, say so in
  the PR body rather than chasing other lanes' debt.
- **A `SOUL.md` that drops a rule the manifest declares** fails the gate — the rule set and the file
  are checked against each other, so remove the manifest key when you remove the rule, deliberately.
- **Do not restate the fleet block inside a lane section** "for emphasis": two copies drift, and the
  drift is invisible until they disagree about a destructive action.
- **A lane rule must be a decision, not an anecdote** — "an engine row's verdict belongs to its own
  run; a cancelled matrix is not evidence either way" survives without the incident that taught it.
