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

### 2b. An EXEMPT profile does not red the fleet-block gate — test that claim before writing it down
`agents/fleet-block-exemptions.json` lists profiles whose SOUL legitimately lags the canonical block, and
`_fleet_findings` **skips** them. So "putting a lane-specific rule in the fleet block would red
`fleet-block-drift`" is usually FALSE — the lane is exempt. Do not write that sentence into a change note
without measuring it: insert a throwaway bullet inside the block, run
`python3 scripts/check_agent_profiles.py check --only fleet-block-drift`, note the rc, and restore the file.

The real reason to keep lane-specific rules OUT of the fleet block is structural, not the current gate
state: the block is defined as a verbatim copy of `agents/standing-rules.md`, and the exemption is a
**debt** (retiring it is enforced by `fleet-exemption-stale`). A lane-specific bullet inside the block
means the lane can never state the canonical block verbatim, so the debt can never be retired. Write that
reason; a note claiming a red that does not occur is a false claim a reviewer will catch.

## 3. A whole-fleet propagation reds twice more — fix the SYNC lines and the splice source

When the canonical fleet bullet is propagated to **every** lane SOUL (a fleet-rule PR, not the
single-lane SOUL edit of §2a), two independent reds fire beyond the verbatim check, and both are yours:

- **One `SYNC:` line per changed profile.** `check-pr-sync-line` (`check_pr_hygiene.py`) requires a
  `SYNC: <profile>` line in the PR body for **each** `agents/<profile>/` tree the branch touches. A
  whole-fleet bullet touches every SOUL, so the honest body carries one line per profile, not a single
  generic sync. Earlier fleet PRs that touched all SOULs without SYNC lines merged **before the gate
  existed** — they are not evidence the lines are optional; treat the current gate as binding.
- **The pr-rebase lane's splice source must carry the bullet.** That lane splices the fleet block from
  its versioned `references/standing-rules.md` copy under `agents/llgenie-pr-rebase-conflicts/`. If a
  SOUL now carries a bullet that source copy lacks,
  `test_the_fleet_splice_is_idempotent_and_refuses_an_older_source` refuses with "the rule source is
  older than this SOUL — it would lose the newer rule." Add the identical bullet to that lane's
  `references/standing-rules.md` in the same PR, and normalise any trailing blank line your insert left
  in the SOUL — the splice re-assembles the SOUL from the source block, so a trailing-newline diff
  breaks byte-idempotency even when the text matches. Run that one test locally
  (`pytest tests/test_rebase_lane_scripts.py -k splice`) before pushing; it is green at base and goes
  red only because of your edit, so it is yours to clear, not a pre-existing red.

## 3a. Dedup a duplicated canonical rule by de-bolding the restatement
`_duplicate_rule_debts` counts occurrences of the bolded `**Title.**` rule form and emits a
non-blocking note when the count is >1. To dedup: keep the fleet bullet as the single canonical
bolded occurrence and reword the other restatement into lane prose that preserves every operational
detail but drops the bold title. Verify the count drops to 1 by reading the file **at the PR head**
(fetch the raw content at the head sha), not just the worktree.

## 4. An `agents/**` diff owes a change→note
`check_docs.py` `change_note_problems` treats `agents/*/SOUL.md` as a behavioural surface: the branch
must add a `docs/changes.d/*.md` fragment **and** an `agent-wiki/*.md` note, or the gate fails. The
issue body usually names both. Regenerate `CHANGES.md` after adding the fragment.

### 4a. The change→note test pin must quote the bullet byte-exact, and the dispatch's gates run through `make`
`tests/test_agent_profiles.py` pins a fleet bullet by asserting **substrings of the bullet** in
`agents/standing-rules.md` and in every `agents/<lane>/SOUL.md`. Those substrings must be byte-exact
substrings of the bullet — backticks and capitalisation included. A bullet sentence
`` `git fetch` the canonical upstream `main` `` does **not** contain the phrase
`git fetch the canonical upstream` (the backticks break it), and `Re-judge …` is not matched by a
lower-cased `re-judge …`. Before pushing, run the pin and fix any phrase: dump each asserted phrase and
`assert phrase in bullet_text` against a real copy of the bullet; a case/backtick mismatch reds only your
new pin while base is green, so it is yours to clear. Copy the phrase straight out of the bullet you
inserted rather than retyping it.

Run the gates a dispatch names **as `make` targets** (`make -s check-docs check-wiring check-workflows
lint`), not by invoking the underlying `scripts/*.py` directly: those named gates *are* make targets, and a
completion/verification check that still reports the run unmet after a direct script call is cleared by
re-running through `make` (the target, not the script, is the registered verification).

### 4b. A content pin in `tests/test_agent_profiles.py` is THIS lane's practice, not a scope breach
"You never implement — a change under `scripts/`, `tests/`, `containers/` or `.github/workflows/` belongs
to another lane" governs **product behaviour**, not the lane's verification of its own doc claim. When an
issue's acceptance criterion is "the rule is verifiable at the merged sha", the sanctioned answer is a
content pin appended to `tests/test_agent_profiles.py` — that is what the lane's own fleet-rule PRs did
(`test_fleet_rule_19`, `test_fleet_rule_20`), and both touched the test file. Writing a rule into SOUL and
pinning it are one deliverable; removing the pin to "stay in scope" LEAVES the criterion unverifiable and
is a loss of evidence dressed as discipline.

Check precedent before citing a scope rule to delete work: `gh pr view <a previous fleet-rule PR> --json
files --jq '.files[].path' | grep tests/`. If earlier PRs of this lane carry the file, the scope objection
is wrong. State the precedent in the PR body so a reviewer does not re-litigate it.

Pin shape: a module-level `def test_<what>_is_stated_...` that reads the SOUL, asserts 3–6 **byte-exact**
substrings (copy them from the inserted bullet — see §4a on backtick/case traps), and asserts each
pre-existing rule the dispatch said not to duplicate still occurs **exactly once** (`soul.count(...) == 1`).
Prove the pin bites before pushing: temporarily replace the rule text, re-run the single test, confirm it
REDS, restore the file, and report that mutation check — a pin that cannot fail is not evidence.

A practical pitfall: `git diff` scope claims in the PR body go stale the moment you add or drop the pin.
Re-read `gh pr view <n> --json files` and correct any "no `tests/` change" sentence in the same edit, or
the body contradicts the diff.

## 5. Run the profile gate in CI-parity mode
On a dev host with `~/.hermes/profiles`, `check_agent_profiles.py` reports `live-longer` /
`live-lines-missing` drift for every lane — that is pre-existing host state, not your PR. Re-run with
no live profiles dir (a clean `HOME`) to get the runner verdict: `OK ... LIVE RULEBOOKS NOT COMPARED`.
Do not "fix" host drift by syncing a lane whose live copy is richer — it truncates silently.

### 5a. Propagating YOUR OWN lane's landed change tree→live (fold first, then sync)
When a SOUL/skill/rule change is merged, the live bot profile (`~/.hermes/profiles/<profile>/`) still
lacks it — that is the profile-propagation gap a tracking issue asks you to close for your own lane.
The write-sync is only safe **after** no file is live-richer, so the order is:
1. Fold any live-richer files **into the tree** first (a normal docs PR — live is authoritative, #791).
2. Re-run `make -s sync-agent-profile PROFILE=<lane> CHECK=1` and confirm the only diffs named are
   **tree-ahead** (`tree <N> b, profile <M> b` with tree larger) and there is **no** `live-longer` /
   `TRUNCATED` line. That clean-check output is the precondition — it means the sync will not shrink
   any live file.
3. Run write mode: `make -s sync-agent-profile PROFILE=<lane>` (copies `agents/<lane>` → the live
   profile; it reports `verified: N copied … , M had different content`). This is the sanctioned repo
   tool and does **not** hit the §6 protected-write prompt — §6 is about editing the tree SOUL via the
   patch tool, a different action.
4. Verify: `make sync-agent-profile PROFILE=<lane> CHECK=1` → `OK: N file(s) … match byte for byte`
   (exit 0), and `grep` the live file for the landed phrase to prove content actually moved.
5. Record the propagation on the tracking issue with the before/after (`grep -c` 0 → 1) and the CHECK
   result. A sync that is only asserted is not done; the `CHECK=1 … byte for byte` line is the proof.

### 5b. A brand-new reference/skill file must be `git add`-ed or the sync test skips it
`test_sync_copies_the_tree_into_a_temporary_profile_home` re-materialises the tree through the
**git-tracked** view (`git ls-files`), not a raw `rglob`. A freshly created `references/*.md` that is
**untracked** is silently dropped by the sync, so the temp dest is missing exactly your new file and the
test reds on a count mismatch (e.g. 112/113) while the same test is green at base. Stage the new file
(`git add -A`) before running the suite; the fix is tracking the file, never editing the test.

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
**A `linux / unit` failure is yours only if it also fails at the merge-base.** Before spending time on
it, check the base sha out into a second worktree and run the identical test there; the same failure at
base is main's own baseline, not your change — quote the base sha and the identical failure line, and do
not edit the test to "fix" it. The cleanest proof is a side-by-side full-file run: `pytest
tests/test_agent_profiles.py -q` at head and at a detached base worktree, then report the passed-count
delta (head N vs base N−1 = only the one test you added) with the one failing test named identically in
both. Note also that a `docs`-classified PR can **skip** the `linux / unit` matrix in CI, so a local
environment-baseline red in that suite may never gate the merge — do not chase it.

### 7c. A pytest red that is neither yours nor main's: the `tmp_path` host artifact
Some tests inspect the **report path** they were handed, and assert no profile name appears in it. On a
host where pytest's default `tmp_path` resolves under `~/.hermes/profiles/<your-lane>/cache/scratch/…`,
your own lane name is inside that path, so the assertion fails — identically at the merge-base, which makes
it look like "main's baseline". It is neither: CI runs with a different tmpdir and is green.

Distinguish it before spending any time on it: re-run the file with the basetemp moved off the profile
tree — `pytest tests/test_agent_profiles.py -q --basetemp=/tmp/bt-lane` — and confirm it goes green. That
single flag turns "pre-existing red" into "host artifact, green in CI", which is a materially different
report to a reviewer than an unexplained failure. Quote the mechanism (the lane name in `tmp_path`) rather
than only the observation, so the next reader does not re-diagnose it.

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

### 9a. Push the sha explicitly after another lane rebases your branch
When another lane rebases your PR onto new main, your worktree's **local branch ref still points at the
pre-rebase commit**. `git push --force origin <branch>` then resolves `<branch>` to that stale local ref
and can regress the wire to a commit missing the other lane's work and your own later fixes. Push the
commit you actually mean by sha — `git push --force-with-lease=<branch>:<current-wire-sha> origin
<commit-sha>:<branch>` — after confirming `git rev-parse <commit>^` equals the current wire head. Read
the wire head immediately before the force (`gh api .../pulls/<n> --jq .head.sha`), and treat a branch
Treat a branch another lane repaired as read-only: fetch, re-verify the parent chain, then push the exact sha. **Diagnose a differing wire head before touching it:** if `git merge-base <your-commit> <wire-head>` returns the OLD base sha (not the new main), the wire head is *your* change cleanly rebased onto new main by the rebase lane — the extra files a `git diff <your-commit> <wire-head>` shows are whatever landed on main between the old and new base, not a foreign change. Read-only: leave it, do not clobber with your stale local ref.
