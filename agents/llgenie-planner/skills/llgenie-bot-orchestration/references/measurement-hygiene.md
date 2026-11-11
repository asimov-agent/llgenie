# Measurement hygiene: your own instruments are claims too

The core rule — "a report is a claim; the API is the evidence" — applies to YOUR OWN
local reads as much as a lane's. A stale tree, a shallow clone, or a malformed
`gh`/`jq`/`git` query yields a confident number that is simply wrong. Verify the
instrument before you report the finding, and never file an incident on a stale read.

## A structured-data probe that walks a dict as a list finds ZERO offenders — check the schema first

`grep` for a URL pattern and a hand-rolled walk over a JSON artifact are instruments that
fail SILENTLY to the wrong answer: they report `0 dead links` / `0 matches`, which reads as
"the premise is false" when the truth is "my walk never visited the values." Real shape: a
catalog artifact is `{meta, files}` where `files` is a **dict keyed by model id** (93 keys),
not a list — `files[0]` raises `KeyError: 0` and a recursion that only indexes lists returns
nothing. Walking the wrong shape found 0 dead links; a schema-aware recursion into dict
**values** found 16 genuine 404s at the same sha.

Rule: before trusting a `0`/`none` result from a probe over structured data, print the
container's type and a one-entry preview and confirm your walkers descend the actual shape
(`isinstance(o, dict)` → iterate `.items()`; `isinstance(o, list)` → iterate items; recurse
both). A `0` from a walk you did not schema-check is a claim about your instrument, not about
the data — and it is exactly the false negative that makes you call a real defect a flake.

## One shell block, several probes: never infer a probe's result from the block's later lines

`git ls-tree --name-only origin/main agents/llgenie-<lane>/` prints a directory listing, and a following
`git grep -l <pattern> origin/main -- agents/llgenie-<lane>/` prints `origin/main:<path>` for each MATCHING file.

**Feed a `git grep` tree-prefixed path back into `git rev-parse`/`git show` WITHOUT re-adding the
`origin/main:` prefix — it is already there.** `git grep -l pattern origin/main -- 'agents/*'` emits
`origin/main:agents/.../SKILL.md`; looping that string into `git rev-parse origin/main:$path` yields
`origin/main:origin/main:agents/...` and `fatal: path ... does not exist` — a self-inflicted
false-negative that reads as "the file is gone". Split on the first colon (tree, path) before
re-rooting:
```bash
git grep -lE '<pat>' origin/main -- 'agents/*' | while IFS=: read tree path; do
  echo "$path $(git rev-parse "$tree:$path")"
done
```

## `git fetch origin <sha>` populates the object store, NOT an `origin/<sha>` ref — `git show origin/<sha>:<path>` silently finds nothing

Fetching a single bare commit (`git fetch origin "$h"`, where `$h` is a PR head sha read from
`gh pr view --json headRefOid`) writes the commit into `FETCH_HEAD` and the local object store; it creates
**no ref named `origin/<sha>`**. So the very next `git show "origin/$h:<path>"` (or `git ls-tree "origin/$h"`)
resolves a ref that does not exist and prints **nothing** — which reads exactly like "the content is
absent / the vehicle did not land," the same false negative about your ref, not the tree. Read the fetched
object by its LITERAL sha:

```bash
h=$(gh pr view <n> --repo <o>/<r> --json headRefOid --jq .headRefOid)
git fetch origin "$h" 2>&1 | tail -1
git show "$h:agents/standing-rules.md"   # literal sha, NOT "origin/$h:…"
```

Only `origin/main` and branch refs you actually fetched live as `origin/<name>`; a bare sha is reachable
only by the sha string itself (or `FETCH_HEAD`). An empty result from `origin/<sha>:<path>` means "that ref
was never fetched," never "the file is gone" — confirm the exact ref name, then read by the literal sha
before concluding absence.

**An empty tree listing usually means the PATH is wrong, not that the content is missing.** Lane directories
are `agents/llgenie-<lane>/` and their skills sit at `agents/llgenie-<lane>/skills/llgenie-<lane>/SKILL.md`
with depth under `references/`. A `git ls-tree -r origin/main | grep agents/<lane>` or an
`ls-tree origin/main:agents/llgenie-<lane>/skills/...` guessed at the wrong depth returns NOTHING for a
branch whose files are all present, and the empty result reads as "content absent / vehicle not landed" — a
false negative about your glob, not about main. Print the parent first
(`git ls-tree origin/main --name-only agents/`) or the file's own content (`git show origin/main:<full/path>`,
which errors loudly on a bad path instead of printing an empty list) before concluding absence.
Run both in one block plus your own `echo "(grep empty = vehicle not landed)"` and it is easy to read the
tree lines as the grep result and conclude "empty" when the grep actually DID hit the lane's SKILL.md.
To decide "does lane X's skill already carry contract Y", run ONE labelled probe and read its matched
path, then read the matching lines themselves:

```bash
git show origin/main:agents/<lane>/skills/<lane>/SKILL.md | grep -n -A3 '<term>'
```

An "already landed" vs "vehicle owed" verdict gates a dispatch — confirm it from the file's own matching
lines, never from a combined block's trailing text or your own echo of what you expected.

## A lane's NEGATED existence claim ("not locatable", "no such file", "absent") is a PATH guess until proven

A refusal that rests on a negative lookup ("the contract text is not locatable under `agents/`", "the file
is absent", "nothing carries that") is the cheapest claim to disprove and the most expensive to repeat. It is
usually a search at the wrong depth/profile, not a real absence — and `git show <head>:<wrong-path>` printing
nothing with exit 0 is indistinguishable from "missing" unless you resolve the real path from the tree:

```bash
git -C <repo> ls-tree -r --name-only origin/main | grep -E '<basename>|<distinctive phrase>'   # real path(s)
git -C <repo> show origin/main:<that-path> | grep -nF '<the distinctive phrase>'              # proof present
git -C <repo> grep -nF '<phrase>' origin/main -- 'agents/*/skills/**'                        # every lane at once
```

State BOTH facts when a lane refuses on absence: (a) the phrase DOES exist on main, quoting the paths + blobs
(this refutes "not locatable"); and (b) whether the criterion actually requires THAT location — a per-lane
rollout criterion may need EVERY affected lane to carry it, so one lane missing is a real gap even when the
text exists elsewhere. Do not build a whole rebuttal on (a) alone; measure the criterion's true scope before
declaring the refusal false, and re-route on the corrected position when the lane self-corrects on the wire
(a reviewer retracting its own "not locatable" is the healthy outcome — accept it and re-confirm against the tree).

## Never declare a merge anomaly from the local `origin/main`
- Local `origin/main` in the primary clone lags the remote by however long since the
  last fetch (the primary clone here is owner-mediated and can be dozens of commits
  behind). "Merge commit is not an ancestor of main" and "change-note is not on main"
  are symptoms of a stale ref far more often than of a dropped merge.
- Before asserting a merge did not land, read the LIVE tip: `gh api
  repos/<owner>/<repo>/commits/main --jq .sha`, or `git ls-remote origin
  refs/heads/main`. If the PR's mergeSha equals that tip, the merge landed — full stop.
- **The same stale ref makes `git cat-file -e origin/main:<path>` report a file MISSING
  that IS on main.** A post-merge "the fix's files are absent from main" conclusion drawn
  before a fetch is the file-presence form of the stale-ref false negative: three merged
  files read `MISSING` off a ref that predated the merge, then all read `PRESENT` after
  `git fetch origin main`. Fetch immediately before any presence/size read, and gate the
  answer on `git rev-parse origin/main` == the API `main` sha — if they differ, your read
  is about a ref, not about main. Distinguish this from a real drop: a file genuinely
  absent at a FETCHED tip that equals the API head is the finding; anything measured off a
  lagging ref is not.
- Confirm the mergeSha is a real object before theorising a "phantom": `git cat-file -t
  <sha>`. `gh pr view` can report `state=MERGED` while the pulls API momentarily returns
  `mergedAt:null` for the same PR; the events feed's `merged` event carrying the commit
  sha is the authoritative record.
- **`state: closed` is not `merged`.** A PR the owner closed without merging and one the owner
  squash-merged both read `state: closed`; the only discriminators are `merged_at != null` (and
  `merged: true`). Before filing "the merge landed" or "the merge was dropped", read
  `gh api repos/<o>/<r>/pulls/<n> --jq '{state,merged,merged_at,merge_commit_sha,base:.base.ref}'`.
  `base.ref` must be `main` — a merged PR whose base was another branch landed on a stacked base and
  did NOT reach `main`.
- **The PR object has `merge_commit_sha`, never `merge_commit_url`.** Requesting
  `p["merge_commit_url"]` raises `KeyError` inside a probe script and kills the whole sweep mid-loop
  (so later PRs print nothing and read as "missing"). Use `merge_commit_sha`, or the
  `pulls/<n>/commits` endpoint. When a multi-PR probe dies on a KeyError, the empty rows after it are
  the crash, not absent data — re-run with the field name confirmed against one PR first.
- **Merged content is verified in the TREE, not by the PR's state.** After a confirmed merge, prove
  the change actually reached `main` with a tree probe: `git/trees/main?recursive=1` and look for the
  expected paths (skill dir, `openspec/changes/<name>`, `docs/changes.d/<row>`, the script+test pair).
  A squash merge can land while a file from the diff is absent because it was dropped in the squash —
  the tree is the evidence, the merge sha is only the vehicle.

## A merge is a FOUR-fact verification — and the auto-merge bot's own disclosure comment names the run

`merged:true` on the pull payload is one fact out of four. Record a landing only after reading all four:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '{state,merged,merged_at,base:.base.ref,head:.head.sha,mc:.merge_commit_sha}'
gh api repos/<o>/<r>/commits/main --jq .sha                                   # main tip == mc ?
gh run view <merge-run-id> --repo <o>/<r> --json status,conclusion,headSha    # completed, not cancelled
gh api repos/<o>/<r>/commits/<mc>/check-runs --jq '[.check_runs[].conclusion]|group_by(.)|map({(.[0]):length})'
```

- **`base.ref` must be `main`.** A stacked PR's merge lands on its stacked base and never reaches `main`, so
  the merge sha will not be the main tip — that is the discriminator, not the `merged` flag.
- **Read the merge run id off the thread instead of hunting `actions/runs`.** The auto-merge job posts its own
  disclosure comment (`<!-- auto-merge: merged <head-sha> -->`) carrying the run id, the judged head sha and
  the decision; that comment is the cheapest authoritative source for the run you must then `gh run view`.
- **`mergeable: null` / `mergeable_state: unknown` immediately after a merge is a recompute artefact, not an
  error state.** GitHub nulls those fields once the PR is closed; re-reading them in a loop never converges.
  Grade the merge on the four facts above and move on.
- **A `blocked` → `dirty` flip right after a `main` advance is the recompute catching up, not a new defect.** It
  confirms the PR is behind the new tip; the action is the rebase dispatch already owed, not a fresh diagnosis.
- **A vehicle's `closes <umbrella>` does not oblige one vehicle to prove the umbrella's cumulative criterion.**
  In a multi-lane rollout (N vehicles, one umbrella) a single vehicle's post-merge acceptance is its OWN
  lane-scoped items; the all-lanes criterion stays on the umbrella as a running count ("N/5 merged, remaining
  #x #y"), never ticked by one vehicle's merge. Reading a lane-scoped `- [x]` set as a claim on the cumulative
  criterion mis-grades both the vehicle and the umbrella.

## Sweeping what moved since your last pass: the `?since=` comments filter, filtered to real lanes

To answer "has any lane posted since my last pass", one call beats N per-issue reads:

```bash
gh api "repos/<o>/<r>/issues/comments?since=<ISO8601-UTC>&per_page=60" \
  --jq '.[]|select(.user.login!="andyholst" and .user.login!="github-actions[bot]")|"\(.created_at[11:19])Z \(.user.login) #\((.issue_url|split("/")[-1])) len=\((.body|length)|tostring)"'
```

- `since` is a strict timestamp filter and is honoured (unlike `sort`/`direction`, which the endpoint ignores), but
  it also returns the fleet's own auto-merge stubs and workflow comments — filter those logins out or the sweep
  reports "lanes are active" on bot bookkeeping.
- **An empty result is a claim about that timestamp, not about the board.** Lane posts can land a few seconds after
  your `since` value; re-anchor `since` to the newest id you actually read, not to the time you started the pass.
- Pair the sweep with per-object reads for the objects you intend to act on — the sweep says *who posted*, never
  whether the PR head moved or the run concluded.

## A branch's real delta is a THREE-dot diff — two-dot shows the owner's staleness as the branch's change
- `git diff --name-only origin/main <branch>` (two-dot) is a straight TREE comparison. If
  `<branch>` was cut from a local `main` that is dozens of commits behind the live tip, the
  two-dot diff reports **every file the owner changed since** as if the branch touched it —
  a one-file deliverable reads as `754 files changed`, and you will waste turns concluding
  your branch is polluted when it is not. Fetching `origin/main` does not fix this: the
  branch's own base is the stale commit, so the merge-base is what it diverged from.
- Measure a branch's real delta with three-dot, which diffs from the merge-base:
  `git diff --name-only origin/main...<branch>` and `git rev-list --count origin/main..<branch>`.
  Three-dot shows ONLY what the branch added on top of where it forked. Sanity-pair it with
  `git merge-base origin/main <branch>` and confirm the file count matches the commits you
  actually authored.
- **`git merge-base --is-ancestor origin/main <branch>` returning "diverged" is the same stale-base
  artifact, not a real problem** — a branch forked from an old `main` genuinely has the current `origin/main`
  tip as a non-ancestor. That does not mean it collides with `main`; it means the branch
  is behind. Distinguish "behind" (`behind_by > 0`, rebase owed) from "diverged/conflicting" by
  the compare endpoint (`behind_by`/`status`, see the PR-ancestry section above), never by the
  local two-dot diff.

## Ancestry checks fail on a shallow clone
- `git merge-base --is-ancestor` returns non-zero on a shallow clone REGARDLESS of the
  truth, because the parent chain is truncated. A "NO" from an ancestry check on a
  shallow clone proves nothing either way — do not act on it.
- If you must run one, deepen first: `git fetch --unshallow` or `git fetch
  --deepen=<n>`. Mind the syntax: `git fetch depth=1` (no leading dashes) does not
  shallow-clone; it must be `git fetch --depth=1`.
- **A repo GATE that shells out to the same primitives inherits the false negative — a
  gate red that appears ONLY in a worktree off the shallow primary clone, and never in
  official CI, is a checkout-depth artefact, not a document/content defect.** A gate built
  on `cat-file -e <sha>^{commit}` / `merge-base --is-ancestor` (llgenie's
  `scripts/check_architecture_census.py` is one) reports "not a real commit / no usable
  referent" and exits non-zero when the far-back `measured at <sha>` pointer object is not
  fetched — while the same gate passes under CI's `fetch-depth: 0` full checkout, so it
  reds EVERY fresh main-cut PR pushed from a worktree off the shallow primary. Before
  adjudicating a pointer/pin red as DOC-wrong: `git rev-parse --is-shallow-repository`;
  if `true`, deepen (`git fetch --unshallow`) and re-run. Clean locally + green in CI =
  the PR is not the defect: file it against the GATE (a checkout-depth diagnostic that
  probes object reachability and exits distinct from "doc is wrong", mirroring the
  existing unreadable-object guard), and never re-pin the pointer to appease it.

## PR ancestry vs #792 preflight: verify both before calling a PR reviewable
- **Ancestry without a clone branch:** prove a PR head descends from the live main tip with the compare endpoint, not a local merge-base (which inherits shallow-clone false negatives): `gh api repos/<o>/<r>/compare/<live-main-tip-sha>...<head-sha> --jq '{ahead_by,behind_by,status}'`. `behind_by: 0` + `status: ahead` means the head already contains the live tip — no rebase owed, the `check-pr-base` gate is satisfied. `behind_by > 0` is the real finding (needs rebase), file/dispatch it.
- **#792 preflight lives in the PR body, not the checks:** every bot PR must carry `AGENTS: <sha> <lines>` and `BASE: <sha> (== origin/main at open)` lines in the body. Audit with `gh api repos/<o>/<r>/pulls/<n> --jq .body | grep -nE 'AGENTS:|BASE:'`. A missing line is a body-hygiene defect the lane must fix (route it), not a green.
- **`--is-ancestor` on a full sha that was never fetched fails `fatal: Not a valid object name`, even when `merge-base A B` just printed that tip as an 8-char abbrev.** The commit is reachable through an already-fetched branch graph (so `merge-base` resolves it) but its own object is not in the local store, and `--is-ancestor <40-hex>` demands the exact object. Do not `git fetch origin <full-sha>` (fails `couldn't find remote ref`); fetch the PR ref (`git fetch origin refs/pull/<n>/head`) or any branch containing it, then run the ancestry test on the **8-char form `merge-base` printed**, not the 40-hex you pasted from the PR body. Getting this wrong reads as `ancestor=False` and produces a FALSE "reddens the AGENTS gate" verdict on a citation that actually passes.
- **The AGENTS/BASE citation must be an ancestor of BOTH head AND base — and after a main advance the two diverge.** A branch cut before a later main merge has merge-base `<old>` (still ancestor of both, so `<old>` passes NOW) while the new main tip is an ancestor of the BASE but NOT of the un-rebased head (so citing the new tip reddens until a rebase lands). Correct order when the PR is also stale-based (`check-pr-base` red, merge-base ≠ base #1015): rebase onto current main FIRST, then cite `AGENTS==BASE==<new tip>` — do not let a reviewer's "measured at current main" remedy paste a sha that reddens on the current head.
- **Gates at a discovered head, not the PR's stale cached rollup:** `gh api "repos/<o>/<r>/commits/<head-sha>/check-runs?per_page=100" --jq '{red:[.check_runs[]|select(.conclusion=="failure")|.name],inprog:[.check_runs[]|select(.status=="in_progress" or .status=="queued")|.name]}'` reads the actual per-commit runs, including `in_progress` legs a `gh pr checks` summary hides.

## An aggregate rollup count hides WHICH cell is pending — name it before you report

`in_progress:1, success:13, 0 failure` tells you a heavy row is running, not *which* one. A pending
`linux/unit` cell means "wait for it to conclude" (owner-gated, not reviewable yet); a pending
**data-gate** cell means a lane still owes the authoritative fix and you must dispatch. Same count,
different owed action — so never infer the pending cell's identity from the aggregate. Filter to it:

```bash
gh api "repos/<o>/<r>/commits/<full-40-sha>/check-runs?per_page=60" \
  --jq '(.check_runs // .)[]|select(.status=="in_progress")|{name,started_at,details_url}'
```

Read `.name` (and `details_url` for the run/job ids) before deciding reviewability or dispatching.
A pending cell still `in_progress` with no `concluded_at`, started within its historical baseline
(measure the baseline off a recent green run — unit ~583s here), is **slow, not stuck**; the forward
move is to dispatch the owning lane to read that exact job's log (`references/actions-job-log-reading-midrun.md`),
not to declare the PR green or red.

## `gh pr checks` conflates every run of a check NAME — measure the LATEST per name by `completed_at`

A head that was pushed, re-run, or body-restamped carries MULTIPLE check-runs with the same name
(two `guard` entries, an old `FAILURE` from a pre-fix run and a fresh `SUCCESS` after a rerun, a
`ci-verdict` computed mid-flight that another run later overtook). `gh pr checks` and a naive
`statusCheckRollup` grouping by name will show both, and reading the wrong one reds a PR that is
actually green — or greens one whose newest run failed. The current gate state is the newest run of
that name at this head, keyed on `completed_at`:

```bash
sha=$(gh pr view <n> --json headRefOid --jq .headRefOid)
gh api "repos/<o>/<r>/commits/$sha/check-runs?per_page=100" --jq '
  [.check_runs[]|{name,conclusion,at:(.completed_at//.started_at//"")}]
  | group_by(.name)[]
  | {n:.[0].name, latest:(sort_by(.at)|.[-1].conclusion), at:(sort_by(.at)|.[-1].at)}'
```

Read `latest`, never the presence of any `success` or any `failure`. Pair it with the run's
`run_started_at` versus the body-edit/rerun time (`second-gate-stale-base-and-stuck-run.md` §stale-body):
a `failure` whose run predates the fix is stale evidence about an older body/head, and the remedy is
a rerun/new head, not a re-fix. When the answer decides a dispatch, quote the `latest` conclusion AND
its timestamp per check name — a bare "guard is red" from a rollup is a claim about your grouping.

## A verdict/summary check-run is a snapshot at its OWN compute time — re-read the run it references before believing its embedded reason

A verdict check (`ci-verdict`, or any aggregate "verdict" gate) can complete `failure` while the
workflow run it judges is still `in_progress`, and its `output.summary` can assert a cause the wire
contradicts. Measured: a `ci-verdict` check-run completed `failure` with a summary naming run X as
`conclusion=failure` and claiming `[ci-scope] guard FAILED` — but run X was still `in_progress` with
only one heavy cell running, and the `guard` job was `success` with nine sibling cells green. The
verdict was computed mid-flight against an incomplete run, and its own cause claim was wrong.

Rule: a verdict check-run's conclusion AND its embedded reason are claims about the state at
computation time, never about now. Before relaying a red, read the referenced run's live status and
the named job's own conclusion:

```bash
gh api repos/<o>/<r>/actions/runs/<run-id> --jq '{status,conclusion}'
gh api repos/<o>/<r>/actions/runs/<run-id>/jobs --jq '.jobs[]|"\(.conclusion//\"in_progress\")\t\(.name)"'
```

If the run is still `in_progress`, the verdict is **premature, not binding** — say so and let it re-run
against the concluded snapshot (green clears it, red becomes a real classifiable failure). If the
verdict's named cause contradicts the live job conclusion, quote the ACTUAL conclusion and retract the
verdict's reason. Never dispatch a re-fix on a stale verdict's stated cause — that sends the lane to
fix a defect the wire does not show.

## A long matrix sweep: census its JOBS to turn "in progress" into a verdict — never wait for the run to finish

A sweep run sitting `in_progress` for 20+ minutes tells you nothing actionable, and "wait for the sweep" is
how a pass ends idle. The run's per-job conclusions decide the criterion long before the run concludes:

```bash
gh api "repos/<o>/<r>/actions/runs/<run-id>/jobs?per_page=100" \
  --jq '.jobs[]|"\(.conclusion//"in_progress")\t\(.name)"' | sort | uniq -c | sort -rn   # census
gh api "repos/<o>/<r>/actions/runs/<run-id>/jobs?per_page=100" \
  --jq '.jobs[]|select((.conclusion//"in_progress")|test("fail|cancel|in_progress"))|"\(.conclusion//"ip")\t\(.name)\tjob=\(.id)"'   # offenders only
```

- **An isolated failure is a stronger, more useful fact than the run's aggregate verdict** — "1 failure, and it
  is cell X while every sibling cell in the same family is green at this head" localises the blocker to one
  issue's domain, and it also proves any sibling fix already shipped at this head DID work. Report the census,
  the offending job id and its conclusion time; do not report "sweep still running".
- **Name which pending cells can change the criterion.** Two `in_progress` cells that are not in the failing
  family cannot flip a verdict already decided by a concluded failure — say so explicitly instead of making the
  reader wait, and re-measure next pass rather than polling in-turn.
- **Re-measuring the same run later IS new evidence, not a repeat.** A census taken 10-20 minutes after the
  first (jobs that were `in_progress` now concluded, the failure now provably isolated) is a different fact
  about the same object; post it as a confirmation of an earlier prediction, quoting both census counts.

## Compare shas at EQUAL length — a short-vs-long prefix reads as a false mismatch
- `git rev-parse --short HEAD` yields 7-8 chars; `gh api … --jq '.commit.sha[0:9]'` yields 9. Comparing the two
  with `[ "$H" = "$T" ]` prints `NO` on the SAME commit — a length artifact, not divergence. This is the
  classic "my instrument reported a drift" false positive: it looks exactly like a real mismatch and sends you
  chasing a rebase that is not owed.
- Fix: normalize both sides to the same prefix length (`${sha:0:9}` on each) or compare full 40-char shas
  (`git rev-parse HEAD` vs the API's full `.commit.sha`). Before reporting "branch diverged / not pushed", re-run
  the comparison at equal length — a `MATCH=NO` from unequal truncation is a claim about your format string.
- **A prefix compared against a hard-coded literal of a DIFFERENT length can never be equal, so a
  `!=` -guarded branch fires EVERY time.** `sha` read as `sha[:12]` (`781f698a7e34`) tested against the
  literal `'781f698a7e'` (10) is unequal at the first compare even though it is the SAME commit — so a
  script whose `if tip != 'known-sha': print("MOVED")` reports movement on every run, and the "moved"
  path is the one that posts. Write the test as an equality on equal-length substrings
  (`sha[:10] == known[:10]`) and make "changed" require a genuine difference, never a length artefact.
- **A false "branch/criterion MOVED" claim that reaches the wire must be retracted on-issue in the same
  pass.** The cost is not the wasted turn: the board now asserts a state change that did not happen and
  the next reader acts on it. Post a correction that (a) names the earlier comment id, (b) states the
  measured truth (tip unchanged, same commit object, its committer date), and (c) restates the routing
  that does apply — then verify the correction by its id like any other mutation. After such a near-miss,
  re-read the comparison line of the script before the next POST in that pass; the same instrument is
  still live in the loop and will fire again.

## `--is-ancestor A B` is TRUE when A==B — using it as a stale test labels a CURRENT base as stale

`git merge-base --is-ancestor <base> origin/main` returns success for TWO distinct states: `<base>` is
**strictly behind** main, AND `<base> == main`. A loop that maps `ancestor==true` → "STALE" therefore
mislabels every already-current PR as behind — an inverted-instrument false positive that makes you
dispatch rebases nobody owes (and, in a "which PRs are stale" sweep, over-reports the whole board).
Measured: a base that exactly equalled the live main sha read as `STALE`.

Fix: a stale test needs the **behind COUNT**, or an explicit equality branch:

```bash
M=$(gh api repos/<o>/<r>/commits/main --jq .sha)
for n in $(gh pr list --state open --json number --jq '.[].number'); do
  b=$(gh api repos/<o>/<r>/pulls/$n --jq .base.sha)
  if [ "$b" = "$M" ]; then echo "#$n CURRENT"
  else echo "#$n STALE behind_by=$(( $(git rev-list --count "$b..$M") ))"; fi
done
```

`git rev-list --count <base>..<main>` is >0 only when base is genuinely behind; equality is its own
branch. Same family as the equal-length-sha trap — the instrument collapses two states into one and
the reported number is a claim about your test, not about the wire. When a stale sweep flags a PR,
re-confirm with `compare/<main>...<head> --jq '{behind_by}'` before dispatching a rebase.

## An EMPTY `git merge-base` output is UNKNOWN, never "CURRENT" — a failed-object loop reads as "nothing stale"

A base-staleness sweep shaped `MB=$(git merge-base <head> origin/main); [ "$MB" = "$ORIGIN" ] && echo CURRENT || echo STALE`
reports **CURRENT for every PR** when `git merge-base` prints nothing (empty stdout) — because `"" = "$ORIGIN"`
is false only if ORIGIN is non-empty, but a loop that compares an empty `$MB` against a variable that also
failed to resolve, or an `||` branch that defaults to "current", silently maps "could not compute" to "up to
date." Measured: a whole open-PR board read `CURRENT` off a merge-base loop whose objects were never fetched
(heads given as short/bare shas, `fetch` silent-failed); the real base-stale PRs only surfaced after re-running
the same loop with full 40-hex heads and confirming `behind_by` per PR. An empty result from an instrument that
can fail is the SAME silent false negative as an unchecked walker returning `0` — treat it as UNKNOWN.

Rule: never let an empty/errored merge-base resolve to "CURRENT." Either
(a) measure behind-ness from the compare endpoint, which returns a real number or an error you can see:
```bash
M=$(gh api repos/<o>/<r>/commits/main --jq .sha)          # full 40-hex
for n in $(gh pr list --state open --json number --jq '.[].number'); do
  H=$(gh pr view $n --repo <o>/<r> --json headRefOid --jq .headRefOid)
  gh api "repos/<o>/<r>/compare/$M...$H" --jq '"#'$n' behind_by=\(.behind_by) status=\(.status)"'
done
```
or (b) if you use local `merge-base`, make a missing sha a LOUD error (`git cat-file -e <head> || echo MISSING`) and
compare only full 40-hex values, printing the real merge-base sha so a blank line is visibly "I could not measure",
not a green. A sweep whose every row reads CURRENT is a claim about the instrument until one row is proven behind.

## A script that measures AND posts must print its verdict before it posts — never fuse the two

When one probe both reads state and chooses which on-wire claim to send
(`if tip != known: post("MOVED") else: post("held")`), a malformed comparison publishes a false
board fact with no human in the loop. Measured: the same unequal-length sha test fired twice in one
session and each time posted "branch MOVED" for a frozen branch.

- **Split the turn: measure, read the verdict, then post.** Run the probe with the chosen verdict
  PRINTED (`print('verdict', tip[:10], known[:10], changed)`) and no write; post in a separate call
  once the printed values agree by eye. Cost is one extra call; the alternative is an on-issue lie.
- **Fail closed on the negative branch.** The default/fallback message must be the no-change one, and
  "changed" must require a positive match of a freshly measured value against a freshly measured
  baseline — never against a literal you typed from memory.
- **If a fused script already posted a false claim, the correction is the mutation** — retract by
  naming the wrong comment id, the measured truth, and the routing that still applies; verify the
  correction by its own id (`measurement-hygiene.md` §equal-length shas).

## A local gate probe does not clear a completion/mutation guard — it reads as test-only

Running a gate yourself (`make check-quant-catalog LIVE=1`, a `make ci-unit`, any test/verify target)
from a worktree or `git archive` tree is classified by the mutation guard as a **read/search/test**
action and refused (`Read/search/test-only actions are paused; mutation tools remain available`).
Do not treat "run the gate locally to prove it green" as the mutation that satisfies the guard: the
in-seat mutation is a board write (a dispatch to the owning lane, an on-issue comment) or a refine
of the issue, never a local build you launch. Decide the mutation from state you already hold.

## Shell: backticks in a heredoc/printf POST body run as command substitution
- Building a comment/PR body in a shell heredoc or `printf '%s\n' "$BDY"` where the text itself contains
  backticks (inline code around a sha, a quoted make target) makes the shell execute the backticked span: a sha
  in backticks fires `<sha>: command not found` on the subshell line, and the character is consumed from the
  body. The POST can still succeed with silently mangled text. Either escape/omit backticks in the body, or
  write the body to a file with a **quoted** heredoc (`<<'EOF'`, which never substitutes) and
  `gh api … -F body=@file`. After any body built through shell interpolation, read the posted text back
  (`gh api …/issues/comments/<id> --jq .body`) and confirm its length and first lines — a 0-exit POST is not
  proof the body landed intact.

## Shell: nested `$( )` inside a for-loop `gh` call breaks under `eval`
- Putting a `$()` subshell (e.g. `HS=$(gh api ...)`) *inside* a `for` loop body that also runs another command with nested parens in a quoted jq expression can abort the whole script with `syntax error near unexpected token '('` — the terminal wrapper runs the block through `eval` and the nesting misparses. Fix: assign the subshell on its own line first (`HS=$(...)`), then use `$HS` in the next command; keep each jq filter in single quotes with no interpolated command substitution inside it. A silent empty stdout from the broken line is not "no rows" — read the exit code.

## jq: `\s` / `\d` inside a double-quoted `--jq` string is a shell escape error, not a regex
- Interpolating a shell variable into a double-quoted `--jq` filter that ALSO contains a regex
  class like `\s` or `\d` aborts the whole call: `failed to parse jq expression … invalid escape
  sequence "\s" in string literal` (and it prints the literal filter line, which reads like a
  syntax bug in your jq). The shell consumed the backslash before jq ever saw it. Two fixes: put
  the filter in SINGLE quotes and let `gh` interpolate nothing (assign `$N` into the filter only by
  concatenation, not shell expansion inside the quotes), or avoid shell interpolation entirely by
  piping to real jq (`gh api … | jq --arg n "$N" '<filter using $n>'`) where the backslash survives.
- When one field of a multi-field sweep errors, the OTHER fields still print per row — do not read
  the partial output as success. A `for` loop that computes a `test(...)` count and a title in the
  same row prints the title and a `failed to parse jq expression` string for the count: the issue
  rows look populated while the PR-count column is garbage. Re-run the count query on its own, clean.
  To map open PRs to the issues they close, read each PR's `closes/fixes #N` from `.body` with
  `scan("#[0-9]+")` (or grep the plain body) rather than a regex `test()` carrying `\s` word bounds.

## jq object construction: only same-name fields can use bare shorthand; computed values need `"k": <expr>`

`{state, head:.head.sha[0:7]}` is valid (`state` is the `.state` shorthand), but a parenthesised
conditional as an object VALUE needs an explicit key — `{state, (.mergedAt?"x":"y")}` errors
`unexpected token`, because jq cannot infer a key from an arbitrary parenthesised expression. When
building a multi-field `--jq` object, give every computed value the explicit `"key": <expr>` form;
drop the `"k": .k` pair only for same-name fields. The parse error prints your literal filter line,
which reads like a syntax bug in your query — it is; read the column the parser flags, not the whole call.

**A numeric (or numeric-string) object key must be quoted.** Building a per-issue/per-PR map like
`{1812:{state,stateReason}, 1804:{...}}` errors `unexpected token "1812"` — jq parses a bare digit
run as a number literal and cannot use it as an unquoted identifier key. Write `{"1812":{state},
"1804":{...}}` (key in double quotes) or let the number be a value, not a key
(`{n:.number, state:.state}`). The error prints your literal filter line, which reads like a syntax
bug in the query rather than "quote the key" — and the empty stdout that follows is not "no data".

## jq: a boolean is not a string
- `(.body | test("## Acceptance"; "i"))` is fine, but applying `test(...; "i")` to an
  already-boolean value errors `cannot be applied to: boolean`. Compute each `test`
  separately and combine with `and`/`or`, or wrap so the input is always a string.
- When a `--jq` filter errors, `gh` prints to stderr and exits non-zero; the empty
  stdout is NOT "the field is empty" — read the exit code before concluding.
- **An EMPTY ARRAY is a legitimate payload, not a broken call — but read it clean before you base a gate
  on it.** `pulls/<n>/reviews` returning `[]` (or `--json reviews` giving `[]`, or `latestReviews` empty)
  is the wire saying "no review has been submitted", and that is a LOAD-BEARING fact when you are about
  to dispatch a reviewer for a verdict-gated tick or assert "no verdict exists yet". Confirm it with a
  counted raw read — `gh api repos/<o>/<r>/pulls/<n>/reviews | python3 -c 'import sys,json;
  print(len(json.load(sys.stdin)))'` — and note the difference in kind: a counted `len==0` from an
  UNFILTERED endpoint is evidence; an empty stdout from a FILTERED `--jq` is a broken filter matching
  nothing, which proves nothing either way. Also stop paying for nested-quote jq: a filter like
  `map(select(.state!="PENDING"))[] | ...` wrapped in a double-quoted shell string must escape every
  inner quote (`\"` → `\\\"` chains) and fails as `unexpected token "\\"`; fetch the raw array and
  filter in python (or put the jq in SINGLE quotes) instead of retrying the escapes.
- **`--paginate` changes the response SHAPE of a list endpoint — `.check_runs` disappears.**
  `gh api repos/<o>/<r>/commits/<sha>/check-runs` returns `{total_count, check_runs:[...]}`,
  so `.check_runs[]` parses. Add `--paginate` and `gh` concatenates the pages into a **bare
  top-level array**, so the same `.check_runs[]` filter errors `Cannot index array with string`
  (or a raw `unexpected token`). Parse defensively when you need all pages — read either shape:
  `jq '[ (if type=="array" then . else .check_runs end)[] | select(...) ]'` — and never treat the
  jq error's empty stdout as "no rows". A per-page `per_page=100` on a commit with <100 checks does
  not need `--paginate` at all; drop it and keep `.check_runs[]`.
- **`.[-N:]` on a list endpoint's default page is NOT "the newest N".** A paginated collection (issue/PR
  comments, branches) returns one page by default (30 for comments), so `.[-3:]` slices the tail of
  that first page — rows from dozens ago when the collection is larger, which reads as "the latest
  comments are old" and hides the POST you just made. Safe forms: `--paginate` then slice
  (`gh api --paginate ... | jq '.[-3:]'`), or ask for the newest directly
  (`?per_page=100&sort=created&direction=desc` then `.[0:3]` — but verify the sort params actually
  applied, they are silently ignored on some list endpoints). The only certain way to confirm a
  specific comment POST landed is to GET its id: `gh api repos/<o>/<r>/issues/comments/<comment_id>`
  returns body/author/timestamp or a 404 — a slice of a list proves neither presence nor absence.
- **Take that id straight from the URL `gh issue comment` prints** (`…/pull/<n>#issuecomment-<id>`)
  and GET it. Do NOT re-derive "the newest id" by fetching a comment page and slicing/sorting it —
  the nested `$(curl … | python …sorted(...)[-1])` inside the receipt call re-hits the pagination
  trap above and returns a stale id, so the GET verifies the WRONG comment and reads as "my post is
  missing / old." The POST's own printed URL is the deterministic id; quote it.

## jq: `[-1]` is an ARRAY LITERAL, not the last element — `.[-1]` indexes

`gh api <list-endpoint> --jq '[-1] | .created_at'` fails `expected an object but got: array ([-1])`:
at the START of a filter `[ … ]` CONSTRUCTS an array (`[-1]` = a one-element array holding -1); it does
not index, so the next `.created_at` is applied to it. Index with the dot: `.[-1] | …` (or `.[-1:]`).
The error text prints the constructed array — read it as "your filter built that array, it did not index".

## jq: nested quotes / regex + `gsub` in a `--jq` body filter is a parse trap — read `.body`, grep it in the shell

Counting or reshaping issue/PR body text inside `--jq` (e.g. turning each `- [ ]` into `[` to count ACs) needs a
replacement arg with its own quotes and escapes: `gsub("(^|[\\n])\\s*- \\[ \\]";"[")`. That dies
`failed to parse jq expression … unterminated string literal` — jq's parser cannot reconcile the nested `"` and the
escaped `\[`/`\\s` classes inside the replacement string, and the printed filter line reads like a quoting bug in
your shell. Do not fight it: fetch the raw field and process it in the shell.

```bash
gh api repos/<o>/<r>/issues/<n> --jq '.body' | grep -c '^- \[ \]'      # unticked AC count
gh api repos/<o>/<r>/issues/<n> --jq '.body' | grep -cE '^## (What|Verification|Acceptance criteria|Not covered|Technical)'  # section count
```

General rule: keep `--jq` to FIELD SELECTION (`.body`, `.name`, a scalar) and do any text counting/slicing/shaping
with shell `grep`/`sed`/`awk` on the emitted text — the same reason you never pipe `--jq` output into a JSON parser.
When a `--jq` filter errors, its empty stdout is not "0 matches" — a failed section-count grep and a genuine zero
look identical in a multi-line block, so re-run the count on its own and read the exit code.

## jq: `not in [...]` is a SYNTAX ERROR — `not` is a zero-arg filter, not an infix operator

`select(.user.login not in ["a","b"])` dies `failed to parse jq expression … unexpected token "not"`
— jq has no infix `in`/`not in`; `not` is only a 0-arity filter applied with a pipe, and `in(obj)`
tests membership in an object, not a list. The clean filter-login exclusion is an explicit inequality
chain:

```bash
--jq '.[]|select(.user.login != "andyholst" and .user.login != "github-actions[bot]")'
```
or the membership form `select((["andyholst","github-actions[bot]"] | index(.user.login)) == null)`.
The parser prints the whole filter, which reads like a bug in the surrounding pipeline; the flagged
column (`not`) is the real fault, and the empty stdout that follows is not "no rows".

## A lane can POST the identical comment several times within seconds — dedupe by body before counting

Fetching a thread can return the SAME comment body at 5 consecutive timestamps (`:49 :50 :52 :53 :55`)
from one lane — a posting-path retry, not five distinct mutations. Do not report it as the lane "posted
the update 5×" as if it were five actions, and do not count those rows as five board facts. Deduplicate
on the body text (identical length + identical first line) and treat the cluster as ONE post; note the
duplicate as a harmless posting-path artefact only if it is worth a line at all. The same dedupe applies
to your own re-POSTs: a guard-bounced comment retried on a flaky channel can land twice — keep the
newest id and delete the extra so one trail survives.

## jq: `+` needs matching types — concatenate string and number with interpolation, not `+`

`(.createdAt[11:19]) + "Z " + .databaseId` dies `cannot add: string and number` — `+` requires both
operands to be the same type (strings with strings, numbers with numbers). Build the whole line with one
interpolated template: `"\(.createdAt[11:19])Z \(.databaseId) \(.workflowName)"`. This is the clean
form for any `gh run list --jq` / `gh api --jq` row listing where a numeric id sits beside timestamps.

**`(.body|length)` and any `|length`/`|tonumber` result are numbers too.** A receipt row like
`(.created_at[11:19])+"Z "+(.user.login)+" len="+(.body|length)` dies the same
`cannot add: string … and number`, and the error text quotes only part of the row, which reads like
the timestamp slice is the bug. Either interpolate it (`"… len=\(.body|length)"`) or wrap the numeric
operand: `"… len="+((.body|length)|tostring)`. When one row of a multi-issue loop errors this way, the
other rows still print — re-run the broken row alone rather than re-reading a half-populated table.

## jq: an escaped/unbalanced paren in `test("…")` breaks the whole filter — keep alternations bare

`test("docs|documentation|doc\\(|wiki")` aborts `failed to parse jq expression … unexpected token "|"`
— the escaped `\(` opened a group the pattern never closes. Use plain alternations of literal words with
no escaped metacharacters (`test("docs|wiki|skill")`) instead of trying to match punctuation; when a
filter dies inside a loop the OTHER columns still print, so a populated-looking row can hide a garbage
column. Re-run that one query on its own, clean.

## `gh api --jq` is NOT jq — `--arg`/`--argjson` become stray POSITIONAL args (`accepts 1 arg(s), received N`)
- `gh api`'s `--jq` flag takes ONE filter string; passing jq's own `--arg n "$N" '<filter using $n>'` after it
  makes `gh` consume `--arg` as the flag's value and leaves `n`, `$N`, and the filter as extra positional args,
  so the call aborts `accepts 1 arg(s), received 4` (or however many tokens). This bites hardest in a `for` loop
  where each iteration musts interpolate the PR/issue number into the filter.
- Two clean fixes: (a) interpolate the shell variable into the single-quoted filter with a double-quoted shell
  wrapper — `gh api repos/<o>/<r>/pulls/$N --jq "{head:.head.sha[0:9],base:.base.sha[0:9]}"` — or (b) pipe to real
  jq when you genuinely need `--arg`: `gh api repos/<o>/<r>/issues --paginate | jq --arg n "$N" '...'`. Prefer (a);
  a simple one-PR-per-call read rarely needs `--arg` at all, so drop it rather than fight it.
- A `--jq` error prints to stderr and exits non-zero; empty stdout is not "no rows" — read the exit code.

## `gh api` has no `--state` — a list endpoint's filters are query params, not `gh pr list` flags

`gh api repos/<o>/<r>/pulls --state=open` dies `unknown flag: --state` and prints the whole gh help block, which
reads like a broken command rather than a wrong tool. `--state`, `--limit`, `--search` belong to the porcelain
commands (`gh pr list`, `gh issue list`); `gh api` takes a raw path plus `--paginate`/`--jq`/`--method` only. To
filter an `api` list, either put it in the path query string (`repos/<o>/<r>/pulls?state=open&per_page=100`) or
leave the path bare and filter in jq (`--paginate --jq '.[]|select(.state=="open")'` — `pulls` already returns
open ones by default, so the filter is usually redundant). Prefer the `--paginate` form for "every open PR":
the default `pulls` page is 30 and a `pulls` list without `--paginate` silently truncates the board.

## A "re-authored" / "reset identity" claim — verify the COMMIT AUTHOR, not that the head moved

A lane dispatched to clear the `check-pr-authors` gate (its commit authored by an identity outside the
allowlist) reports "re-authored, pushed" — and the head sha DOES change, because it force-pushed
something. A new head sha is NOT proof the author identity changed: an amend or force-push that did not
run `--reset-author` (or re-ran as the same bot identity) moves the head while every commit stays
authored `… <bot@nousresearch.com>`. Verify the AUTHOR on the objects, never the push:

```bash
gh api repos/<o>/<r>/pulls/<n>/commits --jq '.[]|"\(.sha[0:9])  \(.commit.author.name) <\(.commit.author.email)>"'
```

The allowlist is by ADDRESS (Andy Holst <andy.holst@protonmail.com> / Asimov Agent <support@docondee.com>);
an alias list names display NAMES, never addresses, so a "same name, bot email" commit still reds.
Re-dispatch with the exact remedy verbatim: `git config user.name "Andy Holst"; git config user.email
andy.holst@protonmail.com; git rebase --reset-author` (or `git commit --amend --reset-author`), then
`--force-with-lease`. Done = `pulls/<n>/commits` shows an allowlisted address at the live head AND the
authors gate is SUCCESS there. A lane that re-pushed and still reads the bot address has not done the fix.

## An UNKNOWN `--json` field aborts the whole `gh pr view` call — a multi-PR loop then prints NOTHING for EVERY PR

`gh pr view <n> --json reviews,mergeable,isMergeable` exits 1 with
`Unknown JSON field: "isMergeable"` and emits **no object at all** — so a `for n in …` loop that
requests one bad field prints an empty line for EVERY PR, which reads exactly like "all five PRs have
no reviews / no data". Same for `mergeBlockedReason` (does not exist on the PR object; the block
signal is `mergeStateStatus`). Verify the field list against ONE PR before looping:

```bash
gh pr view <n> --repo <o>/<r> --json mergeable,mergeStateStatus,reviews --jq \
  '"merge=\(.mergeable) state=\(.mergeStateStatus) reviews=\([.reviews[].state]|join(","))"'
```

Do not read a blank multi-PR table as evidence about the PRs — an unknown field is a claim about your
query. Build the per-PR fields on a single PR first, then loop.

## `gh pr checks --json link` gives a CHECK-RUN id, not a workflow-RUN id — actions/runs/<id> 404s

`gh pr checks <n> --json link` (and a check-run's `details_url`) is `…/runs/<id>`, but that `<id>` is a
**check-run** id. Feeding it to `actions/runs/<id>` or `actions/jobs/<id>/logs` returns HTTP 404
`Not Found` — you will loop assuming the run is missing when the id is simply a different object type.
Recognise it when a check name resolves via `commits/<sha>/check-runs`
(`.check_runs[]|select(.name=="ci-verdict")` → `{id,conclusion,details_url}`) but the same numeric id
404s on every actions endpoint: that id is the check-run, whose log is not exposed at an actions path.
To get the REAL workflow-run ids at a head, don't chase the check-run id — enumerate runs by sha:
`gh api "repos/<o>/<r>/actions/runs?head_sha=<40-hex>&per_page=30" --jq '.workflow_runs[]|{id,name,status,conclusion}'`
returns the actual run ids (whose `/jobs` and `/logs` DO resolve).
Do not burn turns re-trying. Read the verdict from the check-run payload's own `output.summary` /
`output.title`, or hand the reconcile to the owning lane whose harness produced the check.

## Closed/dead PR refs are GC'd, not proof of non-merge
- A closed PR's `pull/<n>/head` ref and branch are routinely deleted from the remote;
  `git fetch origin pull/<n>/head` can 404. That is not evidence the PR never merged —
  check its `state`/`mergeSha` via the API instead. A closed PR that left a live fork
  branch is the cheap reopen vehicle: read that branch's sha, do not re-open blind.

## A per-branch commit loop over ~100 branches blows the foreground timeout — measure recency from ONE paginated call
- To find which `agent/issue-*` branches are live, the instinct is `for b in $(branches); do gh api commits?sha=$b&per_page=1 ...; done`. On a repo with ~100 such branches that is ~100 sequential API calls and it hits the 180s foreground limit (`exit_code 124`) with no usable output — the loop dies before you see a single timestamp.
- Measure branch recency from ONE source instead: `gh api --paginate "repos/<o>/<r>/branches?per_page=100&sort=updated"` already returns each branch's tip commit sha; fetch the handful of tip dates you actually need (`commits/<tip-sha>`) rather than one call per branch, or read `git for-each-ref --sort=-committerdate refs/remotes/origin 'agent/issue*'` locally (fast, no per-branch HTTP). Never conclude "all branches stale" from a timed-out loop — the empty/partial stdout is the timeout, not the data.
- The same applies to `gh api .../actions/runs --paginate` sweeping a busy workflow's history: over a few thousand runs it also exceeds 180s in the foreground. Scope it (`?branch=<ref>` / `?per_page=30`) or run it backgrounded with notify-on-complete.

## Never pipe `gh … --jq` rendered output into a JSON parser

`gh api … --jq '<filter>' | python3 -c 'json.load(sys.stdin)'` fails with `Expecting value: line 1
column 1 (char 0)` — `--jq` emits the filter's RENDERED text (`"x"` for a scalar, nothing on a jq
error), not a JSON document, so the parser sees an empty or quoted stream. Read a field
programmatically by either (a) fetching the raw object and parsing once (`gh api repos/<o>/<r>/pulls/<n>`
with no `--jq`, or `urllib` with the token), or (b) keeping jq for a single scalar (`--jq .body`). An
`Expecting value … char 0` means the upstream produced no stdout — read the gh exit code/stderr before
theorising about the data.

## `gh issue view <n> --json comments` — iterate `.comments[]`, not `.comments`
- `gh issue view <n> --json comments --jq '.comments[]?...'` is correct; `.comments` is the ARRAY inside the top-level object, so a filter that treats `.comments` as the object errors `expected an object but got: array`. Same shape as the list-endpoint traps above — read the field's own type first (`.comments|type`) and descend into it, and never read the jq error's empty stdout as "no comments".

## `gh pr list --search "<n>"` is FUZZY — a hit is not proof that PR is the issue's vehicle

A bare issue number in `--search` full-text matches ANY PR whose title/body/branch mentions those digits, so
searching for an issue's number can return an unrelated PR (a PR closing #1696 surfaced for a search on "1629").
Do not read a search hit as "this issue has an open vehicle" — confirm the link by structure: the PR's
`closes/fixes #N` in `.body`, or a branch named for the issue (`git ls-remote origin 'refs/heads/*<n>*'`), or
`.headRefName` containing the issue number. To answer "does issue #N have a vehicle" reliably, list open PRs
and grep each `.body` for `#N` rather than trusting `--search "N"`.

## Keyword-matching comment text is not a live-claim detector

To answer "is anyone working on this issue", grepping the comment bodies for `claimed` /
`working on` / `branch ` **matches history**: planner notes, past routing records and closed
lanes' reports all contain those words, so a 9-month-old comment counts as "claims=1" and an
unclaimed, idle-capable issue reads as owned. A real live claim is a **structured** object, not a
phrase:

```bash
gh api repos/<o>/<r>/pulls?state=open --jq '.[]|select(.head.ref|test("issue-<N>-"))|{n:.number,ref:.head.ref}'
gh api repos/<o>/<r>/issues/<N>/comments --jq '.[]|select(.body|test("bot-claim:|working on #"))|{id,created_at,user:.user.login}'
```

Judge ownership on (a) an open PR on a branch named for the issue, and (b) a `bot-claim:`-shaped
comment newer than the last dispatch — then confirm liveness (the branch has commits after the claim,
or a run at its head). A keyword hit with neither is a **false positive**; treat the issue as
unclaimed and dispatch, and say in the dispatch that the earlier keyword hit was history, not a claim,
so the next reader does not re-derive it.

Measure all THREE independently before calling an issue owned or idle-capable — the triple is
`claims=<count of claim-shaped comments> branches=<refs/heads matching the issue> openPRs=<PRs
whose head branch or body names it>`. Repeated receipts, audit notes and planner records inflate
`claims` without any work existing; `claims=6 branches=0 openPRs=0` means six historical mentions,
not six lanes on the issue. Conversely `branches>0 openPRs=0` is a branch with no vehicle (stranded
work), and `openPRs>0` is the only state that blocks a dispatch outright.

## An open issue whose closing PR merged may be a deliberate multi-lane reopen

A fleet-rollout issue (one issue, N lanes each shipping its own PR) is routinely CLOSED by the first
lane's `closes #N` and REOPENED minutes later because the remaining lanes are still owed. Before calling
such an issue an anomaly ("merged but still open"), or re-dispatching a fresh vehicle for it, read the
event timeline:

```bash
gh api repos/<o>/<r>/issues/<n>/timeline --jq '.[]|select(.event=="closed" or .event=="reopened")|"\(.event) \(.created_at[11:19])"'
```

A `closed`→`reopened` pair means the remainder is intentional: read the issue's unchecked `- [ ]` ACs to
identify the leg still owed, check whether that leg is in fact already proven `[x]` (reviewer proof in the
body), and if only the owner-path merge/tick remains, record THAT measurement instead of treating the open
state as fresh work.

## Two issues with the same title fragment are not necessarily duplicates
- Before closing/merging one as a duplicate, read BOTH bodies. A follow-on issue often
  cites the other as its dependency ("the bake-at-build unblock for #X …"), so
  consolidating corrupts a dependency chain. Only dedup when both enumerate the same
  root cause and the same acceptance criteria; otherwise link them and leave both open.

## A head can move between your verification and your POST — re-`rev-parse` immediately before posting a head-tree claim

You measure a branch's tree at `origin/<branch>` (a fold present at a line, a file identical
to main, a diff stat), draft the conclusion, and POST it — and by POST time the lane has pushed
again, so the head your comment describes is already superseded. Real shape: verified a timeout
fold at head A, posted "the vehicle carries fold X"; four minutes later the branch sat at head B
with that fold dropped to main's value, so the just-posted comment was false on the wire and had to
be retracted. A push lands in the seconds/minutes between your `git show` and your `gh ... comment`.
Guard: run `git fetch origin <branch>; git rev-parse origin/<branch>` **immediately** before building
the POST, and if the sha differs from what you measured, re-measure the tree at the new sha — never
post a conclusion computed at a sha you cannot re-confirm at post time. Quote the head sha inside the
comment body so a later reader can see exactly which head it described. When your OWN posted claim is
then reversed by an even newer push, retract it explicitly on-issue — name the earlier comment id and
the new head + evidence ("my comment <id> said X at head A; head is now B and the tree reads Y"). A
superseded claim left un-retracted is a false statement on the board the next reader will act on;
retracting your own reversed conclusion is required correctness-keeping, not optional churn.

## A reads-API that returns EMPTY across several endpoints at once is a degraded instrument — recover via `gh pr checks`, do not report "no runs"

When `actions/runs?head_sha=<full-sha>`, `commits/<sha>/check-runs`, `commits/<sha>/status` and
`gh run list --commit <sha>` ALL return empty/`total_count:0`/`state:pending contexts=0` within the same
pass — while `gh pr view <n> --json statusCheckRollup` and `gh pr checks <n>` still answer with real check
names and run/job URLs — the read side is degraded for the runs endpoints, NOT the heads lacking runs.
Distinguish "no runs" from "instrument down" by cross-reading the same fact on an independent endpoint:
a non-empty `gh pr checks <n>` output (which it renders from the check-runs/status API the PR carries) is
proof the runs exist even when the runs/commits endpoints print nothing.

- `gh pr checks <n>` (and `gh pr view --json statusCheckRollup`) is the RESILIENT read: it kept answering with
  real check names, conclusions and run URLs through a window where every `actions/runs?head_sha=` and
  `commits/<sha>/check-runs` call returned empty. When those return empty but `gh pr checks` is populated, grade
  gates off `gh pr checks`, not off the empty endpoints.
- A background poll that retries `gh run view <id> --json status,conclusion` and treats an empty/`""` status as
  progress is polling a degraded instrument — it will spin forever on `in_progress/` with an empty conclusion.
  Probe recovery first (`gh api .../actions/runs?per_page=1 --jq .total_count` returning a real number) before
  trusting any run-status read; if the probe is empty, the read is down regardless of what the run actually is.
- Retry/recovers on its own — this is transient, so the durable lesson is the CROSS-CHECK (grade off the healthy
  endpoint), never "the API is broken." Do not file an incident or report heads as having no CI off an empty
  read; state which endpoint answered and which was empty.

## `git --date=format:'…Z'` prints LOCAL time with a literal `Z` — it is not UTC

`git show -s --format='%cd' --date=format:'%H:%M:%SZ' <sha>` renders the commit time in the
SHELL's local zone and then appends a literal `Z`, so a committer date reading `18:00:03Z` on a
CET host is actually `17:00:03Z` UTC. The `Z` suffix in the format string is a text label you
typed, not a conversion — git never converts to UTC for `format:`. This reads as a future or
mismatched timestamp when you compare it against `date -u` (a fresh rebase then looks like it
happened an hour in the future). Never put `Z` in a `format:` string and treat it as UTC.

- Convert properly: `git show -s --format='%cd' --date=iso-strict <sha>` (emits a real `+00:00`/
  offset), `--date=format-local:'%H:%M:%S'` with `TZ=UTC git …` in front, or read epoch
  `%ct`/`%at` and format in python with `time.gmtime`.
- Freshness is a `committerdate` question — `for-each-ref --format='%(committerdate:iso-strict)'`
  gives the same offset-correct value for a ref (author date can be much older after a rebase,
  which reuses author dates; a "16:29 author / 17:00 committer" pair is a rebase, not two edits).
- ANY comparison of a git date against a `date -u`/ISO-UTC value must normalise both to the same
  zone first; a mismatch there is your format string, not a clock skew on the wire.

## `gh run list` instrument: `--workflow` takes the file name or numeric id, NOT the display name; lane runs need `--all`

- `gh run list --workflow <display-name>` (e.g. `issue-refiner`) returns NOTHING — `--workflow`/`-w`
  accepts the workflow **file name** (`issue-refiner.yml`) or numeric id, never the human display name.
  An empty result from a display-name filter reads as "this lane has no runs / is idle" and sends you
  reporting a quiet lane that is running fine. Enumerate real slugs first
  (`gh workflow list --all --json name,path,state`), then filter by the `.yml` path or the id.
- `gh run list` without `--all` is scoped to the checkout's branch/workflow context; bot runs fired on
  label events or other branches are hidden. Sweep a lane's history with `--all` (or `--branch <ref>`)
  before declaring it idle — an empty scoped list is not "no runs".
- `gh api repos/<o>/<r>/actions/workflows/<id>/runs` needs the workflow's NUMERIC id (from
  `gh workflow list --json id`), not its name — a name-based path 404s `Not Found`.
- A workflow can be `disabled_manually`: a lane with no recent runs may be disabled, not idle. Check
  `state` in `gh workflow list --all` alongside the cron before reporting a lane quiet.
- **A lane may have NO dedicated workflow at all — absence from `actions/workflows` is not
  evidence it does not exist.** Some lines are driven purely by issue labels and dispatches
  (a `security`-labelled queue is worked by a lane with no `security-bot.yml`). For those,
  measure the QUEUE, not run history: open issues carrying the lane's label, their last
  activity, and whether any has a `bot-claim:` comment plus a branch. `could not find any
  workflows named <lane>` from `gh run list --workflow` proves nothing about the lane's idleness.
- **A cron-slot sweep of the bot WORKFLOWS does not measure the dispatch-only HOST lanes.** Lanes
  like the reviewer and tester have no workflow, no cron and no run history at all — they act only
  when you dispatch them. A sweep that loops `gh run list --workflow` over every bot `.yml` therefore
  reports "all lanes busy in their slots" while the reviewer has submitted ZERO reviews on the open
  board. That is the exact false "nothing to dispatch" that ends a pass idle.
  Measure a host lane by its OUTPUT on the objects it serves, not by its run history:
  ```bash
  for n in $(gh pr list --state open --json number --jq '.[].number'); do
    echo "#$n reviews=$(gh api repos/<o>/<r>/pulls/$n/reviews --jq 'length')"
  done
  ```
  A merge-ready PR (`mergeable=MERGEABLE`, base current) carrying `reviews=[]` means the reviewer
  lane is idle-capable RIGHT NOW — dispatch it on that PR regardless of whether any bot workflow
  looks quiet. The reviewer reviews; it never approves or merges, so its dispatch is always
  un-gated by the owner-approval wait.
- **`BLOCKED` + `MERGEABLE` + `reviews=[]` is the owner-approval gate, not a stalled bot.** When every
  open PR reads that triple, the ceiling is a required human approval (bot-authored PRs cannot
  self-approve), so the honest answer to "why is the fleet quiet" is "the lane is done and the PRs
  await the owner" — do not invent a bot-fixable cause, and do not report the runners as idle; check
  their `gh run list` slot timestamps and quote them. Separate the ONE genuinely un-gated lane
  (reviewer/tester) from the owner-gated merge, and say which PRs sit behind each.

## `actions/runs?head_sha=` matches the FULL 40-hex sha only — a truncated prefix returns an EMPTY list, not an error

Filtering runs by commit with an abbreviated sha (`?head_sha=0715c522289c`, 12 chars) returns a valid
200 carrying `{"total_count":0,"workflow_runs":[]}` — zero rows that read as "this head has no runs" while
the runs exist. The `head_sha` query param does an exact FULL-sha match; it does not prefix-match. Either
pass the full 40-hex from `.head.sha`/`headRefOid`, or skip the runs endpoint and read per-commit checks
with `commits/<sha>/check-runs` (which DOES accept the abbreviation and returns the `in_progress`/`completed`
legs you actually want). Before concluding "no runs at this head", confirm the sha you filtered on is 40 hex
— a 200-with-empty-array from a short sha is the same silent false negative as any unchecked walk.

**`commits/<sha>/check-runs` on an abbreviated sha OR on a merge commit's own sha returns HTTP 422
`No commit found for SHA`** — a different failure of the same shape, and one that reads as "this commit
has no checks" if you skim it. A merged PR's `merge_commit_sha` is a commit on `main` whose pre-merge
check runs belong to the PR **head**, so verify gates at `pulls/<n>.head.sha` (or `gh pr checks <n>`),
never at the abbreviated merge sha you pasted from a report.

## Two agents quoting different branch tips: settle by successor relation + commit time, not by whose message is newer

When you and a lane report different head shas for the same PR, neither "my read is newer" nor "the API says" settles it — the wire moves between reads and a lane's local ref can be old. Prove which sha is the *current* tip with three timestamped facts, not with prose:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '{head:.head.sha, updated:.updated_at}'
for s in <shaA> <shaB>; do gh api repos/<o>/<r>/commits/$s --jq '{sha:.sha[0:12], date:.commit.committer.date, msg:.commit.message[0:60]}'; done
gh api repos/<o>/<r>/compare/<shaA>...<shaB> --jq '{status,ahead_by,behind_by}'
git ls-remote origin refs/heads/<branch>
```

- **`compare A...B` with `ahead_by=1, behind_by=0` proves B is A plus one commit** — A is the ancestor (the older, superseded read), not a divergence. Quote the counts.
- **Quote `committer.date` per candidate:** the ancestor sha is the one reading an older point in time, regardless of when either agent sent its message. A reply composed at T can describe a head that moved at T+40min — the sender is not lying, they are describing a valid past state.
- **`ls-remote origin` is the canonical tip**; if the PR head lives in a fork, read `.head.repo` on `pulls/<n>` and use THAT repo's refs (`pr-head-location-and-base-gates.md`). Confirm `head.sha` from `pulls/<n>` matches the ls-remote ref before declaring "settled".
- **Report as a relation, never a verdict:** "tip is X; Y is X minus N commits (ancestor, dated earlier)" — not "you're wrong / I'm right". And once corrected, do NOT re-send the same proof (echo discipline): one corrected message, not a ping-pong of acks.

## A sliced file list hides the file that decides the question

`gh pr view <n> --json files --jq '.files[].path'` over a `.files[:N]` slice (or any hand-truncated listing) can hide the ONE file that proves or disproves the claim — the `tests/test_<x>.py` that satisfies "a test asserts…", the `openspec/` path, the script the criterion names. Concluding "AC unmet / no test / no openspec" from a truncated list is a claim about your slice, not the PR. Before asserting absence: print the FULL list (no slice) or count (`.files | length`) and grep for the specific path class — and when existence alone is not proof of behaviour, read the file at the head (`git show <head>:<path>` or `pulls/<n>/files --jq '.[]|select(.filename=="…")|.patch'`).

## A lane vehicle is branch-first, PR-second — measure branch refs before writing "no PR yet"

A dispatched lane pushes its branch minutes BEFORE it opens the PR, so a fleet-status table assembled
from `gh pr list` alone reports "no PR yet" for a vehicle that already exists on the wire. Measure both
refs in the same pass and timestamp the record:

```bash
git ls-remote origin 'refs/heads/*<issue>*'                 # the branch
git show -s --format='%ci' <tip-sha>                       # when it was pushed
gh pr list --state open --json number,headRefName --jq '.[]|select(.headRefName|test("<issue>"))'
```

- `branch present + PR absent` is **"branched, PR-opening pending"** — report it with the tip sha and
  commit time, never as "no vehicle". A branch one to five minutes old is in-flight velocity, not a
  stalled lane: do not nudge, do not re-dispatch, and do not read its absence from `gh pr list` as
  missing work.
- A status table posted even a few minutes earlier can already be false. When a later measurement
  shows a branch that existed at post time, post a **correction + refresh** naming the earlier comment
  id and the new fact; silently recording a different state next turn leaves a false row on the board
  that a reader will act on (same correctness rule as an un-retracted head-tree claim).
- Judge "idle-capable" only on the full triple — live claim comment + branch + open PR. A lane whose
  own-domain audit is actively claimed on its tracker issue (a `BOT … working on #N` bookend, "no PR
  owed" per the audit) is NOT idle: the continuous-improvement audit is its assigned work, and a quiet
  PR list is the expected shape of that work, not an idle queue.

## Never broadcast one remedy to sibling PRs — read each body before generalising a gate red

When several sibling PRs (one rollout, N vehicles) show the SAME gate red, the tempting move is one
fleet-wide prescription ("all of you drop `closes #<tracker>`"). Siblings reached the red by different
structures, and one blanket edit can DELETE a working fix: measured case — three PRs sharing a
`check-pr-acceptance` red, one of them already carried the sanctioned exemption block (`## Not covered`
bullets reproducing the criterion's leading words with the tracker `#N` linked), which is exactly what
makes the gate green; a "remove the close" instruction would have stripped a passing structure and
re-redded it. Before any multi-PR prescription, print each body's shape individually:

```bash
for pr in <list>; do
  b=$(gh pr view $pr --repo <o>/<r> --json body --jq .body)
  echo "$pr closes=$(printf '%s' "$b" | grep -ciE 'closes[[:space:]]*#<N>') notcovered=$(printf '%s' "$b" | grep -ciE '## Not covered')"
done
```

Then split the fleet: the PR with neither a close nor an exemption needs the body edit; the PR with a
close and no exemption needs the close dropped or an exemption added; the PR with an exemption block
already has the gate's remedy and only owes a re-run or a new head. State the per-PR remedy, never one
rule for the set — and when you have already posted a blanket rule, correct your own comment explicitly
(name the earlier comment id and the per-PR truth) rather than leaving a wrong prescription on the board.

Also check the failing run's `createdAt` against the PR's `updatedAt` (body-edit time): a failure whose
run predates the body edit is stale evidence about an older body, and the remedy is a new head, not a
further body edit — reporting it as a live defect sends the lane to re-fix text that is already correct.

## jq: a literal `#` can open a COMMENT mid-filter — format `#<n>` outside jq

A `--jq` filter that builds a row as `"#"+(.number|tostring)+" "+.headRefName` intermittently dies
`failed to parse jq expression … unexpected token`: outside a string literal (and in some `test("...")`
regex contexts) `#` begins a jq comment and swallows the remainder of the filter. Do not fight the
parser — build the prefix outside jq:

- scalar then shell: `gh api … --jq '.number' | while read n; do echo "#$n"; done`, or `printf '#%s'`;
- or do the whole row in the python/urllib probe form already used for write-verification
  (`print(f"#{n} {ref}")`), which never re-parses a jq filter.

When a multi-column jq row errors, the other columns still print — a populated-looking table can hide a
`failed to parse` column. Re-run that one field on its own, clean.

