## Interrogating a filter: every subcommand must agree

A classifier with more than one entry point (`classify` for humans, `jobs` for the pipeline) can disagree with itself, and whichever one a workflow happens to call then decides whether a missing case is visible. Before accepting "it fails closed", run **each** entry point against the same bad input and compare **exit codes**, not messages:

```bash
python3 scripts/ci_scope.py classify --paths totally/unknown.file; echo $?   # 0 today = silent
python3 scripts/ci_scope.py jobs     --paths totally/unknown.file; echo $?   # 1 = wide + red
```

Two rules follow. **Failing closed means over-selecting *and* exiting non-zero** — selecting everything keeps the pipeline safe, the non-zero exit is the alarm, and a subcommand that widens silently has lost half the control. And **an empty argument must equal an absent one**: `--paths ''` exiting 1 while `--paths` (no flag) exits 0 turns a legitimately empty diff into a red for whoever writes `--paths "$CHANGED"`. **The empty case and the unknown case are not the same contract**, which is where a lane will argue with you for an hour:

| input | selection | exit | why |
|---|---|---|---|
| empty diff | every family | **0** | nothing for a human to fix; a red here fires on the mechanism's own triggers (`merge_group`, `workflow_dispatch`, a force-push that nets to nothing) and the author cannot clear it without inventing a change |
| path matching no class | every family | **1** | the pipeline is safe *and* somebody must add the glob — the alarm is the actionable half |

Put that table in the issue, the PR and the review brief. "It prints the full selection" is not the requirement: the exit code is what the check reports as red or green, so a run that widens and still exits 2 is fail-closed wearing fail-open's clothes. Test the exit code, not the message.

**Name the entry point, not just the expected number.** The same classifier can be right at the CLI and wrong in its
library: a fail-open widening implemented in `main()` (which swaps in `wide()` for an empty or unclassifiable diff)
leaves `scope([])` returning the small, unsafe selection, and the CLI's correctness makes that invisible — both are
"the classifier" to a reader, and only one is right. So every expectation states **who calls it** ("measured via
`jobs --paths`", not "the classifier returns"), and any caller a future change is likely to reach gets the safe answer
by default: move the decision *down* into the library function and let the CLI render what it returns. When two entry
points disagree, one of them is a defect — never a documentation nuance.

**A pin asserts behaviour, never a source spelling.** A guard written against `${{ github.base_ref || 'main' }}`
false-reds a correct implementation written as `BASE_REF="${EVENT_BASE_REF:-main}"`: two spellings, one behaviour, and a
test that cannot tell *absent* from *differently spelled* fails a fix that works. Write the assertion against what the
script does (does a dispatch run still compute a base? does it exit 0?) and only pin the literal text when the literal
is itself the requirement. A guard that rejects correct code is worse than no guard, because it teaches the lane that
the test is noise — and the repair is to publish the false red, not to quietly widen the regex.

**Never assert a list the tree is meant to extend — subset, not equality.** Manifests, rosters, workflow sets, job
lists and profile registries grow by design, so `assert names == ["a", "b"]` reds on the next legitimate addition and
teaches the next person to edit the test instead of the code: four separate instances in one night (a `.PHONY` set, a
`run.status` assumption, an inline→make call, and a manifest that four lanes were each appending a profile to). Write
`assert expected <= set(actual)`, and pair it with a referent check so a typo cannot hide — every listed name must
resolve to something real (`agents/<name>/SOUL.md`, a real job id, a target with a recipe). Subset for growth, referent
for correctness, never equality.

## A filter, its twin and the classifier are one set

A workflow filter must match the classifier's **class**, not a file extension. `**/*.md` in `paths-ignore` silently skips `ci.yml` for `data/trending-README.md`, `.hermes/skills/**/SKILL.md` and `tests/fixtures/**/*.md`, none of which are docs. Prove a filter with the case that catches it (a markdown-data-only PR must still schedule the matrix), not with a docs PR, where the bug is invisible.

**Read the parsed list, never grep for the string.** A branch that documents its own bug will match the grep: `grep -c '**/*.md' ci.yml` returns 2 on a file whose `paths-ignore` is the correct five paths, because both hits are the comment explaining why a bare glob is wrong. Verify the way GitHub evaluates it — load the `on:` block (or the list under `paths`/`paths-ignore`) and test the paths you care about against it — and treat a string hit inside a `#` comment as evidence of nothing. The same trap applies to any "is X present" check on a file that discusses X.

**A zero-count is a scan failure, not a fact — on contested attribution, read the full comment bodies.** At least once a grep/gh count returned `0`/empty on bodies that visibly contained the word, and the durable correction built on that zero was itself wrong (posted "no planner comment used phantom|fabricat" when the planner's *own* 23:45Z refutation had done exactly that a minute before withdrawing it). Attribution between two lanes posting under the same `andyholst` login cannot be settled by the author field — read the body verbatim and trust the self-identification inside it ("(planner, re-measured)"). Never post a correction that proves the *absence* of a thing from a probe that also returned empty for a thing that exists. **A correction against a lane's report is itself a claim and owes the same evidence bar: before flagging a reported fact as wrong, re-measure the *same fact* the lane names — on the surface that actually populates it, not merely a second surface.** A field that is null on one API while the fact is live on another is the same trap: REST `.auto_merge_request` reads null for an *armed-and-waiting* PR (it populates only as a merge fires), so "arm null ⇒ not armed" flags a healthy state; read the GraphQL `autoMergeRequest` before contradicting an "armed" report.

**Assert the three sets are ONE set, not that they are compatible.** The trigger's ignore list, the companion workflow's `paths:` and the classifier's class must be equal three ways — `set(CLASSES[cls]) == set(ci.yml paths-ignore) == set(docs.yml paths)`. A classifier still matching `*.md` while the trigger holds five literal paths makes the *printed selection* lie about the trigger, and the printed selection is the only place a human sees the truth; a pin that only checks one pair leaves the third free to drift.

Two things every trigger change owes, both of which CI catches and reading does not:

- **A new trigger needs its dispatch-form annotation and its regenerated table.** A bare `workflow_dispatch:` fails `check-dispatch-forms` (a column-0 `# dispatch: no inputs — <reason>` line, plus the `docs/BOTS.md` row), and that gate runs inside `ci-unit`, so it reds `linux/unit`: a verdict blocker, never a lint nit.
- **Prove the trigger by running it.** `gh workflow run <scope>.yml --ref <branch>` yields a real run id and a log line naming the fallback (`No github.base_ref for event 'workflow_dispatch': reporting the diff against main.`); parsing the YAML proves only that the text exists. An event the repo cannot emit stays *"not exercised — no merge queue configured"*, which is a different sentence from "impossible".

And the meta-rule from both: **when CI catches a gate your local loop omitted, add that gate to the loop before the next push.** A green local run that skipped `check-dispatch-forms` means less than it looks, and the lane that reports it honestly is doing better work than one that reports green.
