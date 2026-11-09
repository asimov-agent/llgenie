# The acceptance write-back seam (ticking an issue's proven boxes)

`scripts/acceptance_writeback.py` (landed for the acceptance-writeback issue) is the sanctioned way to
flip a closed/settled issue's `- [ ]` acceptance boxes to `- [x]` with a `proven:` marker and a verdict
reference — never a manual body edit. It has three subcommands:

```
acceptance_writeback.py writeback --issue N --proven 1,3 --verdict-ref '<...>' [--dry]
acceptance_writeback.py apply    --body-file BODY --proven 1,3 --verdict-ref '<...>'
acceptance_writeback.py check    --body-file BODY --proven 1,3 --verdict-ref '<...>'
```

## The pitfall that costs a turn: the heading match is EXACT

The tool finds the section with `issue_body.section_body(body, "Acceptance criteria")`, which matches a
`##` heading whose text (`.strip()`) equals **`Acceptance criteria`** exactly. An issue authored with a
suffix — e.g. `## Acceptance criteria (what closing means)` — is NOT found, and the seam refuses:

```
BodyError: the body has no `## Acceptance criteria` section   (rc 1)
```

This reds even when every acceptance item is genuinely proven on `main`: the issue then sits
closed-but-0/5, verified-in-a-comment instead of ticked, and a reader trusts `0/5` over prose. The
root defect is the **issue's own heading spelling**, authored at filing time — not the PR body, not the
merge. So when writing any six-section issue, the acceptance heading is bare `## Acceptance criteria`,
no parenthetical, no subtitle. This is the same class as the "one canonical heading" rule elsewhere: a
section the seam greps for is found only under its exact canonical name.

## Run it `--dry` first, from a clean worktree at the tip

- `--dry` applies the identical heading match and writes nothing: a non-zero rc there names a body-form
defect **before** any wire write, so always dry-run first (`--dry` exits 0 on success and prints the
plan).
- Run the tool from a **clean detached worktree at the fetched `origin/main` tip**
  (`git worktree add --detach /tmp/wt origin/main`), never the repo's moving main checkout: the tool's
  behavior is `main`'s bytes, and a stale checkout can carry an older seam. Remove the scratch worktree
  after (`git worktree remove /tmp/wt --force`) — it is a `/tmp` throwaway, which the never-prune rule
  lets you delete yourself; a lane's vehicle is not.
- `--verdict-ref` carries the proof a reader can re-run: the merge sha plus the verified blob ids or the
  CI run id. It is the origin of the tick, so it must be a measured value, never "reviewed".

## When the seam refuses because of the heading

You cannot make the boxes tick without the canonical heading, and editing a **closed** issue's body to
satisfy the seam is a wire edit that must not be done on silence (no-consent-by-silence; "not manual").
The honest sequence:

1. Post the refusal durably on the issue: the exact command, the `BodyError`, rc, and the fact that the
   items ARE proven (the blob/run ids). A stranger must see the proof even at 0/5.
2. Ask the routing lane for one of: (A) explicit authorization to canonicalize the heading (a precise
   `gh issue edit`/body PATCH to bare `## Acceptance criteria`), then immediately re-run the seam — the
   ticking stays in the seam, only the heading gate is repaired; or (B) file it as a form-gate finding
   (the seam should lenient-match, or a canary should catch a non-canonical heading) routed
   `agent:implement`, leaving the issue documented-proven at 0/5 until the gate is fixed.
3. Never fabricate a "5/5 proven" read-back: the wire still shows 0/5 until one of the above runs.

## The other remedy: a `## Not covered` exemption in the PR body

Ticking the issue is one way to satisfy `check-pr-acceptance`; the gate itself also accepts an
**exemption written in the PR body**. When a criterion is genuinely out of a vehicle's scope (a
docs-only PR whose AC names an `agents/` file), this is the honest remedy — not a self-tick, and not
a claim that the criterion is satisfied.

Mechanics of `scripts/check_pr_acceptance.py::_declared_out_of_scope`, both required:

1. The `## Not covered` section must contain a line matching `^-.*\s*#\d+\s*$` — a **single line**
   starting with `-` and ending with a **bare** `#<n>`.
2. The criterion's leading three normalised words (`re.sub(r"[^A-Za-z0-9 ]", " ", text).lower()`, first
   3 tokens) must appear in that section's text.

The two formatting traps that silently fail BOTH checks:

- A **multi-line** bullet (text wrapped over several lines) never matches the `^…$` single-line regex.
- **Bold/backtick markup around the id** — `**#1234**` or `` `#1234` `` — does not match `\s*#\d+\s*$`;
  end the line with a bare `#1234`, no emphasis.

A bullet that mentions `docs/BOTS.md` can also accidentally exempt a *different* criterion whose
leading words are the same — write the exemption so only the intended criterion's lead is present.

**A criterion whose named target crosses the vehicle's own scope is the exemption case, not a
reason to widen the diff.** A docs-only PR ("no script, no Makefile target, no code") whose AC says
"link it from `agents/…/references/…`" cannot satisfy that AC without violating its own scope rule:
provide the in-scope equivalent where the doc already lives, file the cross-scope pointer as its own
follow-up issue, and name the criterion out of scope with that issue's number.

Verify locally against the **on-wire body**, not your draft file (the gate reads the PR body it is
given):

```bash
gh pr view <n> --repo <o/r> --json body --jq .body > /tmp/wirebody.md
python3 scripts/check_pr_acceptance.py check --body-file /tmp/wirebody.md --base origin/main --rev HEAD
# [check-pr-acceptance] OK — every closed issue's `## Acceptance criteria` is checked or named out of scope
```

## Closing-set mechanics: one keyword per issue, and the honest `does not close`

`check-pr-closing` compares two sets — the issues the **joined commit messages** close and the issues
the **PR body** closes — and reds when they differ, because the squash body is what `git log` keeps and
the PR body is what GitHub auto-closes from. Three consequences:

- The closing regex is `\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\s+#(\d+)`. A **comma is not a
  separator**: `closes #11, #12, #13` closes only `#11`. Repeat the keyword, one issue per line, in the
  body and the commit message alike.
- A branch that **carries a base PR's commits** (stacked) also carries that PR's `closes #N`, so `#N`
  must appear in your body too. When the base lands and you rebase, those commits leave the branch and
  `#N` must come **out** of the body in the same push.
- Naming an issue resolvingly without closing it is itself a red. If a PR genuinely cannot satisfy an
  issue's acceptance criteria (its remaining ACs name something that is not a repository artifact —
  a cron prompt, a live host profile), write an explicit `does not close #<n> because <reason>` note.
  That removes the issue from `check-pr-acceptance` entirely, which is the honest alternative to a
  self-tick or leaving the issue silently orphaned.

Related: the `BASE:` line must name the **same** `origin/main` sha as the `AGENTS:` line
(`BASE: <sha> (== origin/main at open)`). A branch name in that slot fails `agents-line`, and so does a
sha that differs from the `AGENTS:` one — "stacked on #N" belongs in prose, not in that line.

## Never call a gate red "by design" without reading its own logic

A red `check-pr-acceptance` (or any `scope` step) looks like the documented "un-reviewed merge stays
honest" state, so it is tempting to report it as by-design and move on. Before you do, open the gate's
source and test it against the real body: most such gates carry an exemption/repair path (a lenient
heading match, an out-of-scope declaration, a canary). A red you labelled by-design and never read is
a defect you left on the board — and a body-only edit needs a gate re-read to take effect. Check-runs are keyed to the head sha, so a
body edit alone re-triggers nothing — but you do not need a new commit to validate it: re-running the
failed jobs (`gh run rerun <run-id> --failed`) re-reads the PR body from the wire at run time, so the
corrected body is exactly what the gate judges. Push an empty commit only when you also need a fresh
head sha.

### Prove the red at the STEP level, not the check-run name

`gh pr checks` lists check-RUN conclusions (`guard  fail`, `scope  fail`, `ci-verdict  fail`), and three
failing names read as three independent broken gates. They are almost always ONE failing step mirrored
through the aggregating jobs: `guard` and `scope` both call `make check-pr-acceptance`, and `ci-verdict`
reads back the guard's scope-decision artifact. Read each job's own `steps[]` before you believe the
count:

```bash
gh api "repos/<o/r>/actions/runs/<run>/jobs" \
  --jq '.jobs[]|select(.name=="scope")|.steps[]|"\(.conclusion//"pending")  \(.name)"' | grep -i fail
```

That one command converts a hand-wave into proof: it shows every non-acceptance step (`make ci-lint`,
`check-docs`, `check-wiring`, `check-issue-bodies`, `check-pr-closing`, `check-pr-acceptance-form`) as
`success` and names the single `failure  make check-pr-acceptance`. Only then is "every controllable
gate is green; the sole red is the reviewer-gated write-back" a measured claim instead of an assertion.

### When the write-back is genuinely verdict-gated, completion is evidence + hand-off, never a self-tick

If the step-level read confirms the only red is `check-pr-acceptance` AND the boxes are proven, the
correct close-out is three things — a self-tick is never one of them (the seam's write-back belongs to
the lane holding the verdict, per the bounding rule):

1. Post the step-level evidence on the PR (which steps passed, the one that failed, and the per-AC proof:
grep counts, the twin test pass, the mutation-bites result).
2. Give the reviewer the exact command with a MEASURED verdict-ref (head sha + CI run id), e.g.
`acceptance_writeback.py writeback --issue N --proven 1,2,3,4,5 --verdict-ref '<review>/<sha>/<run>'`.
3. State plainly on the record that the PR is NOT claiming the acceptance gate passes — it cannot until
the reviewer ticks it. "Every verification in this lane's power is done and proven at `<sha>`" is the
honest terminal state; repeatedly re-asserting "it's by design" without the step-level read is what keeps
a completion guard (and a reviewer) from accepting the report.

## Don't reconstruct a merged fold's boxes by eye

If a dispatch says "tick the boxes via the seam", the deliverable is the seam's output (the issue
body's `- [x] … (proven: …)` lines, read back with `gh issue view N --json body`), not a claim that the
work is proven. Re-read the body after the run and quote the checked count — the seam's own write is
the fact.
