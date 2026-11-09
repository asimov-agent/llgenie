# Review recipes by PR type (topical depth, loaded on demand)

Moved verbatim out of SKILL.md to keep the always-on body under the 100,000-char cap. Each subsection is a
recipe for one shape of PR; load the relevant one when that shape appears. They are NOT the acceptance
rulebook (that lives in SKILL.md) — they are how to judge a specific diff class without re-deriving it.

### Reviewing a PR that ADDS a workflow file (its own tests pass, the repo-wide convention gates red)

A new `.github/workflows/*.yml` ships with dedicated tests that go green locally while `linux/unit` reds
on the repo's **cross-workflow convention gates**. The PR's own test file is not the acceptance; the
unit leg is. Read the failing job log (see the log-fetch trap) and name each gate, because each is a
different one-line fix:

- **Odd cron minutes (#560).** A scheduled workflow must fire at ODD minutes — `2,32 * * * *` reds
  `test_bot_pipeline_isolation.py::test_every_cron_minute_is_odd` (`GitHub drops even-minute slots`).
  Fix is an odd, collision-free minute (e.g. `3,33`), **and** update the in-PR wiring test that pinned
  the even value — a wiring test asserting the bad cron keeps the defect green locally.
- **Dispatch-forms table.** A new `workflow_dispatch` surface (or a new workflow appended to another
  workflow's roster list) must land in the regenerated `docs/BOTS.md` dispatch table —
  `make check-dispatch-forms report`, commit the row; else `test_dispatch_forms.py` and
  `test_issue_bot_manual_pick.py` (`check-dispatch-forms 1 violation`) both red.
- **Guard byte-identity.** Every guarded workflow's guard step must be byte-identical to the canonical
  guard — `test_workflow_guards.py::test_every_guard_step_is_byte_identical`. A hand-written guard
  missing even one env key (`EVENT`, `GH_TOKEN`, …) is a red.
- **Guard `HEAD_REPO`.** Every guard site must declare
  `HEAD_REPO: ${{ github.event.pull_request.head.repo.full_name || '' }}` —
  `test_every_guard_site_declares_the_head_repo`; without it the guard refuses every bot PR head (#295).
  Copy the whole env set from an existing guarded workflow (`ci-requeue.yml`) rather than writing one.
- **`# proc-allow:` on the opener line** if the helper script calls `subprocess.run(` (see the trap).
- **`check-import-roots` (the import-root ratchet).** A NEW test module that bootstraps its own path —
  a module-level `sys.path.insert(0, str(REPO / "scripts"))` plus a bare `import <scripts_module>` — is
  refused at once: the baseline records the existing offenders and may only fall. The gate names the
  exact sites (`sys-path 35 now vs 34 recorded`, `bare 55 now vs 54 recorded`, then the `file:line`),
  reproduced locally in a head worktree with `python3 scripts/check_import_roots.py ratchet` (rc=1).
  The fix is a one-liner, never a baseline bump: drop the `sys.path.insert`, import through the single
  root as `from scripts import <module> as <alias>` (what `tests/conftest.py` is the only allowed
  bootstrap for), and drop the now-unneeded `# noqa: E402`. A baseline is a measurement — raising it
  to green a new file is the waiver shape.

So the verdict can be **NOT GREEN on the wiring while the logic is sound** — say exactly that ("reaper
logic test-proven 8/8, evidence-before-cancel correct; the workflow fails five repo convention gates")
rather than calling the whole PR wrong, and list each failing test + its one-line fix so the owning
lane can clear them in one push.

**A diff that makes a previously-red path exit 0 (a loud `::warning … SKIP`, a permission-denial
tolerance) is a gate relaxation, not a fix — verify the narrowness in both directions before calling it
green.** Four things must hold: the skip is gated on the event AND the exact permission wording (not
the event alone), the same failure on a push run still fails, a non-permission failure on a
`pull_request` run still fails, and the regression tests drive the literal denial one case per direction
(skip-on-fork, fail-on-push, fail-on-non-permission). The consuming gate on the same path must use
pull-or-build, not a hard pull. Section 10 of `references/gate-auditing.md` carries the full checklist.

### Reviewing a docs-only PR that DOCUMENTS a system (acceptance = the section's own text)

A docs PR whose criteria are "the section names X, Y, Z", "it quotes the measured evidence", "a reader
can rebuild from it alone" is graded by reading the section at the head and grepping for each NAMED
value — not by trusting the body's "satisfies all criteria".

- Extract the section once and grade against it: `git show <head>:<doc> > /tmp/doc.md`, find the heading
  line, `sed -n '<L>,<L+90>p'`, then per criterion grep the literal tokens it demands (mode string, port,
  endpoint/model ids, env-var names, `0600`, the bank template). A criterion whose tokens are ABSENT is
  unticked, whatever the PR body claims.
- "No placeholder" is a grep, not an opinion: search the section for `see the host`, `TODO`, `TBD`,
  `<your`, `varies`, `as appropriate` — zero hits plus every named value literal is the proof.
- Prose-only proofs are not provable ticks: make the ref carry a real gate result you ran at that head
  (`check_docs.py check rc=0 head=<sha>`) so `_is_provable_tick` passes — see
  `writeback-subset-citation-traps.md` §4.
- **A criterion another vehicle must satisfy is left unticked and named, not ticked.** When one criterion
  belongs to a follow-up (an `agents/` pointer on a docs-only vehicle, a fleet-union box), leave it `- [ ]`
  and confirm the PR body's `## Not covered` names it against that follow-up issue — then the gate reads
  `OK` with 6/7 ticked, which is the correct honest state. Declaring it out of scope is the author's act;
  verifying the declaration exists is yours.

### Reviewing a reviewer-pass on named diffs (a subset of a PR, not the acceptance)

A dispatch can hand you **specific diffs** ("verify these two test changes") within a larger PR, rather than the whole PR for acceptance. Judge only what was named, and keep the verdict's scope honest:

- Verify each named diff's **premise against the real files**, not the request's paraphrase: `git show <head>:<the workflow/module it references> | grep -n <the symbol>` to confirm the call site the test asserts actually exists at that head.
- Prove the named tests at the head in a worktree and quote the count (`pytest --noconftest -q <module>` → `34 passed`, both cases among them). A revert-guard test is not proven by passing — say what regression it reds on (the `assert not any(…)` it carries) so "passes" is not confused with "guards".
- **A reviewer-pass verdict is scoped, and says so.** It is `--comment` (or `-a` only if the whole PR's acceptance is met), never a claim about the branch's overall green. If an unrelated leg is red or cancelled at that head (a trailing-newline lint, a mid-run `cancelled` unit), name it as *out of this pass's scope* and attributed to the owning lane — do not fold it into red (accuses innocent diffs) and do not let it block a correct diffs-are-fine verdict.
- **A `cancelled` deciding leg does not convert a scoped "diffs correct" review into a hold.** Report the diffs as validated with local proof, state plainly that full-branch green is NOT established because `<leg>` concluded cancelled (no verdict) and `<other>` is red on the lane's own blocker — the reviewer's job on the named diffs is done; the branch's merge readiness is the owner's. Never read `completed/cancelled` as either green or a fix request.

### Reviewing a hardening fix (a scanner finding: non-root `USER`, dropped capability, tightened path)

A diff that closes a security-scanner finding (`semgrep dockerfile.security.missing-user`, a `RUN as root`,
an over-broad mount) is judged by the **invocation that overrides it**, not by the added line alone. Three
reads settle it:

- The directive is in valid Docker order — `USER` after the `WORKDIR`/`RUN` steps that need root and before
  `CMD`; `git show <head>:<Dockerfile> | grep -nE '^(FROM|RUN|WORKDIR|USER|CMD)'` is the whole check.
- Every write path that now runs unprivileged has an explicit override, proven by grep rather than assumed:
  `git show <head>:Makefile | grep -nE '\-u root|docker run.*root'` — the `OS_OPTS := --rm -u root …` line
  (and the targets that consume it) is what makes a non-root image default safe by construction. If a
  write path has no override, the "hardening" breaks the tool and the verdict is REQUEST_CHANGES naming
  that target.
- The claimed scanner result is reproducible from the change note, and the docs trio (#1123 shape:
  `agent-wiki/<slug>.md` + `docs/changes.d/<slug>.md` + the `CHANGES.md` row) names the issue it closes.

Say explicitly in the verdict that the default-user change touches no gated behaviour because the
invocation pins `-u root` — a reader must not have to take "it is still safe" on trust.

### Reviewing a data-sync / vendor-rehydrate PR (an upstream store split, a fixture regeneration)

A change that vendors a new upstream data file and merges its fields back onto existing rows is judged by
three reads, never by the body's "closes #N":

- **Scope is `base..head`, not `live/main..head`.** A head cut/rebased onto a newer main makes a
  diff against a lagging `live/main` show *already-merged PRs'* files as this PR's work (measured: a clean
  single-commit change read as 18 files / 61 k insertions because the base had moved). Take the base from
  `gh pr view <n> --json baseRefOid` at the head and diff `baseRefOid..head` (or the API `pulls/<n>/files`
  patch); a locally stale `live/main` ref is the usual cause and is never a finding about the branch.
- **The rehydrate is additive-only.** `if counter not in e: e[counter] = p.get(counter, 0)` keeps a
  producer-supplied value authoritative and lets a same-name key upstream win; a merge that assigns
  unconditionally rewrites the store and hides upstream disagreements. Grep the loop and say in the verdict
  which shape it is — additive-only is the acceptance; an overwrite is a REQUEST_CHANGES naming the line.
- **A fixture regeneration that greens a `HubSnapshotMissing` / catalog red must add the REAL recorded
  upstream entry** (the model's HF tree listing, the actual row), never a stub, an empty list or a
  hand-written placeholder: a fabricated entry turns the alarm off and the next real lookup misses in
  exactly the same way. Confirm the added key is the URL the generator looks up at that head
  (`git show <head>:tests/fixtures/<f>.json | grep -i <the model slug>`), then run the snapshot module
  locally and quote `N passed` with the missing-key cases among them.

Fixture churn on these PRs is tens of thousands of lines — read the deltas filtered by symbol
(`git diff <base>..<head> -- tests/fixtures/ | grep -E '^[+-]' | grep -i <slug>`) rather than paging the
whole diff, and check the docs trio names the issue the sync closes.

### Reviewing a skill-admission PR (a new `.hermes/skills/<name>/SKILL.md` + a `HOST_SKILLS` line)

The gate is `scripts/check_agent_skills.py`. It admits a host skill **by name** in `HOST_SKILLS`
(the admission is the name — a leg that preloads it is the alternative), and demands
`REQUIRED_SECTIONS = ('## Inputs', '## Output', '## Rules')` plus frontmatter with a `description`;
prove it at the head with `python3 scripts/check_agent_skills.py report | grep <name>` →
`<name>: host-skill`, and `make check-agent-skills` exit 0. The acceptance tests come in two
directions and both must exist: **name removal → `skill-unused` finding** (the name is the only
admission, so deleting it makes the skill dead weight) and **`## Rules` removal → `skill-section`
finding**. Run the module at the head (`PYTHONPATH="$PWD/scripts:$PWD" python -m pytest --noconftest
-q tests/test_agent_skills.py`) and quote the count, not just "tests pass".

**The gate asserts presence of `## Rules`, never that the rules are stated ONCE — a skill carrying
both `## Rules` and a second `## Hard rules` with overlapping bullets passes green and is the #922
drift class (two texts that drift).** Verify by listing the headings (`git show <head>:<path> | grep
'^## '`) and cross-checking the overlap; report it as a **non-blocking note** (the acceptance is met,
the gate is green), never as a red — and never fold a documentation-quality nit into a
REQUEST_CHANGES. Also check the skill's stated dependency is *named and not restated* (a host skill
that re-documents a `rebase-conflict`-style sibling leg has duplicated the contract it points at).

When the head is green but `-a` is blocked (author == my token), post the verdict as
`gh pr review --comment` and read the review list back with
`gh api repos/<o>/<r>/pulls/<n>/reviews --jq '.[]|{state,user:.user.login,commit_id}'` — confirm
your `COMMENTED` object carries the head `commit_id`, and note any distinct identity's `APPROVED`
already sitting on that head (that one, not yours, is what clears `reviewDecision`).

### Reviewing a pointer/copy PR (a lane skill that only references a procedure living elsewhere)

A "pointer-only" PR adds a reference/link in a lane's own skill to a canonical file authored by "another
PR". The pointer is a **forward reference** and it is only correct if its target exists on the MERGE TREE,
not just on the authoring PR's head. Verify merge-base existence, never the pointer's wording:

- **Prove the target exists at `base`/main, not at the sibling PR head.** `git show <base>:<target path>`
  (expect the file, rc=0) and `git ls-tree -r --name-only <base> | grep -c <basename>` (expect ≥1).
  A target that lives only on the authoring PR's head (`git ls-tree <sibling-head>` hits, `main` = 0) is a
  **dead pointer at the merge base**: merging this PR in first leaves a link to a file that is not there.
- **A conditional AC ("names the canonical reference ON THE MERGED HEAD, after #N merges") is not provable
  until #N is on main.** Check the sibling's real state (`gh api repos/<o>/<r>/pulls/<sibling> --jq
  '{state,merged,merged_at}'`) — `merged:false` / `merged_at:null` means the AC's own prerequisite is unmet;
  do not tick it and do not -a, even when every local gate is green (the per-vehicle half of the AC can be
  green while the merged-head clause is not yet true — say exactly that split in the verdict).
- **A box that names N lanes/vehicles ("each of lane-a, lane-b, … lands X") is a fleet-completion criterion,
  untickable by a single lane's vehicle.** This PR is 1 of N; the box stays `[ ]` until all N land and merge.
  Tick only the narrow claim this PR actually proves; never tick a union box by counting one member.
- **A vehicle that touches `agents/` and ships no `openspec/changes/<slug>/` reds `check-pr-openspec-change`
  by diff shape, not by acceptance.** The gate's docs-only exemption never covers `agents/`, so name it in
  the verdict as a one-line diff-shape finding (the fix is adding the change dir) and keep it separate from
  any unticked AC — a red that is a missing file must not be reported as a criterion the author failed.
- **`closes #<umbrella>` on such a PR keeps `check-pr-acceptance` red BY DESIGN** until the box is honestly
  tickable — a sequencing hold (blocked on the prerequisite merge / the other vehicles), not a diff defect.
  Name the hold as *sequencing*, not a request to change the code, and route the re-evaluation trigger
  (sibling merged → re-read the merged-head clause; more vehicles landed → re-count the union box).

### Reviewing a docs-only audit-record PR (the deliverable is a CLAIM, not code)

A lane publishes an audit (a `agent-wiki/<slug>.md` + `docs/changes.d/<slug>.md` + one `CHANGES.md` row,
~0 deletions) whose acceptance criteria are audit-EXECUTION outcomes ("each open issue X is annotated",
"the ticked-without-run-id count is N", "re-audited at <sha>, no findings"). The diff proves nothing about
whether the audit is true — a record can state `29/29 named` and `14/14 carry a path` with the numbers
entirely fabricated. Judge it by spot-verifying the record's numeric claims against the WIRE, never by the
record's own assertions:

- **Diff vs the merge-base, not the API `base` field.** A docs-only PR whose branch was cut from a pre-main
  sha (or whose API `base_sha` has advanced) shows PHANTOM deletions of another merged PR's product code when
  diffed `api_base..head` — a docs-only change must NOT read as reverting engine/workflow files. Confirm with
  `mb=$(git merge-base <head> refs/remotes/live/main); git diff --stat $mb..<head>` = only the record + fragment
  + index row, and `git diff --name-status $mb..<head> | grep -iE 'engine|delet'` = empty. An engine deletion
  in a non-engine audit diff is the diff-base false alarm, not a regression.
- **Spot-verify the counts, don't trust the table.** For a "last N merged PRs, M/M ticks named" claim, sample
  a handful of the linked issues and count on-wire: `gh api issues/<iss> --jq .body | grep -cE '\- \[x\]'` vs
  `grep -cE '\(proven:'` — they must match the record's `ticks/named` per row. A "14/14 carry an executable
  path" claim → spot-check the issues still exist with the expected labels (`gh api issues/<n> --jq
  '{state,labels:[.labels[].name]}'`). Matching samples from different rows make the whole table credible.
- **Verify an "I annotated the bare thread #N in comment <id>" claim by fetching that comment.** The audit's
  one genuine gap is only closed if the annotation is ON-WIRE: `gh api repos/<o>/<r>/issues/comments/<id>
  --jq '{id,lead:(.body|split("\n")|.[0])}'` returns it. A record that names a comment id you cannot fetch has
  not annotated anything.
- **The tick ref names the guard run that graded the docs-only PR**, plus the record path as the anchor:
  `(proven: run=<guard-run-id> (guard success) head=<sha> + record <path> (…) (reviewer verdict #<pr>))`.
  The audit issue's ACs are satisfied by record-exists + annotation-on-wire + spot-verified counts; there is
  no product command+rc to cite, so the named guard run is what makes the tick re-measurable (`_is_provable_
  tick` needs `run=` or `rc=`+sha — see `verdict-ref-must-name-run-or-rc-sha.md`).
- **Residual reds on such a PR are frequently base-drift (`check-pr-base`) or body-hygiene
  (`check-pr-agents-line`) — NOT the acceptance seam.** Read the failing STEP (job `steps[]`), don't assume
  `check-pr-acceptance`; those two clear by the rebase lane (#1015) and a `make bot-preflight` `AGENTS:` line,
  never by a re-run of your write-back. This is the `dispatch-red-attribution-vs-leg-log.md` rule applied to a
docs-only diff.
