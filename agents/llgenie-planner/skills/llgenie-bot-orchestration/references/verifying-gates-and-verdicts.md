# Verifying gates, verdicts and regenerated fixtures

How to turn a bot's report into a verdict you can stand behind. A report is a claim; the ref, run or API is the evidence. These are the checks that have caught wrong verdicts — including the planner's own.

## Run the command CI runs, not the one the docstring suggests

A script with several subcommands often has a *report* mode that reds by design on a clean tree and a *gate* mode that compares against a baseline. `make <target>` in the Makefile is the gate; a bare `script.py check` may be the unfiltered report of every grandfathered finding.

- Before declaring a tree broken, read the Makefile target (`grep -n '<gate-name>' Makefile .github/workflows/*.yml`) and run exactly that. A report that reds on untouched `main` is not a verdict about the branch.
- If the documented invocation and the CI invocation disagree, that is a real defect worth filing: a reader who follows the usage block either "fixes" grandfathered findings the baseline deliberately permits, or learns to ignore a gate that was telling it nothing. Ask for the usage block to name every subcommand with its failure semantics, plus a test asserting the CI subcommand appears in it.

## Reproducing a PR's CI needs the merge tree, not the head tarball

PR workflows check out the **merge of head into base**. A `git archive <head>` extraction is missing base-side files — a newly added script, a conftest, a fixture — and produces "file not found" and false test failures that the PR never had.

```bash
git fetch <remote> '+refs/heads/<branch>:refs/remotes/origin/<branch>' \
                   '+refs/heads/main:refs/remotes/origin/main'
TREE=$(git merge-tree --write-tree origin/main origin/<branch> | head -1)   # clean merge ⇒ tree sha only
git archive "$TREE" | tar x -C /tmp/verify
```

Run the gate and the tests inside that extraction. If a test fails only in a head-only extract, suspect a missing base-side file rather than the PR.

## Anchor the pattern; a substring is not an artifact

`grep -c <identifier>` over `git log` finds **prose** — commits that document a convention mention the identifier in their body. Trailers are line-anchored constructs:

```bash
git log --format=%b <base>..HEAD | grep -i '^co-authored-by' | grep -c <identity>   # 0 = no such trailer
```

The same class appears elsewhere: counting occurrences to assert a file, fragment or entry exists. Assert the construct (anchored line, parsed field, set membership), never a substring count.

## Every count carries the selector that produced it

A number quoted without its selector is a claim about time, not about the branch. State which subcommand, which flags and which subset produced it — returning only the always-on jobs is a different contract from returning the full matrix, and both are "N jobs".

## Accepting a regenerated golden or fixture

A regenerated fixture is legitimate only if the diff is *explained*, not merely green. Quantify it before accepting:

1. **Case count unchanged**, and the set of models or rows added or removed is empty.
2. **Changed cases counted**, and changed-but-outside-target-scope is **zero** — a change to one arch must not move any case outside that arch.
3. **One representative change quoted old → new**, and the mechanism matches the stated cause. If it does not, the commit message is false even when the suite is green.
4. **Hermeticity stated.** If the test reads only committed fixtures the regen is *durable*. If it walks live data the regen is only *current* — the green says "the live tree happened to match today" — and the tick needs the hermeticity fix named as what makes it hold.

Refuse a regeneration whose purpose is to make a suite agree with the branch: where behaviour differs from main, a rewritten golden or a marker hides the difference instead of fixing it.

## Tick and checkbox provenance

A tick is a claim about a run, and the commit that flips it usually cites that run.

- Check the citation points at a **completed/success** run at a sha that still exists. A tick can be *true* at the current head while the commit that flipped it cites a head where it was false — a reader following the citation lands on a red run.
- **Amending an ancestor commit rewrites every descendant sha**, so a run id cited inside the amended message dangles. Record the run id in a **PR comment** instead, and say the older citation is superseded.
- **Chicken-and-egg:** unticking to "be honest before CI" can red the very gate the tick satisfies, including the run that would earn it. Keep the tick, let the verdict decide, and untick only on a red run — then name the test.

## A lane's versioned instruction outranks a planner dispatch

If a lane refuses an instruction because its own versioned profile rule (SOUL or skill) says otherwise, **that is correct behaviour** — the more specific, versioned rule wins. Do not override it and do not re-dispatch more firmly: file the issue that changes the instruction, then re-sync the profile. A lane that quietly obeys a dispatch against its own rules has learned nothing from the correction.

## The lane shipping a gate ships its prescribed shape first

The PR that adds a policy gate should itself be the reference example of that policy. When a change-PR policy says "add the fragment, never the aggregate", the gate's own PR ships fragment-only, and verifying the gate accepts its own PR's shape is the demonstration. If it does not, the policy is prose.

## Snapshot versus verdict

A status with a `completed_at` is a verdict and cannot revert. A status without one is a snapshot — `in_progress` with `started_at=never` is a queued job, not a hang, and a run reported "stuck since HH:MM" may have concluded successfully minutes after the report was written. Re-read the run before repeating the claim.
