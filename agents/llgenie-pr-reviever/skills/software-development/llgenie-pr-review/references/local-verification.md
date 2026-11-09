# Verifying an llgenie claim locally

Turning "the PR says" or "CI says" into an executed measurement at a named sha.

## Drive a gate script the way its CLI expects

Most `scripts/check_*.py` gates are subcommand CLIs, not flag CLIs. Calling one bare exits **2 with a
`usage:` line saying an argument is required — read that as "wrong invocation", never as the gate
failing:

```
<venv>/bin/python scripts/check_docs.py check                    # check | report (mode is required)
<venv>/bin/python scripts/check_architecture_census.py check     # check | report (cmd is required)
<venv>/bin/python scripts/check_docs.py check --root <dir> --base <sha>
```

Related tells, each one a wrong-invocation artifact and not a defect: a `note: … skipped (no base ref;
set CHECK_DOCS_BASE)` line means the change→note half did not run (pass `--base`), not that it passed;
and a `--check`-style flag on a script whose parser has no such flag exits 2 (`unrecognized arguments`)
— check `--help` before inventing flags.

## A gate needing git history cannot run in a `git archive` snapshot

A `git archive` extract has no `.git`, so any gate that walks objects answers
`UNREADABLE: git could not read this checkout — the census was NOT checked (run this from a full clone or
mount the whole repository)` (exit 2). That is a checkout-depth diagnostic, never a doc/code defect. For
history-dependent gates (architecture census, base/merge checks, anything doing `git ls-tree` or
`git merge-base`) use a real worktree instead of an archive:

```
D=<root>/repo && git worktree add /tmp/wt<pr> refs/remotes/live/pr<pr> --detach
```

Archives are still fine — and faster — for pytest runs and pure-file linters. Pick the shape by whether
the gate reads history, and say which shape you used when a gate exits 2.

## Interpreter

Run the suite with the repo's own test venv (see `Makefile`: `VENV := $(HOME)/llama-gguf-tools/.venv`), not the tool-host python. `tests/conftest.py` imports `scripts.llgenie_serve`, whose re-exec shim reads `sys.argv[1:]`; flags like `-s` / `-x` are swallowed by that argparse and the run dies with exit 2 and **no output**. `-q`, `-k` and `-m` work. Shape that works:

```
<venv>/bin/python -m pytest tests/<file>.py -q -p no:cacheprovider
<venv>/bin/python -m pytest tests/<file>.py -k '<expr>' -m 'not network' -q
```

A bare exit 0 after a pipe is the pipe's status, not pytest's — never read `cmd | tail` as the verdict.

**`--noconftest` fixes only the *parent* module's conftest import — a test that itself subprocess-spawns a
full-repo pytest collection dies the same silent exit-2/empty-stderr way and is NOT the diff's red.**
Tests that assert on gate behaviour ("the unit gate excludes network-marked tests") run
`subprocess(cmd=[python, '-m', 'pytest', '--collect-only', <whole tests/ tree>])` and check
`returncode == 0`; that inner process gets no `--noconftest` and no gguf venv, so it exits 2 with
`stdout='' stderr=''` and the outer test reds with `assert 2 == 0`. Discriminate before attributing:
dump the failing process's argv and result — an `AssertionError: assert 2 == 0` wrapping
`CompletedProcess(args=[… 'pytest' … 'tests/test_x.py' 'prune.py' …], returncode=2, stdout='', stderr='')`
is the spawned-collection artifact, not the branch. The decisive check is to run the diff's **own** new
test in isolation (`-k '<its name>'`): it passes, and the red set is exactly the tests that shell out to
collect the whole tree. Report those as a local-env artifact and let `linux / unit` be the verdict leg —
never carry them into the PR as failing criteria.

## Golden / fixture freshness

A fixture can appear in the PR's diff **and still be stale**: it was regenerated before a later commit in the same branch changed behaviour, so its rows describe an older product. The tell is that the red rows' values correspond to a deliberate change (a disabled build cell falling back, a reordered tier table), not to noise.

Prove staleness rather than assert it — regenerate with the repo's own target, re-run the file, report before/after:

```
make render-trend-list-matrix      # trend-list golden
make changes-index                 # CHANGES.md is RENDERED from docs/changes.d/ — commit the result
```

Decision rule: if the differing value **matches the intended change** (and the neighbours/docstring agree with the new value), the golden is stale — regenerate. If it **contradicts** its neighbours or the recipe's own docstring, suspect the code instead.

**On `CHANGES.md` specifically: render it and commit the render.** It is generated, so never
hand-write a row — but "do not hand-edit" is not "do not touch". `tests/test_changes_index.py`
asserts `committed == rendered` and `tests/test_check_docs.py` asserts the rendered index links
every note, so a PR that adds a fragment and leaves the aggregate alone **passes
`scripts/check_docs.py check` and reds `ci-unit`**. Two checks, one subject, different depths — and
only the suite gates. See `references/gate-auditing.md` §5.

## Measure on the data path the test uses

If the test refreshes its data — a module fixture that downloads an upstream registry, a `live_sync`-style helper — then a probe against the **vendored** copy can disagree with the test and send you after a phantom. Re-run any claim through the same refresh the test performs before publishing it.

## Predict a red from the tree instead of waiting for the matrix

When a reviewable PR's deciding leg is queued behind a long suite (measured: ~18 min per `ci-unit`,
and longer under runner contention), you can usually answer the question **now** by running the
specific test the leg will run, at the PR's own head:

```bash
<venv>/bin/python -m pytest <the test> -q          # at the reviewable head
HOME=/tmp/clean <venv>/bin/python -m pytest <the test> -q   # rule out host drift, same result
```

Post that as a **prediction with its retraction clause** — "if the run concludes green this comment is
wrong and I will say so with the run id" — rather than as a verdict. Two properties make it honest:
the evidence is the tree at a named sha, and the claim names what would falsify it. It also removes
the excuse "we cannot know until CI finishes", which is how a known red sits on the board for half an
hour.

## Probe the gate FUNCTION when the CLI only reads live state

The acceptance gate CLI resolves the live linked issue, so there is no `--issue-file` flag to feed it a
crafted body — `check_pr_acceptance.py check` on your own fixture proves nothing and a flag hunt is
time lost. Import the module in the repo venv and drive the verdict function on inputs you own:

```python
import sys; sys.path.insert(0, '.')
import scripts.check_pr_acceptance as g
f = g.acceptance_verdict(issue_body, pr_body)   # findings list; empty list == GREEN
```

Feed every form the criterion claims to distinguish (named run id, command+`rc=`+sha, hash-only,
fold-sync line, bare self-tick) and require the boundary: the provable forms yield no finding, each
unprovable form yields exactly one `tick-unprovable` naming that criterion. The Unit tests prove the
code path exists; this probe proves where the line sits on inputs the tests may not enumerate — which
is the thing the criterion actually asks about.

## A claim about a leg that never ran is not evidence

"N tests passed in the ci-unit container" is a claim until a unit leg **concluded at that head**. If
that leg was skipped because an earlier job failed, no measurement exists: cite the run you executed
yourself (`<venv>/bin/python -m pytest tests/<file>.py -q` at the head, with its pass count) and say
plainly that the container count is unverifiable at this sha. Repeating the PR's number as if it were
measured is how a skipped leg becomes a green in the verdict. For the same reason, scope every local
run to the named test file: the whole `tests/` tree is tens of minutes and times out, and the file the
criterion names is the verdict.

## Control shape

- **Fail on branch + pass on base**, same venv, same command, same data → in-diff by construction. `live-data` / `environment` requires the base to fail too.
- **Pass on both** → the branch fixed it, or the base already did; say which.
- Quote both results **and the durations**: near-identical runtimes prove both actually fetched/executed rather than one side short-circuiting on a cache.

Re-run the control against the base the branch will land on — a clean result measured at a superseded base proves nothing about the current one.

## Prove a NEW guard test discriminates (both directions)

When the diff's point is a *guard* (a fix that must refuse a wrong input: a truncation check, a
pin, a deny rule) and its acceptance says "the guard catches it", the plain control above is not
enough — on the base tree the new test **does not exist yet**, so "pass on branch" proves only that
the test agrees with the fix it was written beside. Prove the guard is real by making the **wrong
input** reach the **old code**:

```bash
git worktree add --detach ../llgenie-wt/pre <merge-base-sha>
# base module WITHOUT the guard + the PR's own new test file bolted on top
cd ../llgenie-wt/pre && git show <head>:tests/test_<x>.py > tests/test_<x>.py
PYTHONPATH="$PWD/scripts:$PWD" <venv>/bin/python -m pytest --noconftest -q \
  tests/test_<x>.py -k '<the new test name>'          # MUST fail on the pre-fix module
```

Then confirm the guard's own region on the base blob is actually bare (`sed -n '<range>p'
scripts/<mod>.py` shows no check), so "it failed" is the missing guard, not a fixture quirk. The
measured pair is the acceptance: **pre-fix module + head test → 1 failed** (the assertion naming
that the guard accepted a bad verdict) and **fixed tree → N passed**. State both counts; a verdict
that only quotes the green side has not shown the guard *rejects* anything — a test that passes on
the unfixed code is not a guard, it is a mirror of the bug. Remove the worktree after.

## Prove a LIMIT gate by fabricating the over-limit state (you cannot check out the bad tree)

A cap gate ("no `SKILL.md` over N characters", "no file over M b", "no more than K rows") differs from
the guard-test case above: the fixed tree no longer CONTAINS an over-limit artifact, so there is no
pre-fix commit to bolt the test onto. Fabricate the violation instead, then restore byte-identically:

```bash
F=<the graded file>; cp "$F" /tmp/backup.md
<venv>/bin/python - "$F" <<'EOF'
import sys; p=sys.argv[1]; s=open(p).read()
open(p,'w').write(s + "x"*(<cap + 39> - len(s)))   # land a known number of units over
EOF
<venv>/bin/python scripts/<gate>.py check            # MUST fail, naming the file AND the overflow
cp /tmp/backup.md "$F"                                # restore
cmp -s "$F" /tmp/backup.md && echo restored           # MUST be byte-identical
<venv>/bin/python scripts/<gate>.py check            # MUST be clean again (0 findings)
```

Quote both ends: the failure line with its measured overflow (`… is 100,039 characters (100,464 bytes),
39 over the 100,000-character limit …`) and the post-restore zero. A gate only ever observed reporting
zero has not been shown to fire, and `cmp` proves you did not leave the tree dirty.

## Prove a content MOVE lost nothing (subset check, not eyeballing)

When a PR claims "content moved into `references/`, zero-loss", the live-vs-tree byte delta cannot show
it — the live profile has its own unversioned drift, and a naive diff of live lines missing from the
head body reports that drift as loss. Compare against the tree's BASE, and require every base line to
survive somewhere in the head body plus the new references:

```python
base = <head-body at the PR's base>.splitlines()
head = <head body>.splitlines(); refs = "\n".join(all new reference file texts)
gone = [l for l in base if l.strip() and l.rstrip() not in {x.rstrip() for x in head}]
print(len(gone), len([g for g in gone if g in refs]))   # must be equal: 0 uncovered
```

Report both numbers ("51 base lines not in the slimmed body; 51 present in a reference; 0 uncovered").
Lines found only in the LIVE copy and absent from BASE are pre-existing live drift — name them as such
so a pre-existing gap is not attributed to this diff.

## Distinguish a probe artifact from a regression: run the BASE script inside the HEAD worktree

A gate whose finding count moves between two trees may be reporting the environment, not the diff. Hold
everything but the script fixed — same directory, same live state — and run the BASE version of the gate
from the HEAD worktree:

```bash
cd /tmp/wt<pr> && git show <base>:scripts/check_agent_profiles.py > scripts/_base_probe.py
<venv>/bin/python scripts/_base_probe.py check | grep -oE 'FAIL [a-z-]+' | sort | uniq -c
rm scripts/_base_probe.py && git status --porcelain    # leave the worktree clean
```

Identical counts from the base and head scripts means the delta is environmental (host drift, or an
mtime-sensitive comparison reading an `git archive` extract's fresh timestamps) — report it as a probe
artifact with both counts, never as a PR defect. A DIFFERENT count isolates the change to the diff. Note
the probe must live inside `scripts/` so its `from scripts…` imports resolve; a copy in `/tmp` dies with
`ModuleNotFoundError`, which is the invocation, not the gate.

## Profile gates are host-sensitive

`scripts/check_agent_profiles.py` compares the tree against `~/.hermes/profiles/<profile>/`, so a host with drifted live profiles reports findings CI never sees. Separate the two:

```
HOME=/tmp/clean <venv>/bin/python -m pytest tests/test_agent_profiles.py   # the branch's own state
python3 scripts/check_agent_profiles.py check                              # with the real HOME
```

With an empty HOME the gate prints `tree checks only, LIVE RULEBOOKS NOT COMPARED`. Report the clean-home result as the branch's state and the real-home delta as host drift — never file the host's drift as a PR defect.

**The symptom, so it is recognised instead of investigated:** running the profile/wiring tests on the
host with live profiles present gives a batch of failures that all bottom out in one message —
`[check-agent-profiles] 17 finding(s) — an instruction a credential-holding agent runs under is
unreviewable when this tree is wrong`. Measured: 9 failed / 163 passed across
`test_agent_profiles.py` + `test_wiring.py` + `test_changes_index.py` + `test_check_docs.py`, while
the same commit's real CI reported `2 failed, 15149 passed` with **zero** `test_agent_profiles`
failures. The host count (17) is other lanes' unsynced live copies plus your own unsynced edits —
nothing about the branch.

So before reading any local failure in this family, ask whether the run used the host's real HOME.
A local suite on a profile-holding host is **not** a proxy for `ci-unit`, and treating it as one
manufactures defects — which is exactly what this file already says, so the cost of skipping the
clean-HOME wrapper is a false red, not new information.
