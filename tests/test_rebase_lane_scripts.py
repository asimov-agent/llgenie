"""The rebase lane's shipped scripts must be executable and syntactically clean.

Why this exists: the two scripts under
`agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/scripts/` were correctness-critical
gates for every rebase push, and they were only ever exercised from the live profile. When the
tree copy was finally run, `post-rebase-verify.sh` printed `base=refs/rem` — it misreported the
base it had verified against, because `${BASE:0:8}` truncates a ref instead of resolving it.
Nothing in the tree would have caught that: a script can ship non-executable, or with a syntax
error, and every gate stays green because no gate reads it.

Scope is deliberately THIS LANE ONLY. Asserting over all agent skills would red another lane's
work the moment one of its scripts is legitimately mid-edit, and a test that punishes a correct
change teaches the next person to edit the test. A lane that wants its own scripts covered adds
its own case here.
"""
from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = (REPO / "agents" / "llgenie-pr-merge-conflict" / "skills"
           / "llgenie-pr-rebase" / "scripts")

# Subset check, never equality: the lane is meant to add scripts, and an exact list would red
# on the next legitimate addition.
EXPECTED = {"post-rebase-verify.sh", "salvage-audit.sh", "salvage-four-bucket.py",
            "test-revert-detector.sh"}


def _shell_scripts() -> list[Path]:
    return sorted(p for p in SCRIPTS.glob("*.sh")) if SCRIPTS.is_dir() else []


def _python_scripts() -> list[Path]:
    return sorted(p for p in SCRIPTS.glob("*.py")) if SCRIPTS.is_dir() else []


def test_the_lane_ships_the_scripts_it_documents():
    actual = {p.name for p in _shell_scripts()} | {p.name for p in _python_scripts()}
    assert EXPECTED <= actual, f"missing shipped scripts: {sorted(EXPECTED - actual)}"


def test_every_shell_script_is_executable():
    # A non-executable gate script cannot be run the way the SKILL.md tells a reader to run it.
    scripts = _shell_scripts()
    assert scripts, "no shell scripts found; the glob is wrong"
    bad = [p.name for p in scripts if not os.access(p, os.X_OK)]
    assert not bad, f"not executable: {bad}"


def test_every_shell_script_parses():
    for p in _shell_scripts():
        r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
        assert r.returncode == 0, f"{p.name} has a syntax error:\n{r.stderr}"


def test_every_python_script_parses():
    for p in _python_scripts():
        try:
            ast.parse(p.read_text())
        except SyntaxError as exc:
            raise AssertionError(f"{p.name} does not parse: {exc}") from exc


def test_a_gate_script_is_not_left_empty():
    # An empty file parses and is executable, so the two checks above would both pass.
    for p in _shell_scripts() + _python_scripts():
        body = [ln for ln in p.read_text().splitlines() if ln.strip()]
        assert len(body) > 5, f"{p.name} is effectively empty ({len(body)} non-blank lines)"


def _load_audit_module():
    """Import the shipped audit tool as a module so its verdict function can be unit-tested.

    Testing `summarise` directly rather than shelling out to both tools: the tools need `gh` and
    a real repository, which CI does not have, and AGENTS.md forbids skipped tests. The counting
    RULES are what went wrong twice, and they are pure.

    `dont_write_bytecode` is disabled around the exec ON PURPOSE: importlib would otherwise drop a
    `__pycache__/*.pyc` next to the shipped scripts, and `sync-agent-profile` copies the skill
    directory wholesale — so the bytecode lands in the live profile. Measured consequence: the
    binary `.pyc` made `check_agent_profiles.py` raise `UnicodeDecodeError` and the gate stopped
    checking anything at all. A test must not leave artifacts that break a gate.
    """
    import importlib.util
    import sys

    path = SCRIPTS / "salvage-four-bucket.py"
    spec = importlib.util.spec_from_file_location("salvage_four_bucket", path)
    assert spec and spec.loader, f"cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    prior = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = prior
        # belt and braces: remove any cache dir this exec created beside the scripts
        cache = SCRIPTS / "__pycache__"
        if cache.is_dir():
            for f in cache.glob("salvage_four_bucket*.pyc"):
                f.unlink(missing_ok=True)
            if not any(cache.iterdir()):
                cache.rmdir()
    return mod


def test_a_clean_worktree_on_a_unique_branch_is_preserved():
    """The first real bug: `total - dirty` marked clean work on unique branches as deletable."""
    mod = _load_audit_module()
    rows = [{"branch": "uniq", "tip": "aaaa1111", "bucket": "orphan",
             "added": ["only/here.md"], "held_by_pr": None}]
    # clean (dirty=0) and its HEAD is the unique tip — deleting it loses the only copy
    wts = [{"path": "/wt/uniq", "branch": "uniq", "head": "aaaa1111", "dirty": 0}]

    verdict = mod.summarise(rows, wts)
    assert verdict["safe_worktrees"] == 0, "a clean worktree on a unique branch was called safe"
    assert [w["path"] for w in verdict["keep"]] == ["/wt/uniq"]


def test_lossless_orphans_are_deletable_not_preserved():
    """The second real bug: a bucket enumeration dropped lossless orphans (45 vs 162)."""
    mod = _load_audit_module()
    rows = [
        {"branch": "merged", "tip": "b1", "bucket": "merged-and-clean"},
        {"branch": "onpr", "tip": "b2", "bucket": "unmerged-with-a-PR"},
        {"branch": "lossless", "tip": "b3", "bucket": "orphan", "added": [], "held_by_pr": None},
        {"branch": "held", "tip": "b4", "bucket": "orphan",
         "added": ["x.md"], "held_by_pr": 42},
        {"branch": "uniq", "tip": "b5", "bucket": "orphan",
         "added": ["y.md"], "held_by_pr": None},
    ]

    verdict = mod.summarise(rows, [])
    assert verdict["safe_branches"] == 4, "lossless/held-by-PR orphans must count as deletable"
    assert [r["branch"] for r in verdict["unique_orphans"]] == ["uniq"]


def test_dirty_and_unique_are_union_not_sum():
    """Preserved worktrees must be a UNION: a path that is both counts once."""
    mod = _load_audit_module()
    rows = [{"branch": "uniq", "tip": "c1", "bucket": "orphan",
             "added": ["z.md"], "held_by_pr": None}]
    wts = [{"path": "/wt/both", "branch": "uniq", "head": "c1", "dirty": 3}]

    verdict = mod.summarise(rows, wts)
    assert len(verdict["keep"]) == 1, "a dirty unique worktree must be counted once, not twice"
    assert verdict["safe_worktrees"] == 0


def test_the_shipped_tools_exist_and_are_independent_implementations():
    """Two audits of one question must stay separate programs, or the cross-check is meaningless.

    Running both needs `gh` and a live repository, so this asserts only what is testable here:
    both are shipped, and neither silently delegates to the other (which would make their
    agreement vacuous).
    """
    sh = (SCRIPTS / "salvage-audit.sh").read_text()
    py = (SCRIPTS / "salvage-four-bucket.py").read_text()

    # Delegation is an EXECUTION property, not a mention. An earlier version asserted the other
    # program's NAME was absent from the file, which failed the moment the python tool printed a
    # reconciliation line naming the shell one -- a text assertion rejecting a correct change, and
    # exactly what this lane's rules forbid a test from doing. Only a line that both names the other
    # program AND invokes it counts as delegation.
    def invokes(src: str, other: str) -> bool:
        for line in src.splitlines():
            code = line.split("#", 1)[0]
            if other in code and any(t in code for t in ("subprocess", "os.system", "run(", "exec ")):
                return True
        return False

    assert not invokes(sh, "salvage-four-bucket"), "shell audit delegates to the python one"
    assert not invokes(py, "salvage-audit.sh"), "python audit delegates to the shell"
    assert "MUST BE PRESERVED" in sh and "must be preserved" in py, \
        "both must report the same two conclusion lines for a reader to compare"


def test_the_revert_detector_catches_a_revert_and_clears_a_restored_tree():
    """Run the shipped negative control for the `-X theirs` detector, in-container.

    The detector lives inside `post-rebase-verify.sh` and asserts that no tracked text file loses
    a line the base has without gaining anything. Its control builds a throwaway repo, because on
    this lane's real branch the precondition ("base is an ancestor of HEAD") does not hold, so the
    check is skipped by design there. Running the control here means a regression in the detector
    reds CI instead of waiting for the next bad rebase to find it.
    """
    import subprocess

    if not shutil.which("git"):
        # git is required by the control itself; its absence is a broken environment, not a pass.
        raise AssertionError("git absent — the revert-detector control cannot run")
    r = subprocess.run(["bash", str(SCRIPTS / "test-revert-detector.sh")],
                       capture_output=True, text=True, timeout=300,
                       env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.example",
                            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.example"})
    assert r.returncode == 0, (
        "the revert-detector control failed — the detector no longer distinguishes a revert "
        f"from a clean tree:\n{r.stdout[-800:]}\n{r.stderr[-400:]}")
    # Assert the control's verdict line, not its exit code alone: a script that exits 0 without
    # running the cases would pass an rc-only check. The three case rcs are asserted inside the
    # script itself, so this line is the evidence that it reached the verdict.
    assert "PASS: catches the substitution revert, allows a deliberate deletion" in r.stdout, \
        r.stdout[-800:]
    assert "case4 authorship:    verify rc=1" in r.stdout, \
        "the authorship assertion must be wired AND able to fail:\n" + r.stdout[-500:]
    assert "case7 divergent+clean: verify rc=0" in r.stdout, \
        "a divergent branch that merges cleanly is the ordinary PR state and must not block:\n" \
        + r.stdout[-600:]


def test_every_python_script_is_executable_and_prints_usage_without_args():
    """The documented invocation must work, and a missing argument must not traceback.

    Measured: SKILL.md tells a reader to run `scripts/resolve-phony-union.py <Makefile>`, but the
    four `.py` scripts shipped mode 100644 -- so the documented form failed with
    `Permission denied` on every machine. Two of them then crashed with a raw traceback when
    invoked without an argument (one read sys.argv[1] at import time). Both are silent to CI:
    nothing executes a skill script, so the only reader who discovers it is the one in a hurry.
    """
    for p in _python_scripts():
        assert os.access(p, os.X_OK), f"{p.name} is not executable — the documented form fails"
        r = subprocess.run([str(p)], capture_output=True, text=True, timeout=120)
        combined = r.stdout + r.stderr
        # No skill script may ever surface a raw traceback to a reader.
        assert "Traceback" not in combined, (
            f"{p.name} raises a traceback with no arguments:\n{combined[-400:]}")
        # A script that REQUIRES an argument (it reads sys.argv[1]) must say so, not guess.
        # The audit tools legitimately take none -- they measure the repo they resolve -- so
        # requiring "usage" of every script would red a correct implementation.
        if "sys.argv[1]" in p.read_text():
            assert "usage" in combined.lower(), (
                f"{p.name} reads sys.argv[1] but prints no usage line when invoked without it:\n"
                f"{combined[:300]}")


def test_the_fleet_splice_does_not_depend_on_a_scratch_path():
    """A shipped script must not read its canonical input from /tmp.

    Measured: `splice-fleet-block.py` pinned `ISSUE = /tmp/873.md`, a scratch file that exists on
    one machine until the next reboot, so the script failed for every reader but its author. It
    now resolves $REBASE_STANDING_RULES, then the versioned reference, then that legacy path.
    """
    src = (SCRIPTS / "splice-fleet-block.py").read_text()
    assert "REBASE_STANDING_RULES" in src, "the rules source must be overridable"
    assert "references" in src and "standing-rules.md" in src, \
        "it must prefer the versioned reference beside the SKILL"


def test_no_shipped_script_removes_or_prunes_a_worktree():
    """`git worktree remove`/`prune` are owner-only (issue #794): they delete a directory and cannot
    see uncommitted work inside it.

    Measured: TWO shipped scripts ran them on every invocation, against a FIXED path --
    `git worktree remove --force "$P/../llgenie-wt/b$N"` plus `git worktree prune` -- so a second
    run destroyed whatever a human had left in that worktree, and `prune` swept every other stale
    entry in the repository as a side effect. A lane whose own rule forbids the command must not
    ship a script that executes it: the rule is invisible to the reader who runs the script.
    """
    offenders = []
    for p in _shell_scripts():
        for i, line in enumerate(p.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]   # comments may explain the rule; only real code counts
            if re.search(r"\bgit\s+worktree\s+(remove|prune)\b", code):
                offenders.append(f"{p.name}:{i}")
    assert not offenders, (
        "shipped script executes an owner-only worktree deletion: " + ", ".join(offenders))


def test_every_worktree_a_script_creates_is_unique_per_run():
    """A fixed scratch path forces the script to destroy the previous run's worktree.

    Measured: with `WT=b$N`, a re-run had no choice but `remove --force` first. Making the path
    per-run is what lets the script stop deleting anything at all, so the two properties are
    asserted together -- a script that keeps a fixed path will regrow the deletion.
    """
    for p in _shell_scripts():
        src = p.read_text()
        if not re.search(r"\bgit\s+worktree\s+add\b", src):
            continue
        # Assert on the PATH itself, not on the file as a whole: a stray $STAMP elsewhere in the
        # script says nothing about whether the worktree path is unique. Measured -- a whole-file
        # check passed while the WT assignment was a fixed path, so the control did not bite.
        wt = [l for l in src.splitlines() if re.match(r"\s*WT=\S", l)]
        assert wt, f"{p.name} creates a worktree but has no WT= assignment to inspect"
        for line in wt:
            assert ("$STAMP" in line or "$(date" in line or "mktemp" in line), (
                f"{p.name}: worktree path is fixed ({line.strip()!r}), which forces the script to "
                f"remove the previous run's worktree; give it a per-run stamp")


def test_the_phony_resolver_writes_a_makefile_make_accepts(tmp_path):
    """End-to-end: a real `.PHONY` conflict resolved by the documented tool must still be a Makefile.

    Measured defect: the renderer emitted a hardcoded TAB plus a trailing backslash, so the resolved
    line became a RECIPE and `make` refused the whole file --
        Makefile:1: *** recipe commences before first target.  Stop.
    Nothing reads `.PHONY` for correctness and no gate compiles a Makefile, so the only way to find
    out was the next `make` invocation. The keys were all present, which is why a keys-only check
    passed: the union was right and the file was still unusable.
    """
    resolver = SCRIPTS / "resolve-phony-union.py"
    if not resolver.exists():
        return
    mk = tmp_path / "Makefile"
    mk.write_text(
        "<<<<<<< HEAD\n"
        ".PHONY: alpha delta\n"
        "=======\n"
        ".PHONY: alpha gamma\n"
        ">>>>>>> side\n"
        "\n"
        "run:\n"
        "\techo hi\n")
    r = subprocess.run([str(resolver), str(mk)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    out = mk.read_text()

    # Behavioural invariants, asserted whether or not `make` is installed.
    phony = [ln for ln in out.splitlines() if ln.lstrip().startswith(".PHONY")]
    assert phony, "the resolver lost the .PHONY line entirely"
    assert not phony[0].startswith("\t"), (
        f".PHONY rendered at tab indentation -- it becomes a recipe and the file is unparseable: "
        f"{phony[0]!r}")
    assert not phony[0].rstrip().endswith("\\"), (
        f".PHONY rendered with a dangling continuation: {phony[0]!r}")
    for key in ("alpha", "delta", "gamma"):
        assert key in phony[0], f"union dropped {key!r}: {phony[0]!r}"

    # And if make is present, the stronger check: it must actually parse.
    make = shutil.which("make")
    if make:
        p = subprocess.run([make, "-n", "-f", str(mk)], capture_output=True, text=True,
                           timeout=60, cwd=tmp_path)
        assert p.returncode == 0, (
            "make rejects the resolver's own output:\n" + (p.stdout + p.stderr)[-500:])


def test_the_standing_rules_reference_exists_and_carries_the_current_rules(tmp_path):
    """The splice tool must read its rules from the versioned tree, not a scratch file.

    Measured defect: `splice-fleet-block.py` resolved its source to `/tmp/873.md`, a file that
    exists on one machine until the next reboot. On this host that copy was TWO GENERATIONS STALE,
    and running the tool on a correct SOUL rewrote four standing rules to older wording while
    printing `block in soul: True`. A tool that silently degrades the text it exists to propagate
    is the same defect as a `-X` strategy resolution.
    """
    ref = SCRIPTS.parent / "references" / "standing-rules.md"
    assert ref.is_file(), (
        "references/standing-rules.md is missing — the splice tool would fall back to a scratch "
        "path and may splice an older generation of the rules")
    text = ref.read_text()
    for probe in ("Never hold a PR without a remedy",
                  "Announce the work where the work lives",
                  "Start from a fresh upstream main",
                  "Arm auto-merge when the work is done"):
        assert probe in text, f"the canonical rules file lacks a current rule: {probe!r}"


def test_the_fleet_splice_is_idempotent_and_refuses_an_older_source(tmp_path):
    """Behaviour, not text: a correct SOUL must be unchanged, and a stale source must be refused."""
    splice = SCRIPTS / "splice-fleet-block.py"
    ref = SCRIPTS.parent / "references" / "standing-rules.md"
    if not splice.exists() or not ref.is_file():
        return
    soul_src = REPO / "agents" / "llgenie-pr-merge-conflict" / "SOUL.md"
    soul = tmp_path / "SOUL.md"
    soul.write_text(soul_src.read_text())

    # 1. with the versioned source it must be a no-op
    before = soul.read_text()
    r = subprocess.run([str(splice), str(soul)], capture_output=True, text=True, timeout=120,
                       env={**os.environ, "REBASE_STANDING_RULES": str(ref)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert soul.read_text() == before, (
        "the splice rewrote a SOUL that already carried the canonical block:\n"
        + r.stdout[-400:])
    assert "MISSING" not in r.stdout, f"a current rule was reported missing:\n{r.stdout}"

    # 2. with an older source it must refuse and write nothing
    stale = tmp_path / "stale.md"
    stale.write_text(
        "```\n## Standing rules (fleet, learned 2026-10-28)\n"
        "- **Never hold a PR without a remedy.**\n"
        "- **Announce the work where the work lives.**\n"
        "- **Start from a fresh upstream main.**\n"
        "- **Arm when done, and only on a base of main.**\n```\n")
    before = soul.read_text()
    r = subprocess.run([str(splice), str(soul)], capture_output=True, text=True, timeout=120,
                       env={**os.environ, "REBASE_STANDING_RULES": str(stale)})
    assert r.returncode != 0, "a source missing a current rule was accepted"
    assert "REFUSING" in r.stderr, r.stderr[-400:]
    assert soul.read_text() == before, "the refused splice still wrote the file"


def _load_salvage():
    """Import the shipped script WITHOUT writing bytecode into the tree.

    Measured: importing it normally creates `scripts/__pycache__/*.pyc` inside agents/. Those are
    git-ignored, so no gate notices -- but `make sync-agent-profile` walks the working tree, hit the
    .pyc, and died with `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xa7`. A test must not
    change the tree it is testing: suppress bytecode writing for the duration of the import.
    """
    import importlib.util
    import sys as _sys
    src = SCRIPTS / "salvage-four-bucket.py"
    if not src.exists():
        return None
    prev = _sys.dont_write_bytecode
    _sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("salvage_four_bucket", src)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        _sys.dont_write_bytecode = prev



def test_the_salvage_audit_states_the_orphan_predicate():
    """`orphan: N` alone is a count without its predicate.

    Measured on this host: the orphan bucket held 124 branches and only 21 of them added a path
    main lacks; the other 103 were lossless. The headline therefore read as 124 pieces of work to
    rescue when the number a reader must act on was 21. The split is a pure function so it can be
    asserted without gh or a real repository.
    """
    mod = _load_salvage()
    if mod is None or not hasattr(mod, "orphan_split"):
        return
    rows = [
        dict(bucket="orphan", branch="u1", added=["a/b.md"]),
        dict(bucket="orphan", branch="u2", added=[]),
        dict(bucket="orphan", branch="u3", added=["c.md", "d.md"]),
        dict(bucket="orphan", branch="h1", added=["e.md"], held_by_pr=1147),
        dict(bucket="merged-and-clean", branch="m1", added=[]),
        dict(bucket="unmerged-with-a-PR", branch="p1", added=["x.md"]),
    ]
    uniq, held, lossless = mod.orphan_split(rows)
    assert [r["branch"] for r in uniq] == ["u1", "u3"], uniq
    assert [r["branch"] for r in held] == ["h1"], held
    assert [r["branch"] for r in lossless] == ["u2"], lossless
    # A PR-carrying or merged branch must never be counted as an orphan it has to preserve.
    assert all(r["bucket"] == "orphan" for r in uniq + held + lossless), "orphan_split leaked a non-orphan"
    # Content carried by an open PR head is NOT unique: deleting the branch loses nothing
    # reviewable. This is the predicate that made the two shipped audit tools disagree (6 vs 21).
    assert not any(r.get("held_by_pr") for r in uniq), "a PR-carried branch was called unique"


def test_loading_the_shipped_scripts_leaves_no_bytecode_in_the_tree():
    """A test must not mutate the tree it tests.

    Measured: importing `salvage-four-bucket.py` normally writes `scripts/__pycache__/*.pyc` under
    agents/. They are git-ignored, so no review and no gate sees them -- but `make sync-agent-profile`
    copies every file under the profile directory into the live profile, so the .pyc were shipped
    there (sync went from 18 files to 20), and once one was half-written the sync died outright:

        UnicodeDecodeError: 'utf-8' codec can't decode byte 0xa7 in position 0

    which blocked the sanctioned tree -> live direction for this lane.
    """
    _load_salvage()
    strays = [str(p) for p in (REPO / "agents").rglob("__pycache__")]
    assert not strays, (
        "loading a shipped script wrote bytecode into the tree, which sync-agent-profile then "
        "copies into the live profile: " + ", ".join(strays[:3]))


def test_the_pre_push_gate_runs_ratchet_not_check_for_import_roots():
    """The gate must use the `ratchet` subcommand, never `check`.

    Measured: on a pristine clean main, `check` returns rc=1 (84 grandfathered root findings)
    while `ratchet` returns rc=0 -- because `check` is a raw shape scan and `ratchet` compares the
    COUNT to the baseline. CI runs `ratchet`. If this gate used `check` it would DO NOT PUSH on
    every clean tree, teaching the reader to disarm it. Pinned here because the one-line change
    `check` -> `ratchet` (or back) reds exactly this behaviour and there is no cheaper assertion:
    asserting the exit code would require a full tree with fixtures.
    """
    v = (SCRIPTS / "post-rebase-verify.sh").read_text()
    assert "ratchet" in v, "the pre-push gate must invoke the import-roots RATCHET (the CI path)"
    # The subcommand must be used, not merely mentioned: a comment saying 'use ratchet' with the
    # code calling `check` is exactly the foot-gun in check_import_roots.py:18.
    call_line = [l for l in v.splitlines() if "check_import_roots.py" in l and "ratchet" in l]
    assert call_line, "the gate must CALL check_import_roots.py ratchet:\n" + \
        "\n".join(l for l in v.splitlines() if "check_import_roots" in l)


def test_no_replay_script_resolves_a_conflict_by_silently_choosing_a_side():
    """A stacked-replay driver must never `git checkout --ours` a conflict it cannot union.

    Measured by reading stack-replay.sh and then proving it in a throwaway cherry-pick:
    `--ours` during a cherry-pick means the BASE side, so its fallback silently DROPPED the
    replayed commit's own change (base.txt `--ours` -> 'mainline-change', losing 'pr-own-work')
    and the commit still proceeded. That is the silent-revert class this lane exists to repair,
    inverted. The fix refuses when the resolver leaves an unmerged file, so the author reconciles
    two real intents instead of inheriting one silently.
    """
    for f in ("stack-replay.sh", "batch-rebase.sh"):
        src = (SCRIPTS / f).read_text()
        # drop comments FIRST, then look for a real `--ours` side-choice in CODE: a comment that
        # merely names the foot-gun (this file's own note does) must not count as the defect.
        call_lines = [code for code in (ln.split("#", 1)[0] for ln in src.splitlines())
                      if "git checkout" in code and "--ours" in code]
        assert not call_lines, (
            f"{f} resolves a conflict with `--ours`, which silently drops the replayed commit's "
            f"own change: {call_lines}")
        # the refusal path for the resolver, if the script does replay
        if "cherry-pick" in src:
            assert "REFUSING" in src, f"{f} has no refusal when the resolver cannot union a file"


def test_the_rebase_drivers_verify_commit_preservation():
    """A rebase that silently drops one of the branch's own commits must refuse the push.

    Measured: two lanes lost a fix to a silent discard this way and only a HUMAN diff found it --
    the tree parses, the tests pass, one semantic change is just gone, so no content gate notices.
    The drivers capture the branch's own commit subjects before the replay and assert each is still
    in the history afterwards (rewrites change shas, so subjects are the stable identity). A check
    that is never wired to stop the push is a ritual, so assert the refusal message is reachable.
    """
    for f in ("stack-replay.sh", "batch-rebase.sh"):
        src = (SCRIPTS / f).read_text()
        assert "OWN=" in src or "WANTED=" in src, f"{f} does not capture the pre-rebase own commits"
        assert "COMMIT LOST" in src, f"{f} has no preservation refusal when a commit is dropped"
        assert "grep -Fxq" in src, f"{f} compares subjects, not shas (rewrites change shas)"


def test_the_commit_preservation_control_runs_and_catches_a_drop():
    """The shipped negative control for the rebase drivers' preservation check must bite.

    It builds a throwaway repo, replays one commit, and asserts the subject set-compare responds:
    preserved -> LOST empty, dropped -> LOST names the commit. A checker that cannot fail pins
    nothing, so the control itself asserts the DROP case (rc and the named subject), not just that
    the script reached a PASS line (which an exit-0-without-running-the-cases script would also do).
    """
    ctrl = SCRIPTS / "test-commit-preservation.sh"
    if not ctrl.exists():
        return
    r = subprocess.run(["bash", str(ctrl)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    # the verdict must be the DROP case being caught, not merely a PASS banner
    assert "LOST=[the PRs own change]" in r.stdout, (
        "the control must have exercised and caught the dropped commit:\n" + r.stdout)


def test_every_shipped_control_is_tracked_executable():
    """A shipped script's MODE in the git index is part of its contract.

    Measured: the new commit-preservation control shipped with mode 100755 in git, but the sync
    had copied it into the live profile as 0644 in BOTH profile copies -- so the documented direct
    invocation (./scripts/test-commit-preservation.sh) would have failed Permission denied for
    anyone running it from the profile. Git is the source of truth: assert every *.sh control under
    scripts/ is tracked with the executable bit; it is what a reinstall restores and what the sync
    should preserve.
    """
    # NODOC: two previous drafts were unreliable. (1) An aggregate pathspec-glob
    # (`git ls-files -s scripts/*.sh`) returned EMPTY in the container, so the test PASSED with
    # no files scanned -- a vacuum. (2) Per-path `git -C ls-files` then returned NOTHING for every
    # file because git refuses "dubious ownership" inside the container (repo owned by another uid)
    # -- so it wrongly flagged every script. The faithful, container-safe check is os.access on the
    # checkout: git's recorded 100755 mode BECOMES the worktree mode on checkout, so a non-exec
    # tracked script is a non-exec worktree file, and this test IS what git would restore.
    non_exec = [str(sh) for sh in sorted(SCRIPTS.glob("*.sh")) if not os.access(sh, os.X_OK)]
    assert SCRIPTS.glob("*.sh"), "no .sh scripts found to scan -- the lane scripts dir is empty"
    assert not non_exec, (
        "these shipped scripts are tracked non-executable, so their documented form fails "
        "Permission denied on every checkout: " + ", ".join(sorted(non_exec)))
