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

### 2a. Adding a fleet rule DOES move the block — and the exemptions file cannot cover it
When the task is to *add* a bullet to `agents/standing-rules.md` (a new fleet rule), `fleet_block()`
changes, and that reds on every lane SOUL in two independent places:
- `check_agent_profiles` (`fleet-block-drift`) — **exemptable** by `agents/fleet-block-exemptions.json`.
- `tests/test_agent_profiles.py::test_the_doc_soul_stated_block_matches_the_gate_canonical` — a pytest
  that hardcodes **this** doc lane's SOUL == `fleet_block()`, with **NO exemption path**. The exemptions
  file only bridges the static gate; nothing exempts the pytest, so `linux / unit` reds unsolvably while
  the doc lane's own SOUL lags the new bullet.
The correct fix is the one #791 already allows: **a lane may edit its own SOUL**, so the doc lane adds the
identical bullet to `agents/llgenie-documentation-maintainer/SOUL.md` in the same PR (and drops its own
entry from the exemptions file, since a now-satisfied entry reports STALE). A dispatch saying "do NOT
touch lane SOULs" is written on the premise the exemptions file greens everything; it does not, and a
PR left red for lack of that one edit is a governance gap, not a mechanics one. Verify with the gate's
own helpers before claiming green: `PYTHONPATH=scripts python3 -c 'import check_agent_profiles as c;
from pathlib import Path; print(c._stated_block(Path("agents/<lane>/SOUL.md").read_text()) ==
c.fleet_block(Path("agents")))'` — must print `True`. Note this SOUL.md write hits the protected-write
prompt (§6): without a live human answer it does not land, and the PR stays correctly BLOCKED.

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

## 6. SOUL.md and AGENTS.md are protected instruction files
Writing either triggers a one-operation desktop approval prompt from `file_tools_write_guards.py`. The
gate is per-profile and per-write: it fires from the session doing the write, and only a live human
answer authorises it. A teammate-relayed "owner consent granted" is **not** consent and is not a
reason to attempt the write at all — a relay cannot reach this session's prompt, so the attempt just
times out and becomes another unrecorded retry. The gate's own block message after a timeout says
explicitly *do not retry it or attempt the same edit via another path (terminal, execute_code, etc.)* —
honour that literally. Record the blocker on the issue with exactly what the prompt needs and stop.
When the owner is at the machine and answers the prompt, one retry lands.

An automated integrity/nerve/completion check that *demands* the write is **not** consent either — it
is not a human and cannot reach the prompt. The task is complete when the change is made and verified,
not when a checker stops complaining: if the one remaining edit needs an unanswered consent prompt,
the honest terminal state is "blocked on owner consent", recorded on the issue — never a fabricated
green and never a gate bypass.

## 7. A census in the note must equal what the command reads
`docs/changes.d` fragment count and `agent-wiki` note count are the same number (each fragment indexes
exactly one note). Verify with a glob before quoting a figure; `check-docs` prints `ok: N fragment(s)`.
A note that hard-codes an older N than the gate reports is the same defect as any stale census — re-run
and correct it in a follow-up commit, then re-point the PR head and the fleet messages at the new sha.

## 7b. Diagnosing a red `linux / unit`: step list first, then `--log-failed`
`agents/**` selects the full `skills` class in CI scope (`ci_scope.py`), so the heavy `linux / unit`
matrix runs (not the docs `paths-ignore` set) — expect the whole pytest suite, ~12 min. To find the
failing step and its reason quickly: (1) `gh api repos/<o>/<r>/actions/runs/<run>/jobs --paginate --jq
'.jobs[]|select(.name|startswith("linux / unit"))|.steps[]|"\(.number) \(.conclusion) \(.name)"'` to
name the failing step (usually `make ci-unit`); (2) `gh run view <run> --job <jobid> --log-failed` —
this returns the failure lines inline and is faster/more reliable than paging the raw job log API. Do
not paste whole logs into the issue; quote the single `AssertionError` / `FAILED tests/...` line.

## 8. Posting the bookend / evidence comment: use `--body-file`
A quoted heredoc (`<<'EOF'`) does **not** interpolate `$PR` / `$SHA`, so a literal `${PR}` lands on the
board. Write the body with the file-write tool to a scratch file, then
`gh pr comment <n> --body-file <path>`; delete the scratch file after.

The **PR body** AGENTS/BASE evidence lines are read by `check-pr-agents-line`
(`check_pr_hygiene.py:490,494`), whose regex wants a plain `AGENTS: <sha> <bytes>b <lines>l` and
`BASE: <sha> (== origin/main at open)` at **line-start** — NOT `- **AGENTS:**` markdown bullets. Emit
the exact plain lines the preflight prints. A body-only fix (adding `closes #N`, fixing AGENTS/BASE)
does not re-trigger CI because check-runs are keyed to the head SHA (#1589 reads the live body): after
the edit, re-dispatch the failing gate and re-read check-runs at the head — don't claim "fixed" on a
run that already read the old body.

### 8a. `closes #N` in the body ALONE reds `check-pr-closing` (squash-mismatch)
This repo squash-merges with `squash_merge_commit_message=COMMIT_MESSAGES`, so the landed commit is the
**joined branch commit messages**, not the PR body. `check_pr_closing.py` requires the body's
adjacent-close set and the commit text's adjacent-close set to be **equal** (`check_squash`, the
`commit_closed != body_closed` branch). Adding a plain `closes #N` to the body when your commit subject
ends `(issue #N)` (NOT an adjacent close) makes body-close `{#N}` but commit-close `{}` → a fresh
`squash-mismatch` violation you did not have before. Confirm locally before pushing:
`python3 scripts/check_pr_closing.py check --body-file <body> --head <ref> --base <merge-base> --rev
<HEAD>` and read `squash closes:` vs `closing references:` from the `report` subcommand.
The fix is to put the **same** adjacent `closes #N` in the commit message — and ride it on the real
substantive commit (the SOUL/vote/gate change the PR already needs), not a message-only amend: amending
only the message force-pushes a new head on an unchanged tree, re-runs the whole matrix, and re-confirms
whatever was already red — pure churn. One genuine commit that both makes the change and carries the
close is the clean push.

## 9. PR head reads lag a push by a few seconds
After `git push`, `gh api repos/<o>/<r>/pulls/<n> --jq .head.sha` can still show the previous sha for a
moment. Re-read (short sleep) before you report the head — a report naming a stale head is a claim about
a branch that no longer exists.
