"""A PR must be cut from origin/main itself — the foreign-commit gate (issue #845).

Criteria 3 and 5 of #845: the gate fails a PR whose merge-base with
`refs/remotes/origin/main` is not `refs/remotes/origin/main` itself (the branch
carries commits from another PR — the #794 case), naming the foreign commit; and
it stays GREEN for a clean branch that is exactly one commit ahead of
`origin/main` (the negative control). Real commits, real merge-bases.

Issue #1734 makes the one trust boundary explicit: the gate measures against a
FRESH `main`, re-fetching it at measure time rather than trusting a possibly
stale `refs/remotes/origin/main` — and it REFUSES (never passes) when that fetch
fails. A missing tracking ref is therefore no longer "fabricated a pass": when
the remote is reachable the gate restores it by fetching; when the remote is
unreachable the gate refuses with a fetch-failure and never quietly passes.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent

import scripts.check_pr_base as cpb  # noqa: E402

ENV = {**os.environ,
       "GIT_AUTHOR_NAME": "Andy Holst", "GIT_AUTHOR_EMAIL": "andy.holst@protonmail.com",
       "GIT_COMMITTER_NAME": "Andy Holst", "GIT_COMMITTER_EMAIL": "andy.holst@protonmail.com",
       "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}

def git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=ENV)
    assert r.returncode == 0, f"git {' '.join(args)} failed: {r.stderr}"
    return r.stdout.strip()


def repo(tmp_path: Path) -> Path:
    """A bare origin and a clone on main, with refs/remotes/origin/main present."""
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    origin.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    (work / "README").write_text("seed\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "seed")
    git(work, "remote", "add", "origin", str(origin))
    git(work, "push", "-q", "-u", "origin", "main")
    git(work, "remote", "set-head", "origin", "main")
    return work


def test_a_foreign_commit_fails_and_is_named(tmp_path):
    """A branch cut from another PR (diverged from current origin/main) fails, #845.

    The #794 shape: the other PR branch was cut from an OLDER main and carries
    commits origin/main never saw; our branch cut from ITS tip (as a worktree
    inheriting the primary checkout's parked branch would) therefore has
    merge-base with CURRENT origin/main != origin/main. The foreign commit is
    named.
    """
    work = repo(tmp_path)

    # another PR branch: cut from the THEN-current main, work NOT pushed to main
    git(work, "switch", "-q", "-c", "pr/other", "main")
    (work / "other.txt").write_text("other lane\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "other PR's work")
    foreign = git(work, "rev-parse", "HEAD")

    # origin/main ADVANCES past the point pr/other was cut at (a merge, another PR)
    git(work, "switch", "-q", "main")
    (work / "main2.txt").write_text("main moved on\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "origin/main advances")
    git(work, "push", "-q", "origin", "main")

    # OUR branch cut from that stale other-PR tip — the #794 worktree shape
    git(work, "switch", "-q", "-c", "pr/mine", "pr/other")
    (work / "mine.txt").write_text("my lane\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "my work")

    ok, foreign_commits = cpb.check(work, cpb.DEFAULT_BASE, "pr/mine")
    assert ok is False
    assert foreign_commits, "a foreign merge-base must name foreign commits"
    joined = " ".join(foreign_commits)
    assert foreign[:7] in joined or "other PR's work" in joined
    # and origin/main is genuinely not an ancestor of the head
    assert git(work, "rev-parse", "refs/remotes/origin/main") != git(work, "merge-base",
                                                                     "refs/remotes/origin/main", "pr/mine")


def test_a_clean_one_ahead_branch_passes(tmp_path):
    """The negative control: exactly one commit ahead of origin/main, no foreign work."""
    work = repo(tmp_path)
    git(work, "switch", "-q", "-c", "pr/clean", "main")
    (work / "clean.txt").write_text("one ahead\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "one commit ahead, clean")
    ok, foreign = cpb.check(work, cpb.DEFAULT_BASE, "pr/clean")
    assert ok is True, foreign
    assert foreign == []


def test_a_missing_base_ref_is_restored_by_fetch_not_vice_versa(tmp_path):
    """#1734: a missing tracking ref is re-fetched; it is not a quiet pass either.

    When `refs/remotes/origin/main` is deleted but the remote is reachable, the
    gate now RESTORES it by fetching (the fresh measure wins) and still judges the
    branch — reachable remote, so a branch cut from live main passes.
    """
    work = repo(tmp_path)
    git(work, "switch", "-q", "-c", "pr/clean", "main")
    (work / "clean.txt").write_text("one ahead\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "one commit ahead, clean")
    git(work, "update-ref", "-d", "refs/remotes/origin/main")
    ok, foreign = cpb.check(work, cpb.DEFAULT_BASE, "pr/clean")
    assert ok is True, foreign
    assert foreign == []
    # and the fetch genuinely restored the ref (the measured sha is the live one)
    assert git(work, "rev-parse", "refs/remotes/origin/main")


def test_a_fetch_failure_refuses_rather_than_passing_stale(tmp_path):
    """#1734 acceptance: a failed fetch must REFUSE, never pass on a stale measure."""
    work = repo(tmp_path)
    git(work, "switch", "-q", "-c", "pr/clean", "main")
    (work / "clean.txt").write_text("one ahead\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "one commit ahead, clean")
    # make the remote unreachable — the base ref still resolves LOCALLY (the stale
    # measure would look resolvable), so only the fetch-failure path can catch it
    git(work, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    ok, foreign = cpb.check(work, cpb.DEFAULT_BASE, "pr/clean")
    assert ok is False
    assert foreign and ("could not fetch" in foreign[0] or "does not resolve" in foreign[0])


def test_stale_local_main_is_refreshed_before_the_verdict(tmp_path):
    """#1734 regression: a STALE refs/remotes/origin/main must not drive the verdict.

    Advance origin/main past the clone's snapshot, leave the clone's tracking ref
    stale, then cut a branch from the LIVE tip and confirm the gate re-fetches and
    measures against the live main (its sha appears in the verdict), not the stale
    one.
    """
    work = repo(tmp_path)
    # origin/main advances (a merge / another PR) while this clone is not re-fetched
    git(work, "switch", "-q", "main")
    (work / "advance.txt").write_text("main moved\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "origin/main advances")
    git(work, "push", "-q", "origin", "main")
    live = git(work, "rev-parse", "main")

    # NOW refresh the clone's tracking ref to the PRE-advance tip: deliberately stale
    git(work, "update-ref", "refs/remotes/origin/main", f"{live}~1")
    stale = git(work, "rev-parse", "refs/remotes/origin/main")
    assert stale != live, "test premise broken: the tracking ref must be stale"

    # a branch cut from the LIVE tip (what a freshly-cloned next lane would sit on)
    git(work, "switch", "-q", "-c", "pr/live-cut", "main")
    (work / "mine.txt").write_text("my lane\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "cut from the live tip")
    head = git(work, "rev-parse", "HEAD")

    ok, foreign = cpb.check(work, cpb.DEFAULT_BASE, "pr/live-cut")
    lines = cpb.render(ok, cpb.DEFAULT_BASE, "pr/live-cut", foreign, work)
    text = "\n".join(lines)
    assert ok, text
    # the verdict must measure against the LIVE main sha, which it only has after
    # re-fetching the deliberately stale tracking ref (issue #1734)
    assert f"measured against `{cpb.DEFAULT_BASE}` at `{live}`" in text, text


def test_the_cli_exits_correctly_for_both_cases(tmp_path):
    """`check` exits 0 for a clean one-ahead branch, 1 when a foreign commit is present."""
    work = repo(tmp_path)
    git(work, "switch", "-q", "-c", "pr/clean", "main")
    (work / "clean.txt").write_text("one ahead\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "clean ahead")
    r = subprocess.run(["python3", str(REPO / "scripts" / "check_pr_base.py"), "check",
                        "--base", cpb.DEFAULT_BASE, "--rev", "pr/clean", "--cwd", str(work)],
                       capture_output=True, text=True, env=ENV)
    assert r.returncode == 0, r.stderr + r.stdout

    # origin/main advances; a branch cut from the OLD clean tip then carries foreign work
    git(work, "switch", "-q", "main")
    (work / "mainx.txt").write_text("main advances\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "origin/main advances")
    git(work, "push", "-q", "origin", "main")

    git(work, "switch", "-q", "-c", "pr/borrowed", "pr/clean")
    (work / "borrow.txt").write_text("borrowed\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "borrowed work on my branch")
    # merge-base(origin/main, pr/borrowed) is the fork point, not origin/main
    borrowed_gate = subprocess.run(
        ["python3", str(REPO / "scripts" / "check_pr_base.py"), "check",
         "--base", cpb.DEFAULT_BASE, "--rev", "pr/borrowed", "--cwd", str(work)],
        capture_output=True, text=True, env=ENV)
    assert borrowed_gate.returncode != 0, borrowed_gate.stdout + borrowed_gate.stderr
    assert "foreign commits" in borrowed_gate.stdout or "NOT cut" in borrowed_gate.stdout


def test_a_pushed_main_commit_overtaken_by_a_newer_main_passes(tmp_path):
    """#1867/#1906..#1909: a head that is an ANCESTOR of live main must pass.

    A push to main whose commit a busy fleet already overtook (back-to-back
    merges) has `merge-base(origin/main, HEAD) == HEAD != origin/main` — yet
    `base..rev` is empty: HEAD carries nothing absent from live main, so a PR
    from it would leak nothing (#845's concern is a branch cut from ANOTHER PR,
    which always leaves non-empty `base..rev`). Reddening this shape is the
    phantom base-staleness the reactor filed issues #1906..#1909 for; the gate
    must stay green while still failing a genuine foreign-commit leak.
    """
    work = repo(tmp_path)
    # main advances to B; a pushed commit A (already part of main's history) is
    # now an ANCESTOR of the live tip.
    git(work, "switch", "-q", "main")
    (work / "a.txt").write_text("first merge\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "merge A lands on main")
    a = git(work, "rev-parse", "HEAD")
    git(work, "push", "-q", "origin", "main")
    (work / "b.txt").write_text("second merge\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "merge B lands right after A (back-to-back)")
    git(work, "push", "-q", "origin", "main")

    # the pushed commit A is the run's HEAD; live origin/main is already B
    ok, foreign = cpb.check(work, cpb.DEFAULT_BASE, a)
    assert ok is True, foreign
    assert foreign == []
    lines = cpb.render(ok, cpb.DEFAULT_BASE, a, foreign, work)
    assert "ANCESTOR" in "\n".join(lines)


def _ci_guard_step() -> dict:
    """The `make check-pr-base` step in ci.yml's guard job, as parsed YAML."""
    wf = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text())
    guard = wf["jobs"]["guard"]
    for step in guard.get("steps", []):
        name = step.get("name", "")
        if name and name.startswith("make check-pr-base"):
            return step
    raise AssertionError("ci.yml guard job declares no 'make check-pr-base' step")


def test_the_check_pr_base_step_is_gated_to_pull_request():
    """#1867: ci.yml runs `make check-pr-base` only on a `pull_request` event.

    On a push to main the pushed commit IS main's history the instant the run starts, but the
    step re-fetches `origin/main` LIVE and a busy fleet has already advanced it — so
    `merge-base(origin/main, HEAD) == HEAD != origin/main` and the gate reds on a phantom
    base-staleness (foreign commits (0), content IS on main). The #845 protection exists to
    catch a PR branch cut from another PR, which a push event cannot be — so the step must be
    skipped on push and judged only for PRs.
    """
    step = _ci_guard_step()
    cond = step.get("if")
    assert cond is not None, (
        "ci.yml 'make check-pr-base' step has no event guard — a push-to-main run re-fetches "
        "a live origin/main that already advanced past the pushed HEAD and reds on a phantom "
        "base-staleness (issue #1867)"
    )
    # A GitHub `if:` condition may be spelled bare (`if: github.event_name == 'pull_request'`)
    # or wrapped in an expression. Strip an optional wrapper so the behaviour is what is tested.
    expr = str(cond).strip()
    m = re.fullmatch(r"\$\{\{\s*(.*?)\s*\}\}", expr, re.S)
    if m:
        expr = m.group(1).strip()
    bound = re.sub(r"github\.event_name", "'pull_request'", expr)
    # GitHub evaluates an empty/absent expression; here we already asserted cond is not None.
    assert bool(eval(bound, {"__builtins__": {}}, {})), (  # noqa: S307 — repo-owned expression
        f"check-pr-base must run on a pull_request (expression evaluates false): {cond!r}"
    )
    bound_push = re.sub(r"github\.event_name", "'push'", expr)
    assert not bool(eval(bound_push, {"__builtins__": {}}, {})), (  # noqa: S307 — repo-owned expression
        f"check-pr-base must be SKIPPED on a push (expression evaluates true): {cond!r}"
    )


def test_a_stale_but_clean_branch_passes_with_distinct_message(tmp_path):
    """#2016: a branch cut from an OLDER main (merge-base IS a main ancestor, own commits
    only) passes with the distinct 'rebase onto a fresh origin/main' STALE message — it is
    NOT attributed to the #845 foreign-branch leak.

    This is the `#1969/#1976/#1933` shape: the branch is cut from an older main tip (merge-base
    is on main's history), carries only its OWN work, and is merely behind the live tip. The old
    gate redded it with the same message as a genuine leak ('so the branch carries commits from
    another PR / another base (issue #845)') — a false accusation that cancelled the guard job's
    walking legs (issue #2016). Under the fix it exits 0, keeps its own-commits facts, and names a
    rebase owed, not a leak.
    """
    work = repo(tmp_path)
    # a branch cut from the THEN-current main (the seed), carrying only its OWN commit
    git(work, "switch", "-q", "-c", "pr/stale", "main")
    (work / "stale.txt").write_text("my own work\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "feat(mine): my own work (issue #2016)")
    head = git(work, "rev-parse", "HEAD")
    # origin/main ADVANCES past the point pr/stale was cut at (a merge / another PR)
    git(work, "switch", "-q", "main")
    (work / "adv1.txt").write_text("advance one\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "main advance one")
    (work / "adv2.txt").write_text("advance two\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "main advance two")
    git(work, "push", "-q", "origin", "main")

    ok, foreign = cpb.check(work, cpb.DEFAULT_BASE, "pr/stale")
    assert ok is True, foreign
    assert foreign == []
    lines = cpb.render(ok, cpb.DEFAULT_BASE, "pr/stale", foreign, work)
    text = "\n".join(lines)
    # the distinct STALE verdict: a rebase is owed, NOT a #845 leak accusation
    assert "STALE" in text, text
    assert "Rebase onto a fresh" in text, text
    assert "NOT the #845 foreign-commit leak" in text, text
    assert "carries commits from another PR" not in text, text
    assert text.count("issue #845") == 0, text
    # the merge-base IS on main (the STALE verdict itself requires merge-base-on-main,
    # so this asserts the probe carried a real main-tip ancestor)
    mb = git(work, "merge-base", cpb.DEFAULT_BASE, head)
    assert mb

    # and the CLI exits 0 — the guard job passes, so linux/ci-images/scanner-images run
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "check_pr_base.py"), "check",
                        "--base", cpb.DEFAULT_BASE, "--rev", "pr/stale", "--cwd", str(work)],
                       capture_output=True, text=True, env=ENV)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_genuine_leak_cut_from_a_stale_other_pr_still_reds(tmp_path):
    """#2016 regression guard: the discriminator must NOT weaken the real #845 detection.

    A branch cut from ANOTHER PR's tip (the worktree-inherits-parked-branch shape) carries a
    commit reachable from that OTHER branch's ref — a genuine foreign leak — and must STILL red
    with the original issue #845 message even though the merge-base happens to be on main.
    This mirrors the existing `test_a_foreign_commit_fails_and_is_named` but asserts the message
    -- not merely the exit code -- is the #845 accusation, proving the discriminator did not
    reclassify a real leak as stale.
    """
    work = repo(tmp_path)
    git(work, "switch", "-q", "-c", "pr/other", "main")
    (work / "other.txt").write_text("other lane\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "other PR's work")
    foreign = git(work, "rev-parse", "HEAD")
    git(work, "switch", "-q", "main")
    (work / "adv.txt").write_text("main moves on\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "origin/main advances")
    git(work, "push", "-q", "origin", "main")
    # our branch cut from that OTHER PR's tip — the #794/#845 worktree shape
    git(work, "switch", "-q", "-c", "pr/mine", "pr/other")
    (work / "mine.txt").write_text("my lane work\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "my work on top")

    ok, leaked = cpb.check(work, cpb.DEFAULT_BASE, "pr/mine")
    assert ok is False, "a genuine #845 leak must still red"
    assert leaked, "the foreign commit must be named"
    assert "other PR's work" in " ".join(leaked)
    lines = cpb.render(ok, cpb.DEFAULT_BASE, "pr/mine", leaked, work)
    text = "\n".join(lines)
    assert "issue #845" in text, text
    assert "carries commits from another PR" in text, text
    assert "STALE" not in text, "the leak is NOT a stale-but-clean verdict"
    # and the CLI exits non-zero — the guard job fails, so the legs are cancelled for a leak
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "check_pr_base.py"), "check",
                        "--base", cpb.DEFAULT_BASE, "--rev", "pr/mine", "--cwd", str(work)],
                       capture_output=True, text=True, env=ENV)
    assert r.returncode != 0, r.stdout + r.stderr


def test_a_merge_ref_behind_branch_passes_when_the_head_branch_is_named(tmp_path):
    """#2138: a merely-behind branch whose PR head is checked out as its MERGE ref is GREEN.

    `linux / unit` runs `make ci-unit`, which runs `make check-pr-base` with no PR_HEAD, so
    `--rev HEAD` resolves to the PR's **merge ref** — a synthetic commit whose parents are the
    head commit and the base. The branch's own remote ref points at the head commit (an ancestor
    of the merge), so `for-each-ref --contains <merge>` does NOT include it, and the old
    discriminator read that own ref as a foreign signal and redded an 8-way false positive
    (issue #2138). The fix names the head's OWN refs from `--head-ref-name` (PR_BRANCH) and
    `--pr-number`, so the same git facts exit 0 STALE with the branch's own commit listed as own.
    """
    work = repo(tmp_path)
    # a branch cut from the THEN-current main, carrying only its OWN commit
    git(work, "switch", "-q", "-c", "pr/mine", "main")
    (work / "mine.txt").write_text("my own work\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "feat(mine): my own work")
    own = git(work, "rev-parse", "HEAD")
    git(work, "push", "-q", "origin", "pr/mine")
    seed = git(work, "rev-parse", "refs/remotes/origin/main")
    # the PR's /merge ref is created NOW against the THEN-current base (seed), exactly as
    # GitHub builds refs/pull/N/merge at event time — then origin/main ADVANCES past it
    git(work, "switch", "-q", "-c", "pr/merge", seed)
    git(work, "merge", "-q", "--no-ff", "--no-edit", "-m", "Merge pull request", "pr/mine")
    git(work, "switch", "-q", "main")
    (work / "adv.txt").write_text("main moves on\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "origin/main advances")
    git(work, "push", "-q", "origin", "main")
    # the `linux / unit` checkout leaves HEAD on the PR's MERGE ref (a synthetic
    # 2-parent commit), not on main — switch back so `--rev HEAD` measures it
    git(work, "switch", "-q", "pr/merge")
    # the own commit IN the checked-out base..HEAD — the failure shape from #2078/#2138
    assert own in git(work, "rev-list", "--no-merges",
                      "refs/remotes/origin/main..HEAD").splitlines(), "test premise: own commit must be in base..HEAD"

    # WITHOUT the head-ref-name the old bug returns: the own commit reads foreign
    ok_old, leaked_old = cpb.check(work, cpb.DEFAULT_BASE, "HEAD")
    assert ok_old is False
    assert own[:7] in " ".join(leaked_old), "premise: the bug must be reproducible (own commit as foreign)"

    # WITH the head branch named, the same git facts are STALE/own/green
    ok, leaked = cpb.check(work, cpb.DEFAULT_BASE, "HEAD", "pr/mine", "128")
    assert ok is True, leaked
    assert leaked == []
    lines = cpb.render(True, cpb.DEFAULT_BASE, "HEAD", leaked, work, "pr/mine", "128")
    text = "\n".join(lines)
    assert "STALE" in text, text
    assert "own commits carried (1)" in text, text
    assert "feat(mine): my own work" in text
    assert "carries commits from another PR" not in text, text
    # and the CLI — the exact `make check-pr-base` on `linux / unit` once PR_BRANCH is forwarded — exits 0
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "check_pr_base.py"), "check",
                        "--base", cpb.DEFAULT_BASE, "--rev", "HEAD",
                        "--head-ref-name", "pr/mine", "--pr-number", "128",
                        "--cwd", str(work)],
                       capture_output=True, text=True, env=ENV)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_genuine_leak_still_reds_in_the_merge_ref_shape(tmp_path):
    """#2138 negative control: naming the head branch must NOT weaken the real #845 detection.

    The same merge-ref checkout that mis-reported a merely-behind branch as foreign must still
    red a GENUINE leak — a branch that really carries another branch's commit — naming only the
    foreign commit. The head branch's own refs are OWN; the other branch's ref is not.
    """
    work = repo(tmp_path)
    git(work, "switch", "-q", "-c", "pr/other", "main")
    (work / "other.txt").write_text("other lane\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "other PR's work")
    foreign = git(work, "rev-parse", "HEAD")
    git(work, "push", "-q", "origin", "pr/other")
    seed = git(work, "rev-parse", "refs/remotes/origin/main")
    # our branch cut from the other PR's tip
    git(work, "switch", "-q", "-c", "pr/mine", "pr/other")
    (work / "mine.txt").write_text("my lane work\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "my work on top")
    # the PR /merge ref built NOW against the THEN-current base (seed), as GitHub does,
    # then origin/main ADVANCES past it
    git(work, "switch", "-q", "-c", "pr/merge", seed)
    git(work, "merge", "-q", "--no-ff", "--no-edit", "-m", "Merge pull request", "pr/mine")
    git(work, "switch", "-q", "main")
    (work / "adv.txt").write_text("main moves on\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "origin/main advances")
    git(work, "push", "-q", "origin", "main")
    # the `linux / unit` checkout leaves HEAD on the PR's MERGE ref — switch back
    git(work, "switch", "-q", "pr/merge")

    ok, leaked = cpb.check(work, cpb.DEFAULT_BASE, "HEAD", "pr/mine", "130")
    assert ok is False, "a genuine leak in the merge-ref shape must still red"
    assert leaked, "the foreign commit must be named"
    assert "other PR's work" in " ".join(leaked)
    assert foreign[:7] in " ".join(leaked)
    text = "\n".join(cpb.render(False, cpb.DEFAULT_BASE, "HEAD", leaked, work, "pr/mine", "130"))
    assert "STALE" not in text, text
    assert "carries commits from another PR" in text, text

