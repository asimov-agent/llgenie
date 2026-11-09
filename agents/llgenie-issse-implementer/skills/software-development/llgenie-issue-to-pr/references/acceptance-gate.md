# `check-pr-acceptance` reds — proving a criterion vs. `## Not covered`

A `guard`/`scope`/`ci-verdict` FAILURE driven by `check-pr-acceptance` is **not a code defect**.
It is the acceptance gate reporting one unticked criterion of the driving issue. Do not treat it as
something to "fix" in the code, and do not re-rebase or rewrite the branch hunting for a fix.

The gate names exactly two resolution paths:

1. **Prove the criterion** with a green run, then let the **reviewer** tick it via
   `acceptance_writeback`. The write-back is **verdict-gated (#1644) — you never self-tick** your own
   PR's acceptance criterion. Your job is to produce the proving run at the CURRENT head, confirm it
   concludes green (read every job/cell, not just the top-level `conclusion`), and hand it to the
   reviewer.
2. **Name the criterion out of scope** under a `## Not covered` heading with a **linked work item**
   (the item that will cover it).

When the criterion IS the PR's own deliverable (e.g. "the default `make engine-build` sweep is green"),
only **path 1 is honest** — never "not covered" your own deliverable just to clear the gate.

## Producing the run a verdict-gated AC names — dispatch it yourself, by workflow ID

Many verdict-gated ACs are written so that the EVIDENCE IS THE DELIVERABLE: "engine-build vllm
arch=rocm **push=false** is green (run id recorded, head sha bound)". No prior run satisfies this — the
criterion wants a run at the CURRENT head, so dispatching it is your job, not something to bounce to the
reviewer. "Verdict-gated" governs who TICKS the box (#1644), not who produces the run.

Dispatch a `workflow_dispatch`-only producer:

    # 1. resolve the workflow ID — NOT its name
    gh workflow list --repo asimov-agent/llgenie --all --json name,id \
      --jq '.[]|select(.name|test("engine-build";"i"))|{id,name}'
    # 2. dispatch at the BRANCH (not a PR ref), one --field PER input
    gh workflow run <id> --repo asimov-agent/llgenie \
      --field engine=vllm --field arch=rocm --field push=false \
      --ref fix/<branch>
    # 3. bind the run to the head and read it back
    gh run list --repo asimov-agent/llgenie --workflow <id> --limit 3 \
      --json headSha,status,databaseId --jq '.[]|{head:.headSha[:9],status,run:.databaseId}'

- **`gh workflow run <name>` fails** when the workflow's `name:` is long or carries an em dash
  (`engine-build — builds and verifies EVERY …`) → `could not find any workflows named engine-build`.
  Always dispatch by the numeric ID from `gh workflow list --json id`.
- **`--field` takes exactly ONE value** — one `--field` per input. Passing two inputs into one
  `--field` (or an array spliced as positionals) is silently rejected with no run created.
- A `push=false` build-and-verify witness runs in its OWN concurrency group and does not queue behind a
  stuck `push` anchor (see terminal-and-guard-pitfalls.md). A duplicate dispatch at the same head simply
  supersedes/serialises — check `gh run list` for an already-`in_progress` run of the same cell before
  firing a second one.
- A run that is still `in_progress`, or one at a head the branch has since moved past, is NOT the
  witness the criterion asks for — dispatch at the pushed head and report the run id + head sha once it
  `concluded`. Then hand it to the reviewer to tick.

## Consequences for the lane

- A run that is `in_progress` is **not a failure**. Wait for `conclusion`, then enumerate jobs
  (`gh run view <id> --json jobs`) and check each engine cell — a heavy 25-cell matrix takes a long
  time; a red/green claim before completion is a guess. A synchronous foreground poll loop
  (`for i in …; gh run list; sleep`) burns wall-clock and can time out on the terminal while the
  matrix is still running — instead launch the wait as a **background** process that notifies on exit:
  `gh run watch <run> --repo asimov-agent/llgenie --interval 30 --exit-status` with `background=true`
  and `notify=true`, then do other work and act on the completion notification. Never re-report green
  off a ceiling the loop didn't reach; a poll that ends `in_progress` proves nothing.
- While the proving run is pending, the gate stays red by design. That is the correct, expected
  state — there is nothing to push. Report "AC<n> waiting on sweep <run> at head <sha>" and let it
  conclude.
- Once green, the reviewer ticks the criterion; all gates clear together. If you are blocked because
  no reviewer is picking it up, escalate to the planner / owner — do not self-tick.

Seen on #1837 (AC4 of #1836: default `make engine-build` sweep green with vllm cpu-only): the sole red
was `check-pr-acceptance`, branch already rebased onto live main and code verified correct — the red
cleared only when the sweep concluded green and the reviewer ticked AC4.

## A `--proven` TICK must carry a REPLAYABLE annotation (#745), not a prose pointer

A ticked criterion is only as honest as the annotation behind it. The gate parses the tick's
`(proven: …)` tail and requires it to name a **replayable** thing — a CI run (`run=<id>`) or a
reproducible `command rc=<n> <sha>` — so a re-measurer repeats one command, not a whole byte-compare.
A tick whose annotation is prose, e.g. `(proven: reviewer verdict #PR @ <sha>)`, **reds the gate** even
though the criterion is genuinely proven: the failure line reads
`is \`- [x]\` but its \`(proven: …)\` names no CI run and no reproducible \`command + rc=<n> + <sha>\``.

- You cannot self-tick (#1644), so you cannot fix the annotation yourself — but when you **re-dispatch
the reviewer** to tick, state the required shape explicitly, e.g.
`(proven: gh api actions/jobs/<job>/logs | grep -c '<error-string>' rc=0 run=<run> head=<sha>)`.
Handing the reviewer the exact command + expected rc → a one-command reproduction → the tick lands
clean first time instead of cycling.
- The reference log/run you cite in the annotation must be the SAME one the AC text cites and the one
whose log you actually read — a tick naming run X while the AC text names run Y is a rejection even if
both are green elsewhere.
- Do not "fix" a wrongly-shaped tick by editing the AC text or the body — the tick is verdict-gated
metadata owned by the reviewer; correct it at the source (re-dispatch) or leave the un-tick to the
reviewer's call.

## Exemption-bullet FORMAT — the gate is a regex, not a reader

The `## Not covered` path is matched mechanically, and getting the bullet shape wrong silently keeps
the criterion a violation (or, worse, an edit that looks like it adds the exemption REMOVES it):

- **The bullet must END with the bare `#NNN`.** The matcher is `^-.*\s*#\d+\s*$` — anything after the
  issue number (e.g. `#1888 (OPEN, filed today)`, a trailing sentence) breaks the match and the
  criterion stays flagged. Put every note BEFORE the number; the line's last token is `#NNN`.
- **The bullet must START with the criterion's first-3-normalized-words.** The gate maps a bullet to
  an AC by normalizing the criterion's opening words; a bullet that doesn't open the same way never
  attaches to that AC. Copy the criterion's opening words, then `→ … #NNN`.
- **One bullet may name SEVERAL work items; nest the extras so the TOP line still ends bare.** A single
  AC blocked by several distinct defects still gets one exemption bullet: carry the extra items as
  nested `- ` sub-bullets underneath (or inline before the number), and make the LAST token of the
  outermost bullet line the final `#NNN`. A sub-bullet's own trailing prose is harmless — only the
  top-level line is matched — but a closing `)` or parenthetical after the top line's number is not.
- **A run-on paragraph that *contains* the link does NOT count — it must be a `- ` bullet inside the
  `## Not covered` section, alongside its siblings.**

Never rewrite an exemption bullet without re-running the checker afterward: a well-meaning "clarifying"
tail after `#NNN` regresses a passing exemption to a violation.

## AC shape: "the failure … is attributed to a named stage, with the log line quoted in a comment on this issue"

Some ACs require EVIDENCE, not a code change: name the failing job/run, name the stage, and quote the
actual failing log line. This shape is proven only when all of it is real on the wire, and the reviewer
WILL reject it (measured, not formal) otherwise:

- **Cite the ACTUAL failing job/run, verified via the API — never a guessed or cancelled one.**
  `gh api repos/<o>/<r>/actions/jobs/<job>/logs` for the log; confirm the job is the failing cell, not a
  skipped/`cancelled` sibling (`gh run view <run> --json jobs`). A cancelled-with-tensorfold-job run is
  not the default-sweep failure; a scanner-images/skipped job is not the engine failure. A stale run
  sha in the AC text is a rejection even if a correct one exists elsewhere.
- **The log line must be REAL QUOTED TEXT in a COMMENT ON THE ISSUE — not the PR body, not a
  `@/tmp/...` path marker.** The AC says "a comment on this issue"; a comment whose body is
  `@/tmp/evidence.md` (or a bare path) is the `-f body=@file` literal trap again — it counts as no
  evidence. Post via `-f body="$(cat /tmp/x.md)"` and READ THE COMMENT BACK (`.body|length`, contains
  the error string); a 17–25 byte body is a marker, not a proof.
- De-marker old comments too: a superseded comment still carrying `@/tmp/...` will be re-found by the
  reviewer's "no quoted log line in any comment" check — PATCH it to a real snippet, don't leave it.

## Pre-check the gate locally instead of waiting for CI

Predict the acceptance verdict against the LIVE PR body + LIVE issue before pushing:

```
gh pr view <n> --repo asimov-agent/llgenie --json body --jq .body > /tmp/body.md
python3 scripts/check_pr_acceptance.py check --body-file /tmp/body.md --repo asimov-agent/llgenie
```

It prints `N violation(s)` naming the exact unticked ACs. Target: the number is the ACs you knowingly
left for the reviewer's `--proven` tick (path 1), and NO AC you intended to exempt. Run this after any
body edit; do not trust "the body looks right".

Then **confirm the exemption on the pipeline, not only locally** — the CI gate is the authority and it
re-judges the body from the PR's live metadata. After the push that carries the body/tree change, read
the `guard` job's OWN log at the new head and quote its lines:

```
gh run view <run> --json jobs --jq '.jobs[]|select(.conclusion=="failure")|{name,id}'
gh api repos/<o>/<r>/actions/jobs/<job-id>/logs --allow-escape-sequences | sed 's/\x1b\[[0-9;]*m//g'
```

A remediation is proven when that log's `[check-pr-acceptance] N violation(s)` names ONLY the ACs you
left for the reviewer's tick. Beware that a body-only edit produces no new run until something pushes —
a stale `N violation(s)` from an older head is not a verdict on the current body.

### A reviewer's AC TICK is an ISSUE-body edit — the guard stays STALE until you `gh run rerun` it

When the reviewer lands a `--proven` write-back it edits the **ISSUE** body (`- [ ]` → `- [x]` with the
`(proven: …)` tail). An issue-body edit triggers NO CI event — no push, no PR sync — so the guard/scope/
ci-verdict rows keep the PRE-tick `failure` from the last push, indefinitely. The gate re-reads the live
issue body at run time, so the tick WOULD clear it — but nothing re-runs to notice. Symptom: the reviewer
says "ticked, this clears guard" while `gh pr checks` still shows guard/scope/ci-verdict `FAILURE`, and
the failing log's `[check-pr-acceptance]` line is timestamped BEFORE the tick. Do NOT read that stale red
as "the tick didn't work" and do NOT push a no-op commit to force a wave — re-run the existing runs AT
the same head:
```
gh run rerun <guard-run-id> --repo <o>/<r>   # the CI workflow run carrying the guard job
gh run rerun <scope-run-id>  --repo <o>/<r>
```
The re-run re-executes the gate against the CURRENT issue body and the tick takes effect. Verify locally
FIRST (`check_pr_acceptance.py check --body-file <live-pr-body>` against the also-live issue) to predict a
clean `[check-pr-acceptance] OK`; then confirm the re-run's guard log shows it. A re-run that STILL reds
once the acceptance line reads OK means the residual red is a DIFFERENT gate (e.g. `check-pr-base` base
drift) — that one is not this lane's to force-fix (see pr-close-mismatch-recovery.md).

**Read the PR run's guard job, not a branch-push run.** A `gh run list --branch <b>` mixes two event
kinds: the `pull_request` run (which validates the live body) and `push` runs of the default suite. The
push run's guard job prints `[check-pr-acceptance] no PR body on this run (a push to main): nothing to
validate` — grepping that line as if it were a pass is a false green. Enumerate the failing job, confirm
the run carries a `PR_NUMBER`/`PR_REPO`/`--body-file` step (that marks the PR run), then read ITS log's
`[check-pr-acceptance] N violation(s)` line. If the only failing runs are push runs, the PR run has not
started yet — wait, do not report a verdict.

## A PROVABLE AC is credited off the gate by a replayable body line; a VERDICT-GATED AC is not

Two kinds of unticked AC clear by different paths, and conflating them either wastes a reviewer cycle
or leaves a red you cannot explain:

- **Provable AC** — one whose truth a command reproduces (a test passes, a file has shape X, a flag
  answers). Put its evidence INTO the PR body's `## Acceptance` as a `command → rc=<n> → head=<sha>`
  line. The `check_pr_acceptance.py` checker then stops counting it as a violation — measured as the
  local count dropping 2→1 after the body edit, reproduced by the CI gate at the pushed head. This
  credits the GATE only; the issue's `## Acceptance criteria` checkbox stays reviewer-owned (#1644).
- **Verdict-gated AC** — one whose truth is an external run's outcome ("the default sweep completes
  `success`", "CI is green"). No body line credits it; it stays a violation until that run is green and
  the reviewer ticks it via `acceptance_writeback`. Hand it to the reviewer with the run id + head sha,
  never a self-tick.

So: write replayable evidence into the body for every AC you can reproduce yourself, re-run the local
check to confirm the count drops, and reserve the reviewer handoff for the verdict-gated remainder. A
single residual violation that is a verdict-gated AC is the DESIGNED end state, not a defect to chase.

## "with the run id recorded here" — fill the AC TEXT, never tick the box

Some verdict-gated criteria are phrased so the EVIDENCE ITSELF is the deliverable: "… completes
`success` **with the run id recorded here**." For this shape the AC text is asking you to edit the
criterion line, and that edit is NOT a self-tick (#1644) — editing the text and ticking the box are
two different acts. Supplying the run id in the criterion text is required and allowed; flipping
`- [ ]` to `- [x]` is still the reviewer's verdict.

- Append the run id as a parenthetical TAIL that keeps the line starting with the original criterion
  words and keeps the box UNCHECKED: `… with the run id recorded here.  (run-id fill: engine-build run
  `<id>` at head `<sha>` conclusion=success, `<job>` exit 0, bind-proof #1293 passed — reviewer proves
  then ticks, #1644)`. The trailing clause naming the reviewer makes explicit on-wire that this is a
  fill, not a tick, so the next reader is not confused by evidence on a still-unchecked line.
- The fill does NOT reduce the acceptance-gate violation count — a verdict-gated AC stays a violation
  until the reviewer ticks it. That is expected; the fill's job is to give the reviewer the run id at
the current head so their tick is a one-step act.
- Only fill once the run has actually CONCLUDED at the CURRENT head. A run that is still `in_progress`,
  or one dispatched at a head the branch has since moved past, is not the run the criterion asks for.
- Editing an AC's TEXT to satisfy its own "record X here" wording is distinct from rewriting a bullet
  to fake an exemption or a tick — the former is contract compliance, the latter is the gate-gaming the
  rules above forbid. Do not confuse the two.

## The deferral must also live in the tree, not only the PR body

A verdict that exists only in PR-body metadata is not in the audit trail — the acceptance rollup is the
`agent-wiki/<issue>.md` note (`## Acceptance coverage`) and the `docs/changes.d/` index row, gated by
`make check-docs`. When you defer an AC to a linked work item, record it there too: which AC, why it is
out of scope, the cause, and the tracked item number. Re-run `make check-docs` (it requires every
agent-wiki note to still index) and confirm one clean tree path before committing — that persisted
change is the deliverable, the PR-body prose is the summary of it.

## Sweeping the open board: find the ONE shared blocker before fixing anything

When the owner says "work the open PRs", the efficient first move is one measurement pass, not five
investigations — most boards are blocked by a single mechanism:

1. `gh pr list --repo <o>/<r> --state open --json number,title,isDraft,headRefName,headRefOid,baseRefName,mergeable,mergeStateStatus,reviewDecision,autoMergeRequest`.
   Read `autoMergeRequest` explicitly: an already-armed PR that reads `BLOCKED` is **not** short an arm,
   so re-arming or reporting "needs arming" is wrong. `mergeStateStatus=BLOCKED` with
   `reviewDecision=REVIEW_REQUIRED` on every row means the queue waits on verdicts, not on code.
2. Per head, enumerate the failing rows:
   `gh api repos/<o>/<r>/commits/<sha>/check-runs --jq '[.check_runs[]|select(.conclusion=="failure")|{name,url:.details_url}]'`.
3. Turn a row into a log. **`gh run list --commit <sha>` returns EMPTY** (it filters on the full sha and
   on event shape) — do not conclude "no runs". The `details_url` from step 2 already carries both ids:
   `…/actions/runs/<run>/job/<job>`, so read the job log directly:
   `gh api repos/<o>/<r>/actions/jobs/<job>/logs --allow-escape-sequences` (without that flag the call
   fails with "the response contains terminal escape sequences" and writes 0 bytes — that is not a
   missing log). Strip ANSI with `sed 's/\x1b\[[0-9;]*m//g'` and grep for `##[error]`, `make: ***`,
   `Error [0-9]`.
4. Quote each error line and group by cause. Four PRs commonly share ONE line — `check-pr-acceptance`
   — in which case there is no code work on any of them: hand the reviewer the per-head evidence and
   stop. Only a row quoting a DIFFERENT error (a failing build, a smoke timeout) is real lane work, and
   it belongs to the lane owning that file, not to whoever swept.

Report the sweep as a table of number / head / failing rows / cause, so a shared cause reads as one row
repeated instead of four separate emergencies.
