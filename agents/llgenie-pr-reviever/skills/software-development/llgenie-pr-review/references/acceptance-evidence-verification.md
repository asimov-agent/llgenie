# Acceptance-criterion evidence: verify, never accept a dispatch's word

A dispatch or inbox message that says an AC "is provable — verify and tick it" is a **hypothesis**.
Re-measure what the AC text actually demands before any `[x]`; the wire decides, not the messenger.

## 1. The cited job must belong to the cited run

ACs usually name a failure as `job <id> (run <id>)`. Check both directions:

```bash
gh api repos/<o>/<r>/actions/jobs/<job> --jq '.run_id,.name,.conclusion,.head_sha'
gh api repos/<o>/<r>/actions/runs/<run>/jobs --jq '[.jobs[].id]|contains([<job>])'   # must be true
gh api repos/<o>/<r>/actions/runs/<run> --jq '.name,.conclusion'
```

Common failure modes that make the AC unprovable:

- The job id resolves to a **different run** than the one named — classically a `skipped` job of an
  unrelated workflow, while the named run is itself `cancelled`. Neither is a completed named-stage failure.
- The run is `cancelled`: cancelled is *no verdict*, never a named-stage failure to attribute.

Mismatch ⇒ AC unproven, no tick, regardless of how confident the dispatch is.

## 2. "Quoted in a comment on the issue" means a comment, not the PR body

```bash
gh api "repos/<o>/<r>/issues/<n>/comments?per_page=50" --jq '.[]|{id,body}'
```

- A comment whose body is a bare `@/tmp/<file>.md` path marker (≈18–25 bytes, empty `body_html`) quotes
  **nothing**. It is a pointer to an off-wire file, not the evidence the AC demands.
- Quoted `ERROR:` / `[engine-image]` lines living in the **PR body** do not satisfy an issue-comment
  requirement, and are frequently about a *different* defect than the AC's named job.

If the AC says "comment on this issue", the log line must be in a comment on that issue.

## 3. Verdict state follows the cause

- Evidence gap or a legitimately deferred AC (blocker filed and linked under a `## Not covered` section) ⇒
  `gh pr review <n> --comment --body-file <f>` (COMMENTED). Not REQUEST_CHANGES: the *code* may be correct.
- Real code/security defect ⇒ `--request-changes`.
- Every criterion met with its anchor ⇒ `--approve`.

A COMMENTED verdict that names head sha, run id, the failing criterion and the exact unblock condition is
honest state; a body-only comment with no state is not a verdict at all.

## 4. Confirm the review landed by id, not by a body filter

```bash
gh api repos/<o>/<r>/pulls/<n>/reviews --jq '[.[]|{id,state,commit_id,len:(.body|length)}]'
```

A `--jq` select over `body|contains("<phrase>")` can return `[]` for a review that posted fine
(multiline / escape / pagination), which reads as a silent no-op and tempts a duplicate re-post.
Trust the id/state/commit_id listing; if it looks empty, list all reviews and match by `len` + head.

## 5. Report back

Send the inbox the head sha judged, which ACs were ticked (often none), the measured reason with the command
output, and the exact unblock condition — so the delegation loop closes on evidence rather than on a tick.

If the lane you are reporting to **messaged you in this turn** (a dispatch that is still open in the same
session), put the report in your final response instead of calling `message_agent` — a separate outbound
message to that lane is refused as a duplicate of the reply already going back to it. The report is the
same content either way; only the channel changes, and a refused send retried in a loop wastes the turn.

## 6. Mutation-prove the FIX, not only the test

A new test that passes at the head proves nothing on its own: it may pass against the unfixed code. The
claim an AC usually makes is "the defect is gone", so prove the delta — run the *same* command against the
base version of the changed file and show it fails, then show it pass at the head.

```bash
# defect class: a subcommand/flag that the parser never registered
cd <base-checkout>; python3 scripts/<tool>.py <subcmd> --repo <o>/<r>; echo "base rc=$?"   # expect SystemExit 2
cd <head-checkout>; python3 scripts/<tool>.py <subcmd> --repo <o>/<r>; echo "head rc=$?"   # expect 0
```

- A base failure of `error: unrecognized arguments: --repo` / `SystemExit: 2` is the mutation: it shows the
  invocation the AC names was impossible before the patch and is possible after.
- Run the new test file against the **base** source, not just the base test file — copying the head's test
  onto stale code is the cleanest form and localises the delta to the fix.
- Cite the mutation in the verdict as a measured pair (`base rc=2 / head rc=0`), plus the test count you
  personally observed. Never reuse the dispatch's test count: dispatches quote a stale or partial run
  (`40 passed` where the file at the head yields `13 passed`), and a copied number is an unverified claim.
- When the AC is a *wiring* change with no runnable defect (a condition moved from `inputs.push` to a
  matrix guard), the equivalent mutation is a structural assertion in the new test that fails closed when
  the old wiring is restored — say so, and name the test.
