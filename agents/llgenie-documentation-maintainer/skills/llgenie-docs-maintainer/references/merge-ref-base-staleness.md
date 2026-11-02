# check-pr-closing ranges over the merge ref — a stale base fabricates violations

The `make check-pr-closing` guard (CI job `guard`) does not compare your commits to the PR body's base directly. It reads `base..HEAD` where **HEAD is GitHub's merge ref** (`refs/pull/<n>/merge`) — a temporary merge of your branch into the *current* default-branch tip.

**Consequence:** if your branch predates commits that landed on `main` after you branched, those main commits fall inside the checked range. Their own `#N` references (`closes #1514`, a `#1524` mention) then read as *your* claims, so the guard reds with "claims #X without adjacent close" and "close sets differ" — even though your commits never mention those ids.

**Symptom:** `guard` + `scope` + `ci-verdict` FAIL **together** at a head that looks fine locally when you run the gate with `--base origin/main` and a correct body. `mergeStateStatus` reads `UNSTABLE`/`BLOCKED`.

**Diagnose** (measure, don't guess): `git log --oneline origin/main` and `git merge-base --is-ancestor <your-base> origin/main`. If the failing run's base sha (e.g. `--base 309cdf69`) is older than current `origin/main`, and main has since gained a squash mentioning the "foreign" ids, that is the defect.

**Fix:** rebase your branch onto fresh `origin/main` (fetch the explicit refspec first), then `--force-with-lease` push. The merge-base becomes the main tip, the range collapses to only your commits, and the guard greens. This is the #1015-permitted rebase (red/conflicting base), not rebasing on every main move.

**Never** "fix" it by adding the foreign `closes #N` to your commit or PR body. The defect is the stale base, not the claim set; editing the body fabricates a closure you do not own.

Measured example (docs lane, PR #1525): head `5d08f34c` red on `guard`/`scope`/`ci-verdict`, run base `309cdf69` predating `origin/main` `279fc0d6` (which carried the merged #1524 fix, `closes #1514`). Rebasing the same three commits onto `279fc0d6` → head `b96a257e`: `guard` x3 + `scope` + `holds` all SUCCESS, zero reds.
