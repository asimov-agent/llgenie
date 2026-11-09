# Triaging a red PR: own defect vs owned ambient red

A red check on a PR you opened does not automatically mean your diff is wrong. Classify it before doing anything, because "fixing" an ambient red rewrites a correct commit, and appeasing it goes green falsely.

## The three-question test

Ask all three; if they point away from your diff, route, do not fix:

1. **Is the failing test/file inside your diff?** `git diff --stat HEAD~1..HEAD` — if the red test is not in the changed-file list, you did not cause it.
2. **Does it red main's own CI in the same window?** `gh run list -R <repo> --workflow=ci.yml --limit 5 --json databaseId,headSha,conclusion,createdAt` — a shared red also appears on main's runs at unrelated heads.
3. **Is there an open issue naming the class?** Search issues for the test name / symptom BEFORE filing anything. An owned umbrella means the fix belongs to another lane.

All three pointing elsewhere = ambient owned red. Comment the measured cause on the PR naming the owning issue, notify the planner with head sha + run id, and leave the commit alone.

## ci-verdict is downstream, never an independent defect

When `ci-verdict` is red on a PR, read its check-run output — it is a per-check ledger that repeats the verdict:

```bash
ID=$(gh api repos/<repo>/commits/<sha>/check-runs \
  --jq '.check_runs[]|select(.name|test("verdict"))|.id' | head -1)
gh api repos/<repo>/check-runs/$ID --jq '.output.summary[0:400]'
```

It prints lines like `[ci-scope] linux/unit FAILED`. So `ci-verdict=failure` with one failing leg is ONE defect (the leg), reported twice — do not count it twice, and never treat the verdict as your bug.

## Do not manufacture a green for a PR blocked outside the lane

When the unblock needs something outside your lane — re-enabling a disabled producer workflow, publishing an image, a short availability window (e.g. 2 minutes) that is shorter than the producer's real build+push cycle — no dispatch you make can clear it in time. Correct disposition:

- Never weaken the gate: do not touch its assertions or shrink its red-set to appease a red.
- Post the precise measured cause on each PR, name the owning issue, and notify the planner with the head sha and run id.
- Say plainly that the PR gate has NOT gone green. "My change is verified by its own tests; the merge is blocked on owned issue #N" IS the completion — a claim of green is not.

## Direction check: did your own fix weaken anything?

When a fix touches a gate's red-set or an assertion, confirm the direction: the set GROWS (more conclusions treated as red), never shrinks. `grep -n "RED_CONCLUSIONS = " scripts/auto_merge.py` — making `cancelled`/`neutral` red is a strengthening; removing `failure` is a weakening.
