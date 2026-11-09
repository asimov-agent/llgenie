# PR-body gates and how a body-only fix clears them

## The CLI surface — three different tools, three different argument shapes

Guessing these wastes a call each and, worse, a wrong invocation that exits 0 reads like a pass. The
three are NOT one command with one flag set:

| what you want | the actual invocation |
|---|---|
| a body gate (`agents-line`, `sync-line`, `openspec-change`, `acceptance-form`, `changes-index`) | `python3 scripts/check_pr_hygiene.py <subcommand> --head <sha> --base <sha-or-ref> --body-file <f>` |
| base freshness | `make check-pr-base PR_BASE=origin/main` — a **Makefile target**, not a hygiene subcommand; there is no `check_pr_hygiene.py base` |
| acceptance ticks | `python3 scripts/check_pr_acceptance.py check --body-file <f> --base origin/main --rev <sha> --cwd <worktree>` — `--rev`/`--cwd`, **not** `--head` |

`check_pr_hygiene.py check --head …` fails with `unrecognized arguments`, and `… base` fails with
`invalid choice: 'base' (choose from 'check', 'report', 'agents-line', 'sync-line', 'openspec-change',
'acceptance-form', 'changes-index')` — that error message is the authoritative list, so read it rather
than trying the other spellings. Validate every body gate in ONE pass before pushing, because the
anonymous exit-0 of a wrong subcommand name is indistinguishable from a pass in a chained `&&` line.

## The guard gates run in a FIXED ORDER, so one red MASKS the rest

`ci.yml`'s guard job runs its `check-pr-*` steps in sequence and stops at the first failure, so the gate
showing red is usually only the first of several. Clearing it does not make the PR green — the next gate
down the chain surfaces, and it reads exactly like a regression you just introduced. The order is:
`check-pr-authors` → `check-pr-closing` → `check-pr-agents-line` → `check-pr-sync-line` →
`check-pr-openspec-change` → `check-pr-acceptance-form` → `check-pr-acceptance` → `check-pr-base` (LAST).

Two consequences:

- **`check-pr-base` is the last step**, so it never appears in a run's log while any earlier gate is red.
  When asked for "proof check-pr-base passes", run it yourself in the worktree at the pushed sha
  (`make check-pr-base PR_BASE=origin/main`) and say it was measured locally because the guard has not
  reached that step. Never report it green from an absent log line, and never read its absence as a red.
- When a red you just cleared exposes a new one, prove the new one is **pre-existing at the ORIGINAL head**
  before attributing it to your change: `git worktree add --detach /tmp/attr <old-head>`, run the same
  gate there, and compare. A gate that was merely unreachable behind an earlier failure is not your bug.

## Guards read the PR body LIVE, not the tree

`check-pr-acceptance`, `scope` and the `guard` job read the PR body from the API at run time (issue #1589),
not the committed tree. So **a body-gate red is never fixed by a commit**: edit the body, then rerun the
concluded run at the SAME head sha. The head does not move; nothing is re-pushed; previously green
check-runs at that sha stay valid.

```bash
gh pr edit <n> --repo asimov-agent/llgenie --body-file /tmp/body.md
gh run rerun <run-id> --repo asimov-agent/llgenie --failed   # per failed workflow run, not the PR
```

Rerunning a *concluded* run whose verdict was measured against a stale body is the owed case; it is not
the "never cancel a live run" ban. Then read the verdict from `check-runs` conclusions (`success` /
`failure` / `cancelled`), and poll the run object with `gh api repos/.../actions/runs/<id> --jq` —
`gh pr checks` alone renders `cancelled` like red.

## `check-pr-acceptance`: a TICKED criterion must carry inline proof, or the gate reds

Ticking every box on the issue is not enough — an unproven tick is refused exactly like an unticked box.
The marker is parsed **inline, at the end of the criterion line**:

```python
PROVEN_MARKER = re.compile(r"\(proven:\s*(.*?)\)\s*$", re.S)   # must END the line
RUN_ID  = re.compile(r"\brun\s*=\s*\d+\b")                        # a CI run id, or
RC_SHA  = re.compile(r"\brc(?:\s*=\s*|[\s(])\s*\S+\b") + GIT_SHA  # reproducible command + rc + sha
```

So this passes:

```markdown
- [x] the script resolves `gh` and runs under `PATH=/usr/bin:/bin` (proven: `env -i PATH=/usr/bin:/bin python3 scripts/x.py` rc=0 3786c7fa)
```

and a `(proven: …)` on its **own line below** the criterion does **not** — the regex anchors to `$` of the
criterion's own line, so the box reads as ticked-but-unproven and the gate prints
`names no CI run and no reproducible command+rc+sha (measured text: "")`. Measured: two separate edits
were spent moving the same evidence from a following line onto the criterion line.

Either form satisfies it — a CI `run=<id>` for something only CI can prove, or
`<command> rc=<n> <sha>` for something a re-measurer repeats in one command. Write the tick and its proof
in the same edit, and re-run the gate on the live body:

```bash
python3 scripts/check_pr_acceptance.py check --body-file /tmp/body.md --base origin/main --rev <sha> --cwd <worktree>
```

Note the argument names: `--rev`/`--cwd`, **not** `--head`. The gate reads the ISSUE's body from the API
(so the tick lives on the issue, not in the PR body) and the PR body only for what it closes.

## `check-pr-sync-line`: a PR touching `agents/**` owes an exact-format `SYNC:` line

Any PR whose diff touches `agents/<lane>/` reds until the body carries a line naming each changed profile
and its re-sync command, matched by `SYNC_LINE = ^SYNC:\s+([A-Za-z0-9_-]+)\s+make sync-agent-profile PROFILE=\1\s*$`.
One profile per line, and the backreference means the profile name must appear **twice, identically**:

```
SYNC: llgenie-pr-merge-conflict make sync-agent-profile PROFILE=llgenie-pr-merge-conflict
```

Two failure shapes: naming the profile once, and adding prose after the command (the `\s*$` anchor kills
it). When the sync itself REFUSES (`live-edited-not-tree`, see `skill-script-hygiene.md`) do not silently
force it — add the `SYNC:` line and **disclose the refusal in the body** so the reviewer sees which files
did and did not propagate, rather than reading a bare `SYNC:` line as "everything synced".

## `check-pr-acceptance`: closing a multi-lane umbrella issue

A PR that closes a fleet-rollup umbrella (criteria spanning several lanes) cannot tick every box, so the
gate reds unless each un-tickable criterion is declared out of scope. The exemption is parsed strictly:

- The heading must be **exactly** `## Not covered`. `issue_body.section_body` matches
  `HEADING_RE = ^##\s+(.+?)\s*$` with `group(1).strip() == name`, so `## Not covered — <subtitle>`
  matches NOTHING and the section reads as empty. Put the explanation in the first paragraph, under the
  bare heading.
- Each bullet must **end** with `#<n>`: `OUT_OF_SCOPE = (?im)^-.*\s*#\d+\s*$`. A trailing `)` or `.`
  after the link kills the match.
- Each criterion's **first three words**, normalised to lowercase `[a-z0-9 ]`, must appear somewhere in
  the section text (`_declared_out_of_scope` does `lead in normalised_section`). Quote the criterion's
  opening words in the bullet rather than paraphrasing them.

## Debug the gate against your body file before pushing

Do not push-and-wait to discover a parse miss — import the gate's own functions and run them on the body:

```python
import sys; sys.path.insert(0, 'scripts')
from scripts import issue_body
from scripts.check_pr_acceptance import _declared_out_of_scope
body = open('/tmp/body.md').read()
print(repr(issue_body.section_body(body, 'Not covered'))[:300])   # empty string => heading mismatch
a = issue_body.load_issue('asimov-agent/llgenie', 1812)
```

Assert per criterion (`_declared_out_of_scope(body, crit)`) rather than trusting the aggregate error count.
An empty `section_body` output is the tell for a heading that merely *looks* right.

## The openspec-presence gate does not exempt `agents/**/SKILL.md`

`_is_docs_only` covers `docs/`, `CHANGES.md`, `agent-wiki/` — NOT `agents/<lane>/SKILL.md`. A skill-text
change therefore trips the openspec-presence gate and must carry either a real change under
`openspec/changes/<name>/` (proposal + `specs/**/spec.md` with `### Requirement:` delta headers and
`#### Scenario:` blocks, plus `tasks.md`) or a `OPENSPEC:` body line. Validate with
`make openspec-validate NAME=<change>`, and note the openspec container writes the change dir root-owned —
`docker run --rm -u root -v "$PWD":/repo llgenie/test chown -R $(id -u):$(id -g) /repo/openspec/changes/<name>`
before you write into it.

## An `openspec-change` red on a PR you only REBASED is author content — disclose it, never fabricate

`check-pr-openspec-change` reds when a PR changes product code (`scripts/**`, tests, workflows) but its body
names no `openspec/changes/**` file and no `OPENSPEC:` line. On a PR this lane only rebased, that red is the
ownering lane's content defect: the rebase preserved their commit and their body, and a rebase cannot
introduce or cure an openspec declaration. Do **not** add an `OPENSPEC:` line or invent an openspec change
to make the gate green — that is claiming another lane's change was specified when nobody specified it, and
it is exactly the "edit the code until the test passes" failure shape in reverse.

The correct report has three parts: (1) name the run id and head sha it was measured at; (2) quote the
gate's own sentence; (3) state that `check-pr-base` is unreachable behind it (it runs LAST in the guard
chain) and give the **local** `make check-pr-base PR_BASE=origin/main` result at the pushed sha as the
proof that the rebase itself is sound. That distinction — "the rebase is correct, the body is theirs" — is
the whole message; without it a reader sees a red guard and assumes the rebase broke something.
