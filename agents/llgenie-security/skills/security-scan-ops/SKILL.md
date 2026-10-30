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

## When to Use

Any task on `asimov-agent/llgenie` in the security lane: the daily scan is red, no issues were filed, no
bump PR appeared, a finding will not clear, a PR carries a security hold, the open security issues need a
review pass, or this lane's behaviour/SOUL and its branches must be reconciled. Repo:
`/home/asimov/repository/git/llgenie` (`origin` = asimov-agent/llgenie, `fork` = andyholst/llgenie;
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
cd /home/asimov/repository/git/llgenie && git fetch origin && git log --oneline -1 origin/main
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
- **`enforce=report`** asks "is the finding set gone on `main`": `pr_fail_on` is empty, so the run cannot red,
  and it hands back a verdict line plus a run id. Use this for a clean-up check so it never adds a red to a
  board you are trying to prove is clean.

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
   remedy. Checklist: `references/security-issue-review.md`.

## Trust-boundary audit of the pipeline itself

Audit what runs the scan as well as what it finds — greps and reasoning in
`references/security-issue-review.md`. The three properties to check every time: the scanner image is
addressed by **digest** (a tag can be re-pushed), the scanner mounts the checkout **read-only** (otherwise it
can edit the scripts the later steps execute), and the **write token lives in a different job** from the one
that ran the binary.

## Gates to run before opening the PR

```bash
make check-security-scan check-security-issues check-security-bumps check-workflows check-docs check-wiring
docker run --rm --user $(id -u):$(id -g) -v "$PWD":/repo -w /repo -e HOME=/tmp llgenie/test:latest \
  python -m pytest tests/test_security_issues.py tests/test_security_scan.py tests/test_security_bot.py \
    tests/test_issue_body.py tests/test_check_issue_body.py -q -p no:cacheprovider
```

Local `python3` has no pytest — always use the `llgenie/test:latest` image (pulled/built by `make
test-image`). A `make sbom && make security-scan TOOL=trivy` run locally (pinned images via docker) plus
`python3 scripts/security_scan.py verdict --event schedule` is the cheapest real proof a finding set is gone.

## Standing rules for this lane

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
- **Arm auto-merge only on a `main`-based PR, and read `state` before `autoMergeRequest`.** On a PR whose base
  is another branch, `gh pr merge <n> --squash --auto` does not arm — it **merges within seconds** into that
  branch, because there are no protected-branch rules to wait for (measured four times in eight minutes:
  #958, #954, #965, #966; #964). So a stacked PR is reported `auto=none (stacked base: arms into <base>)` and
  the flag is never passed. On a `main`-based PR, `auto=armed` may only be claimed when the read-back shows
  `state == OPEN` **and** `autoMergeRequest != null` — GitHub clears `autoMergeRequest` when a PR merges, so
  checking it alone reads "armed nothing" on a PR that already merged. A merged PR is `merged`, never `armed`.
- **Never hold a PR without a remedy.** `do-not-merge` means "a concrete defect with a tracked fix". If
  this lane places one, the same comment names the issue that makes the tag removable and the exact
  condition for removal, and the lane removes the tag itself when that evidence exists. Detail:
  `references/holds-and-publishing.md`.
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
- **A deliberate weakening is never the fix.** No allowlist entry, no widened severity set, no
  `require_fix: false`, no emptied `fail_on` to turn a run green.
- **Report scope, not remediation-by-patch.** What is exposed, the measurement (command + output + sha),
  who decides, the smallest fix that closes it.
- **A scanner is untrusted code that holds nothing** — digest not tag, read-only mount, no write token in
  the job that ran it.
- **Never add `push:`/`pull_request:` triggers** to `security-scan.yml`: `make check-security-scan` refuses
  them, and a pre-existing advisory must never red a PR. Artefact steps carry
  `if: always() && hashFiles('security-reports/*') != ''` so a scanner that died files nothing.
- **Compose issue/PR/comment bodies in a file and pass `--body-file`.** A bash heredoc with backticks,
  fences or quotes gets mangled by the shell and the step is silently wrong; `write_file` then
  `gh issue create --body-file <path>` / `gh pr comment <n> --body-file <path>`.
- **Confirm a push by fetching the branch**, not by `gh pr view --json headRefOid` (which can report the old
  head for a while), and never push while a run at that head is in progress.
- **History rewrites are scoped to a branch, not to a range computed from the wrong HEAD.** Assert
  `git branch --show-current` first; a rebase started from a shared checkout on `main` rewrites other
  sessions' merged commits. Full procedure: `references/branch-and-push-hygiene.md`.
- **Rebase only when the PR is actually `CONFLICTING` (issue #1015).** Do not rebase onto every `main` move —
  let `main` advance under the PR until a merge needs it; a license covers *what*, the conflict decides
  *when*. Fetch / pull latest asimov-agent/llgenie `main` is still mandatory before any work, with an explicit
  refspec or the API — never a quoted sha, and the local `origin/main` branch is a shadow that goes stale
  (`refs/heads/origin/main` read `6d9fef1d` while the API's real main was `6b8fafcf`).
- **End a splice directly above a heading with a blank line**, or lint_linefeeds reds the file: the #1010
  fence-before-block splice routed `## Standing rules` without a preceding blank and reded `make lint`
  until PR #1044. Check the repo lint on the file, not just the canonical-block gate.
- **When workflows are disabled**, read their states first: `disabled_manually` is a deliberate pause, not a
  defect. A disabled workflow cannot be dispatched and its runs cannot be re-run, so the resume order is
  enable → verify with `enforce=report` → schedule. Detail: `references/fleet-pause-and-resume.md`.
- **Lane behaviour is a repository artifact.** `SOUL.md`/skills change by issue and PR under
  `agents/<profile>/`, never by a private edit of `~/.hermes/profiles/<profile>/`. Two hard edges: a direct
  write to `SOUL.md` is **blocked by a protected-file approval that times out**, and a timeout is not
  consent — never route it around, put the exact sentence in the PR body and report it as the one open
  item; and when the live profile skill is richer than its tree copy, **migrate → sync → `CHECK=1` → retire
  the host-only copy**, never delete first. Layout, manifest gate, exemptions, stacked-branch rule and the
  canonical-block extraction: `references/agent-soul-versioning.md`.
- Open a repo-style issue FIRST (`## Problem` / `## Why it matters` / `## How we fix it` / `## Benefit` /
  `## Acceptance criteria` / `## Technical`, with measured command output), then commit
  `type(scope): subject (#NNN)` + `Closes #NNN`, push, `gh pr create --base main`.

## Inputs
`$REPO` (owner/name), the scan reports on disk (`security-reports/`), `containers/scanners/digests.json`
for the scanner refs, and `data/security-policy.json` for the severity policy.

## Output
Nothing but a report. This lane reads the scan, names exposures, and files/clears issues — it does not
implement the remediation. The one file it may write is its own `agents/llgenie-security/SOUL.md`.

## Rules
1. **A deliberate weakening is never the fix.** A red is the code or the rule, not the gate: no allowlist
   entry, no widened severity set, no `require_fix: false`, no emptied `fail_on`.
2. **Report scope, not remediation-by-patch.** What is exposed, the measurement (command + output + sha),
   who decides, the smallest fix that closes it.
3. **Secrets and identity are verified, never asserted absent.** Name the command and its answer —
   `gh auth status`, `gh secret list`, keyring, env *names* — and never print a value while checking.
4. **A scan result nobody can see is not a finding.** Publish on the issue with the sha it was measured at;
   sensitive detail goes private first, the existence and the reference never do. A scan that touches
   `scripts/` or `.github/workflows/` messages that lane with the scanned sha before it files or pushes.
5. **Every finding names the sha it scanned and the command that produced it.** Start from a fresh
   `origin/main` (`asimov-agent/llgenie` is upstream; a fork named `origin` is not) and write that sha into
   the first comment; bookend the work with a start comment (branch, main sha, what "done" means) and a
   finish comment (head sha, what changed, the command or run id that proves it, what is left open). A
   finding measured against a tree that moved is a false positive (wasted remediation) or a false negative
   (a fix assumed present); a scan that cannot name its sha is not a result.
6. **A security hold is the case where an untracked hold is itself the finding.** Name the exposure, the
   issue that closes it and the evidence that proves closure (a patch, a policy change, a scan showing
   absence), then remove the tag yourself with that evidence (#948).
7. **Never trust a write you did not read back.** `gh issue create --label` is dropped on the runner path
   (#724, #781-#784), so every write that matters is paired with a read-back that fails the step (#785).
8. **A scanner is untrusted code that holds nothing** — digest not tag, read-only mount, no write token in
   the job that ran it (#810).

## Procedure
1. **Audit** — `gh run list --workflow security-scan.yml`, then read the failing step list from
   `gh run view <id> --json jobs`. A red run whose FIRST failure is `security-verdict` means the reporting
   steps never ran: the gate is ahead of the report.
2. **Replay the run's own reports**, never infer from the summary:
   `gh run download <id> -n security-reports`, then `make security-issues-plan` and `make security-bumps-plan`.
3. **Relevance test before believing a finding** — is the named pin in a file the build installs
   (`tools/requirements*.in`/`txt`), or in a committed copy of a build-time input (#787)? A finding about a
   generated file can never clear.
4. **Prove a fix by running the scanner**: `make sbom && make security-scan TOOL=trivy`, then
   `python3 scripts/security_scan.py verdict --event schedule` -> `0 finding(s)` at a named sha.
5. **Gate before the PR**: `make check-security-scan check-security-issues check-security-bumps
   check-workflows check-docs check-wiring`; local `python3` has no pytest, so use the `llgenie/test` image.

## Never
- Never weaken a gate to make a run green (allowlist entry, widened severity set, emptied `fail_on`).
- Never put `secrets.BUMP_TOKEN` in a job that executes a pulled scanner image, and never mount the
  checkout read-write into a scanner (#810).
- Never add `push:`/`pull_request:` triggers to `security-scan.yml` — `make check-security-scan` refuses them.
- Never file a security finding without the run id and the scanner digests it was measured with (#787).
