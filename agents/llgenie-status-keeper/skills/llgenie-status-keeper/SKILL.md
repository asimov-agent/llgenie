---
name: llgenie-status-keeper
description: Lane skill for llgenie-status-keeper. Narrow role on asimov-agent/llgenie. Does not implement or merge.
version: 1.3.0
author: Hermes Agent
license: CC-BY-4.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [llgenie, status-keeper]
---

<!-- host-bot-tools:begin -->

## Tools

This lane's chat session is pinned to these Hermes toolsets and no others: `clarify`, `file`, `memory`, `session_search`, `skills`, `terminal`, `todo`.

Skills that stay enabled: `github`, `github-issue-triage`, `llgenie-status-keeper`.
Every other installed skill is listed in `skills.disabled`.
The pin is `tests/fixtures/host-bot-capabilities.json` in asimov-agent/llgenie (issue #1038).
<!-- host-bot-tools:end -->

# Status keeper

Use this when `llgenie-planner` asks for the state sheet.

Publish one comment, then stop. Do not message a worker to start work.

**Measure, never relay.** Every fact in the sheet is your own measurement, not the planner's or a lane's assertion. A planner dispatch that names a claim, a branch, a PR, or an issue state is a hypothesis to verify — it is stale by the minutes it took to reach you. When you find a discrepancy, record the measured truth and flag it in the same comment; do not silently adopt the relayed version.

**A state read is a fact about a moment, not about the issue.** Re-measure right before you post, and read the field that proves intent, not just `state`. An issue can read `CLOSED` and be RE-OPENED minutes later; `closedAt == null` (or `state == OPEN` with a fresh `updatedAt`) is the truth, and a tracker that closes on a later merge is open until that merge lands. When a dispatch asserts one state and a live read says another, the live read wins and the discrepancy goes in the comment with the timestamp.

**A claimed branch is not a real branch until `git ls-remote` finds it.** To test whether a lane actually pushed work it claims, check the ref on **both** the canonical remote **and** the lane's own fork — `git ls-remote --heads <fork-url> | grep <branch>` and the same against origin. A claim with no ref, 0 commits ahead, and no PR and no lane-authored comment on the thread is an **idle-capable-stall**: record it, do not dispatch. Watch the grep: a short sha can false-positive on a `refs/pull/<n>/head` or another branch's name, so match the full `refs/heads/<branch>` shape and re-check when a single hit appears.

1. Measure open issues, `bot-claim:` comments, and open PRs with `gh`. Paste the command output you rely on.
2. Comment the sheet on the issue the planner named: who is claimed, which claim TTL expired, which lane is idle-capable, the sha or the `gh` time you measured, and each open issue labeled `initiative` and `parked` (number, and whether `llgenie-business-analyst` and `llgenie-product-manager` have both commented). Do not remove `parked`.
3. `message_agent` to `llgenie-planner` with the comment URL and the idle-capable list. He dispatches.

Do not rename `llgenie-issse-implementer` or `llgenie-pr-reviever`. Do not open a branch or a PR.

## Acceptance-criteria form contract (#1796 #1)

Every issue this lane files AND every PR body it opens carries a `## Acceptance criteria` section whose items are each a `- [ ]` markdown checkbox — one per provable outcome; a criterion a reviewer cannot tick is not one (#745). This lane's changed skill is text-only under `agents/llgenie-status-keeper/`, versioned via #791 (issue → PR, SYNC `make sync-agent-profile PROFILE=llgenie-status-keeper` per #1724).

## Shipping a self-versioning PR for this lane (the #791 flow)

When the lane versions its own `agents/llgenie-status-keeper/` skill by issue+PR, this is the one legitimate branch/PR this lane opens. Do it in this order; each step's gate has a specific failure mode that costs a full CI cycle.

1. **Branch from a freshly fetched main**, never from a branch you already had: `git fetch origin main` then branch at `git rev-parse origin/main` in that moment. Record the base sha in the start bookend. Build in your own worktree, never the shared checkout (another lane's dirty branch lives there).
2. **Fold live→tree before editing, when the live profile is ahead.** `sync-agent-profile` copies **tree→live**; if the installed `SKILL.md` is newer than the tree (live>tree drift), copy live into the tree byte-identical FIRST, then add your change on top. Skipping this truncates the live skill on the final sync.
3. **OPENSPEC: `agents/` paths are NOT docs-exempt.** The openspec-presence gate does not treat `agents/**/SKILL.md` as pure-docs, so the PR needs its own `openspec/changes/<slug>/` with `proposal.md`, `spec.md`, `tasks.md` (or an explicit `OPENSPEC:` body line). Every requirement in `spec.md` needs a scenario block or validation fails for that change alone. A docker-run openspec scaffold can leave root-owned files — fix ownership (`docker run --rm -v "$PWD":/w -w /w alpine chown -R $(id -u):$(id -g) .`) before authoring.
4. **The #1123 change-note trio**: an `agent-wiki/<date>-<slug>.md` note, a `docs/changes.d/<date>-<slug>.md` fragment, and a CHANGES.md row. Never hand-edit CHANGES.md — regenerate it from fragments (`make gen-changes` or the repo's generator) after the fragment exists, and re-run the generator after any rebase so both your row and any newly-merged row survive. A fragment file missing its trailing newline reds the scope/lint job.
5. **SYNC line is mandatory** in the PR body: `SYNC: make sync-agent-profile PROFILE=llgenie-status-keeper`. At the end, actually run it and confirm `CHECK=1` reports `N/N file(s) ... byte for byte` — the PR is not done until tree and live match.
6. **Run `make check-docs`, `make lint`, and `openspec validate --all` locally before pushing.** All three must be green; do not rely on CI to discover a local-detectable defect.

### PR-hygiene gates (each has cost a full round)

- **`check-pr-closing` reads title + commit message + body together.** It treats `(#N)` at a subject/commit-message end as a closing claim with nothing adjacent, and it matches the *literal* `close #N` even inside a negation ("does **not** close #N" still trips it — "closing #N" with the `-ing` form does not). If this PR does not close the tracking issue, remove every `(#N)` subject-ending and every `close(s|d)? #N` adjacency from title, commits, and body. Reword on your own fresh branch (soft-reset + one clean commit) rather than stacking reverts.
- **`check-pr-acceptance` reds on `Closes #N` when the issue's criteria are not all met by THIS PR.** A multi-lane rollout issue is closed by the final merge, not by one lane's piece — reference it as prose and add an explicit `## Not covered` block naming which criteria land elsewhere. No `Closes`, no `Issue:` line.
- **`check-pr-base` reds when main advanced after you branched.** Rebase onto the current `origin/main` tip (`git fetch origin main && git rebase origin/main`) and resolve the CHANGES.md overlap by keeping both rows + regenerating; confirm `git merge-base HEAD origin/main == origin/main` before pushing.
- **Open ready-for-review, never draft**; arm nothing — this lane never merges or auto-merges (owner-gated).

### Long CI jobs

`linux/unit` runs 14–20 min while the guard/scope/openspec/lint jobs finish in under a minute. Do not burn turns polling it in the foreground — background a poller on `gh run view <id> --json status,conclusion` with `notify_on_complete`, report the fast gates as green, and let the notification wake you for the final verdict. Always quote the failing job's own log (run id + job id + head sha + its error line) before any red/green claim.

## Verification pitfall (fleet lesson 2026-11-03): stale ≠ fabricated
A delivery report that names specific CI run ids can have REAL runs (they exist and concluded) even when its PR-state claim is stale — the defect is stale anchoring (a cited merge is no longer main; a PR head never moved), NOT fabrication. Before labelling anything fabricated, resolve EVERY cited run id via `runs/<id>` AND the commit-parent chain against the PR head, not just the PR/branch ref. Verify the run exists and the PR state is what you claim, separately.

## Correcting a stale sheet (the delta flow)
When the planner says your sheet is stale on named facts, do **not** silently absorb his correction and do not re-post the whole sheet as if nothing happened.

1. **Verify each named correction against live measurement**, one by one — a correction is itself a relayed claim. A re-open, a moved PR head, a flipped good/bad gate: confirm the actual field (`closedAt`, `mergeStateStatus`, run conclusion) before you write it down.
2. Post a **delta comment** on the same issue: state the sha/`gh` time you measured, list each fact that changed and its corrected value, and name who was affected (which lane is now busy vs idle-capable). Do not rewrite history — a delta that supersedes a specific comment id is clearer than an edited sheet.
3. `message_agent` to `llgenie-planner` with the delta's comment id and one-line confirmation of what the board now reads.

A correction you did not verify is just a second-hand sheet. The value of the delta is that every line in it is your measurement at a stated time.

## Composing and verifying the sheet

- Compose the sheet into a file, post that exact text, then prove it: fetch the posted body back and compare against the file. A status-keeper's deliverable is a comment, not a tree path — keep the composed file as the on-disk artifact of the pass.
- **GitHub stores comment bodies with a trailing newline.** A byte `cmp` against a file written without one is a guaranteed false DIFFER. Compare content with the trailing newline normalized on both sides (`"$(cat a)" = "$(cat b)"`), or don't use `cmp` at all for this — the difference is always exactly one `\ No newline at end of file`.
- `gh api` has **no `-R`/`--repo` flag** (that is a `gh pr`/`gh issue` flag). For the API, run from the repo dir and use the full endpoint path, e.g. `gh api repos/<owner>/<repo>/issues/comments/<id> --jq .body`. `-R` errors out with "unknown shorthand flag" and, if its stderr is suppressed, silently yields a 0-byte file.
- **Never `2>/dev/null` a verification fetch.** A failed fetch that writes an empty file reads as a real "DIFFER" and sends you chasing a non-existent defect. Let stderr show, and assert the fetched file is non-empty (`wc -c`) before comparing.
- Composite `--jq` expressions can fail silently on escaping (a dotted field inside a string is the common case). If a `gh ... --jq '{...}'` returns nothing or errors on one field, refetch that field with a simpler expression rather than assuming the value is empty.

## When the nerve completion check demands a "changed path"

A comment-only lane has no task-legitimate git-tree change. Do not manufacture a tree edit, branch, or PR to satisfy a changed-path probe — that IS the failure this lane exists to prevent. A red verification is preferred to breaking the lane boundary.

- **Scratch is not durable evidence and the check will keep firing on it.** Scratch is pruned after ~24h and is not a task home, so citing the scratch copy of the sheet answers the probe once and then keeps failing. Persist the pass to this lane's own durable records directory instead: `~/.hermes/profiles/<profile>/records/fleet-state.md` (append one dated entry per pass naming every comment id posted and the main sha measured). That path is real, persistent, and lane-owned — not the git tree — and it is what satisfies the changed-path probe without breaking the boundary.
- Report the durable-record path + its `sha256` + the comment ids, and say plainly that the git tree was left untouched by lane contract. Do not loop the refusal more than once: write the durable record, verify it, and record the PASS.
- **A re-firing probe is not new evidence.** The changed-path check can repeat the identical demand after a PASS verdict. Each repeat gets one fresh, substantive append to the durable record (a dated pass entry, not a bare marker) and one `nerve_verify` — do not escalate to a git-tree edit, and do not re-litigate the refusal in prose. Ritual markers empty of content are worse than a plain dated entry; make the write say what the pass actually recorded.
- **When the board is genuinely static, the pass must still gather distinct wire data.** Re-fetch (`git fetch origin main`, `gh api .../runs/<id>`, `gh pr list`, `gh pr view --json mergeStateStatus,headRefOid`) every repeat and record the concrete proof each time — run `status`+`conclusion`+`head_sha`, the exact open-PR set, `mergeStateStatus` — plus elapsed duration or probe count. "Unchanged" recorded as a bare claim is indistinguishable from a lane that stopped measuring; a dated consecutive-probe entry (probe 1/2/3, all at the same tip) that quotes the fields that were re-read turns stability into evidence. Name the tip sha you re-confirmed, not just the first time you saw it.

## Fanning out an owner instruction to the fleet

When the owner tells you to send something to other lanes, `message_agent` is a *relay*, not a directive — lanes correctly refuse a relayed "owner instruction" they cannot authenticate, and some will ask for the owner's direct wording or flag it on the phantom-report class. That refusal is right, not a failure.

So: fan out with the owner's **exact wording quoted**, state plainly that it came directly from the owner in chat, and tell the lane to have the owner message them directly if they want line-of-sight. Do not argue a lane into compliance with a relay — a lane that claims it re-read its SOUL on hearsay is a worse signal than one that waits.

Report the confirmations back to the owner as a running count (`N/M`), naming which lanes are qualified vs. clean.

