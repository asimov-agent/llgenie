# The change->note gate (#1123) and a branch cut before the gate existed

## What the gate checks

`make check-docs` -> `scripts/check_docs.py check` runs a change->note leg ONLY when a base ref
is available (`--base` or `CHECK_DOCS_BASE`; default resolves `origin/main`). It diffs
`git diff <base>...HEAD` and fails when the diff touches a *behavioural surface*
(`agents/<lane>/skills/`, `scripts/`, `Makefile`, workflows, `docs/*.md`, `data/`, ...) but adds no
`agent-wiki/<stem>.md` note. The note must also have a `docs/changes.d/<stem>.md` index row
(enforced by `problems()`), and both must be **committed** — the gate reads committed paths, an
untracked note is invisible to it.

It runs in the **`scope` workflow (`ci.yml` docs-class), against CURRENT `origin/main`** — not against
the branch's own cut point. So a branch cut before the #1133 gate landed is red on that head even
though locally `check_docs.py check` passes (no base, gate skipped with a printed note).

## The failure shape and the fix

Symptoms: `scope` job fails `make check-docs` with `change->note: this branch changes
agents/<lane>/skills/... (+N more) but adds no agent-wiki/<stem>.md note` while local
`check_docs.py check` (plain) says ok.

Root cause is almost always a **stale cut**: the branch is based on main *before* the change->note
gate merged, so its version of `check_docs.py` has no gate and CI (diffing against newer main) flags it.

Fix (one vehicle, atomically):
1. Rebase the single atomic commit onto current `upstream/main` (the canonical `asimov-agent/llgenie`,
   NOT the fork `origin`) so the branch carries the gate.
2. Add `agent-wiki/<date>-<stem>.md` (note, references its issue/PR with `#<n>`) and
   `docs/changes.d/<date>-<stem>.md` (one index row), folded into the SAME commit as the change.
3. Verify with the real base, not a plain run:
   `python3 scripts/check_docs.py check --base upstream/main` — expect ok AND no
   "change->note skipped" note; confirm the note path appears in `git diff --name-only <base>...HEAD`.
   Then run `python3 scripts/changes_index.py check` — it enforces the fragment<->note bijection
   (every note has a row, every row points at an existing note).
   The row format is a single pipe-table line:
   `| <date> | <one-line summary> | [note](agent-wiki/<stem>.md) | #<issue> |`
   — the `[note](agent-wiki/<stem>.md)` relative link and the trailing `#<issue>` are what the
   index parses; a bare filename or a missing issue column is not a valid row.
4. Force-push your own branch with `--force-with-lease` (lease = the current remote head); read the
   remote head back; re-arm auto-merge only after scope+guard+unit green at the new head.

## The change landed on main WITHOUT its note (owner merged the pre-amend head)

An owner merge can take the branch at its pre-amend head while you are still assembling the note pair;
that amend is then orphaned and the branch ref is deleted. Do not force-push a merged branch and do not
re-cut it. Land the note as a **new documentation-only follow-up PR against current main**:

1. Fresh worktree from the freshly fetched `upstream/main` tip; record that sha in the commit's
   `AGENTS:` line so the record says which main it completes.
2. Add ONLY `agent-wiki/<stem>.md` + `docs/changes.d/<stem>.md` (exactly one row), then render
   `CHANGES.md` with `make changes-index`. Three files, nothing else — the change itself is already on main.
3. Verify the gates on that tree (`check_docs.py check` ok, `check_dispatch_forms.py check` OK, the new
   row present in `CHANGES.md`) before pushing.
4. Open the PR ready-for-review with `closingIssuesReferences` **empty** — the parent issue is already
   closed by the earlier merge, and a closing keyword in the body attaches the PR to it. Read back
   `gh pr view <n> --json closingIssuesReferences --jq '[.closingIssuesReferences[].number]'` → `[]`.

Mechanism that makes this work: `check_docs.py`'s change→note leg returns no problems as soon as the
diff contains ANY `agent-wiki/` path, so a note-only diff satisfies the leg without re-touching the code.
The note body should still name the merged PR/issue it records, or it reads as a note for nothing.

## A missing trailing newline reddens `lint_linefeeds` (any file, not just the note pair)

`lint_linefeeds` (in the `scope` job, alongside `check-docs`) fails the PR when ANY changed tracked
file does not end with a `\n` — the workflow YAML, the docs edit, the `scripts/` module, the note pair.
The tool-writing path matters: a `write_file` (or a patch that rewrites a whole file) can leave the file
WITHOUT a final newline even when your content string looked complete, and the fragment case compounds it
— `changes_index.parse_row` counts non-empty lines and does NOT require a filesystem newline, so a valid
one-row fragment with no trailing newline passes the bijection check and still reds `lint_linefeeds`.
Every file you write, always end with a newline. This cost two PR laps in one session: hit it on the
workflow YAML and on two docs before checking the whole changed set.

**Check the byte before pushing, over the WHOLE diff, do not infer from `tail`:**
```bash
git diff --name-only upstream/main...HEAD | while read f; do
  [ -f "$f" ] || continue
  [ "$(tail -c1 "$f" | od -An -tx1 | tr -d ' ')" = "0a" ] || echo "NO NEWLINE: $f"
done
```
The last byte of every changed file must be `0a`. A pair whose fix lands one file's newline but not the
other gets merged in two separate follow-up PRs; fix ALL offenders in the same commit.

## The `scope` job's other leg: `openspec-tasks` (an unrelated red)

The docs-class `scope` job runs more than `check-docs` + lint: it also runs an `openspec-tasks`
census that reds on ANY `openspec/changes/*/tasks.md` with unchecked task checkboxes, on the diff
OR on main. An unchecked OpenSpec migration task file that another lane ships to main (e.g. the
subprocess-wrapper refactor) turns EVERY docs-scope PR red with e.g.
`openspec-tasks FAIL proc-seam: unchecked task checkbox(es) at lines [8, 11, 12, 13]`, regardless of
your note. Read the failing `scope` log line to a name: if it is `openspec-tasks` and the file is
untouched by your diff, this is a pre-existing red in another lane's product change — it is a
REPORT routed to that lane, never your fix and never something to "go green" by checking the boxes
in your PR. Report it to the planner so whoever owns that OpenSpec change checks them.

## A "docs contradict the shipped value" claim needs a FULL dated-note census — a superseded note is history, not the record

When a peer/reviewer files (or asserts) a docs-drift — "the change-note documents the superseded value X, but the head ships Y, so the criterion is unmet" — do NOT accept it or file a twin on one note's text. Reads the SPECIFIC note the claim cites and compare it to the fold at the head, then enumerate EVERY dated note for that change and read the one matching the shipped value. Two notes legitimately coexist: a PRIOR/superseded one recording an earlier value (a vetoed 480 raise) and the CURRENT one documenting the landed fold (360). The AC commonly names a file DATE that never existed (e.g. `2026-11-03-<stem>.md`) while the real note carries a later date; an AC whose INTENT is "a note documents the fold verbatim" is MET by the correctly-dated note even when its literal filenames are absent — a date/filename miss is a shape error, not a documentation absence.

Measure, at the PR head, in this order:
1. The fold itself: `gh api repos/<o>/<r>/contents/.github/workflows/<wf>.yml?ref=<head>` → the `timeout-minutes:` / value line.
2. The CURRENT note the head carries (`agent-wiki/<stem>.md` + `docs/changes.d/<stem>.md` whose date matches the change), read verbatim — if it states the fold value, the intent is satisfied.
3. The openspec change dir (`openspec/changes/<name>/{proposal,tasks,specs/...}`) and the `CHANGES.md` row — they usually agree with the fold.
4. Only if NONE of the current notes state the shipped value is the drift real. A genuinely-remaining gap is often a single artifact (e.g. a missing `docs/BOTS.md` per-change row with a `##`-help/`user-facing` target), not a rewrite of the note.

Do not rewrite a correct note to match a superseded value, and do not rename it to satisfy an AC's literal (wrong) filenames. Report the census (each path + its documented value) and narrow the issue to the one real gap; route the correction to the lane that filed it and to the planner. The dated historical note stays untouched — it is the record of a rule that used to differ (same rule as the docs-of-record pitfall in the SKILL body).

## Gate-free verify-by-dispatch tickets (#1475/#1482/#1486/#1493/#1498 shape)

These are NOT code PRs. Their AC says "evidence lands on a `verify` comment, then ticks": the vehicle IS the dispatch run, not a diff. If the target bot is `disabled_manually`, verify requires the owner/restore first — the bots were all restored by #1879, so dispatch and record. `gh workflow run <wf>.yml -f dry=true --ref main` for bots with a `dry` input (previews, files nothing); a workflow_run-only reactor (run-failure-reactor) has NO dispatch trigger and must be recorded as a named deliberate skip (424: Workflow does not have 'workflow_dispatch' trigger) — do not fabricate a failure to force it. Post each prove as a `verify` comment citing run id + per-job conclusions (guard + main job). When restoring a whole paused fleet (#1879), the restore-ORDER is data (`bots/pause.toml` restore_first/restore_after), and the execute-then-read-back loop must verify each `gh workflow enable` reached `active`; a count recheck (`remaining disabled_manually = 0`) is the honest summary.

## The OTHER gates a product PR reds when only check-docs is satisfied

Satisfying `check-docs` (note + fragment) is one leg of a product PR, not the whole battery. Two
sibling gates red a building-PR that adds a script/workflow change but nothing else:

1. **`check-pr-openspec-change`** (in `ci.yml`'s guard): a PR that changes product code under a
   behavioural surface must ADD a file under `openspec/changes/<name>/` (a real change dir with
   `.openspec.yaml` + `proposal.md` + `specs/<name>/spec.md` + `tasks.md` for `schema: spec-driven`)
   **or** name an ACTIVE change via an `OPENSPEC: <name>` body line. A PR that satisfies check-docs
   and nothing else still reds this. `make openspec-new NAME=<kebab>` scaffolds it but needs the
   openspec image (offline/fork it fails `Error 1`); hand-mirror a committed-valid active change
   (e.g. `zero-job-job-count-read`) exactly — `schema: spec-driven` REQUIRES the
   `specs/<name>/spec.md` with `## ADDED Requirements` / `### Requirement:` / `#### Scenario:` blocks
   and a `tasks.md` with ONLY `- [x]` (an unchecked box reds `openspec-tasks` in scope).
2. **`check-pr-acceptance`** (in `ci.yml`'s guard): `closes #N` is held against the linked issue's
   `## Acceptance criteria`; each `- [ ]` box must be ticked (verdict-gated, #1644 — never self-tick)
   **or** named out of scope under a `## Not covered` bullet that ends in a `#<n>` and whose first
   ~3 words match the criterion's lead. The gate's message literally offers this: "name it out of
   scope under `## Not covered` with a linked work item." A criterion my PR genuinely satisfies but
   that only a reviewer re-verify can tick stays RED until the reviewer writes back — that is by
   design (#1644), not a defect to clear by weakening. Use `## Not covered` only for criteria the
   PR structurally cannot prove (e.g. post-merge producer runs that read the workflow from `main`);
   route the genuinely-satisfied criteria to the reviewer for the verdict write-back.

   The write-back seam is `scripts/acceptance_writeback.py` (`apply|writeback|check`): it ticks ONLY
   items a COMMENTED reviewer verdict proved, each tick carrying `(proven: <reviewer> review <id> head
   <sha> run <id>)`. It needs a `--verdict-ref`; there is no self-tick path, and an auto-merged PR with no
   reviewer verdict ticks nothing (an un-reviewed merge stays honest). So make the reviewer's job cheap:
   post a PR comment per delivered criterion with a `proven: (<test_a> && <test_b>) rc=0 head=<sha>` line
   and the one-file mechanism, then DM the reviewer lane. Posting a long markdown body must use
   `gh api repos/<o>/<r>/issues/<n>/comments -F "body=@/path/file.md"` — `--input` expects a JSON
   document and 400s `Problems parsing JSON`, and a bare `-f body=...` with backticks/parens is mangled
   by shell eval. Expect `check-pr-acceptance` to stay red on exactly the genuinely-satisfied criteria
   until that verdict lands — that is the gate working, not a defect, and not something to loop on.

## When acceptance clears but the guard still reds: the stale-base `check-pr-base`

After a reviewer #1644 write-back ticks the last checkable AC (the rest `## Not covered`), a guard
re-run reads `check-pr-acceptance` **OK** — but the SAME re-run may then red `check-pr-base`: "NOT cut
from `origin/main` — its merge-base with ... (measured against `origin/main` at <sha>)". This is the
PR-became-stale class: main advanced (other PRs merged) after the branch was cut from its base, so the
head no longer sits on current main (`gh compare <head>...main` reads `behind=1 diverged`). Re-read the
failing guard LOG, not the badge — acceptance and base are two different steps in the same job, and a
policy that "acceptance is green" papers over the next gate in sequence.

This is NOT a product defect in the fix — route it to `@llgenie-pr-merge-conflict` (the lane that owns
rebases, my lane never does, owner 2026-10-30) with the PR#, both branches, both head shas, the measured
`gh api repos/<o>/<r>/compare/<head>...main` behind count, and the guard re-run run-id. Do NOT rebase it
yourself and do NOT edit the workflow/gate to skip it. The acceptance ticks and `## Not covered` bullets
survive the rebase (they live in the issue body, not the diff), so all the reviewer did stays;
`check-pr-base` clears once the head is re-cut onto current main. Report measured stale-base findings to

## The `check-pr-acceptance-form` gate (#1796) and the `## Not covered` lead-match

Main's `check-pr-acceptance-form` (landed via #1804) requires EVERY bot PR body to carry a `## Acceptance criteria` `- [ ]` checklist (each item a checkbox, one per provable outcome) — a bot PR body without it is red in the scope/guard job (`make check-pr-acceptance-form`). Add 3-4 tickable `- [ ]` items with `proven: <cmd> rc=0 head=<sha>` evidence. This is separate from `check-pr-acceptance` (the linked-issue criteria gate, #1644 verdict-gated). For a linked issue's still-unticked criterion, name it out of scope under `## Not covered` — but `_declared_out_of_scope` requires a bullet LINE that starts with `- ` AND ends with `#<n>` (`.*#\d+$`), and the lead-match is the criterion's first ~3 normalized words with a COLON producing a double space in the NC normalize — so `- No regression: the ...` never matches criterion `No regression: the ...`; write `- No regression the ...`. Verify before pushing with `python3 scripts/check_pr_hygiene.py acceptance-form --head HEAD --base origin/main --body-file <body>` and by calling `_declared_out_of_scope(body, <criterion text>)`, then re-run the wire scope `gh run rerun <fail-run> --failed` to read the true verdict (a body PATCH is live-read per #1589, so rerun picks it up).
the planner too.

Verify BEFORE pushing, or the scope/guard job eats a lap: `python3 scripts/check_docs.py check
--base <main>` ok, `python3 scripts/changes_index.py check` ok, `python3 scripts/check_openspec_tasks.py
<name>` ok (all tasks checked), `python3 scripts/check_pr_hygiene.py openspec-change --head HEAD --base
<main> --body-file <body>` => `OK: ... its own OpenSpec change`, and `python3 scripts/check_pr_acceptance.py
check --body-file <body> --repo asimov-agent/llgenie` reports only the verdict-gated criterion. The
openspec STRUCTURE gate (`make openspec-validate-all`) needs the container image and fails `Error 1` offline
— but `openspec` is an npm CLI, so validate the structure on the HOST without docker:
`npx --yes @fission-ai/openspec@1.10.0 validate --changes` (sweep; read the `N passed, 0 failed` total)
and `npx --yes @fission-ai/openspec@1.10.0 validate <change-name>` (expect `Change '<name>' is valid`).
Use this instead of "rely on the wire" when docker is down — it runs the same check the `linux/openspec`
CI job runs.

## Rules that keep it honest

- **The gate proves a note EXISTS; it never proves the note is ACCURATE. A change-note that mis-describes
  the PR's own behaviour is a documentation defect of the same weight as a red.** When a pipeline-fix PR
  makes more than one behavioural change, the fragment and its `CHANGES.md` row must state EACH of them —
  including a **step REORDER** (a gate swapped to run *before* a sibling, so its verdict is not masked by
  that sibling's self-red; see the SKILL body on ordering a body-form gate first). Measured: a PR moved
  `check-pr-acceptance-form` ahead of `check-pr-acceptance` in `ci.yml` + `scope.yml`, but the note said
  it "runs beside" the sibling — the deliberate BEFORE-order and its reason were undocumented and the
  tree read as if the ordering were incidental. Fix by rewriting the fragment sentence (the ordering, and
  WHY it is order-independent/unweakened), then re-render `CHANGES.md` (next bullet), then amend the one
  atomic commit. A reorder is a real pipeline-behaviour change; leave it out and the gate still passes
  green on a note that lies.
- **Editing an EXISTING fragment (a correction) reds `check-docs` until `CHANGES.md` is re-rendered from
  the fragments again** — the fragment↔`CHANGES.md` agreement is bidirectional, so a hand-edit to one
  side leaves the other asserting the old text. After any fragment edit: `make changes-index` (wraps
  `python3 scripts/changes_index.py write`, prints `wrote CHANGES.md from N fragment(s)`), then
  `make check-docs` (expect the `[check-docs] ok` line) and `python3 scripts/lint_linefeeds.py` — then
  `git add` BOTH the fragment and `CHANGES.md` (they are one change; staging only the fragment pushes a
  half-rendered pair). Verify the corrected text reached the wire branch with
  `git show <new-head>:CHANGES.md | grep -o '<the new phrase>'`.
- A container `check_docs.py check` run with NO base ref prints `change->note skipped (no base ref)` and
green-lights the whole gate WITHOUT exercising the change->note leg. A green there proves nothing for a
diff that touches `scripts/`, `docs/*.md`, workflows, etc. Always re-run the leg with a real base —
`python3 scripts/check_docs.py check --base upstream/main` — before concluding a note is not required.
- The surface set is ADDITIVE — never weaken the gate, never pin an exact file list, never move the
docs gates to `push`/`pull_request` to dodge them.
- A note for a test-only/fixture/rendered change is a filler note, not compliance; the gate already
  exempts `tests/`, `agent-wiki/`, `docs/changes.d/`, `CHANGES.md`.
- **Never conclude "this path is exempt" by grepping the gate for an exclusion pattern — run the leg
  against a real base and read its output.** `check_docs.py` carries per-leg exclusion sets, and a path
  under `agents/<lane>/skills/**` is a behavioural surface even when a nearby regex in the same
  function suggests otherwise; the base-relative run is the only verdict. Reasoning from the source
  produced a commit message asserting "no note required" that the gate then redded on the committed tree.
- When you add the note pair *after* the commit already exists, **amend the message and the PR body in
  the same amend** — a `Technical:` line saying no note was required is a false record of the gate's
  behaviour, and the next reader trusts it over the diff.
- Add the note in the same commit as the behaviour; a follow-up commit that adds it after CI already
  reddened is just the red passing and the fix — the gate wants the pair on the diff.
- When a branch predates the gate, the remedy is REBASE onto current main + note, never a rerun of the
  old green branch (a rerun replays the stale base and stays red).
