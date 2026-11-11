# Running llgenie's gates, and proving a change is real

Depth for the part of llgenie work that is not the pipeline itself: how to run the gates without
tripping over the harness, and how to prove a fix rather than assert it.

## Long gates: run in the background, poll the log

`make test-unit` is 13-20 minutes. A foreground tool call caps out (600s) and **SIGTERMs the whole
process group**, taking `make` and pytest with it — the log stops mid-run and reads like a hang. Three
re-runs of one suite were lost that way in a single session.

```bash
terminal(command="cd <wt> && make test-unit > /tmp/unit.log 2>&1; echo EXIT=$? >> /tmp/unit.log",
         background=true, notify=true)
# then poll: grep -c '^EXIT=' /tmp/unit.log ; tail -3 /tmp/unit.log
```

Never `nohup`/`&` it (Hermes refuses, and an untracked process is worse). Never re-send a promoted
background command: the tool promotes anything over its cap and tells you not to re-run it.

## A focused pytest run must use the repo's own container invocation

`docker run --rm -v "$PWD":"$PWD" -w "$PWD" llgenie/test:latest python -m pytest …` is WRONG for
this repo: in a git worktree `.git` is a FILE pointing into the parent clone, so `git` inside the
container sees no repository and every test that shells out to real git fails (e.g. `git check-ignore`
returns 128 for every path — which reads exactly like "my change broke the ignore roster").

Copy the Makefile's `TEST_OPTS` shape instead:

```bash
docker run --rm -u root \
  -v "/home/asimov/repository/git/llgenie":"/home/asimov/repository/git/llgenie":rw \
  -v "$PWD":/repo -w /repo -e HOME=/root llgenie/test:latest \
  python -m pytest tests/<module>.py -q -p no:cacheprovider
```

`make test-image` first if `llgenie/test:latest` is not local. For a CHANGE that only adds tests, the
full suite is still the last gate — focused first (seconds), then the suite in the background.

## Proving RED: swap the base file in

A new test proves nothing until it fails on the base. With a worktree clean except your change:

```bash
cp scripts/<file>.py /tmp/new.py
git show origin/main:scripts/<file>.py > scripts/<file>.py
<run the focused tests>            # expect the fix-bearing cases RED
cp /tmp/new.py scripts/<file>.py    # restore; verify with git diff --stat
```

Report the asymmetry: "N of M new cases fail on the base, the contract guard passes on both" is the
honest shape. A test that passes on both is a guard, not proof — say which is which.

## Tests that pin the OLD contract get re-specified, never weakened

A behaviour change breaks tests written against the old rule. Update them to the new rule with the
same strength (the dead-flag case now asserts `--help` answered and `--version` did not, instead of
one exit code for the whole probe). If an old test asserted a state your fix calls a defect (a
stranded worktree kept while its branch was deleted), rewrite it as the corrected policy **plus** a
case pinning the boundary that must not change, and say in the docstring what it used to assert.

## Measure the data before implementing an issue's literal assertion

An issue states the fix it assumes. Check that assumption against the tree first: an issue asked to
assert `-h` for every engine, and the generated manifest showed NO engine documents `-h` and six
document `--help` only — the literal fix would have reddened the whole matrix. Implement the
strongest rule the data supports (each documented flag individually + one answer per flag FAMILY),
and state the deviation and its evidence in the PR body.

## Probe/parse seams are cross-platform seams

A bash probe that emits a machine-readable line (`KEY <name> <rc> <bytes>`) is parsed on Linux, on
macOS and inside containers. BSD `wc -c` pads its count (`"      12"`) where GNU does not, so a
single-space pattern silently yields no matches and the check passes on Linux while reding macOS.
Normalise in the producer (`| tr -d ' '`, default to 0) AND accept `\s+` in the parser, then pin the
padded shape in a test. Same rule for any `awk`/`sed`-produced field with a fixed-space assumption.

## openspec from the container owns what it creates

`make openspec-new NAME=<change>` runs in a container as root, so the new
`openspec/changes/<name>/` is root-owned and every `write_file` into it is refused. There is no
passwordless sudo on this host; chown through the container instead:

```bash
docker run --rm -u root -v "$PWD":/repo -w /repo llgenie/openspec:latest \
  chown -R 1000:1000 openspec/changes/<name>
```

Every `#### Scenario:` needs its own `WHEN/THEN` steps and a `- **Test:**` line, and every top-level
Requirement needs at least one Scenario — `make openspec-validate NAME=<change>` errors with
`ADDED "<requirement>" must include at least one scenario` until both are true.

## Run the gates from the worktree, not the user's checkout

`git worktree add -b feat/<kebab> ../llgenie-wt/<kebab> origin/main` first, then every edit, commit
and gate happens there. `make worktree-prune` (never `git branch -D`) removes it after the PR merges —
and a branch whose worktree git reports as DETACHED needs a second run unless the pruner matches
worktrees by HEAD, so check `git branch --list` after pruning rather than trusting the summary line.
