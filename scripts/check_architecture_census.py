#!/usr/bin/env python3
"""Gate the architecture census in `docs/ARCHITECTURE.md` against the tree (issues #896, #1053).

The document states a census of the tree ("The tree is N tracked files: data/ 9, skills/ 17, ...")
and two table cells with the `tests/test_*.py` count and the `openspec` change count, next to a
`measured at <sha>` pointer naming the commit it was counted on. A census is a claim about ONE
commit, so that commit — not `HEAD` — is the referent (issue #1053):

- the counts are read with `git ls-tree -r --name-only <sha>` at the sha the doc names, so a branch
  that adds a file does not have to rewrite the doc (and a pointer naming its own branch head no
  longer dangles once the PR is squashed);
- the pointer must be a real commit AND an ancestor of `HEAD`, so the census is reproducible from a
  tree this branch actually contains (the surviving half of #1043);
- a doc whose numbers disagree with the tree at that sha still fails, naming the claim it could not
  find, on `main` and in a PR alike.

Usage:
    python3 scripts/check_architecture_census.py check     # exit 0 = OK, 1 = census defect, 2 = unreadable
    python3 scripts/check_architecture_census.py report    # print the census, exit 0 always

Exit codes for `check` are part of the contract (issue #1141): 0 = the census matches the tree at
the `measured at <sha>` pointer, 1 = the document is wrong (a stale number, an absent pointer, or a
pointer to a sha that is not a real commit an ancestor of HEAD), and 2 = git could not read THIS
checkout **or** the pointer object is merely unfetched — no repository, a `.git` file pointing at an
unmounted bare repo, dubious ownership, no git binary (issue #1141), or a shallow/filtered checkout
that does not hold the pointer object (issue #1686). In both exit-2 cases the census was NOT checked,
and the caller should fix the checkout (fetch/unshallow), not the document. Only when the pointer is
provably absent from `origin/main` (not just missing locally) does the gate red as a doc defect.

Stdlib only; runs in the repo checkout (`HEAD` = the working tree's commit). Wired into `check-docs`
via the Makefile.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=REPO_ROOT)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)


def _ls_names(path: str = "", ref: str = "HEAD") -> list[str]:
    cmd = ["ls-tree", "-r", "--name-only", ref]
    if path:
        cmd += ["--", path]
    return [l for l in _git(*cmd).stdout.split("\n") if l]


# A `scripts/*.py` or `scripts/*.sh` module name as it appears in prose: a bare basename
# (`engine_matrix_pushed.py`) or a `scripts/`-prefixed path (`scripts/foo.py`). The §Scripts table
# and the BOTS.md sentence name modules by basename, so the referent check reads those names out of
# the prose and resolves them against `git ls-tree -r --name-only <sha> -- scripts/`.
# A script whose BASENAME is hyphenated (`fold-live-profile.py`) is resolved by `_scripts_coverage_names`,
# which additionally recognises `scripts/`-prefixed paths (issue #2015).
_SCRIPTS_MODULE_RE = re.compile(r"(?<![\w./])([\w]+\.(?:py|sh))(?![\w])")


def _scripts_section(text: str) -> str:
    """The §Scripts table section of ARCHITECTURE.md (between `## Scripts` and the next `## `)."""
    start = text.find("## Scripts")
    if start == -1:
        return ""
    rest = text[start + len("## Scripts"):]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _bots_push_fact_paragraph(text: str) -> str:
    """The BOTS.md paragraph that states the push-fact mechanism (the one naming the dead module)."""
    for para in text.split("\n\n"):
        if ("engine_matrix_pushed" in para or "pushed an\nimage" in para
                or "install-published" in para and "pushed" in para):
            return para
    return ""


def _scripts_mentions(*docs: str) -> list[str]:
    """Every `scripts/*.py`/`.sh` basename the §Scripts table and the BOTS push-fact sentence name."""
    seen: list[str] = []
    for text in docs:
        for m in _SCRIPTS_MODULE_RE.finditer(text):
            name = m.group(1)
            if name not in seen:
                seen.append(name)
    return seen


def _scripts_tree_names(ref: str) -> set[str]:
    """The set of `scripts/*.py`/`.sh` basenames tracked at `ref`."""
    return {n.rsplit("/", 1)[-1] for n in _ls_names("scripts", ref)
            if n.rsplit("/", 1)[-1].endswith((".py", ".sh"))}


def _referent_problems(ref: str) -> list[str]:
    """Named §Scripts/BOTS modules that do not exist at `ref` (subset check: named ⊆ tree).

    The §Scripts half is read with the hyphen-aware `_scripts_coverage_names` (NOT the `\\w`-only
    `_SCRIPTS_MODULE_RE`): the table now rows `fold-live-profile.py`, and the plain regex would
    capture a phantom `profile.py` out of it. The BOTS push-fact sentence has no hyphenated module,
    so it keeps the plain spelling (issue #2015).
    """
    arch = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    bots_path = REPO_ROOT / "docs" / "BOTS.md"
    bots = bots_path.read_text(encoding="utf-8") if bots_path.exists() else ""
    tree = _scripts_tree_names(ref)
    section_names = _scripts_coverage_names(_scripts_section(arch))
    bots_names = _scripts_mentions(_bots_push_fact_paragraph(bots))
    return [name for name in (section_names | set(bots_names)) if name not in tree]


# Modules a §Scripts group row is not expected to name, with the reason each is exempt.
# `__init__.py` is the package marker the §Scripts opening line states but never rows; it is its
# own spelling by construction and the reverse check must not chase it. A module added here needs a
# dated reason in this comment — an exemption is a decision, not a hole (issue #2015).
_SCRIPTS_MAP_EXEMPT: set[str] = {"__init__.py"}


def _scripts_coverage_names(section: str) -> set[str]:
    """The set of `scripts/*.py|.sh` names the §Scripts section names, in any spelling it uses.

    The table rows name modules as backticked basenames; the opening line and the two trailing
    paragraphs name `scripts/`-prefixed paths (`scripts/__init__.py`, `scripts/tools/llgenie_harness.py`,
    `scripts/module_name_guard.py`) and a hyphenated basename (`fold-live-profile.py`) that the plain
    `\\w`-only `_SCRIPTS_MODULE_RE` cannot see. The coverage direction must recognise every spelling
    the map uses or the reverse check chases phantom gaps (issue #2015). Three passes:
    - `scripts/…/name.ext` paths → basename (a `scripts/` prefix is the map's own path spelling);
    - backticked bare basenames (`` `name.py` ``) and comma/pipe-delimited one-word basenames;
    - a `-`-tolerant basename scan so `fold-live-profile.py` is captured whole, never as `profile.py`.
    """
    names = {
        m.group(1) for m in _SCRIPTS_PATH_RE.finditer(section)
    } | {
        m.group(1) for m in _SCRIPTS_BASENAME_RE.finditer(section)
    }
    return names


# `scripts/`-prefixed path spellings: take the leaf basename of a `scripts/…/name.py|.sh` token.
_SCRIPTS_PATH_RE = re.compile(r"scripts/[\w./-]*?/([\w-]+\.(?:py|sh))")
# A bare one-word basename that may carry a hyphen (`fold-live-profile.py`); the lookbehind refuses a
# preceding `[\w-]` so the hyphenated name is captured whole and `profile.py` is not stolen from it.
_SCRIPTS_BASENAME_RE = re.compile(r"(?<![\w-])([\w-]+\.(?:py|sh))(?![-\w])")


def _coverage_problems(ref: str) -> list[str]:
    """Every tracked `scripts/*.py|.sh` at `ref` that the §Scripts section does not name (issue #2015).

    The reverse of `_referent_problems`: a module that joins `scripts/` without a row in the §Scripts
    group table is invisible to the map a reviewer reads, and the census never noticed. That module
    is the defect — `tree ⊆ named-in-doc`, except the documented `_SCRIPTS_MAP_EXEMPT` set.
    """
    arch = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    section = _scripts_section(arch)
    if not section:
        # No §Scripts section, no map to hold the tree to — the reverse direction is vacuous
        # (matches the forward check, which also reads an empty section as naming nothing).
        return []
    named = _scripts_coverage_names(section)
    tree = _scripts_tree_names(ref)
    return sorted(name for name in (tree - named - _SCRIPTS_MAP_EXEMPT))


def measure(ref: str = "HEAD") -> dict[str, int]:
    """Count the census of the tree AT `ref` (never implicitly the working tree's HEAD)."""
    tracked = _ls_names(ref=ref)
    tests_names = _ls_names("tests", ref)
    changes = {l.split("/")[2] for l in _ls_names("openspec/changes", ref)}
    return {
        "tracked": len(tracked),
        "data": len(_ls_names("data", ref)),
        "skills": len(_ls_names("skills", ref)),
        "containers": len(_ls_names("containers", ref)),
        "tests": len(tests_names),
        "scripts": len(_ls_names("scripts", ref)),
        "openspec": len(_ls_names("openspec", ref)),
        "agent-wiki": len(_ls_names("agent-wiki", ref)),
        "docs": len(_ls_names("docs", ref)),
        "test_py": len([n for n in tests_names if n.rsplit("/", 1)[-1].startswith("test_") and n.endswith(".py")]),
        "openspec-changes": len(changes),
    }


def doc_flat() -> str:
    """Collapse whitespace/newlines so the wrapped census sentence matches one regex."""
    doc = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", doc)


# How the document spells each counted claim's NUMBER, so a failure can name both values.
CLAIM_SPELLINGS = {
    "tracked": r"The tree is (\d+) tracked files",
    "openspec-changes": r"\((\d+) changes\)",
    "agent-wiki-entries": r"\((\d+) entries\)",
    "test_py": r"(\d+) `tests/test_\*\.py`",
}


def doc_stated(label: str, text: str) -> int | None:
    """The number the document itself states for `label`, or None when it states none."""
    pattern = CLAIM_SPELLINGS.get(label, rf"`{label}/` (\d+)")
    found = re.search(pattern, text)
    return int(found.group(1)) if found else None


def claims(m: dict[str, int]) -> list[tuple[str, str]]:
    """The census tokens the document must state, rendered from a measured census `m`."""
    return [
        ("tracked", f"The tree is {m['tracked']} tracked files"),
        ("data", f"`data/` {m['data']}"),
        ("skills", f"`skills/` {m['skills']}"),
        ("containers", f"`containers/` {m['containers']}"),
        ("tests", f"`tests/` {m['tests']}"),
        ("scripts", f"`scripts/` {m['scripts']}"),
        ("openspec", f"`openspec/` {m['openspec']}"),
        ("agent-wiki", f"`agent-wiki/` {m['agent-wiki']}"),
        ("docs", f"`docs/` {m['docs']}"),
        ("openspec-changes", f"({m['openspec-changes']} changes)"),
        ("agent-wiki-entries", f"({m['agent-wiki']} entries)"),
        ("test_py", f"{m['test_py']} `tests/test_*.py`"),
    ]


def short_sha(ref: str = "HEAD") -> str:
    return _git("rev-parse", "--short", ref).stdout.strip()


def doc_measured_sha() -> str | None:
    """The `measured at <sha>` pointer the document states next to its census."""
    m = re.search(r"measured at `([0-9a-f]{7,})`", doc_flat())
    return m.group(1) if m else None


def git_unreadable() -> bool:
    """True when git itself cannot read this checkout (the environment failed, not the document).

    The probe is the gate's own plumbing failing, never a guess at the document: a
    `git rev-parse --git-dir` that returns non-zero (no repository, a worktree whose
    `.git` file points at an unmounted bare repo, `dubious ownership`), returns nothing,
    or cannot even be invoked (git is not installed). In all those cases the census was
    NOT checked — the failure is a property of the checkout, and must not be rendered as
    if the document had named a bad commit.
    """
    try:
        probe = _git("rev-parse", "--git-dir")
    except FileNotFoundError:
        return True  # git is not installed
    return probe.returncode != 0 or not probe.stdout.strip()


def commit_is_real(sha: str) -> bool:
    """A real, non-dangling commit (not a sha from an amend that vanished)."""
    return _git("cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def commit_is_ancestor(sha: str, ref: str = "HEAD") -> bool:
    """The pointer names a commit this branch contains, so the census is reproducible from it."""
    return _git("merge-base", "--is-ancestor", sha, ref).returncode == 0


def checkout_is_shallow() -> bool:
    """True when this checkout was cloned shallow/filtered, so a far-back object may be unfetched.

    `git rev-parse --is-shallow-repository` prints `true` for a shallow clone. That is the cleanest
    signal the object-read failure is a property of the clone depth, not of the document (issue
    #1686). A `--filter` (blobless/treeless) clone reports `false` here but still omits history
    objects; the `origin/main` reachability probe in `pointer_is_unfetched` covers that case too.
    """
    probe = _git("rev-parse", "--is-shallow-repository")
    return probe.returncode == 0 and probe.stdout.strip() == "true"


def pointer_is_unfetched(sha: str) -> bool:
    """The pointer object is merely unfetched, not absent from the branch's history.

    A worktree cloned off a shallow primary (or a filtered clone) holds `HEAD`'s tip but not a
    far-back `measured at <sha>` object, so `cat-file -e <sha>^{commit}` and
    `merge-base --is-ancestor <sha>` both return non-zero WITHOUT the commit being bad. To tell that
    from a genuine dangling/foreign pin, probe object reachability from the remote-tracking refs:
    when the checkout is shallow, or `origin/main` still names the sha as an ancestor, the object is
    real but unfetched — the checkout is at fault, not the document. Only when the commit is provably
    absent from `origin/main` too (a full clone, no such ancestor) is it a doc defect.
    """
    if checkout_is_shallow():
        return True
    for ref in ("refs/remotes/origin/main", "refs/remotes/origin/HEAD"):
        if _git("merge-base", "--is-ancestor", sha, ref).returncode == 0:
            return True
    return False


def check() -> int:
    problems: list[str] = []
    stated = doc_measured_sha()
    measured: dict[str, int] | None = None
    if git_unreadable():
        print("[census-gate] UNREADABLE: git could not read this checkout — the census was NOT "
              "checked (run this from a full clone or mount the whole repository)")
        return 2
    if stated is None:
        problems.append("measured-at: docs/ARCHITECTURE.md states no `measured at <sha>` pointer; it must "
                        "name the commit its census was counted on")
    elif not commit_is_real(stated) or not commit_is_ancestor(stated):
        if pointer_is_unfetched(stated):
            print("[census-gate] CHECKOUT-DEPTH: the doc's pointer `" + stated + "` is a real commit "
                  "on origin but THIS checkout is shallow/filtered and does not hold the object — the "
                  "census was NOT checked (fetch the pointer object / unshallow; the document is not "
                  "at fault)")
            return 2
        problems.append(f"measured-at: the doc's pointer `{stated}` is not a real commit" if not commit_is_real(stated)
                        else f"measured-at: the doc's pointer `{stated}` is not an ancestor of HEAD "
                             f"({short_sha()}); the census must name a commit this branch contains")
    else:
        measured = measure(stated)
        text = doc_flat()
        for label, token in claims(measured):
            if token in text:
                continue
            stated_number = doc_stated(label, text)
            doc_value = (f"the doc states {stated_number}" if stated_number is not None
                         else "the doc states no such claim")
            problems.append(f"{label}: {doc_value} but the tree at `{stated}` states {token}")
        for name in _referent_problems(stated):
            problems.append(f"referent-membership: §Scripts/BOTS names `scripts/{name}` but the "
                            f"tree at `{stated}` does not contain it — the module was removed; "
                            f"correct the prose or restore the file")
        for name in _coverage_problems(stated):
            problems.append(f"scripts-map-coverage: `scripts/{name}` exists at `{stated}` but the "
                            f"§Scripts group table does not name it — the tree is no longer fully "
                            f"mapped; add it to its group row")

    for problem in problems:
        print(f"[census-gate] {problem}")

    m = measured if measured is not None else measure()
    verdict = ("OK" if not problems else
               f"{len(problems)} claim(s) stale" if measured is not None else
               "the census has no usable referent")
    referent = (f"referent `{stated}` is an ancestor of HEAD ({short_sha()})" if measured is not None
                else f"no usable referent; HEAD is {short_sha()}")
    print(f"[census-gate] {verdict} — census measured at `{stated or 'nowhere'}` (tracked={m['tracked']}, "
          f"testspp={m['test_py']}, changes={m['openspec-changes']}); {referent}")
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="gate the ARCHITECTURE census (issues #896, #1053)")
    ap.add_argument("cmd", choices=("check", "report"))
    args = ap.parse_args()
    if args.cmd == "report":
        m = measure()
        print(f"measured at {short_sha()}: " + ", ".join(f"{k}={v}" for k, v in m.items()))
        print(f"doc pointer: {doc_measured_sha() or '(none)'}")
        return 0
    return check()


if __name__ == "__main__":
    sys.exit(main())
