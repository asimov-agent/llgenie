# Changing `agents/<profile>/` text (SOUL.md, skills)

Editing a bot's SOUL or skill is a **behavioural-surface** docs change, not an ordinary doc edit. It
has its own gates and its own hazards; run them all before you open the PR.

## 1. Branch from freshly fetched upstream `main`
Explicit refspec, never a sha quoted in a message:
`git fetch origin refs/heads/main:refs/remotes/origin/main`. Write that sha into the start bookend.

## 2. The verbatim fleet block must not move
A profile SOUL carries a `## Standing rules (fleet, ...)` block that must stay **byte-identical** to
`agents/standing-rules.md`; `check_agent_profiles.py` (`_fleet_findings`) reds a `fleet-block-drift`.
Never edit inside that block to resolve a duplicate rule — edit only the lane's own prose above it.

## 3. Dedup a duplicated canonical rule by de-bolding the restatement
`_duplicate_rule_debts` counts occurrences of the bolded `**Title.**` rule form and emits a
non-blocking note when the count is >1. To dedup: keep the fleet bullet as the single canonical
bolded occurrence and reword the other restatement into lane prose that preserves every operational
detail but drops the bold title. Verify the count drops to 1 by reading the file **at the PR head**
(fetch the raw content at the head sha), not just the worktree.

## 4. An `agents/**` diff owes a change→note
`check_docs.py` `change_note_problems` treats `agents/*/SOUL.md` as a behavioural surface: the branch
must add a `docs/changes.d/*.md` fragment **and** an `agent-wiki/*.md` note, or the gate fails. The
issue body usually names both. Regenerate `CHANGES.md` after adding the fragment.

## 5. Run the profile gate in CI-parity mode
On a dev host with `~/.hermes/profiles`, `check_agent_profiles.py` reports `live-longer` /
`live-lines-missing` drift for every lane — that is pre-existing host state, not your PR. Re-run with
no live profiles dir (a clean `HOME`) to get the runner verdict: `OK ... LIVE RULEBOOKS NOT COMPARED`.
Do not "fix" host drift by syncing a lane whose live copy is richer — it truncates silently.

## 6. SOUL.md is a protected instruction file
Writing it triggers a one-operation desktop approval prompt from `file_tools_write_guards.py`. A
planner-relayed "owner consent" does **not** satisfy it — the prompt must be answered at the desktop
by a human. Repeated timeouts are evidence the gate is real, not a reason to retry blindly: record the
blocker on the issue with exactly what the prompt needs and stop. When the owner is at the machine and
answers, one retry lands. Never leave a stuck state unrecorded.

## 7. A census in the note must equal what the command reads
`docs/changes.d` fragment count and `agent-wiki` note count are the same number (each fragment indexes
exactly one note). Verify with a glob before quoting a figure; `check-docs` prints `ok: N fragment(s)`.
A note that hard-codes an older N than the gate reports is the same defect as any stale census — re-run
and correct it in a follow-up commit, then re-point the PR head and the fleet messages at the new sha.

## 8. Posting the bookend / evidence comment: use `--body-file`
A quoted heredoc (`<<'EOF'`) does **not** interpolate `$PR` / `$SHA`, so a literal `${PR}` lands on the
board. Write the body with the file-write tool to a scratch file, then
`gh pr comment <n> --body-file <path>`; delete the scratch file after.

## 9. PR head reads lag a push by a few seconds
After `git push`, `gh api repos/<o>/<r>/pulls/<n> --jq .head.sha` can still show the previous sha for a
moment. Re-read (short sleep) before you report the head — a report naming a stale head is a claim about
a branch that no longer exists.
