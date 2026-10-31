# Assertions, shape changes, and gates that actually fire

Depth for the "assert behaviour, not text" rule. Every item here is a defect that shipped green, or was caught one
message before it did.

## A shape change has a spelling — grep the suite for it before you push

When a change replaces a construct (an inline command becomes a make target, a status field gains a new meaning, a group
is deleted), some test asserts the **old spelling**. CI reds on a fix that is correct, and the red looks like the fix's
fault.

```bash
# after changing a shape, before the first push
grep -rn "<old construct>" tests/ | head -30     # e.g. "python3 scripts/<x>.py", "callers[\"macos\"]", ".PHONY"
```

Then pin the **wiring** rather than the spelling: assert the make target is invoked, its arguments are passed, the old
inline form is *absent*, and the recipe still calls the script (so the decision stays covered end to end). A test that
asserts a literal command line reds on every behaviour-preserving refactor — the same failure mode as a test that pins
one spelling of a shell fallback (`${{ github.base_ref || 'main' }}` vs `${EVENT_BASE_REF:-main}`).

## Never assert a list the tree is meant to extend

Manifests, rosters, workflow sets and job lists grow. Equality reds on the next legitimate addition and teaches the next
person to edit the test:

```python
assert {"a", "b"} <= set(names)          # subset — the rule
assert set(names) == {"a", "b"}          # snapshot — reds when c joins
```

Keep the rule *and* the referents: subset membership plus "every listed name resolves to something real" (a directory,
a file, a live workflow). Subset alone lets a typo through, because `{"a","b"} <= {"a","typo","b"}` passes.

## Assert against the entry point that runs in production

A library and its CLI can disagree, and the CLI's correctness hides the library's failure — both are "the classifier"
to a reader, only one is right. When a decision lives in a wrapper (`main()`) rather than in the function (`scope()`),
the fail-safe branch exists at exactly one call site:

- measure expectations through the entry point the workflow invokes, and **name that entry point next to every table
  row** — otherwise two lanes measure 22 and 3 and both are "right";
- when a fail-open widening lives in the wrapper, move it into the function so the safe answer is the default, and flip
the test that documented the divergence into one that forbids it.

## A gate must fire on the PR that introduces it

Before trusting a new gate, run it against the change that adds it. A predicate that classifies *who* the change is for
can silently exclude the change itself:

```python
is_bot_pr = all(author == BOT_EMAIL for author in authors)   # one human commit → False → gate skipped
is_bot_pr = any(author == BOT_EMAIL for author in authors)   # errs toward enforcement
```

A real branch almost always contains a human commit (a rebase, an owner fixup), so `all(...)` makes the gate skip the
majority case. Encode the decision as **`any(...)`, or `all(...)` plus a notice naming the human commits**, and prove it
with a negative control executed on that branch.

## A repo-wide gate lands against the whole open board, not one PR

A gate that begins enforcing when it merges applies to **every open PR at once**. Measure the blast radius before it
lands and publish it, or the first thing it does is red several lanes on a check none of them introduced:

```bash
for n in $(gh pr list --repo <o>/<r> --state open --limit 100 --json number --jq '.[].number'); do
  f=$(gh api repos/<o>/<r>/pulls/$n/files --paginate --jq '.[].filename')
  echo "$n surface=$(grep -cE '<surface the rule governs>' <<< "$f") artefact=$(grep -cE '<artefact it demands>' <<< "$f")"
done     # surface > 0 and artefact == 0 ⇒ this PR reds the moment the gate lands
```

- **Publish the list and the count in the gate's own PR body** — "landing this reds these five; each fix is one note plus
  one row". A foreseeable red is a sequencing decision; an unforeseeable one is five lanes diagnosing each other's work.
- **Fix your own first.** The gate author's PR is usually on the list, and the cheapest proof that the rule is
  satisfiable is your own branch passing it before it is enforced.
- **Decide from the PR's own diff, never from the whole tree.** A rule evaluated against repository state reds every PR
  on every other PR's omission and no single lane can satisfy it; read `base...head` for that PR.
- **The window is part of the number.** "N of the last M merged PRs" is reconcilable when two lanes quote different
  windows; "N of recent PRs" starts an argument instead of settling one.

## A check that cannot compare must say so

When a guard's second side is absent — no live profile on a CI runner, no credentials, no fixture — do **not** return silently. Silence makes "compared and fine" indistinguishable from "could not compare", and that ambiguity is how a truncated copy ships green.

```python
if live_home is None:
    print(f"[check] live comparison SKIPPED: no profile home at {path} — tree checks only")
    return 0
```

Skip (never fail) when the missing side is something the environment cannot supply — a runner that reds for a condition it cannot fix is an unfixable red — but make the skip a stated outcome, and assert the line appears so it cannot degrade back to silence.

## Symmetric gates

Every gate needs the negative control **in both directions**, or it is decoration:

| gate | must red when | must stay green when |
|---|---|---|
| trigger list equals class list | a path is added to one side | both sides are edited together |
| no inline script in a workflow | the inline form returns | the make target is used |
| no draft PRs | a draft is created | a ready PR is opened |
| no hung job | a job exceeds its ceiling | a job runs long but inside it |
| live profile covers tree copy | the tree file is shorter than the live one | both are byte-identical |

Run the red direction by *making* the defect (add the entry back, drop the bullet, shorten the file), watch it fail,
restore, watch it pass. A gate proven only by passing runs has never been seen to work.

## A sync/import direction has a dangerous side

When a repo copy mirrors a live artefact, the risk is asymmetric: a **tree copy shorter than the live file** means a
sync would silently replace a working rulebook with a fraction of itself, with a green gate — while a tree copy longer
than a stub is merely unsynced. Compare byte counts against the live artefact before any sync, refuse to shrink without
an explicit force flag, and make the length relation an assertion rather than a convention.

**The lie to design out: a sync verifies the copy, not the content.** A tool that writes tree → live and then reads
back what it wrote prints `verified: 3 file(s) read back identical` and exits 0 while the destination **shrank**,
because "identical" only meant "what I wrote matches what I copied". Rules disappear under a green, verified, successful
run. Three consequences for the guard and its tests:

- **Read the live size at sync time**, never against a captured number — the live file can change between measuring it
  and running the guard, so a stored byte count is stale on arrival.
- **Never print the word "identical" for a file whose size changed**: `verified: 3 copied, 1 shrank (7,509 → 5,149 b)`.
- **Pin the message, not just the exit code.** A refusal that still prints "verified" is the same lie with a non-zero
  status: assert the non-zero exit, both sizes present in the output, the shrink named, and `"verified" not in out` on
  the refusing path. **Compute the expected sizes from the fixture**, never as literals — a literal goes stale the moment
  the file changes, and the live file can grow between measuring it and committing. Add the mirror test for the success
  path too (`copied … replaced an existing file`, never `identical`): the refusal half alone leaves the misleading
  sentence alive on the path production actually runs.

Prove the whole thing on a **sandbox copy** of the destination (`cp -a` the profile or corpus, run the real target
against it, then check string presence for three rules that must survive). Reproduction on a copy is what turns "this
could delete rules" into a merge blocker nobody argues with — inference gets a discussion, a sandbox transcript gets a
fix.

## A gate that prints its own HEAD but never validates the pointer it claims to enforce is a self-reference

When a gate is meant to keep a claim in a doc from drifting (`"measured at <sha>"`, `"the tree is N files"`), it must
validate the pointer the doc states — parse it, resolve it, compare the two sides. A check that only prints `git
rev-parse --short HEAD` and never reads the doc's own sha is a self-reference: the doc can stale-vs-main by exactly the
PR's own not-yet-merged files, the head-pass stays green, and the pointer can dangle (a commit hash present in the repo
but unreachable from any ref) with no signal. Red the moment the pointer's tree disagrees with HEAD's count, or the
pointer is not a real commit (`git cat-file -e <sha>^{commit}`).**The work lands with the guard**: a gate that is added
alongside the fix must catch exactly the class the fix prevents, or the next drift slips the same hole.

**A doc that measures the tree it lives in cannot use `pointer == HEAD`.** Literal equality is unsatisfiable by design
— every pointer update re-heads the document, so the check can only pass before it is ever true. The sound invariant for
a self-measuring doc is *the pointer resolves to a real commit and its tree carries HEAD's tracked count*: it reds the
moment the tree grows past what the census was measured against, and it stays green through the squash. Prefer the
count-based form and flag the choice, rather than a string equality that cannot be met.

## Anchoring a regex at end-of-line skips lines that carry trailing comments

A mechanical rewrite that matches `^import x$` never sees `import x  # noqa: E402`. Order the passes so scaffolding
goes first:

1. strip the trailing-comment scaffolding (`# noqa`, `# type: ignore`),
2. rewrite the construct,
3. then remove the line the construct needed (a path insert, a shim).

Otherwise the rewrite silently drops the import and leaves the path entry gone — a module-not-found on files you did not
sample. Prove any regex-driven migration by importing every file it touched, not a sample of five.

## An exemption is debt, not amnesty

An allowlist that lets a known-incomplete item pass must carry a **reason** and an **owner**, or it never gets paid
down: an entry with no reason is an amnesty, an entry with no owner is a gap nobody closes, and an entry naming something
the manifest does not list is a stale record. Make all three findings in the gate itself, plus "this entry is now stale
because the item became compliant — delete it". A verbatim-content gate should name the **item and the first missing
clause**, never just "drift", so the lane does not re-derive which rule is absent.

## A stack of one-file-each PRs merges foundation-first

When several lanes each add one file under a shared tree (per-profile behaviour files, per-service config), the only
workable shape is **one foundation PR plus per-profile PRs stacked on it** — the foundation merges first, then the rest
collapse to their own single file. A lane that re-cuts the whole tree is a duplicate, not a parallel effort: close it
with a file-by-file comparison and state explicitly that the diagnosis was not rejected. Corollary for ordering: a PR
carrying another PR's file must land **after** it, or the earlier gate silently regresses when the carrier merges.

**Detect the duplicate by content, not by description.** File counts look identical when every PR re-derives the same
skeleton: diff each PR against its own base and compare the *shared* file list — five "profile" PRs that each carry the
same sixteen-file skeleton plus one own file are five copies of one change. Then count the actual payload (profiles,
services, entries), not the files: a PR claiming to add the tree while its payload count is unchanged is a copy.

### Verify a seeded copy against the live artefact at commit time

```bash
git cat-file -s <sha>:<tree path>      # what the PR will merge
stat -c %s <live path>                 # what the profile actually loads
```

Comparing those two is the check; comparing a worktree's files compares neither, and a size quoted in a message is stale
before it is read — the live file here grew three times in one session. Re-read at commit time and state both numbers in
the PR body so a reviewer can confirm the sizes rather than trusting the gate.

**A replacement that is LARGER while dropping lines defeats every shrink guard.** Size is the one signal an operator and
a gate read first, so a rewrite that grows a file while omitting live clauses sails through a length check and a
"non-shrinking" assertion. When merging two copies, do not take either side wholesale: diff, then confirm **no tree-only
line disappears and every live-only line is either taken or consciously declined**, and say which in the commit message.
A lane's own longer spelling of the same rule is not a superset of the live text.

**After any rewrite, verify content, not the sha.** A rebase preserves content and destroys shas, so a lane quoting "my
head is `<sha>`" after a fetch can be describing a commit nobody else has — measure `git cat-file -s <sha>:<path>`,
the test suite, and `CHECK=1` byte-identity instead, and treat the sha as "the head when measured".

## The tree is the source; the live copy is not

A gate that compares a committed copy against a live artefact **becomes unsatisfiable** the moment anyone edits the live
authority directly: the reference moves faster than the PR, so the comparison reds forever and every "re-take the live
file" instruction just launders an unversioned edit into the repo. Measured drift on one file in a single session:
tree 4,936 b unchanged while live went 8,596 → 10,591 → 14,045 b.

- **Sync one way.** Tree → live only. A reverse direction is an escape hatch that produces the drift; refuse it and say
  which file and what to change instead.
- **Two distinct findings.** `live longer than tree` (a truncated seed) and `live edited after the tree commit` (an
  unversioned edit) need different fixes; collapsing them lets a re-take masquerade as a repair.
- **Refuse to overwrite differing content** unless the tree change is committed and force is explicit.
- **A live profile is evidence, not a source of truth.** When copying from it, take a named artefact (a PR's blob at a
  sha) rather than the moving file, and say in the commit message what was kept and dropped.

## Identity gates key on email, never on a display name the platform sets

A gate that compares the *author name* to an allowlist reds on innocent commits, because the display name is written by
the platform (a squash takes the profile name) and by ad-hoc `git -c user.name=...`, neither of which the committer
controls. The durable shape:

- the **email** is the identity key; each allowed identity carries an explicit **alias list of names** it may appear under;
- an email outside the allowlist still fails, and the message names the **email**;
- a **typo email still fails** — the alias list is names only, never emails, or "fixing" the gate quietly allowlists a
  wrong address;
- **verify the identity across the whole range, not at the tip** — a one-character typo on a single commit out of
  seven (`…@doccondee` for `…@docondee`) reds the gate while every other commit is clean. The check is
  `git log --format='%ae' <base>..HEAD | sort -u` (expect exactly one address), and the fix is
  `git commit --amend --reset-author` on that commit followed by the same range check — never a fix of the tip alone;
- the docstring records *why* the name cannot be the key, so the next author does not restore exact-name matching.

Fixing the gate is usually cheaper than rewriting history: re-authoring N commits means rewriting every descendant and
invalidating the verdicts of all stacked children, while the gate is one file plus a negative control. And a gate runs
the script from the PR's own tree, so a PR that loosens the check passes its own guard trivially — **the tests are the
evidence, not the green run**.

## A field answers a neighbouring question — quote the one that decides

Every instance of this family shipped green or was reported with confidence, and the field names differ each time, so
check the name against the question before quoting it.

| quoted | actually answers | question being asked |
|---|---|---|
| `mergeable` / `mergeStateStatus` | does the diff apply | will this merge — read the per-head `conclusion` |
| `mergeable: UNKNOWN` on a closed PR | nothing; the object is gone | `state` + `mergedAt` |
| a CLI `check` exiting 0 | is anything unaccounted for | does the committed file equal a fresh render |
| `autoMergeRequest.enabledAt` | when an arm was requested | which head is armed — it records a time, never a head |
| `skipped` on a job | scope decided it is not needed | nothing was verified — a cancelled fan-out prints this too |
| a frozen `run.updated_at` | when the last event was | is it hung — only elapsed time against a run that CONCLUDED decides |
| two set sizes subtracted | arithmetic | how many are uncovered — set difference is not `len(a) - len(b)` |
| `grep -c` for an identifier | prose mentions | a line-anchored construct (`^co-authored-by`) |
| `grep <filename>` on `git merge-tree --messages` | an `Auto-merging <file>` notice | does it conflict — `grep -E '^CONFLICT'` only |

Rules that follow from the table:

- **Quote the buckets, never a summary word.** "0 failures" and "0 failures with 5 cancelled/skipped" are the same
  number of failures and different states of knowledge. Report `success / failure / cancelled / skipped / pending`
  separately and treat a head carrying non-verdicts as unverified, however the summary line reads.
- **After any state change, re-read the object.** `state`, `mergedAt`, `conclusion`, `completed_at` describe what
  happened; derived flags describe a question that may no longer exist.
- **A redirect is a verdict.** `cancelled` means superseded or stopped — never a stall, never a pass, and never
  "superseded" unless a newer run exists at that same head.
- **A number derived from another number needs its own measurement.** Set difference is a set operation, and a count
  taken through a narrower filter is a property of the filter — state the filter whenever you quote the count.

## An arm is a decision, not a field

`autoMergeRequest` describes a *request*, not the current head and not the intent behind it.

- **Re-read `headRefOid` beside `enabledAt`.** An arm survives head changes, so a PR can sit armed against a head that
  no longer exists — including one whose deciding gate never ran. `enabledAt` records a time; only the sha beside it says
  what was armed.
- **A deliberate disarm needs a comment, not just the field.** Every later pass reads "not armed" as "nobody got round
  to it". Post the reason plus a checkable re-arm condition ("re-arm only when the head carries the artefact at the size
  measured in that push, and the deciding gate concludes at that head"), or the decision is invisible to the next sweep —
  including your own.
- **A sweep that cannot express "deliberately disarmed" will red the lane that did the right thing.** If its only
  exemptions are drafts and non-default bases, it treats a correct refusal as a defect and teaches lanes away from the
  correct behaviour. Add the decision to the sweep's inputs; do not widen the exemptions.
- **Never attribute an arm from the identity field.** Every lane shares one authoring identity, so `enabledBy` names all
  of them. Attribute from the arming actor's own log plus the per-PR timestamp — and first check whether the workflow you
  are blaming arms at all, because a report-only workflow does not.

## A defect you must ship, made self-cancelling

When a change has to land before its dependency exists, do not choose between a red PR and a golden that records a lie:

- **record the honest value** in the fixture or doc — the backend actually measured, the state actually true;
- **name the defect in the PR body** with the tracking issue, its close condition, and the measurement that rejects the
  tempting shortcut, so the next reader can tell a known defect from a regression without re-deriving it;
- **add a canary test that reds the moment the real fix lands** — its assertion is "the defect is still present", so
  landing the fix forces the marker and the paragraph to be removed in the same change.

A documented hole then cannot outlive its own documentation, which is the only form of "we will fix it later" that
survives a fleet of lanes.

## A gate that cannot fail is an assertion with no verdict

A check whose pass condition can be met without asking the question is worse than no check, because it occupies the
place where evidence should be.

- **Prove the population is non-empty.** A directory/file audit asserts `checked > 0`; without it an empty scan passes.
- **An expected-failure marker must fail when the expectation starts passing.** `xfail(strict=False)` swallows the
  xpass, so when the underlying defect is fixed nothing forces the marker's removal and it silently stops checking.
- **A project that bans skips bans its markers too.** Hooks can disagree: a later hook exempting `wasxfail` does not
  save an earlier hook that marks every skipped report as failed. Read the earlier one, it wins.
- **"Not invoked by any workflow" is not "never runs".** Coverage tools report callers; report-only, internal and
  bot-script targets have no caller by design, and the output must carry that caveat rather than imply a verdict.
- **A prose contract is usually enforced in one direction.** A generated file can state an absolute rule ("every
  change has one dated note of its own and its fragment, and nothing else") while the gate only reds a note missing
  its fragment — so the direction lanes actually forget, a change with no note at all, passes every check, and the
  omission is invisible to CI *and* to review. Before trusting a contract, exercise the direction that costs a lane a
  cycle: remove the artefact entirely and see whether anything reds.

## A red test can be the change's own safety check

Before filing a red as a symptom of the change, read **which assertion fired**. A relocation, a verbatim copy or a
rename is exactly the operation a duplicate-detector exists to catch — the test that reds may be reporting that the
change's own construction was wrong, not that the change broke something else. The difference decides whether the fix is
in the change or in the code the change touched, and it is invisible in a failure count.

## Verify a merge by content, because a squash rewrites the sha

After a squash-merge, `git merge-base --is-ancestor <pr-head> origin/main` correctly returns non-zero — the head never
became part of main. That is not evidence of a failed merge, and treating it as one sends a lane hunting a phantom.

```bash
gh api repos/O/R/pulls/N --jq '.state, .merged_at, .merge_commit_sha'
git cat-file -s <merge_commit>:<path>        # what landed
grep -c '<the named section or row>' <file>  # the content the PR added
cmp -s <tree copy> <live copy>               # for a synced artefact
```

Quote `state: MERGED` plus `mergedAt` plus one content check. The sha test answers "is this commit in that history";
the merge question is "did this content land".

## Unreachable is not nonexistent

`git log --all` and `git for-each-ref --points-at <sha>` enumerate **refs**, so a head that was force-pushed away is
reachable from no ref and both commands print nothing. The commit still exists on the server and in any clone that
fetched it, so "my log shows no such sha" is not evidence the sha was invented — after a lane force-pushes repeatedly,
every superseded head is unreachable-and-present.

```bash
git cat-file -t <sha>                                        # exists in this clone?  -> commit
gh api repos/O/R/commits/<sha> --jq .sha                     # exists on the server?
```

When a report and a measurement disagree about a sha, compare **which question each tool answers** before accusing
anyone: reading a stale-but-real head and reading a fabricated one look identical to `--points-at`. Name the subset the
sha belongs to as well (`<sha> was the head at hh:mmZ, superseded by <sha2>`), because a head is a fact with an expiry.

## A fix is on the branch only when the diff lists it

Two mechanisms silently discard committed work, and both have shipped a PR whose body described a fix the commit did
not contain:

- **`git checkout HEAD -- <path>`** reverts a file to the last commit, discarding uncommitted edits in it. Never run it
  on a file modified this session; use `git stash`, or recover from a named sha.
- **A rebase onto a moved base** can drop commits. Capture `git log <base>..HEAD --oneline` **before** the rebase and
  diff it against the same list **after** — a commit that disappears is a red, not a note.

Verify with the questions the PR answers, not with what a run said:

```bash
gh pr diff N --name-only | grep <the file the fix touches>   # must list it
gh pr diff N --name-only | grep <its test>                   # must list it too
git show HEAD:<path> | sed -n 'a,bp'                          # must show the changed lines
```

**A passing test count cannot detect this.** If the fix's assertions live inside existing tests, the count is identical
before and after: six passing tests on the unfixed tree look exactly like six on the fixed one. A number that cannot
distinguish the fixed tree from the broken one is the same vacuity as a gate that only ever says OK — check the
diff, and pin with an assertion that fails without the fix.

## Push churn destroys the verdict it is trying to obtain

With `cancel-in-progress`, every push cancels the matrix running on the previous head, so a lane that re-cuts on each
new main commit can produce many `MERGEABLE` heads and **no completed verdict at any of them**. Nine heads can pass
with zero conclusions; the PR is not failing, it is never allowed to finish.

- **Rebase when the diff is actually dirty, not when the base merely moved.** `mergeable` is the fact; a `MERGEABLE`
  head owes no action, and re-seating it costs a matrix and buys nothing.
- **Wait for main to be quiet, then push once.** Read the base sha in the same call that writes the push; a queue
draining faster than a branch can chase it turns rebasing into a self-cancelling loop.
- **A re-cut earns nothing a red does not.** If the content is right and only a verdict is missing, stopping is the
  productive move — the next push restarts the clock.

## A profile can hold the same skill twice, and the two copies have different readers

A skill at two paths inside one profile splits its readers: `skill_view` loads one copy, a sync or drift check compares
the other. Edits land in the loaded copy, the gate reads a file nobody edited, and **both report success** — neither can
see that the other exists. A "sync fails for reasons unrelated to my edits" symptom is this until proven otherwise.

```bash
find ~/.hermes/profiles/<lane>/skills -name SKILL.md | xargs -n1 dirname | xargs -n1 basename | sort | uniq -d
# empty = single copy; any line = a split, and the two readers disagree from now on
```

Two consequences worth carrying into any lane that ships scripts:

- **A script verified only in the profile copy is unverified as a shipped artefact.** Run the tree copy once — the
  first execution is where the bugs that every gate missed live.
- **Profile scratch is pruned** (a day, not a release). A tool that exists only under a profile directory is not a tool
  the fleet owns; version it under the lane's tree path with an issue and a PR, and prove the subset before copying
  (`tree-only lines that would be lost: 0`, then `N present, 0 missing` — moves show as delete+add in a diff, so confirm
  each moved line by content rather than waving the count away).
