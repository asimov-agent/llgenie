# Proving a gate is ENFORCED (not just present)

A finding that says "gate X is wired into no workflow" — or an audit claim that "gate X is enforced" — is only answered by a chain, not a grep. Verify every link; a missing link is a real defect even when the gate happens to fire today.

## The five-link chain (a gate truly gates merges only if all five hold)

1. **Script exists** and does the check (e.g. `scripts/check_empty_files.py`).
2. **A make target runs the script** — and note the *indirection*: the gate is often composed in via another target (`ci-lint:` runs `$(MAKE) check-empty-files`), never named literally in the workflow YAML.
3. **A workflow runs that target** (`scope.yml` / `pipeline.yml` call `make ci-lint`). Confirm from a **live run log**, not from reading YAML — the log line `make check-empty-files` executing is the only proof the chain runs in CI.
4. **A red on that check-run blocks the merge.** Branch protection may 404 (rulesets / app-managed); then read what the merge gate actually consumes — e.g. `auto_merge.py` `failing_checks()` folding `RED_CONCLUSIONS` from the check-run rollup. If the red check does not appear in the merge gate's failing set, the gate is decorative.
5. **A test pins the wiring.** This is the link that silently rots: nothing asserts the make target still composes the script. Static proof of links 1–4 is not enough — an unpinned wiring can be dropped by any future make-target edit with zero test noticing. If link 5 is missing, THAT is the defect to fix (do not stop at "it already works").

## Grep-the-indirection pitfall

When checking "is X wired in?", grep the composition, not only the literal name. `git grep check-empty-files` over workflow YAML finds nothing when the gate is composed inside a make target — conclude "not present" only after checking every indirection layer (make targets, composite actions, reusable workflows). A literal-string grep that misses an indirection produces a false "not wired" finding.

## Prove the guard catches the bug (never skip)

Before trusting a new wiring/proof test: run it green → **plant the bug** (temporarily delete the wiring line from the make target) → run again, confirm it goes RED and names the break → restore → confirm green. A test only ever run against the fixed tree has demonstrated nothing.

Guard-prove a test that sits in a loop over ALL jobs (`for name, text in runs.items()`), not just the one job the issue named. Plant the exact spelling the fix removed into a DIFFERENT job than the one already pinned — if two tests fire (the named-seam test and the all-jobs test), both must red naming the planted job; if only the named-seam test reds, the all-jobs loop still *accepts* the forbidden spelling and a new job could silently reintroduce the defect class. Then restore and confirm the whole file green, not just the touched test.

## A "pulls/uses set" that lists the forbidden spelling ACCEPTS it

The expensive hole: a helper builds a positive set of legitimate spellings (`pulls = {n for n,t in runs.items() if "make foo-pull" in t or ...}`) and a job that uses the DEPRECATED target lands in that set as a legitimate consumer — so nothing forbids a NEW job from calling it. When a target is deprecated-by-design (fork PRs can never publish the hash, so a strict `pull` reds for a write GitHub will never grant), add an explicit negative: `assert not any("make <deprecated-target>" in t for t in runs.values())` over every CI/pipeline/published job, not only the two gates the issue named. The named-seam test pins today's callers; only an all-jobs negative stops tomorrow's.

## Line references in a note rot — grep before you commit one

A doc note or wiki page that cites `Makefile:1392` or `ci.yml:83` is a measurement frozen at write time; the next rename/insert shifts it. Before committing a note with a `file:line` reference (and when auditing an existing one), run `grep -n '^<target>:' Makefile` and reconcile: a note pointing at the wrong line sends the next reader to the wrong target. Fix the note in the same commit as the change that moved the line, and treat a stale line ref as the same class of defect as a red run.

## Fix-PR checklist for a gate-wiring change

- One atomic commit; push to the fork (`origin`) branch; open ready-for-review (never draft) against `upstream main`:
  `gh pr create -R asimov-agent/llgenie --base main --head <user>:<branch> --title … --body-file …`
- Body/message must carry an **adjacent** `closes #<issue>` line (an `Issue: #N` claim alone does not close — the closing gate reds).
- Test-only change with no behaviour change → no `changes.d` note needed (per the docs gate); but append a trailing `\n` to any new doc/test file — a missing linefeed reds `ci-lint`.
- Read the PR back before reporting: `gh pr view <n> --json isDraft,mergeable,mergeStateStatus,closingIssuesReferences,headRefOid` — `draft=false`, `closes` lists the issue, head matches the pushed sha.
- Do not arm auto-merge as this lane; report PR number + head sha + proving run id to the planner.
- After the change lands, verify the gate by its OWN new test going red-on-plant / green-on-restore, and confirm the full rollup is green (the new test usually lives in `linux/unit`, a long matrix cell — wait for it rather than claiming green on partial checks).
