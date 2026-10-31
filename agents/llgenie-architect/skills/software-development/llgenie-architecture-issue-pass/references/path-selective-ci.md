# Reviewing a path-selective CI change

The recipe for judging a "select stages from the changed paths" branch: what the trigger may filter, what
must stay unfiltered, how the two selection levels relate, and the controls that prove the gate survived.

## The filter is the class, not the extension

A trigger-level `paths` / `paths-ignore` list runs the moment ONE path fails to match, so it is only safe
when its patterns equal the docs class exactly. `**/*.md` does not: markdown in this repository is also data,
contracts and fixtures, each read by a gate that the filter would skip.

| path | what it is | gate it feeds | class alone? |
|---|---|---|---|
| `data/trending-README.md` | the vendored store's README, read by `sync_registry.py` | `check-registry`, `check-quant-catalog`, unit | no — `data` + `docs` |
| `data/MODEL_CONTRACT.md` | the contract the store is validated against | `check-registry` | no — `data` + `docs` |
| `.hermes/skills/**/SKILL.md` | a bot leg's contract | `check-agent-skills` (inside `ci-unit`) | no — `skills` + `docs` |
| `skills/engines/**/SKILL.md` | the source `generate-engine-params` reads | `check-engine-params`, `check-engine-skill-gap` | no — `engines` + `docs` |
| `tests/fixtures/**/*.md` | unit-test fixtures | the unit suite | no — `tests` + `docs` |
| `docs/**`, `agent-wiki/**`, `openspec/**`, `README.md`, `CHANGES.md` | documentation only | the docs gates | yes |

So the trigger lists the last row verbatim, and `ci.yml`'s `paths-ignore` must equal the sibling docs
workflow's `paths` — the two workflows split one class, so a path one ignores the other must run.

## Empty and unclassifiable diffs must WIDEN, never narrow

An empty diff (merge-queue ref, force-push, `workflow_dispatch`) and a path no class names are the two
silent-failure paths: a classifier that treats either as "nothing to run" removes the whole pipeline for
the runs nobody is watching. Both select every class, and the exits differ on purpose:

| diff | selection | exit | why |
|---|---|---|---|
| empty | every class | 0 | nothing to fix — the run simply widens |
| path matching no class | every class | 1 | the pipeline runs safe AND a human owes the missing glob |

Test both as data: assert the selected set equals every family, `skipped` is empty, and the unknown path
still returns non-zero. A classifier whose default is "no paths → usage error" is the failure this table
prevents — a loud exit alone is not enough if the selection it published was still partial.

## Two selection levels, never merged

| level | question | mechanism |
|---|---|---|
| family | can this diff reach the family at all? | the path classifier, at the trigger |
| row | did this cell's inputs actually change? | `list-engine-images … CHANGED=<ref>`, rendered-`Dockerfile.<backend>` comparison |

The class gate only short-circuits a family the diff cannot reach; it never decides which cells inside a
family run, and never replaces the rendered-input comparison with a path heuristic. Where a family has no
`CHANGED=` producer, the family gate is the only gate — say so per row rather than implying otherwise.

## What must not be filtered

- **`push` to `main`.** A merge keeps the whole matrix; assert it in a test, not a comment.
- **The classifier itself.** It runs on every PR with no filter of its own, and it must listen to
`merge_group` and `workflow_dispatch` too — a reporting check that only fires on `pull_request` vanishes
on exactly the refs where the diff is unusual. `github.base_ref` is EMPTY on those two events, so fall
back (`${{ github.base_ref || 'main' }}`) or the diff runs against `origin/` and fails on the merge-queue
runs the requirement was written for.
- **Anything the docs class can still break.** The docs gates live inside `ci-unit` today; a docs-only PR
that merely skips the matrix loses them, so the docs workflow must run them explicitly.

## Enforcement with no required checks

When `branches/main/protection` is 404 and the ruleset carries only deletion/non-fast-forward, a red check
is advisory for a human merge. What still refuses is the merge bot: it requires `mergeStateStatus == CLEAN`.
GitHub's documented behaviour is that a failed non-required check yields `UNSTABLE`, not `CLEAN` — label
that as documentation unless a red PR exists to measure it on, and name "make these required" as an owner
decision rather than implying the gate is airtight.

**`mergeStateStatus` cannot answer that question on a repo whose PRs all sit at `REVIEW_REQUIRED`.**
Measured: `BLOCKED` appears identically with one failing check and with none, because `REVIEW_REQUIRED`
masks `UNSTABLE` — so a probe that plants one broken link and reads `BLOCKED` will "prove" blocking and
prove nothing about checks. Isolating the check needs the review requirement out of the way, which a
bot-authored PR cannot do (GitHub refuses `Can not approve your own pull request`). Record the honest,
narrower conclusion instead: only `auto_merge.decide()` discriminates here, because it refuses on
`!= CLEAN`; `mergeStateStatus` needs `reviewDecision` and `isDraft` beside it, plus a **before/after pair
on the same PR**, before it means anything.

**`UNSTABLE` is a third cause collapsing onto the same value.** Measured on a PR whose 27 checks were 18
`SUCCESS`, 1 `SKIPPED` and **8 with no conclusion at all**, zero failures: `mergeStateStatus` still read
`UNSTABLE`. So "a check failed" and "checks are still running" are indistinguishable from the field.
Any probe must capture the `statusCheckRollup` conclusion buckets — **including the no-conclusion count**
— in the same snapshot as `mergeStateStatus`, or it records `UNSTABLE` and calls a question settled.
Also check whether the bot path can even reach the decision: `auto_merge.decide()` declines on an empty
`GH_TOKEN`/`GITHUB_TOKEN` before evaluating any of this, so a local run proves nothing about the refusal.

## Expectations for a verification table come from the LIVE head, never a predecessor's

Before accepting or writing an expected column, print the classifier's own constants at the head that will
actually run:

```bash
git show <head>:scripts/ci_scope.py | grep -A3 '"docs":'
```

A table measured at a superseded branch head carries that head's bugs into the test — when the docs class
still contained `*.md` there, every markdown path matched two classes and the counts were inflated
(`data/*.md` 12 instead of 10, a skill file 15 instead of 13, a fixture 8 instead of 6). Checking a
colleague's table against two heads, and naming which head each number came from, is the review; replacing
the table wholesale is not.

State **which entry point** produced each number — CLI vs imported function. When they disagree (the CLI
widens to every class on an unreadable diff, the library returns the narrow set), a table without the
entry point is unmeasurable: the tester measures one value and the library reports another, and both are
"right".

## Negative controls to demand in the PR

1. A class-absent stage still reports a check name (or, when the trigger filters, the always-present
   classifier check states which families it did not select, with the class that would have).
2. A deliberately broken link in a docs-only PR still reds the docs gate.
3. A deliberately broken engine param still reds its engine row — selection is by path, never by "looks
   harmless".
4. `workflow_dispatch`, a merge-queue ref and an empty/unknown diff all run everything.

Each control is a run id at the head sha, cited; "asserted in the body" is not a demonstration.

## Adding a trigger to a workflow here

`make check-dispatch-forms` (a `ci-unit` gate) rejects a bare `workflow_dispatch:` and a stale doc table:

- exempt it with a **column-0** line `# dispatch: no inputs — <reason>` above `on:`; the matcher is
  `^#\s*dispatch:\s*no inputs`, so an indented comment inside the `on:` block does not count;
- regenerate the table in `docs/BOTS.md` with `make dispatch-forms-report` and paste it between the
  `dispatch-forms` markers — the gate keeps failing while the table is stale, which is it working.
