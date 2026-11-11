#!/usr/bin/env python3
"""Assert a skill reference's code citations and symbols resolve (issue #1924).

A skill reference exists to spare a lane re-deriving a diagnosis, so a sentence that cites a test
to prove it ("tests/test_x.py::test_y", issue #745's `proven:` family) must not outlive that test's
rename or deletion: a doc that describes a test that no longer runs is worse than no doc, because
the next lane reads the stale anchor and concludes something true that is not. The same holds for a
backticked code symbol that names a file in this repository — it must resolve, or the sentence cites
nothing.

  check_skill_code_parity.py check    exit 1 on any unresolvable citation/symbol
  check_skill_code_parity.py report   print what was read and the verdict (always exit 0)

Scope decisions (the tree is the gate's subject, so it must be green on the current tree):

- Only `agents/*/skills/**/*.md` are read: those are the skill references. `agents/standing-rules.md`
  and the SOUL files are not a skill's references, and `scripts/` prose is not this gate's subject.
- A citation inside a fenced code block (```` ``` ````) is a quoted log or command sample, not a
  claim the reference makes; it is not checked. The stale `test_changes_index.py::test_the_real_...
  _renders_the_committed_changes_md` in gate-auditing.md is exactly this shape — a `ci-unit` failure
  log, quoted, where the test was later renamed. A gate that reds a quoted paste teaches nobody.
- `tests/test_x.py::test_name` is the generic template (merged-over-red-gate.md), not a real anchor.
  The whole `test_x.py` filename is the template family (`::test_y` is the same shape), so a bare
  `tests/test_x.py` symbol is skipped too.
- `agents/llgenie-planner/skills/.archive/**` are FROZEN fold snapshots (issue #2262): byte-identical
  copies of the live profile's archived skills, kept immutable so a rebuild cannot downgrade the
  lane. Their citations are historical — rewriting them would break the byte-identical fold parity
  the fold proves with `cmp`. Same exclusion as `check_proc_gate.py` and `module_name_guard.py`.
- `EXTERNAL_SKILL_MIRRORS` are the tree copies of UPSTREAM Hermes-agent skill docs (folded live→tree
  byte-identically, issue #2262 fold parity). Their `tests/...` / `scripts/...` tokens name files in
  the Hermes-agent repository, not this one, so they are environment, not claims this repo owns —
  exactly the external-token rule above, applied at the whole-file level because every code citation
  in them belongs to the other repository.
- A trailing `...` in a test id is abbreviation ("test_the_fleet_splice_is_idempotent..."), resolved
  by prefix: at least one collected test in that file starts with the given name.
- A backticked symbol resolves only when it names a repository-owned file (`scripts/`, `tests/`,
  `agents/`, or a bare `.py`/`.py::sym` that exists in the repo). External or vendored tokens
  (`vllm/…`, a Hermes tool path, a shell tool name) are environment, not this repo, and are skipped.
- A test citation must also be COLLECTED by the hermetic suite (`scripts/unit_tests.py`), not merely
  present on disk: a test the roster excludes does not run, so it cannot "pass" for the citation.

Stdlib only, like `scripts/check_issue_body.py` — `make ci-unit` runs it on a bare host.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

#: The tree surface this gate reads: every markdown file inside a skill directory.
SKILL_MD_GLOB = "agents/*/skills/**/*.md"
#: A test citation: `tests/<file>.py::<_test_id>` with an optional trailing `...` abbreviation.
TEST_CITATION_RE = re.compile(r"`?tests/([A-Za-z0-9_./-]+\.py)::([A-Za-z0-9_]+)(\.+)?`?")
#: A backticked code symbol: a `*.py` file, optionally with a `::symbol` anchor.
SYMBOL_RE = re.compile(r"`([A-Za-z0-9_./-]+\.py(?:::[A-Za-z0-9_]+)?)`")
#: The generic template id, never a real anchor.
TEMPLATE = ("test_x.py", "test_name")
#: FROZEN fold snapshots (issue #2262): immutable byte-identical archived-skill copies; their
#: citations are historical and rewriting them would break the fold's `cmp` parity.
ARCHIVE_SNAPSHOT = "agents/llgenie-planner/skills/.archive/"
#: Tree copies of UPSTREAM Hermes-agent skill docs: their code tokens name Hermes-repo files, so
#: nothing inside them is a claim THIS repo owns (issue #2262 fold, same rule as external tokens).
EXTERNAL_SKILL_MIRRORS = (
    "agents/llgenie-planner/skills/autonomous-ai-agents/hermes-agent/",
    "agents/llgenie-planner/skills/software-development/hermes-agent-skill-authoring/",
)
#: Root-owned namespace prefixes whose filename must resolve in the repo.
REPO_PREFIXES = ("scripts/", "tests/", "agents/", "data/", "openspec/", "docs/", "Makefile")


def _iter_skill_md(root: Path):
    for path in root.glob(SKILL_MD_GLOB):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(ARCHIVE_SNAPSHOT) or any(rel.startswith(m) for m in EXTERNAL_SKILL_MIRRORS):
            continue  # frozen fold snapshot / external Hermes mirror (see module docstring)
        yield path


def _strip_fences(text: str) -> str:
    """Remove fenced ``` blocks — quoted logs/commands are not claims (see module docstring)."""
    return re.sub(r"^```.*?^```", "", text, flags=re.M | re.S)


def _collected_tests(root: Path) -> set[str]:
    """The hermetic suite's collected node ids (`tests/<file>.py`), via unit_tests.py."""
    out = subprocess.run([sys.executable, str(root / "scripts/unit_tests.py"), "list"],  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                         capture_output=True, text=True, cwd=root)
    return {ln.strip() for ln in out.stdout.splitlines() if ln.strip()}


def _file_node_ids(root: Path, file: str) -> set[str]:
    """All module-level function ids defined in a test file, plus class-qualified forms.

    A citation is not required to be a `test_` forwarder: `tests/test_hf_auth.py::_short_hub_
    process_limits` names the module-level helper that the sentence is about, and it must still
    exist. Any top-level `def` resolves a `::name` citation.
    """
    path = root / "tests" / file
    if not path.is_file():
        return set()
    text = path.read_text(errors="replace")
    ids = set(re.findall(r"^def\s+([A-Za-z0-9_]+)\s*\(", text, re.M))
    for cls, func in re.findall(r"^class\s+([A-Za-z0-9_]+)[\s\S]*?^    def\s+([A-Za-z0-9_]+)\s*\(",
                                text, re.M):
        ids.add(f"{cls}::{func}")
        ids.add(func)
    return ids


def _repo_walk(root: Path, name: str) -> Path | None:
    """Find a file by basename anywhere a repo-owned script can live: root, scripts/, tests/,
    and the profiles' helper dirs (`agents/<profile>/scripts/` and the nested
    `agents/<profile>/skills/<skill>/scripts/` — the lanes keep helper scripts beside their
    skills). The index is built ONCE per ROOT (the gate scans every symbol in 300+ references, and
    a per-symbol glob over the agents tree would iterate it hundreds of times); the cache is keyed
    by root so several tmp-tree checks in one test process each resolve against their own tree."""
    cache = getattr(_repo_walk, "_caches", None)
    if cache is None:
        cache = _repo_walk._caches = {}
    if root not in cache:
        cache[root] = {
            c.name: c for c in root.rglob("*") if c.is_file() and c.suffix == ".py"
            and ("scripts" in c.parts or "tests" in c.parts)
        }
    return cache[root].get(name)


def check(root: Path = REPO) -> list[str]:
    """Findings, one per unresolvable citation or symbol (empty = the tree is honest)."""
    findings: list[str] = []
    collected = _collected_tests(root)
    for path in _iter_skill_md(root):
        rel = str(path.relative_to(root))
        text = _strip_fences(path.read_text(errors="replace"))
        for fname, tid, ellipsis in TEST_CITATION_RE.findall(text):
            if fname == TEMPLATE[0]:
                continue  # the whole `test_x.py` template family is not an anchor
            tfile = f"tests/{fname}"
            if tfile not in collected:
                findings.append(f"{rel}: `{tfile}::{tid}` is not in the hermetic suite — a test "
                                f"that does not run cannot prove the sentence")
                continue
            ids = _file_node_ids(root, fname)
            if ellipsis:
                if not any(i.startswith(tid) for i in ids):
                    findings.append(f"{rel}: `{tfile}::{tid}...`'s prefix matches no test in "
                                    f"`{tfile}`")
            elif tid not in ids:
                findings.append(f"{rel}: `{tfile}::{tid}` is not a test in `{tfile}` — it was "
                                f"renamed or removed, and the sentence has no living proof")
        for sym in SYMBOL_RE.findall(text):
            filepart = sym.split("::", 1)[0]
            anchor = sym.split("::", 1)[1] if "::" in sym else None
            if filepart.split("/")[-1] == TEMPLATE[0]:
                continue  # a bare `test_x.py` template filename is not an anchor either
            if not _is_repo_symbol(filepart):
                continue  # external/vendored/tool token (vllm/, a Hermes tool, a shell tool) — not a claim this repo owns
            resolved, reason = _resolve_symbol(root, filepart, anchor)
            if not resolved:
                findings.append(f"{rel}: backticked symbol `{sym}` does not resolve ({reason})")
    return findings


def _is_repo_symbol(filepart: str) -> bool:
    """Is this a token this repository owns, i.e. MUST resolve? (external tools/vendors: no)."""
    if any(filepart.startswith(p) for p in REPO_PREFIXES):
        return True
    if not filepart.endswith(".py"):
        return False
    # A bare `foo.py`: owned iff a repo file with that basename exists somewhere repo-owned.
    return _repo_walk(REPO, filepart.split("/")[-1]) is not None


def _resolve_symbol(root: Path, filepart: str, anchor: str | None):
    """(resolved, reason). File must exist; `::symbol` must be defined (ast/grep)."""
    exists = _repo_walk(root, filepart.split("/")[-1])
    if exists is None:
        if filepart.startswith("scripts/"):
            # A `scripts/<name>` token may be a Makefile target's script referred to by its
            # conceptual name — only resolve where a real file backs it.
            return False, f"no repo file `{filepart}`"
        return False, f"no repo file `{filepart}`"
    if anchor is None:
        return True, "file present"
    text = exists.read_text(errors="replace")
    if anchor not in text:
        return False, f"`::{anchor}` not defined in `{filepart}`"
    return True, "symbol present"


def report(root: Path = REPO) -> int:
    refs = list(_iter_skill_md(root))
    findings = check(root)
    print(f"[skill-code-parity] {len(refs)} skill reference(s) scanned")
    print(f"[skill-code-parity] {len(findings)} finding(s)")
    for f in findings:
        print(f"  - {f}")
    if findings:
        return 1
    print("[skill-code-parity] OK: every cited test runs in the hermetic suite and every "
          "repository-owned backticked symbol resolves")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Skill references cite tests and symbols that exist "
                                             "(issue #1924)")
    ap.add_argument("cmd", choices=("check", "report"))
    ap.add_argument("--root", default=str(REPO))
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    return report(root) if args.cmd == "report" else (0 if not check(root) else 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
