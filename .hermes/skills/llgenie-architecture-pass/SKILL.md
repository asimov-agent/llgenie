---
name: llgenie-architecture-pass
description: "Audit this repository's architecture and file refactor issues."
version: 1.0.0
metadata:
  hermes:
    tags: [llgenie, architecture, github, issues, refactor]
    category: software-development
    related_skills: [github, codebase-inspection]
---

# Architecture pass

A structural audit of this repository that ends in issues another bot implements. This is the contract a
host agent runs when the owner says "go over the architecture and file the refactoring work". It is the
HOST half of the fleet: no CI leg preloads it, and it is admitted by name in `HOST_SKILLS`
(`scripts/check_agent_skills.py`) so every admission is a reviewed diff.

## Inputs

- **`origin/main`**, and its sha taken from the API, never from the checkout's `HEAD`:
  `gh api repos/asimov-agent/llgenie/commits/main --jq .sha`.
- A read-only tree of that commit — the working checkout is routinely parked on a PR branch:

  ```bash
  cd /home/asimov/repository/git/llgenie && git fetch origin
  git worktree add --detach ../llgenie-wt/<name> origin/main
  # 0 modified files, real main; `git worktree remove` it when the pass is done
  ```

- `docs/ARCHITECTURE.md` §Scripts (the grouping the tree is supposed to have) and `AGENTS.md` (the house
  rules a finding must not contradict).
- The open + closed issue list: `gh issue list --state all --limit 900`. A finding already filed is a
  comment on that issue, never a second issue.

## Output

- One issue per finding, labelled `agent:implement`, rendered through `scripts/issue_body.render`
  (`Problem`, `Why it matters`, `How we fix it`, `Benefit`, `Acceptance criteria`, optional
  `Not covered`, `Technical` last) — the marker is the body's first line and is what dedupe reads back.
- The baseline sha in each body's `## Technical`, plus the method that produced every count.
- One cross-reference comment per issue naming the dependency order, and a hand-off to the planner to
  triage rather than an assumption about capacity.

## Rules

- **Measure `origin/main`, never the working checkout.** `/home/asimov/repository/git/llgenie` is often
  parked on a feature branch; six issues were once filed against a PR tip while claiming `main@<sha>`.
  Take the sha from `gh api`, cut a detached worktree, and write that sha into the issue.
- State the counting method next to every count a reviewer could reproduce differently: targets come
  from `make -qp`, not a line regex; "files containing the call" and "test modules containing the call"
  are different denominators and must be named.
- Name the population a count is drawn from when two counts share a number. "Eleven wrappers" meant
  three different elevens in one pass (the names, all helpers, and the bodies that never read an exit
  code); the implementer greps the narrowest one and under-scopes the fix.
- A file path or line number in an issue is a claim: read it at the measured commit, not from memory or
  from the branch you happened to be in.
- Read the label back after filing (`gh issue view <n> --json labels`) — a create-flag label can be
  silently dropped on a CI token path.
- Reference linked issues by NUMBER in the body. "the issue linked below" breaks the moment bodies are
  regenerated and edited out of order.
- A finding about someone else's code is an issue, and the change is another leg's PR — never implement
  it from a pass. **A finding about your own behaviour artifact is the exception**: when the rule that
  failed lives in a skill, a SOUL or a procedure doc, carry it into the tree yourself as an issue **and**
  a reviewable PR. Filing the issue and stopping leaves the rule outside version control, which is the
  defect you just filed. Never merge, never push to `main`, never edit `AGENTS.md` (owner approval).
- Copy the mechanism from the tree, not from imagination: `git diff origin/main...<branch>` of the closest
  precedent and match its shape, so the second instance is a one-line neighbour rather than a second
  design. Check whether that precedent is merged; if it is not, say in the issue which of the two lands
  first, so the conflict is one line either way.
- Verify a gate you touch by **negative control**: break the thing, run the gate, confirm the exact
  finding key, restore. Restore from a copy taken before the sabotage — `git checkout -- <file>` restores
  HEAD and silently discards your own uncommitted work in that file.
- A gate that matches a **substring** proves nothing: `if section not in body` still passes a body whose
  heading was renamed to `## Rules for reviewers`. Read the matcher before citing a gate as evidence, then
  measure every committed instance before tightening it — when they all already comply, tightening is free
  and it is what makes an acceptance criterion real rather than rhetorical.
- Keep the profile mirror and the repo copy in step: normalise `name`/`description`/provenance and diff
  them. Drift between the two is a finding, not a chore for later.
- A criterion that names TWO docs hides a second owner: `grep -rln '<subject>' docs/ AGENTS.md README.md`
  before saying the documentation is done. The queued alarm was described in `docs/BOTS.md` *and* in a row
  of `docs/ARCHITECTURE.md`'s cron table, and only the first got the fix until the criterion was re-read.
- A corrected number means correcting the BODY, not just adding a comment — the implementer reads the
  body.

## The audit checks that have produced real issues

Run these over `scripts/*.py` with `ast`; hashes of normalised `ast.unparse` bodies find copies that
`grep` misses.

| check | how | why it lands |
|---|---|---|
| import graph vs the doc's own grouping | resolve local imports, map onto the §Scripts groups, DFS for cycles | a prose-only layering plus a real cycle is a gate waiting to exist |
| duplicate function bodies across modules | sha1 of normalised `ast.dump` per `FunctionDef` | byte-identical readers per leg = drift in a coordination protocol |
| subprocess wrappers | defs named `_run`/`_sh`/`_gh`/`run_gh`/`_cmd`, and whether the body reads `returncode` | "never reads the exit code" is the actionable count, not "N wrappers" |
| import roots | count `sys.path.insert` and both spellings (`import <m>` vs `import scripts.<m>`) per test file | two module objects in one session |
| Makefile size | `make -qp` for the TARGET count; line regexes only for recipes and inline snippets | a line regex double-counts targets declared twice |
| workflow duplication | identical `- name:` steps across `.github/workflows/*.yml`; `workflow_call` users | scaffold copies that must be fixed N times |
| a documented invariant with no gate | for each claim in `docs/ARCHITECTURE.md` ("X is refused/guarded/checked"), find the make target that runs it — `grep -c <script> Makefile` | a guard wired to no target enforces nothing, and is usually red when you finally run it |

## When two PRs both add a host skill

Every host skill writes `HOST_SKILLS`, `.hermes/skills/README.md` and `tests/test_agent_skills.py`, so the
second PR to merge always conflicts. Measure it (`git merge-tree --write-tree --messages a b`), resolve in a
throwaway worktree, and prove it on the MERGED tree — the recipe, including the README trap that leaves two
host-skill paragraphs and a false "the one HOST skill" sentence, is `references/host-skill-merge.md`.

## When a number is challenged

Re-measure, then post a **delta table** (claim / as filed / measured / verdict) plus a rescope verdict,
and edit the body so the artifact is right: a comment alone leaves the wrong number where the
implementer reads it. Rescope when the corrected count changes an *acceptance criterion*, not when it
only changes prose.
