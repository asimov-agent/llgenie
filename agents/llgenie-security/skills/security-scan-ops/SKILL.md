---
name: security-scan-ops
description: "Use when the security scan reds, files nothing, or must be proven clean."
version: 2.0.0
author: LLGenie Security Officer
license: MIT
metadata:
  hermes:
    tags: [security, ci, github-actions, llgenie]
    related_skills: [github-workflow-admission, github, containerized-repo-verification]
---

# Keep the llgenie security pipeline reporting

<!-- host-bot-tools:begin -->

## Tools

This lane's chat session is pinned to these Hermes toolsets and no others: `clarify`, `file`, `memory`, `session_search`, `skills`, `terminal`, `todo`.

Skills that stay enabled: `github`, `security-scan-ops`.
Every other installed skill is listed in `skills.disabled`.
The pin is `tests/fixtures/host-bot-capabilities.json` in asimov-agent/llgenie (issue #1038).
<!-- host-bot-tools:end -->

## Role artifact (2026-11-01)

The artifact is the finding on the issue: exposure, sha, and the lane that owns the files. This lane does not write the patch. `message_agent` to `llgenie-planner` with the issue number and the sha.

## When to Use

Any task on `asimov-agent/llgenie` in the security lane: the daily scan is red, no issues were filed, no
bump PR appeared, a finding will not clear, a PR carries a security hold, the open security issues need a
review pass, or this lane's behaviour/SOUL and its branches must be reconciled. Repo:
`$HOME/repository/git/llgenie` (`origin` = asimov-agent/llgenie, `fork` = andyholst/llgenie;
`gh` auth = andyholst, permission `write`).

## The pipeline contract

`security-scan.yml` is its OWN pipeline — `schedule` 04:05 UTC + `workflow_dispatch` only, never a
`push`/`pull_request` check. Flow: guard → `make check-security-scan` → `make security-scan-all` →
`make security-verdict EVENT=…` → `make security-issues` → `make security-bumps` → SARIF + artifact.
Scanners run from pinned images in `containers/scanners/digests.json`. Policy is data:
`data/security-policy.json` (`fail_on`, `issue_severities`, `enforce_events`, `require_fix`).
Downstream: `security-bot.yml` picks ONE issue per run by LABEL and opens a reviewable PR.

## Audit in four commands

```bash
cd "$HOME/repository/git/llgenie" && git fetch origin && git log --oneline -1 origin/main
gh run list --repo asimov-agent/llgenie --workflow security-scan.yml --limit 10 \
  --json createdAt,status,conclusion,event --jq '.[]|"\(.createdAt[0:16]) \(.status)/\(.conclusion) \(.event)"'
RID=$(gh run list --repo asimov-agent/llgenie --workflow security-scan.yml --event schedule --limit 1 --json databaseId --jq '.[0].databaseId')
gh run view "$RID" --repo asimov-agent/llgenie --json jobs \
  --jq '.jobs[]|.name as $j|.steps[]|"\($j) :: \(.name) => \(.conclusion)"'
```

A red run whose FIRST failure is `security-verdict` means the reporting steps never ran (see
"Failure modes" #1). A red run whose LAST step failed is the intended red: findings were filed.

## Failure modes and their fixes

1. **Gate before report.** `security-verdict` exits 1 mid-job, so `security-issues`/`security-bumps`
   never run. Fix: `id: verdict` + `continue-on-error: true`, `if: always() && hashFiles('security-reports/*') != ''`
   on both reporting steps, and a LAST step `if: always() && steps.verdict.outcome == 'failure'` → `exit 1`.
   Never put the verdict's exit code earlier than the reporting steps.
2. **`gh issue create --label` is dropped on the runner.** Issues arrive unlabelled → invisible to
   `security_bot.pick`. Fix: after create, `POST repos/<repo>/issues/<n>/labels` with `-f labels[]=<name>`
   per label, then READ BACK `gh api repos/<repo>/issues/<n>/labels --jq '.[].name'` and `SystemExit` when
   one is missing. Re-label on the update path too. Repair live issues by hand once.

   **A label write can also fail with `HTTP 403: Resource not accessible by personal access token`, not just
   be dropped.** The run's `GITHUB_TOKEN`/PAT lacks `issues:write` scope (or is a fine-grained token without
   the issues permission) on that repo, so `POST .../labels` errors and the step exits non-zero — which, on a
   report-mode run, still reds the whole run (see "Verify with the run's OWN reports"). Same consequence as a
   dropped label (the freshly-created issue is unlabelled → invisible to `security_bot.pick`), different
   mechanism: a schema/read-back fix will not cure it; the run token needs the issues write scope, and until
   that lands, hand-label the created issue and file the scope mismatch as its own pipeline defect. Read the
   exact verbatim error from the step log before choosing the remedy.

   Mind the output shape: the label endpoints return an **array**, so `--jq '[.name]'` dies with
   `expected an object but got: array` even though the write succeeded. Read back with
   `--jq '[.[].name]|join(",")'` (or `.[].name` for one label per line). A jq shape error is not a
   failed write — re-read before re-writing.
3. **A finding that never clears = a committed copy of a generated file.** `trivy fs .` reads every pin in
   the tree, so a stale tracked lockfile gates forever while `security-bumps` says "every floor is already
   satisfied" (it reads `tools/requirements*.txt` only). Check `git ls-files containers/*/requirements*.txt`
   — build-time copies belong in `.gitignore`, and the build should copy `tools/` pins into a `mktemp -d`
   context (as `scripts/ci_images.py::context` does).
4. **`security-bot` skipped its `fix` job.** It fires on `issues: labeled` with
   `github.event.label.name == 'auto-fixable'`; a multi-label POST can land the trigger on another label.
   Dispatch it: `gh workflow run security-bot.yml --repo asimov-agent/llgenie -f dry=false`.
   The 05:09 UTC schedule is the backstop.

## Verify with the run's OWN reports, never by eye

```bash
mkdir -p /tmp/sec && gh run download "$RID" --repo asimov-agent/llgenie --name security-reports --dir /tmp/sec
cp /tmp/sec/* security-reports/            # security-reports/ is gitignored
make security-issues-plan SLUG=asimov-agent/llgenie     # what would be filed (labels + marker)
make security-bumps-plan                               # the floors the findings demand
```

Then prove a fix by dispatching the workflow — no merge needed. Pick `enforce` by what you are proving:

- **`enforce=full`** shows the fix gates in the right place: expect the LAST step red, everything above it green.
- **`enforce=report`** asks "is the finding set gone on `main`": `pr_fail_on` is empty, so the *verdict*
  cannot red, and it hands back a verdict line plus a run id. Use this for a clean-up check so it adds no
  finding red to a board you are trying to prove is clean.

  **`enforce=report` disables the verdict gate, NOT the reporting steps — a report run can still go red.**
  Any step after the verdict that exits non-zero (typically `make security-issues`, e.g. its label-write step
  403ing on the run's token — see Failure modes #2) fails the job and the run concludes `failure` even though
  no finding gated it. So when a report run reds, **read which step failed before calling it a finding signal**:
  a red at `security-issues`/`security-bumps` is a pipeline defect to file (unlabelled findings, invisible to
  `security-bot`), whereas a red at `security-verdict` in `enforce=full` is the intended gate. "Report mode is
  non-gating" is a claim about the verdict, never a promise the whole run is green.

`--ref main` is only meaningful AFTER the fixing PR merged: findings are read from the checked-out tree, so a
pre-merge dispatch re-reports the advisories and proves nothing. Escalate from schedule to dispatch when a
scheduled run's artifact is ambiguous — a dispatch carries a head sha and a run id, a scheduled run ties to
neither. Full detail: `references/scan-verification.md`.

## Issue review pass — auditing the open security issues

"Do the security issues still make sense?" is its own task; the answer is measured against the tree, never
against the issue body (bodies carry stale line numbers and closed-PR references).

1. **Build the roster** — `gh issue list --state open --json number,title,labels`, then read every
   candidate; title/label filters miss cases.
2. **Verify each claim in code** — grep the file and symbol the issue names and say what you found. An issue
   is *valid* only while the mechanism it describes is still in the tree; a stale line number is not
   staleness, a fixed mechanism is.
3. **Verdict per issue, and act on it** — still valid → comment with current line numbers and any constraint
   the fix must carry; mechanism gone → close with the evidence; parent tracker whose children are all closed
   and re-verified → close it and name what you re-checked.
4. **Review the FIX, not only the defect** — an issue can be right about the problem and dangerous in its
   remedy. Checklist: `references/security-issue-review.md`. When another lane proposes a **scanner-suppression
   carve** (inline `# nosemgrep: <check_id>` to silence a triage false-positive class), approve it as a per-site
   carve (rule stays live elsewhere, no policy widening) but re-derive the CURRENT flagged line at the fixing
   head — SARIF line numbers are scan-time and drift onto dead lines, so a suppression placed by quote reds the
   run or carves the wrong line. Demand a two-part guard-prove (0 matches at head AND a planted genuine injection
   still reds), and name the full reported `check_id`.
   Verify placement **from the diff, not the body**: `git diff <base> <head> -- .github/workflows/ |
   grep -A3 '^+.*nosemgrep'` shows each comment directly above its target `run:` line — that pair is
   the ground truth; the body's site table line numbers are usually stale and are not what the scanner
   acts on. Confirm the rule stays live by diff scope, not by inspection: `git diff <base> <head>
   --name-only` must list only the suppressed workflow files (+ docs/CHANGES) and **no**
   `data/security-policy.json`, scanner config, `Makefile`, or digests — an inline carve that also edits
   policy is a weakening. Then check the guard-prove covers both halves (0 at head AND a planted genuine
   injection still reds). When reviewing another lane's carve PR, post the sign-off as a **comment**
   (`gh pr comment <n> --body-file`): `gh pr review <n> --approve` is refused with `Can not approve your
   own pull request` whenever the gh token is the branch/commit author, so an approval review cannot be
   recorded — the comment is the decision record. In particular, when the fix **widens the accept-set
   of a merge-blocking gate** (an identity/allowlist/severity set), review the invariant, not the diff size:
   the commit **address** is the identity and the allowlist of addresses is the only real boundary — a display
   name is not a security control, because GitHub writes a squash commit's author name from the account *profile*,
   a field the commit's author cannot set. So: (a) aliasing the display name of an already-allowlisted address
   adds names, not identities — the trust set is unchanged; (b) a "lookalike address" (allowed name, wrong
   domain-local) must still fail, which is the half of the rule that survives; (c) do NOT "fix" the widening by
   re-adding a name check to the commit path, it reintroduces the squash reds that motivated the change; keep the
   strict name+email pair only on the *producer* path (a workflow a human authors is committer-controlled). A gate
   that accepts "any display name under an allowlisted email" is looser than exact-pair but is NOT an equivalence
   hole, because the address is still allowlisted.

## Trust-boundary audit of the pipeline itself

Audit what runs the scan as well as what it finds — greps and reasoning in
`references/security-issue-review.md`. The three properties to check every time: the scanner image is
addressed by **digest** (a tag can be re-pushed), the scanner mounts the checkout **read-only** (otherwise it
can edit the scripts the later steps execute), and the **write token lives in a different job** from the one
that ran the binary.

A fourth property: the scanner's **rule set** is **pinned**, not a live registry alias — `--config p/default`
re-resolves from the registry on every run and cannot be dumped to a byte-exact file, so a build-time re-pin is
not reproducible while a deterministic ref swap changes rule parity. A vendored pack trips `GH013`
push-protection; clear it only with a path-scoped push-protection allowlist or an owner-activated unblock URL
(no local git flag bypasses it, and encoding the pack to dodge the scan is a weakening). Decision and the
measured mechanism: `references/rule-set-freshness.md`.

## Gates to run before opening the PR

**One PR that closes two duplicate findings needs an adjacent `closes #N` for EACH issue, in the joined commit text AND the PR body.** `scripts/check_pr_closing.py` (make `check-pr-closing`) reads the squash/commit range and the body and requires the same adjacent-close set in both; a duplicate pair (same finding, bodies differing only by the scan-run URL) routed to this lane is closed by one branch whose commit body and PR body each carry `closes #1593` and `closes #1597` on their own lines (keyword adjacent to `#N`, nothing between — `closes #1593, #1597` in prose or a markdown wrapper does not count). Prove it locally before pushing. **The gate scripts' accepted flags DRIFT — read the script's own usage line before believing a red, and never
reuse one script's flags on another.** A remembered flag list is stale the moment the script is edited:
`check_pr_closing.py check` rejected `--base`/`--rev` as `unrecognized arguments` in one version and **accepted
both** (`check --body-file <f> --head <ref> --base <base> --rev <rev>` → OK) in a later one, so do not treat
either behaviour as permanent. `python3 scripts/check_pr_base.py check --base <main-tip> --rev HEAD` asserts the
branch is cut from the base (merge-base == base, no foreign commits). A wrong flag looks like a gate failure
when it is only a usage error — run `python3 scripts/<script>.py check --help` (or read the printed error)
before concluding a gate reds on content. Both scripts are cheap and catch the two most common PR reds on this
lane.

**The bot-PR body must ALSO carry the `AGENTS:` and `BASE:` preflight lines — a docs/record PR reds `scope` at
`check-pr-agents-line` even after `check-pr-closing` passes.** Generate both with `make bot-preflight` (its
stdout is exactly the two lines: `AGENTS: <sha> <bytes>b <lines>l` and `BASE: <sha> (== origin/main at open)`)
and paste them into the PR body beside each other; the gate reds `[check-pr-hygiene] PR body: no BASE: ... line` (or the `AGENTS:` equivalent) when either is missing. `make bot-preflight` ITSELF REFUSES when HEAD has
diverged from `origin/main` — that refusal is the rebase signal, not a bug: `git fetch origin main`, `git
rebase origin/main`, THEN regenerate the preflight lines against the new base and re-push. Because the
`AGENTS:`/`BASE:` sha is the base you are cut from, a rebase invalidates pre-rebase preflight output — always
regenerate after rebasing, and the body you push must be the one you re-ran both gates against.

**A PR that changes `agents/<profile>/**` ALSO reds `guard`+`scope` at `check-pr-sync-line` unless the body
carries a `SYNC:` line for EACH changed profile** — literally `SYNC: <profile> make sync-agent-profile
PROFILE=<profile>`. This is a body/squash-text contract (#1724), NOT a command that must actually run: once
merged the branch tree already equals live, so the declared `make sync-agent-profile` is a forward-looking
no-op a reviewer can verify. Do NOT satisfy it by actually running `make sync-agent-profile` tree→live — that
direction REFUSES when the live profile is ahead of the tree, which is the correct one-way LIVE→TREE invariant
(see the lane-behaviour rule), and running it is a truncation attempt, not a fix. Add the line to the PR body,
then rerun the failed check (`gh run rerun <run-id> --failed`) — a body edit alone does not re-trigger the
push workflows, and the per-check-run rerun endpoint 404s; the run-level rerun's jobs see the CURRENT body
because these gates fetch it live.

**A `ci-verdict` check reporting `red (run <id>)` is a snapshot pinned to that run, not a live verdict — it
recomputes to green only when that run CONCLUDES.** Rerunning the run's failing guard/scope jobs does not
refresh it; letting the run's long job (e.g. `linux / unit`, routinely 10+ min) finish does. So a lone red
`ci-verdict` beside an in-progress unit job is "not recomputed yet", not a defect — do not chase it, do not
edit the workflow, just let the run complete and re-read `gh pr checks <n>`.

**Stage named paths, never `git add -A`, and keep body/message scratch files OUTSIDE the worktree.** A file
written for `--body-file` or a commit message (`commit-body.txt`, a scratch note) is still sitting in the
worktree when the commit is built; `git add -A`/`git add .` sweeps it in, and because the path matches no
`CLASSES` entry in the scope classifier the `scope` gate reads the diff as WIDE and reds while guard, lint,
openspec and holds stay green (a lone `scope` red on a small PR is a stray path before it is a content
problem). Defend cheaply: write scratch files to `/tmp` or the profile scratch dir, stage with
`git add <path> <path>`, confirm with `git status --short` that the staged list is exactly the intended files,
and read back what landed with `git show --stat HEAD`. Evicting a stray file afterwards means amend +
`--force-with-lease` + a fresh CI run over the new sha — the cheapest fix is never staging it.

**A `gh` usage error also impersonates a missing field or a dead command — read the error, do not re-read the
object.** `--json` names are validated against a printed list (`Unknown JSON field: "baseRefName@"` → retry
with only listed fields); and inside `--jq` every field MUST carry a leading dot — a bare identifier parses as a
zero-arg function call and errors `function not defined: headRefOid/0`, which looks like the field does not
exist on the PR. So write `--jq '{head:.headRefOid,base:.baseRefName}'`, never `{head:headRefOid,…}`, and
prefer `--jq '{state,mergeable,head:.headRefOid}'` over hand-slicing (`[0:10]`) when a short sha is wanted —
an abbreviated sha in the report can be taken from `git rev-parse --short` or sliced in `python3`, not fought
in `gh`'s jq.

**A base refresh does NOT invalidate a prior verdict proof when the fixed file is byte-identical across the
rebase — prove it with sha256, do not re-derive it.** When the planner asks to re-anchor a PR onto a moved
`main` tip (base now stale by one or more merges, no overlap with your files), rebase, then prove the earlier
scanner verdict still binds by hashing the fixed artifact at both heads:
`git show <old-head>:<path> | sha256sum` vs `git show <new-head>:<path> | sha256sum` — equal hashes mean the
pinned-scanner evidence (0 at head / control finding pre-fix) carries over unchanged and you state the sha256
in the rebase comment. If `CHANGES.md` is auto-generated and the base move appended fragments, **regenerate it
from the fragment set** (`python3 scripts/changes_index.py write`, expect no residual diff against the committed
file) rather than hand-merging the generated table, then re-run the four gates on the rebased head. Push the
rebased branch with `git fetch origin <branch>` first, then `git push --force-with-lease --force-if-includes
origin <branch>` against that true fetched sha.

**`gh run list` has no `--head` flag** — to find the run(s) for a PR's head sha, use `gh pr checks <n>` (parse
the `runs/<id>` from the details URL) or `gh run list --commit <sha>`; `gh run list --head` errors `unknown flag`.

**`gh pr checks` exits 8 while any check is pending and 1 on a failure — a non-zero exit is not by itself a
red run.** Read the per-check verdict (`--json name,state,bucket`) instead of trusting the exit code, and if
the output is piped through a truncating utility, capture `$?` on the `gh` call itself or the pipe eats it (`cmd | trunc; echo
EC=$?` reports the last pipe element's status). A run that is merely in progress reports pending checks and a rollup field of
`""`; only `bucket=fail` is a red.

**`gh pr checks` is not the run inventory — a `failure` run with ZERO jobs can be a workflow-file issue, and
it can be invisible to the PR view.** Corroborate every rollup with `gh run list --commit <sha>` (or the
check-runs API), never `gh pr checks` alone. A run whose `actions/runs/<id>/jobs` returns `total_count: 0`
failed *before any job dispatched* — but DO NOT attribute it to a specific diff's caller-side evaluation
without a **same-head control that dispatched**. Measured counter-proof: three zero-job "failure" runs across
three heads (incl. the merged one) were NOT a deterministic #1618 evaluation break — at the same head, other
runs dispatched 1 and 2 jobs and SUCCEEDED, and a later PR run dispatched 10; the workflow evaluates fine and
dispatch is *intermittently zero/partial* (the "dispatchability-manifest gate", same class as 41438694895).
The two real mechanisms are distinguished only by control runs at the **same sha**: a deterministic
workflow-file defect refuses the call on every run that carries it (incl. `main` after merge), an intermittent
gate reds some runs and lets peer runs through. When dispatch drops intermittently it is NOT a `.github/workflows/*`
content defect owned by the pipeline lane — do not file it as one and do not patch workflows; report the run id +
sha and the gate. Only a same-sha control (a peer run that dispatched) settles which it is. Full diagnosis:
`references/ci-run-rollup.md`.

**A squash merge is not a descendant of the branch head, and `mergeCommit` is an object.** Prove a merge
landed with `gh pr view <n> --json state,mergedAt,mergeCommit` (`MERGED`) + the issue's `state`, not with
`git merge-base --is-ancestor` (which reds on a correct squash merge) — and read the sha as
`.mergeCommit.oid` (`.mergeCommit[0:10]` errors `expected an array but got: object`). Once merged the
auto= verdict is moot: report `merged (<sha>)`. **After a merge lands, clean only YOUR refs — auto-merge
deletes the REMOTE branch but leaves the local branch and a stale `origin/<branch>` tracking ref:**
`git branch -D <branch>` + `git update-ref -d refs/remotes/origin/<branch>` + `git fetch origin --prune`, then
confirm by branch NAME. Do NOT check for leftovers with `git for-each-ref | grep <issue-number>` — the number
matches sha SUBSTRINGS in unrelated branches (`...b1773...`), which reads as "still there" when your branch is
gone.

```bash
make check-security-scan check-security-issues check-security-bumps check-workflows check-docs check-wiring
docker run --rm --user $(id -u):$(id -g) -v "$PWD":/repo -w /repo -e HOME=/tmp llgenie/test:latest \
  python -m pytest tests/test_security_issues.py tests/test_security_scan.py tests/test_security_bot.py \
    tests/test_issue_body.py tests/test_check_issue_body.py -q -p no:cacheprovider
```

**Never block on a degenerate terminal result from a giant parallel batch.** A single turn that fires ~30+ `terminal` calls returns them in a way that can render as empty/timed-out even though every command ran fine (measured: a mid-run burst of `echo`/`touch`/`git status` calls all executed; the results came back out-of-order and looked like a wedged shell, and the lane posted a `kanban_block` over nothing). If a batch's results look empty, re-probe ONE simple command alone (fresh turn, no parallel siblings) before concluding the backend is down — and never post a block/reason grounded in a batch you misread. Keep terminal batches small; the cheap correctness win is verifying with a single clean call rather than trusting an interleaved dump. The signature is not only emptiness: **one command that fails can make a fan-out of
20+ near-identical probes return the SAME output for all of them**, which reads as a wedged shell when it is
really a replay. Re-run the ONE command that failed, alone, and if it answers, stop probing — do not fan out
variants to "confirm" a tool is healthy, and do not convert a misread batch into a `blocked` handoff before
that single clean call has actually returned.

**A write that "looks failed" is unproven until you read the external artifact — never send a `blocked`/"take the branch" handoff on a failed-looking tool display.** A push/PR that a buried command reported as not-happening may have actually succeeded (output buffered/displayed empty while the command ran); the fact lives in the remote, not in the run's echo. Before telling the planner a push or PR is blocked, re-verify with an INDEPENDENT read of the real state: `git ls-remote origin refs/heads/<branch>`, `gh api repos/<o>/<r>/branches/<branch> --jq .name`, and `gh pr list --repo <o>/<r> --head <branch> --json number,state`. Only a negative on those is evidence of "not done" ("Everything up-to-date" with rc=0 is a real positive). If a hasty pessimistic handoff already went out, send an explicit CORRECTION on the record quoting the API read-back — a false
"blocked, please duplicate the work" message makes the planner take over a branch that is already landed.

**Waiting on CI: set the tool's `timeout` parameter, not a shell `timeout` prefix.** A foreground
`gh run watch <run-id> --exit-status` dies at the tool's default 180s (an inner `timeout 540` prefix does not
raise the tool limit) and the `unit`/`install` jobs routinely run 2–10 min. For anything past ~2 min, launch
run with `background=true, notify_on_complete=true` and reap the exit code, or poll
`gh pr checks <n>` in a bounded loop; a timed-out watch is not a red run. **Once a run reads
`status=completed` (any conclusion), STOP polling it** — one `gh api repos/<o>/<r>/actions/runs/<id> --jq
'{status,conclusion}'` is the fact, and a fan-out of near-identical polls for the same id adds nothing and
burns the turn (measured: ~a dozen identical `gh api .../runs/<id>` probes after the run had already read
`completed/success`). If a probe renders empty, that is the degenerate-batch artifact, not an unfinished run —
re-read once, alone.

Local `python3` has no pytest — always use the `llgenie/test:latest` image (pulled/built by `make
test-image`). A `make sbom && make security-scan TOOL=trivy` run locally (pinned images via docker) plus
`python3 scripts/security_scan.py verdict --event schedule` is the cheapest real proof a finding set is gone.

**Prove a single-file finding closes by running the repo's OWN pinned scanner image on the file — with a
control pair — not by asserting the fix.** For a Dockerfile/`# nosemgrep` finding, the verdict evidence a
reviewer can re-check is the exact CI invocation against the fixed head vs the pre-fix tree, both on the
same digest-pinned image (`python3 scripts/security_scan.py ref semgrep` prints it; the CI form is
`scan --config=p/default --json --metrics off <path>`). Copy each Dockerfile to a temp dir (a *real
filename* `Dockerfile`, not a bare copy — semgrep refuses `fixed-Dockerfile` as an invalid scanning root),
`docker run --rm -v <dir>:/work -w /work -e HOME=/tmp <pinned-image> scan --config=p/default --json
--metrics off .`, and parse `json.load(...)['results']`. Expect **0 findings on fixed / the exact
`check_id` on orig** at the finding's line — that pair is what proves the carve is real and not a
suppression/widening. A lone "fixed head is clean" run carries no control and could equally mean the scan
never ran; the pre-fix match is the half that proves it. Mount a temp dir, not a worktree; the scanner
writes no report, so nothing needs cleanup beyond `rm -rf` the temp dir.

**A local `docker build` red is not your diff's red until you prove the failing step PRECEDES your
change, and the CI image gates are the authoritative build proof.** When `make test-variant-image` /
`docker build` fails at a `RUN pip install`, do not assume the hardening broke it: check
`git diff origin/main --stat` (does your branch touch `tools/requirements*.txt`?) and
`git log origin/main -- tools/requirements*.txt` — a committed pin (e.g. an `filelock==X` unsatisfiable
on the base image's older python) is pre-existing and fails identically without your diff. Point at the
PR's own `ci-images` + `scanner-images` PASS (they build in the repo's real environment) as the build
proof, and state the pre-existing break honestly on the issue rather than treating it as introduced by
your change. **A `missing-user` Dockerfile finding on a build-only image is closed by a trailing
non-root `USER` after the last root-requiring step — but first prove the image is never `RUN` in any
workflow or target** (`grep -rn '<image-tag>|<make-target>' .github/workflows/ Makefile`; if `CMD`
writes nothing, e.g. `--help`, the drop is safe) and use a reserved non-root UID already precedent
(`USER 65532:65532`, the scanner image's) so the choice is not arbitrary.

**A change-note fragment reds `scope`/`check-docs` unless it matches the parser's shape.** The fragment is
parsed by `scripts/changes_index.py`: it must be **exactly one row**, and its note column must point at an
`agent-wiki/<stem>.md` work record **that exists in the tree** — a multi-row fragment, or a note column naming
anything other than an in-tree `agent-wiki/*.md`, reds `scope` in ~15s while `lint`, `openspec`, `guard` and
`holds` stay green (so a lone `scope` failure on a docs/`agents/**` PR is the fragment schema, not the content).
Validate locally before pushing: `python3 scripts/changes_index.py` (expect every fragment indexed) and re-run
the exact `make check-docs` the gate calls.

**When the diff touches `agents/**/*.md` (SOUL, skills, references), also run `make lint`** — it carries
`scripts/lint_linefeeds.py`, which reds a markdown heading not preceded by a blank line. A section spliced
directly above the canonical fleet-rules heading drops that blank line and reds the whole tree gate while
every other check passes; insert a blank line before each heading and re-run `make lint` (expect
`LINT OK`), not just `make check-agent-profiles`. The same script also reds any tracked text file with **no
trailing newline** (it is not limited to `agents/**`); ground-truth the final byte with `tail -c 4 | od -c`
rather than trusting `read_file`/editor rendering, and check whether `main` already broke it before attributing
the red to your diff — if it did, a one-byte restore is a documented drive-by, not scope creep.

## Standing rules for this lane

- **Verify a dispatch's premise against the tree before implementing it, and never re-implement shipped work.**
  A dispatch body is written at some past sha and goes obsolete: when it claims an architecture is missing
  ("0 scanners, no renovate config, no pinned Actions"), check the children (`gh issue list --state all`) and
  grep the tree for each named artifact at the CURRENT `origin/main` before cutting a branch. If the children
  are all CLOSED and the artifacts are present, the deliverable is a **completion-audit record on the parent
  tracker** (an `agent-wiki` note + one fragment + PR whose body carries `closes #N`), not a second
  implementation — re-building merged work duplicates it and re-violates the no-PR-gate contract. Say so on the
  tracker with the merged shas and the gates you re-verified, then close it through the PR's own closing keyword
  so the close and its evidence are the same artifact.

- **Every reply opens with a status line** — in force whether or not a turn was dispatched:
  `BOT <name> · working on #<id> · branch <ref> · since <hh:mmZ> · blocked on <x|none> · next <y>`.
  Say it first when working something nobody dispatched, and use `no issue dispatched · idle` when
  stopped. A report without an id or a branch is not a report.
- **Act, then report — do not ask.** The standing directive for this repo is that approval is not needed:
  open the issue, push the branch, open the PR and let the repo's own auto-merge land it. Never end a turn
  on "want me to…?"; end it on what you did and what the runs said. Do not merge by hand unless asked.
- **Never open a draft PR.** Open ready-for-review; if one is somehow draft, `gh pr ready` before reporting.
  A draft is invisible to the merge queue, to auto-merge and to every reviewer — and for this lane worse
  than invisible: an advisory opened as a draft is an exposure that stays open while the board reads
  "blocked on approvals".
- **A PR whose rebase leaves nothing is a duplicate — close it, do not leave it on the board.** After a
  rebase onto a moved base, `git log <new-base>..HEAD` empty (0 unique commits) with a message like
  "patch contents already upstream" means the change already landed in the base. Close the PR as
  superseded and name that empty-diff as the evidence; an OPEN, not-armed PR whose content is already
  merged elsewhere reads on the board like it is blocked for a reason that does not exist.
- **Arm auto-merge only on a `main`-based PR, and read BOTH arm signals before claiming `armed` or `none`.**
  On a PR whose base is another branch, `gh pr merge <n> --squash --auto` does not arm — it **merges within
  seconds** into that branch, because there are no protected-branch rules to wait for (#964). So a stacked PR
  is reported `auto=none (stacked base: arms into <base>)` and the flag is never passed. On a `main`-based PR,
  a lone REST null is **NOT** proof of "not armed": the REST `pulls/<n>.auto_merge` object is a projection that
  *omits* `enabled_at` while the PR is blocked on a required review, so it reads `NULL` for a PR that is
  genuinely armed and will merge the moment the owner approves. Read **both** signals:
  `gh api repos/<o>/<r>/pulls/<n> --jq '.auto_merge.enabled_at // "NULL"'` (REST) **and**
  `gh pr view <n> --json autoMergeRequest --jq '.autoMergeRequest.enabledAt // "NULL"'` (GraphQL request
  identity). Declare `auto=armed` if **either** is non-null; declare `auto=none` only when **both** are null.
  On a true disagreement (REST null, GraphQL set) **default to armed and dis-arm** (`gh pr merge <n> --cancel`),
  read both back null, then report `auto=none` — never report `auto=none` on a lone REST null (measured: an arm
  showed REST `enabled_at` NULL the same second GraphQL `enabledAt` was set, and the PR merged two minutes
  later; the lane had reported it "inert", a false negative whose dis-arm came too late). **Do NOT assume a
  merge clears the signals or that either field is the state on a merged PR.** Measured: a PR merged while
  GraphQL `autoMergeRequest.enabledAt` STILL read the pre-merge request stamp (the gh client keeps the
  request-identity projection after merge) even though REST `.auto_merge.enabled_at` was NULL because the PR
  was closed — so a merged PR routinely shows a REST-null / GraphQL-set split, and quoting either alone
  contradicts the other. The operative fact is **`state` + `merge_commit_sha`**, read first: `gh pr view <n>
  --json state,mergedAt,mergedBy,mergeCommit` and `gh api repos/<o>/<r>/pulls/<n> --jq
  '{state,merged_at,merge_commit_sha}'`. A merged PR is `merged`, never `armed` — report it as merged and name
  both arm fields only as context (the stamp was mooted by the merge), never as "still armed" and never as
  "NULL so inert". `--cancel` on a merged PR is moot. Reserve `auto=armed` / `auto=none` verdicts for an
  OPEN PR; once merged, the verdict is `merged (bf44197d)` and the read-back of an arm is a historical detail.
- **Never hold a PR without a remedy.** `do-not-merge` means "a concrete defect with a tracked fix". If
  this lane places one, the same comment names the issue that makes the tag removable and the exact
  condition for removal, and the lane removes the tag itself when that evidence exists. Detail:
  `references/holds-and-publishing.md`.
- **A red bot-gate reads the failing job's OWN log before anything else — this skill surface points at the canonical sequence (#1791-AC3).** On any red gate, before reporting green/red/reviewable/mergeable or routing "another lane's drift", load `references/read-the-failing-job-log-pointer.md` (it names the canonical implementer procedure), follow its mandatory sequence: name the run + head, find the failing job, read that job's OWN log verbatim, attribute the root cause to that gate via the gate→defect map, and report green only off a completed run id + head sha with no `linux/*`/guard/scope row `in_progress`/`cancelled`. The security-scan-specific twist ("red" at the verdict is the intended filing red, not a defect; `enforce=report` disables the verdict gate not the reporting steps; a stale `ci-verdict` recomputes only when its run concludes) is in `references/scan-verification.md` + `references/ci-run-rollup.md`.
- **Read an issue's state before quoting it as open/closed — a finding you report as "still open" without a fresh re-read is a false board claim.** The completion guard and the planner have both caught this lane reciting stale "both open" phrasing for #1652/#1661 after their fix-merge closed them hours earlier; a board claim about today's state must be measured today, never restated from a session summary, a compaction snapshot, or "what we said last time". The league standard: `gh issue view <n> --json state,stateReason,closedAt,labels` FOR the issue before it appears in a report, and when the state differs from what you last held, post the correction on the issue naming the merged sha + the re-measure, quote `closed_at`, and say the earlier phrasing is superseded. The durable source of the stale line is the compacted-context Active-State/Blocked snapshot — after correcting on-record, no future report may cite the old phrasing.
- **Every finding names the sha it scanned and the command that produced it.** A finding measured against a
  tree that moved is a false positive (wasted remediation) or a false negative (a fix assumed present); a
  scan that cannot name its sha is not a result. Start from a freshly fetched `origin/main`
  (`asimov-agent/llgenie` is upstream — a fork named `origin` is not, and a sha quoted in chat is stale by the
  time you read it), write that sha into the first comment, and **bookend**: a START comment (issue/PR id,
  branch, main sha, what "done" means) and a FINISH comment (head sha, what changed, the command or run id
  that proves it, what is left open). A start with no finish is an abandoned claim; a finish with no start has
  no baseline. Report both lines to the planner.
- **A scan result nobody can see is not a finding.** Publish on the issue with the sha it was measured at;
  sensitive detail goes to the private channel first, but the existence and the reference stay traceable.
  An overlap with another lane is a message carrying the scanned sha before it is a filing.
  Detail: `references/holds-and-publishing.md`.
- **A merged fix is not a clean scan — report absence, not silence.** "Clean" may only be claimed by a run
  that scanned a named sha and printed `0 finding(s)`. An issue whose fix merged but whose scan has not run
  since is **"fix merged, absence unproven"**: the `cleared` path that closes it needs a scan to execute, so
  open findings with a merged fix are a scan gap, not a failed fix. When the workflow is
  `disabled_manually`, say so with a measured gap — compute it from the last run's timestamp in a command,
  never eyeball it (an eyeballed gap understates an exposure by a day or more and changes how urgently it
  escalates) — name the open findings including any `critical`, and hand over the exact re-enable proof you
  will run (a report-only dispatch that cannot red). While the workflow is off you can still prove the *tree*
  clean at a named sha without it: `git worktree add <tmp> <sha>` then `make sbom && make security-scan
  TOOL=trivy` and `python3 scripts/security_scan.py verdict --event schedule` — expect `0 finding(s) recorded`
  — and quote that line plus the sha in the issue comment. But a tree-local scan is evidence for the comment,
  NOT the `cleared` close path: the finding still needs the workflow's run id to close, so leave it OPEN and
  never close a merged-fix finding by hand. A silent security lane and a scanned-clean one look identical
  from outside; only the run id tells them apart.

- **Never restate a finding's OPEN/CLOSED state from memory — re-read the tracker first, and prove a close by
  the mechanism being ABSENT from the current tree.** A finding's state moves under you the moment a fix PR
  merges: a squash body carrying `closes #N` closes the issue even while the implementer keeps working past
  that moment, so any report that repeats an earlier "both OPEN" without a fresh read is a false claim about
  time, not about the tree (measured: a lane re-stated two findings as OPEN for hours after the merged fix had
  closed both, and the completion-integrity check was right to reject until it re-measured). Measure per
  finding: `gh issue view <n> --json state,stateReason,closedAt`, then find the closing vehicle
  (`gh api 'search/issues?q=repo:<o>/<r>+is:pr+is:merged+"<n>"'` → the merged PR whose title carries
  `closes #N`). Then verify the close is **legitimate, not premature**, by checking the named mechanism is
  gone from the CURRENT tree — `git grep -n '<the pin/symbol the finding names>' origin/main` returning only
  docs/`agent-wiki` records and no live manifest means the exposure is gone (a host-level red from
  `make check-engine-launchers CHECK_REGISTRY=1` such as "NOT PUBLISHED" / "stale launcher" is launcher-tag
  staleness on THAT host, not a committed-tree ref — do not read it as the finding still live when the pins are
  absent from the tree). A premature close (mechanism still in the tree) is reopened with the fresh gate; a
  legitimate close is corrected on-record with the merged sha + the tree measurement, superseding the stale
  phrasing.
- **A deliberate weakening is never the fix.** No allowlist entry, no widened severity set, no
  `require_fix: false`, no emptied `fail_on` to turn a run green.
- **Report scope, not remediation-by-patch.** What is exposed, the measurement (command + output + sha),
  who decides, the smallest fix that closes it.
- **A scope-only claim still needs a vehicle — dispatch it, do not let it sit.** When this lane verifies a
  finding live and writes the acceptance criteria, it has scoped the fix but not owned it: the patch belongs to
  the implementer queue. A finding that is claimed-and-scoped with **no** PR, no `agent/issue-<n>-*` branch and
  no `agent:implement` label is blocked on dispatch, not unclaimed — say exactly that to the planner (state,
  verify sha, the acceptance, and `Vehicle: NONE / Blocked on: dispatch`), then apply `agent:implement` and
  **read the labels back** (`gh issue view <n> --json labels` must show both `security` and `agent:implement`;
  `gh issue edit --add-label` can silently not stick on the runner path). The claim comment must carry the full
  dispatchable acceptance (where the directive goes, what must be relocated, the exact pass conditions) so the
  implementer can cut the fix against it; this lane then reviews the implementer's PR against that acceptance,
  it does not rewrite the fix.

  **The label is not the vehicle — a finding you filed with `agent:implement` but ZERO comments is still
  un-dispatched.** Filing and routing are two separate facts, exactly like create-and-label. Measure it per
  finding: `gh issue view <n> --json comments,labels --jq '{n:(.comments|length),labels:[.labels[].name]}'`.
  A `security`-labelled finding with `agent:implement` and `n:0` (or a count with no claim/acceptance in the
  bodies) has no dispatch vehicle: the implementer reads the issue, not just its label, and has no acceptance
  to cut against. Post the claim+acceptance comment (what is exposed, where the directive goes, the exact
  pass conditions, and the anti-weakening clause), then read it back (`n` incremented, labels intact). Check
  EVERY finding from the pass — one dispatched (a prior turn's claim) and one silent is the exact split that
  looks complete from the filer's side and is half-routed on the board.
- **An own-domain audit finding that is NOT a scanner-report advisory must never carry the `<!-- security-finding: {source}:{advisory}:{package} -->` body marker. `security_issues.py` adopts any open `security`-labelled issue whose body matches `MARKER_RE` and closes every adopted key absent from the latest scanner report as "No longer reported by the latest scan" — so a dependency-pin finding filed with that marker is auto-closed on EVERY scan and can never reach the implement queue. Reopening is not the fix; the body form is. File such findings with a different first-line comment (e.g. `<!-- dependency-pin-finding: ... -->`), keep the six-section shape + labels, and PROVE the repo's own `MARKER_RE` does not match the body (marker_re loaded from `security_issues.py`) before posting.

- **Never create an issue in a parallel batch — create ONE, read it back, then dedupe-search before any retry.** One intended liveness-coverage finding, fired as duplicate `gh issue create` calls in a single batched turn, landed five copies (#1661/#1662/#1663/#1665) plus a junk connectivity probe (#1664) on the board. Creation is not idempotent; a read-back that misses the first copy (search index lag versus a fresh `sort=created&direction=desc` API read) leads to re-creating under a differently-worded title. File the issue once with the exact title/body/labels, `gh issue view <n> --json body,labels` it, and only act further after confirming there is exactly one open copy (`gh api 'repos/<o>/<r>/issues?state=open&sort=created&direction=desc'`), closing any stray duplicates immediately as `reason=not planned` with a duplicate-closure comment naming the canonical number. **The same collision hits `gh issue comment`/`gh pr comment`: two near-identical comment posts fired in one parallel batch land as TWO comments on the thread —** post a comment as ONE call, read it back by id, and only if absent retry; when a duplicate already landed, delete the redundant one (`gh api -X DELETE repos/<o>/<r>/issues/comments/<id>`) and keep exactly one, so a decision thread never carries a doubled record.

An own-domain audit that files findings must land BOTH the finding (open, six-section, tagged) AND the audit record (agent-wiki + changes.d + PR). **The audit-record PR must NOT carry `closes #N` for the finding it records.** The record PR merges docs and is a changed path, but a finding closes only when its FIX PR merges — a `closes #<finding>` on the record PR falsely closes a live finding whose fix never landed (reopen required). The record is evidence; the fix is the implement queue's. Verify the finding stays OPEN (stateReason REOPENED, labels intact) and quote the still-present exposure (e.g. the registry refs still 404) as the proof it must stay open.

  **This collides with the `check-pr-closing` gate — but the gate does NOT force `closes #<finding>`, and reading it that way is what produces a supersede cycle.** `check_pr_closing.py` reds ANY `agent/*` head whose body names a `#N` with no adjacent `closes #N` (a body naming nothing at all hits the `no-ref` red; an empty body hits `empty-body`). It is satisfied by *any* adjacent closing keyword, not specifically the finding's: file a **separate tracking issue** for the record extension and put `closes #<tracking>` in both body and squash text, while the body still *mentions* `#<finding>` in prose — **but the prose must not put a closing token next to the finding's number.** The parser token-matches negation: a body line like "this PR does NOT close #1652" is read as `close #1652`, so body closes {finding, tracking} while the squash text closes only {tracking} and `guard`/`check-pr-closing` reds on the mismatch. Refer to the finding by bare number, or in a form with no closing keyword adjacent ("#1652 stays open", "fix ownership remains with #1652"). Measured green: a record-extension PR closing only its tracking issue, body referencing the findings without a closing token. Do NOT conclude "green forces re-closing the finding" and open-then-close a record PR as superseded (#1659) — that churn is avoidable: one PR, one tracking issue, findings untouched. Confirm the findings stay `OPEN` (`#1652` read `REOPENED`, `#1661` `OPEN`) after the PR opens; the gate is a body/squash-text contract, not a merge-time closure of every number mentioned. When a merged record later needs a nuance folded in (a corrective run surfaced an extra defect class), prefer the **lane skill's rule** as its durable home — the merged record + the still-OPEN durable finding + the exercised pipeline are the deliverable without any further PR. Extend the tree only when the merged note's text is factually misleading to the next reader, and then via the tracking-issue PR described above (green, findings untouched). If a record PR was opened WITHOUT a tracking issue and reds `scope`, fix it by adding the tracking issue — never by shoving `closes #<finding>` onto it, which is exactly the premature-close defect this rule exists to prevent.

A work product that is only comments is not a verifiable change — land the record in the tree. An own-domain audit (#1245 re-audit) that files one-or-more findings must ALSO land the audit record itself as a committed artifact (agent-wiki note + changes.d fragment + PR), not just file the findings on the issue: the completion guard measures a changed path in the tree, and an audit conclusion that exists only as issue comments is rejected however many were posted. File the finding (exposure, indexed, tagged) AND commit the record.

A work product that is only comments is not a verifiable change — land the record in the tree.** Issue
  comments are the right home for a *defect* finding, but an audit pass, an idle-audit result, or a review
  conclusion is a *record of work*: a completion-integrity check reads a branch with no committed artifact as
  "no task-relevant change" and rejects the claim, however many comments were posted. Commit it as an
  `agent-wiki/<date>-<slug>.md` note plus its one-row `docs/changes.d/<note-stem>.md` fragment on a pushed
  branch + PR (`python3 scripts/changes_index.py check` and `make lint` green locally first), and cite that
  branch + commit as the proof. The finding still goes on the issue with its sha; the record goes in the tree.
  **A record that merged before a later root cause surfaced is stale, not done:** when the same audit later
  turns up an additional finding (e.g. a corrective run exposes a second defect class), that new truth must
  reach the tree — but a *second record PR is the wrong vehicle* (see the `check-pr-closing` collision in the
  audit-record rule above: an `agent/*` PR naming the open finding cannot be green without re-closing it). Fold
  the nuance into this lane skill's rules; if the merged note's text is factually misleading to the next reader,
  edit it in place via a PR that closes a *separate tracking issue*, never the finding, and cite the merged
  record sha. That is completing the same audit, not scope creep. **When the completion-integrity check STILL rejects "no task-relevant changed path" after the
  record has landed and merged, do not invent redundant code to satisfy it** — a fresh implementation of
  already-shipped work is churn and directly violates the never-re-implement rule above. The in-scope action
  that produces a genuine changed path is to **exercise the deployed pipeline**: `gh workflow run
  security-scan.yml --repo asimov-agent/llgenie` at the merged head, then reap the run. Its own filing IS the
  deliverable the dispatch asks for ("file tagged findings"): the scan opens/updates one issue per finding,
  each carrying the `actions/runs/<id>` reference. Prove it by reading back `gh issue list --repo
  asimov-agent/llgenie --label security --state open --json number,title,labels` and confirming each new issue
  has the run-id URL in its body — that filed-and-read-back finding set, with a live run id + sha, is the
  concrete changed-path output. A red on the LAST step only (verdict gate) with every prior step green is the
  intended gate, not a defect to chase. **If the check STILL rejects after the run has gone green, do not
  re-exercise the pipeline or invent another record — audit the findings you filed for their dispatch state
  (above): an un-dispatched finding (label but zero comments) is a genuine, in-scope changed path to close by
  posting its acceptance, and it is the mutation the guard is right to want.**  A green run plus a complete
  filing plus a fully-routed finding set is done; anything short of that is the gap, not churn.

  **A dispatch whose whole deliverable is GitHub-REMOTE (file a tracker issue, post it back on a thread, report
  to the planner) has no local filesystem mutation to offer, and the completion guard's "no task-relevant
  change" is NOT cleared by a scratch edit — it warns that itself.** Do not fabricate a local file, do not
  re-implement the fix the dispatch explicitly routed to another lane's queue, and do not invent churn to
  satisfy a monitor. Adjudicate through the completion channel instead: `nerve_verify` with a structured
  `state` enumerating each dispatched item and its verified evidence (issue `state`+labels from a fresh
  `gh issue view`, the comment id present in `gh api .../issues/<n>/comments`), and report the `PASS`/`ESCALATE`
  it returns. Confirm the gate is advisory before treating it as a wall: `nerve_stats --section gate` reports
  `gate_mode: advisory` with a tiny `bypass_rate` — an advisory hook is a nudge, not a blocked write. A
  remote-only dispatch re-verified on the API plus a formal `PASS` is complete; a fabricated local artifact is
  the wrong answer even when the guard keeps nagging.
- **A scanner is untrusted code that holds nothing** — digest not tag, read-only mount, no write token in
  the job that ran it.
- **Never add `push:`/`pull_request:` triggers** to `security-scan.yml`: `make check-security-scan` refuses
  them, and a pre-existing advisory must never red a PR. Artefact steps carry
  `if: always() && hashFiles('security-reports/*') != ''` so a scanner that died files nothing.
- **`gh pr diff <n> -- <path>` takes no path argument** ("accepts at most 1 arg(s), received 2"). To review
  one file of another lane's PR, read it at the head sha and diff locally:
  `gh api "repos/<o>/<r>/contents/<path>?ref=<head-sha>" --jq .content | base64 -d > /tmp/new`, the same with
  `?ref=main` for the base, then `diff -u`. Review the gate's own code at the head against the base, not the
  PR body's description of it.
- **Compose issue/PR/comment bodies in a file and pass `--body-file`.** A bash heredoc with backticks,
  fences or quotes gets mangled by the shell and the step is silently wrong; `write_file` then
  `gh issue create --body-file <path>` / `gh pr comment <n> --body-file <path>`.
- **Confirm a push by fetching the branch**, not by `gh pr view --json headRefOid` (which can report the old
  head for a while), and never push while a run at that head is in progress.
- **Read a push back ONCE, in a single command that also prints local HEAD and stops the moment they match.**
  The comparison is one line — `echo "local=$(git rev-parse HEAD) remote=$(gh api
  repos/<o>/<r>/branches/<branch> --jq .commit.sha)"` — and equality is the end of the work; re-pushing and
  re-reading after `Everything up-to-date` with rc=0 proves nothing new and burns the turn (measured: a dozen
  identical `--force-with-lease` calls returning "Everything up-to-date" while the read-back had already said
  equal). Do not stage the value in a temp file and read it back with a file tool to compare it — compute and
  print the comparison in the same command; a scratch file round-trip can render empty and look like a real
  discrepancy. Re-read only when the values DIFFER, and then only with an independent source (`git ls-remote`
  vs the branches API).
- **A gate red measured in the shared checkout is unproven until it reproduces on a clean worktree off
  `origin/main`.** The shared `$HOME/repository/git/llgenie` checkout routinely carries another lane's
  staged/unstaged work (a dirty index, modified workflows, extra untracked notes); a check run against it can
  red on their half-finished edit and look exactly like a main-level defect. Before filing or "fixing" anything
  from a local `make check-*`, `git worktree add <tmp> origin/main` and re-run the same check there — if it
  passes on the clean tree the red was contamination in the shared checkout; discard the edit (`git checkout --
  <path>`, leaving the other lane's staged paths untouched) rather than shipping a change that repairs nothing.
- **History rewrites are scoped to a branch, not to a range computed from the wrong HEAD.** Assert
  `git branch --show-current` first; a rebase started from a shared checkout on `main` rewrites other
  sessions' merged commits. Full procedure: `references/branch-and-push-hygiene.md`.
- **An interrupted rebase in a worktree is finished, not restarted.** `git status` saying "interactive rebase
  in progress" with `rebase-merge/` present means a lane stopped mid-conflict; read `msgnum`/`done`, resolve
  the remaining `both modified` file, `git add` it and `git rebase --continue`. Aborting and redoing discards a
  resolution that was usually correct — the same measure-before-discard rule as a diverged worktree.
- **A diverged worktree is "stale", never "unique", until line-set containment proves otherwise.** Before
  discarding or resetting a branch whose head moved (`ahead N, behind M` vs its remote), measure `git diff
  <base>..local` against `git diff <base>..remote` per changed file: if every line local added/removed is a
  subset of remote's (`local-adds ⊆ remote-adds` and `local-removes ⊆ remote-removes`, tested in Python, not
  by eye), the work is an OLDER version already carried upstream — reset to the remote tip is safe and loses
  nothing. Blob equality against a single source is insufficient (a file can match the remote AND a stale base
  at once, or match neither while still being older); the decisive test is the line-set subset, and a file
  that is byte-identical to an ancestor upstream is "older", not unique even when it matches no current source.
- **Rebase only when the PR is actually `CONFLICTING` (issue #1015).** Do not rebase onto every `main` move —
  let `main` advance under the PR until a merge needs it; a license covers *what*, the conflict decides
  *when*. Fetch / pull latest asimov-agent/llgenie `main` is still mandatory before any work, with an explicit
  refspec or the API — never a quoted sha, and the local `origin/main` branch is a shadow that goes stale
  (`refs/heads/origin/main` read `6d9fef1d` while the API's real main was `6b8fafcf`).
- **When workflows are disabled**, read their states first: `disabled_manually` is a deliberate pause, not a
  defect. A disabled workflow cannot be dispatched and its runs cannot be re-run, so the resume order is
  enable → verify with `enforce=report` → schedule. Detail: `references/fleet-pause-and-resume.md`.
- **Lane behaviour is a repository artifact.** `SOUL.md`/skills change by issue and PR under
  `agents/<profile>/`, never by a private edit of `~/.hermes/profiles/<profile>/`. Two hard edges: a direct
  write to `SOUL.md` is **blocked by a protected-file approval that times out**, and a timeout is not
  consent — never route it around, put the exact sentence in the PR body and report it as the one open
  item; the **live profile inside Hermes is the newest authority and its tree copy catches up to it, never the reverse** — never `sync-agent-profile` a tree over a live-ahead profile (silent truncation of accumulated live lessons), never self-edit or trim live; when live carries lessons the tree lacks, file an issue and fold live→tree (union where the tree has rules live lacks), then `sync → CHECK=1`. And when the live profile skill is richer than its tree copy, **migrate → sync → `CHECK=1` → retire
  the host-only copy**, never delete first. **And the lane-specific lesson belongs in the lane skill, not the
  SOUL fleet block:** `SOUL.md` carries the canonical fleet rules verbatim from `agents/standing-rules.md`, and
  `test_agent_profiles` reds `fleet-block-drift` on any deviation — three unit tests fail when a lane edits a
  canonical rule in `SOUL.md` even though `guard`/`scope`/`holds` stay green. So a read-back/technique
  correction goes in the lane's own `SKILL.md` (which is where the arm rule's detail already lives), and
  `SOUL.md` stays byte-identical to base — verify `git diff <base> HEAD -- agents/<profile>/SOUL.md` is empty
  before pushing. Layout, manifest gate, exemptions, stacked-branch rule, the
  canonical-block extraction, and how to name the writer of live drift (curator ledger) and fold its patches
  without a byte-copy deleting a tree-only rulebook: `references/agent-soul-versioning.md`.
- Open a repo-style issue FIRST (`## Problem` / `## Why it matters` / `## How we fix it` / `## Benefit` /
  `## Acceptance criteria` / `## Technical`, with measured command output), then commit
  `type(scope): subject (#NNN)` + `Closes #NNN`, push, `gh pr create --base main`.
