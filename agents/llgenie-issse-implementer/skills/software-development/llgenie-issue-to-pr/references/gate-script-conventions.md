# Gate-script conventions (`scripts/check_*.py`)

Shared shape of llgenie's checker scripts and how to change one without breaking its CI leg.

## Editing a regex-heavy block: restore-from-git, splice literally, AST-check

The patch/fuzzy-edit tool mangles Python source that contains regex literals with nested
backslashes and quote classes (`r"\{.*?\}"`, `["']`): each round-trip can silently double or drop
a backslash, and a truncated splice can delete everything after the anchor. Do NOT keep re-patching
the corrupted block.

- Recover from committed state: `git show HEAD:scripts/<f>.py > /tmp/stage.py` (the ORIGINAL, before
your edits) — never trust the on-disk working copy once it may be corrupted.
- Apply every edit as a LITERAL string splice in a script (`content.replace(old_exact, new_exact)` or
  slice by a unique marker), not via shell interpolation or a regex in the edit command itself.
- Keep the blast radius small: build small helper functions with simple `str.find`/`startswith`
slicing instead of regex char classes where the parser allows it — a plain "does this line start
  with `{` and `json.loads` it" needs no regex at all.
- Verify with `python -c 'import ast; ast.parse(open(p).read())'` after EVERY write, and confirm the
  file still ends at the expected line count before running it — an AST-valid truncation (functions
  closed early) still parses.

## Exit-code vocabulary

- `0` — clean: nothing to report.
- `1` — findings that ARE a failure (the tree is wrong).
- `2` — bad invocation: unknown flag value, `--root` not a directory, malformed args.

Keep 1 and 2 distinct. A CI leg treats any nonzero as red either way, but a reader needs to tell
"the tree is wrong" from "you typed the flag wrong", and two failures with identical exit codes
become indistinguishable in the logs after the fact.

## Per-subject violations must NAME their subject — a shared placeholder collapses them

When a gate can emit one violation per subject (one linked issue, one file, one PR), thread the
subject's identifier INTO each evidence string, never a fixed placeholder. A repeated literal
(`closes #<n>`, `<file>`) across N violations makes two simultaneous violations
indistinguishable: the reader cannot tell which issue/file each charge belongs to, and a test
that only COUNTS violations passes the collapsed version. Build the evidence from the actual id
(`f"... closes #{n} ..."`), and assert that a TWO-subject input yields two violations whose
evidence each name their OWN id (`#1000` in one, `#1001` in the other) — a count-only assertion
does not catch the placeholder. This is "assert behaviour, not text" applied to gate output: the
test must prove the evidence DISCRIMINATES, not merely that it exists. When threading a new id
through a helper, grep the whole test tree for the helper's old signature before widening it —
a hand-rolled call site that passes the old arg count reds on a shard you did not run.

## The `ratchet` subcommand — a DIFFERENT contract from `check`

A checker often ships two subcommands over the same scanning code, with INVERSE exit semantics:

- `check` — inventory/report mode. `0` = nothing to report, `1` = it found anything at all
  (including every pre-existing offender). Exit `1` here is NOT a claim that YOUR branch broke
  anything; run it on pristine `origin/main` and it reds identically.
- `ratchet` — the GATE the Makefile/CI actually runs. It compares the current counts against a
  recorded baseline (`{sys-path, bare, syntax, …}`) and exits `0` while every count is
  **at or below** the baseline, `1` only when a count GREW. Its green line is
  `OK: counts at or below the recorded baseline {…}`.

When a dispatch says "the ratchet grew N→N+1", do not trust it: run the `ratchet` subcommand
itself at the LIVE head and read the printed per-key counts. The `check` inventory and a ratchet
number measured at a superseded head are both the wrong measurement. A change that cannot move a
count (e.g. editing a line the scanner never flags) is a no-op commit — verify the file lines the
claim names against the live head FIRST.

## The `--only <key[,key…]>` filter flag

Add it when a Makefile target or a lane wants one finding class on its own:

- Name the flag `--only`, `default=None`, `metavar="KEY[,KEY...]"`, and split on commas.
- Filter the finding list by `item["key"]` AFTER `findings(...)` returns and BEFORE **both** the
  print loop and the count that decides the exit code. Filtering only the print leaves the run
  still failing on excluded classes; filtering only the count still buries the reader in rows.
- Validate every requested key against the module's `KNOWN_<X>_KEYS` frozenset. On an unknown key,
  write the offending key(s) and the sorted known keys to **stderr** and `return 2`. Silently
  ignoring an unknown key turns a typo (`--only live-long`) into "clean", which is worse than the
  crash it replaced.
- Leave every other path byte-identical so a run with no flag behaves exactly as before; the flag
  is a view, not a change to what counts as a finding.

A lane-scope flag (`--profile <lane>`) is the same shape one axis over: filter findings to the
subtree the lane owns and keep the repository-wide run unchanged, so a lane's PR greens while a
growing drift anywhere still reds the global gate. Assert the scope with a SUBSET check
(`set(scoped) <= set(global)`), never equality — an exact list reds on the next legitimate
addition. Make the scoped run audible (`OK (lane <x>): …`) so a reader cannot mistake a scoped
green for the global verdict.

### The bug shape this flag fixes

A Makefile target that has always passed `--only <key>` to a script that never implemented the
flag exits `2` with `unrecognized arguments` and compares NOTHING — the control has been dead
since it was written, and its green-looking absence is unremarkable. The acceptance is therefore
**"the target now prints real findings"**, not "the target exits 0": on a host that genuinely has
those findings it must still fail, and only a host with none may pass.

## A gate that scans the WHOLE tree reds its own introducing PR

When the new gate forbids a condition that already exists on `main` (a stray zero-byte file, a
deprecated pattern, a bad historical line), a default whole-tree scan makes the PR that ADDS the
gate fail on its own base — the gate cannot go green until the offending file is removed in a
SECOND PR, and until then `ci-lint` reds the gate PR for a defect that is not in its diff.

Design the default to gate the **change set**, not the tree:

- Default mode diffs the base and checks only paths the change ADDS —
  `git diff --name-only --diff-filter=A <base>...HEAD` (three-dot: merge-base, not the base tip).
  A path this PR introduces is exactly what the gate is for; a pre-existing one is somebody
  else's cleanup.
- Offer the whole-tree sweep as an explicit OPT-IN (`--all` / a separate `report` subcommand),
  never the default. That is what a human or a later ratchet runs once the base is clean.
- Degrade cleanly when no base resolves (a bare `make <gate>` in a shallow CI checkout): fall back
  to a present-scan or print a skip note — do NOT raise a traceback out of the base-diff helper
  when `git diff` cannot reach the ref. A gate wired into `ci-lint` runs on both PR and main-push;
  the main-push leg has no base and must still exit 0.
- Give the gate an allow-list for the ONE legitimate empty/exceptional case (`.gitkeep`-style
  sentinels, `--allow <path>`) — a spec that says "zero-byte files are banned" without naming the
  sentinel exemption is a gate that reds a correct tree.

## A scanner that greps the tree finds its OWN source as a violation

A gate that looks for a text pattern (a header shape, a required token, a banned literal) will
also match the gate's own CONSTANTS, docstrings, help text, evidence f-strings, and its test
fixtures that quote the pattern — so the whole-repo green test reds on the checker itself, not on
the tree. Two fixes, apply both:

- Keep the pattern in ONE module constant and interpolate it, but ALSO exclude the scanner module
  (and `tests/`) from the scan roots, or skip lines that are the constant's own definition. A
  partial fragment embedded in an emitted message (`"working on #<id> · branch …"` inside an
  evidence f-string) trips a fast-path substring match even when no real report is malformed.
- When you decide "is this a concrete value or a template placeholder", make the placeholder char
  class cover every real placeholder shape: `<hh:mmZ>` has an UPPERCASE `Z`, so a class of
  `[a-z:]` fails to see it as a placeholder and reads the template as a concrete (wrong) value.
  Include uppercase/digits where the placeholders use them.

Test the scan against the whole tree in the same run as your unit fixtures: a suite that passes
10/10 fixtures but flags its own script on `--all` is not green, and the fix is to narrow the
scanner's inputs — never to weaken the assertion.

## A git-dependent gate leg can SKIP and report GREEN — read the `note:` lines

`check_docs.py` run inside `llgenie/test` against a LINKED WORKTREE prints
`[check-docs] note: change->note skipped (fatal: not a git repository: …/.git/worktrees/<n>)` and
still exits 0 with `ok`. The leg that proves your change→note trio exists never ran — a false
green, worse than a red because it looks like a pass. Rules:

- Treat a `skipped` note on the leg that gates your diff as an UNVERIFIED gate, not a pass; grep
  the gate output for `skipped`/`note:` before reading the exit code.
- The fix is to run that leg where git resolves — a standalone `git clone`, not the mounted
  worktree — not to trust the green and not to edit the script.
- Same family: a bare `make check` target does not exist; its rc 2 is `No rule to make target`, not
  a gate red. Run the per-leg targets (`check-docs`, `check-pr-closing`, `lint`, `unit`) or the
  `scripts/check_*.py` directly.

## Testing a CLI flag through the real entry point

Drive `main([...])` (or `run_cli`) with `tmp_path` + `capsys`, not the helper:

```python
def test_only_filters_through_real_main(tmp_path, monkeypatch, capsys):
    import check_agent_profiles as cap
    agents = tmp_path / "agents"
    (agents / "someone").mkdir(parents=True)
    (agents / "someone" / "SOUL.md").write_text("short\n")
    live = tmp_path / "live" / "someone"
    live.mkdir(parents=True)
    (live / "SOUL.md").write_text("a much longer live rulebook\n" * 40)  # tree is a prefix -> live-longer
    (agents / "manifest.json").write_text('{"profiles": [{"name": "someone", "rules": ["never-merge"]}]}')
    monkeypatch.setenv("HERMES_PROFILES_HOME", str(live.parent))
    monkeypatch.setattr(cap, "_STARTED", 0.0)   # every live file counts as changed during the run

    assert cap.main(["check", "--root", str(tmp_path), "--agents-dir", "agents",
                     "--only", "live-longer"]) == 1
    out = capsys.readouterr()
    assert "FAIL live-longer:" in (out.out + out.err)
    assert "FAIL absent-from-tree:" not in (out.out + out.err)
```

Assert all four behaviours, each as its own block so a failure names which one broke:

1. a class that IS present → rc `1`, and only that class's rows appear;
2. a class that is absent → rc `0` (the filtered set is empty);
3. a comma list → the union of those classes;
4. an unknown key (alone, and mixed with valid ones) → rc `2` with both the bad key and the
   known-key list named. The mixed case matters: a partial filter that quietly drops the bad key
   passes a single-key test.

`HERMES_PROFILES_HOME` points the live-profile comparison at a fixture instead of the host;
`_STARTED = 0.0` defeats the snapshot caveat that would otherwise treat unchanged fixture files
as pre-existing and skip the comparison. Without both, the live-direction findings never appear
and the test passes for the wrong reason.

### Driving the real `main()` when it shells out to `gh`

A gate that fetches issue/PR bodies via `gh` can be exercised END-TO-END without network by putting
a fake `gh` first on `PATH` — a tiny script answering `gh issue view <n> --json body` with a fixed
`{"body": ...}` — then calling `main([...])` and reading the rendered violation lines. That proves
the CLI's real output (each violation naming its own `#N`), not a unit-level reconstruction. Run it
from the repo MOUNT ROOT so `scripts/` is importable: `docker run ... -w /repo python demo.py`.
A bare `python /demo.py` puts the SCRIPT's dir on `sys.path`, not the repo, so
`from scripts.check_x import main` fails with `ModuleNotFoundError: No module named 'scripts'` —
copy the demo into the worktree or `cd` into the mount before invoking.

## A new Makefile gate must be CLASSIFIED in `issue_bot_gates`, not only wired

Adding a `check-*` target to a CI aggregate (`ci-lint`, `ci-unit`, …) is not enough: a guard test
(`test_the_real_tree_is_wired`) enumerates the gates each aggregate runs and requires every one to
be classified in `tests/test_issue_bot_gates.py` (`FAST_GATES` or `DEFERRED`) — an unclassified
entry reds `linux/unit` ~12 min in, after the fast legs looked fine. Run that guard file locally
right after wiring the Makefile (`make unit` or `pytest tests/test_issue_bot_gates.py`) instead of
discovering it in CI. Classify by cost: a tree-only static read belongs in `DEFERRED`, not `FAST`.

## `check-wiring` is a SECOND registry: `.PHONY` + host-only fixture, and it ROUND-TRIPS

`check-wiring` reds a new `check-*` / script target for reasons `.PHONY`-in-aggregate and
`issue_bot_gates` do NOT cover. A brand-new target/script typically needs BOTH of these, and each
reds a different line of the same job:

- **`.PHONY` declaration.** A new target must be declared `.PHONY` — the checker scans for a
  declaration near the target's recipe (an explicit `.PHONY:` line right after the recipe is enough;
  the repo's shared `.PHONY:` block also counts). A target wired into an aggregate without `.PHONY`
  reds `check-wiring` even when the recipe itself is correct. Watch the patch tool here: a fuzzy
  edit near `.PHONY:` can silently re-write whitespace on an unrelated line — revert and re-apply as
  a surgical single-line insert, then `git diff` the Makefile to confirm only your line moved.
- **host-only fixture entry.** A script CI cannot reach (it needs the host — a live `jobs.json`
  probe, a launcher/image read) must be recorded as an explicit host-only entry in the wiring
  fixture JSON, or `check-wiring` reds it as "a script nobody runs and nobody declared host-only".

**The round-trip trap: the host-only entry becomes STALE the moment a test makes the script
CI-reachable.** `scripts/unit_tests.py` DISCOVERS `tests/test_<x>.py`, so adding
`tests/test_<script>.py` pulls `scripts/<script>.py` into the CI unit leg — and `check-wiring` then
reds the host-only entry as STALE (declared host-only, yet CI now runs it). Delete the entry in the
SAME PR that adds the test. Decide the branch by whether a test exists: target+script only → ADD
the host-only entry; target+script+test → do NOT add it, and if it was already committed, remove it.
Run `make check-wiring` AFTER both edits (`.PHONY` + fixture), never just one — they are separate
reds in the same job and fixing one exposes the other.

**Edit the wiring fixture JSON with `ensure_ascii=True`, from a pristine copy.** A
`json.dump(..., ensure_ascii=False)` round-trip un-escapes every `\u2014` (em-dash) in the file and
churns dozens of unrelated lines into the diff. Start from `git show origin/main:<fixture> > f.json`,
add ONLY your entry with `ensure_ascii=True`, and confirm `git diff origin/main -- <fixture>` is a
handful of lines — a 20-line diff for a one-entry change is the escaping churn, not your change.

## A gate comparing a file to a JSON string must normalize ONE trailing newline

When a drift/existence gate compares a tracked file's bytes against a value stored in a JSON blob
(`jobs.json`, a manifest), `make lint`'s "every tracked text file ends with a newline" rule and the
JSON string's own lack of a trailing `\n` are in direct conflict: add the newline for lint and the
byte comparison reds; drop it and lint reds. The fix is a PARSE-LEVEL normalization — strip at most
one trailing `\n` from the file side (or both sides) before comparing — never weakening the
comparison into a substring/`in` check. Prove both arms: normalized-equal → exit `0`, and a genuine
text divergence → exit `1`. A gate that only ever greened is untested.

## Tests that read the LIVE host red on OTHER lanes' drift

A test that calls `findings(root)` / `report(root)` without setting `HERMES_PROFILES_HOME` reads
the real `~/.hermes/profiles` of whoever runs it. On a fleet host the other profiles' live drift
bleeds in, so a test asserting "this clean tree is clean" reds for a reason that is not in the
tree — and reds only on machines with drift, never in CI. Point the live root at an empty dir for
the duration of the assertion (`monkeypatch.setenv("HERMES_PROFILES_HOME", str(tmp_path/"live"))`)
rather than weakening the assertion or adding a `--only` that hides the class. Any test whose
subject is the TREE must isolate the live root; only the live-comparison tests should set it to a
fixture.

## A monitor script that must turn a run RED needs `checks: write` in its workflow

A monitor (`check_*.py` run from a scheduled/Actions workflow) that must force a verdict posts a
check-run on the run's head. That needs `permissions: checks: write` in the CALLING workflow — a
workflow granting only `issues: write` (enough to file a deduped issue) will have the check-run POST
rejected while the issue path still works, so the "forced red" silently never happens. Add both
permissions and document the contract in the workflow header.

Two design rules that generalise beyond monitors:

- **A pending run publishes no decision, and "no decision" is already red.** So a monitor's job is
  not to invent a verdict — it is to publish a FAILURE check-run with the SAME payload the verdict
  script (`scripts/ci_verdict.py`) uses, so downstream readers see one vocabulary.
- **Never conflate a benign queued state with a defect.** Zero running jobs can mean "queued behind
a concurrency group that a sibling run of the SAME workflow is holding" (benign) or "stranded with
the group free" (the real fault). Discriminate on the group's holder: same-workflow `in_progress`
sibling ⇒ benign and never filed as "no runner matched"; no holder ⇒ file once (deduped) AND force
RED. Testing this means planting BOTH arms and asserting call-counts (stranded → exactly one issue
create + exactly one check-run POST; benign with `--file` → zero of each) — a test that only plants
the bad arm passes a detector that files every queued run.

## Verify against a real host, and state why a nonzero is correct

Run the modified script (and the Makefile target) once against the host: the filtered run should
show the same rows the unfiltered run showed for that class and nothing else. If the host has real
drift, that run is `1` — say so in the PR body, because "the target fails here" reads as a defect
to a reviewer who has not seen the host. `make lint` (linefeed gate) is a separate check: any new
file must end with a newline. **`make lint` scans only TRACKED files — a lint run before `git add`
of NEW files is a false green that ships the missing newline to CI.** Stage (`git add`) the new
files, THEN lint, then commit; an untracked file is invisible to lint and reds `scope` only after
the push.

**`write_file` does NOT guarantee a trailing newline**: a generated `.py`/`.md` lands without the
final `\n` even though the write reports `verified`, so staging it does not help. Assert it before
staging — `data.endswith(b"\n")`, append if not — or lint reds the file the moment it becomes
tracked. One-line fix, and cheaper than a second push: re-stage + re-run `make ci-lint`.

## The proc-gate: bare `subprocess.run` call sites need `# proc-allow:`

`check-proc-gate` (a `make`/`scope` leg) reds any direct `subprocess.run(...)` / `subprocess.Popen`
call site in a script unless it is either in `scripts/proc.py` or carries an inline allow comment.
Use the tracked-remainder form that names the migration issue:

```python
subprocess.run([...])  # proc-allow: direct subprocess call site, tracked remainder for issue #<n> (migrate onto scripts/proc.py)
```

Copy the exact comment placement from a sibling `# proc-allow:` already in the repo (same line vs
line above, per the gate's parser). The gate is diff-scoped like the others, so a new script's
subprocess calls are YOURS the moment your branch introduces them; a red on an old file is
pre-existing. Run `check-proc-gate` / `make` locally before the push rather than discovering it as a
`linux/unit` job failure ~14 min in.

## Importing `proc` from a standalone script

A script run as `python3 scripts/<name>.py` has `scripts/` as its import root, so `proc` is a
SIBLING module: `from proc import run_ok, run_text`. **`from scripts import proc` fails** — there is
no `scripts` package on that path. Match the repo convention at the top of the file:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from proc import run_ok
```

Use `proc`'s helpers (`run_ok`, `run_text`) for anything that shells out — a host probe like `df`
belongs there, not in a hand-rolled `subprocess.run` — so the proc-gate above stays green by
construction rather than by an allow comment.

## Proving a referent/existence gate DISCRIMINATES (negative control)

A gate asserting "every module named in the docs exists at the pin" is worthless unless you show it
REDS when the bad condition is present — a green alone proves only that the check ran. Inject the
failure, confirm the exact red line, then restore:

```bash
python3 - <<'EOF'
from pathlib import Path
p = Path("docs/ARCHITECTURE.md"); orig = p.read_text()
p.write_text(orig.replace("<existing-table-row>", "<row naming a removed module>"))
import subprocess, sys
r = subprocess.run([sys.executable, "scripts/check_architecture_census.py", "check"], capture_output=True, text=True)
print("rc=", r.returncode, [l for l in r.stdout.splitlines() if "<removed-module>" in l])
p.write_text(orig)  # restore — never leave the doc modified
EOF
```

Acceptance is `rc=1` AND a line naming the injected module — not merely nonzero. Restore the file,
re-run to confirm `rc=0` on the clean tree. The same injection proves any "X must exist / must be
absent" gate: create the forbidden state, capture the named red, undo it.

## A trimmed verification clone can red a gate by failing to RESOLVE an ancestor, not by finding a defect

When you verify at a pushed ref inside a `--depth N` clone, a gate that resolves a RECORDED sha
(a census doc's commit pointer, a generated provenance marker) can red with `cannot resolve <sha>`,
`bad revision`, or `unable to read tree` — the sha is a legitimate ANCESTOR of `main`, just beyond
the depth slice, and a full CI checkout has it. That is a clone artifact, never a branch defect.

- Deepen until the ancestor object exists: `git fetch --deepen=<n>` (or `git fetch --unshallow`),
  then re-run the gate. Do not amend a census/sha pointer or edit code to "fix" it — the pointer is
  correct and the clone was short.
- Discriminator: the red does NOT reproduce on a full clone, and `git merge-base --is-ancestor
  <sha> origin/main` is exit `0` once the object is present. Prove the sha is a real ancestor before
  believing the gate.
- Same family, other shape: a `--depth 1 --single-branch` clone also lacks `origin/main` itself,
  reddening any gate or unit test that diffs against the base. Fetch the ref (or deepen), don't
  rewrite the code.
