"""A documentation review of an engine's derived build params, before the bump PR opens (issue #583).

`make engine-bump` proves the derived params **build**. It cannot prove they are **right for this
engine version and this arch**: the derive extractors are structural (CMake options, renames, recipe
`-D` flags, toolchain pins), so a flag the upstream's own docs now recommend — but which is missing from
the old params — is at best report-only and usually invisible.

This module is the deterministic half of the review leg. Hermes reads `params-review-in.md` (the engine's
docs at the pinned sha, its current params, the derive's findings) and writes `params-review.md` with
`PROPOSE` lines; this module then decides what may be written:

  * **the deterministic core stays the writer.** The agent cannot invent a flag: a proposal is applied
    only when the flag AND its quoted evidence both appear, verbatim, in the named upstream file at the
    pinned sha. Anything else is dropped and reported, never applied.
  * the engine's own `SKILL.md` is where the flag lands (its `cmake_flags.<backend>` string), because
    that is the only writer of params/Dockerfiles (`make generate-engine-params`).

`brief` writes the input, `apply` validates and writes, `--dry` prints the decision and mutates nothing.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine_skills as es  # noqa: E402  (the one reader of a skill's front matter)

#: A proposal line, as the skill tells the agent to write it:
#:   PROPOSE <backend> <flag> DOC <repo-relative path> "<quote from that file>" WHY <reason>
PROPOSE = re.compile(
    r'^PROPOSE\s+(?P<backend>[A-Za-z0-9_-]+)\s+(?P<flag>-D[A-Za-z0-9_]+(?:=[^\s]+)?)\s+'
    r'DOC\s+(?P<doc>\S+)\s+"(?P<quote>[^"]+)"\s+WHY\s+(?P<why>.+)$')

#: How many bytes of one upstream file to carry into the brief.
DOC_BUDGET = 20_000

#: The TOTAL the brief may carry (issue #597). `brief` used to be bounded per file only, so an engine
#: with a big doc tree produced 1.8 MB (214 files, 424 sections) of which the largest were benchmark
#: result pages — an input the leg could not use. Selected highest-build-relevance first, until this.
DOC_TOTAL_BUDGET = 80_000

#: A file that PROVES a flag is not cut at the per-file cap: `CMakeLists.txt` carries its `option(...)`
#: lines below 20 KB on real trees, and cutting them off is how the one authoritative file became the
#: least useful one in the 1.8 MB brief (issue #597).
ALWAYS_BUDGET = 60_000

#: How much of the brief the flag-proving files may take TOGETHER. Their per-file cap alone let six
#: Dockerfiles/CMakeLists consume every byte and leave no room for the documentation that explains the
#: arch (issue #597, measured on strata).
ALWAYS_TOTAL_BUDGET = 45_000

#: Files whose content is build evidence, ranked ahead of everything else.
ALWAYS_INCLUDE = re.compile(r"(^|/)(CMakeLists\.txt|Dockerfile[^/]*)$")

#: Trees that are documentation only by accident of a glob: benchmark logs, examples, fixtures.
NOISE_PREFIXES = ("bench/", "benchmarks/", "examples/", "tests/", "fixtures/", "assets/", "apps/")

#: What makes a document worth the model's context: the vocabulary of building this engine.
BUILD_SIGNALS = ("option(", "-D", "CMAKE_", "CUDA_ARCHITECTURES", "GPU_TARGETS", "cmake", "cuda",
                 "rocm", "hip", "torch", "requires-python", "pip install", "apt-get", "build",
                 "install", "compile")


def _score(text: str) -> int:
    """How much this file looks like build documentation. Counts signal occurrences, capped."""
    low = text.lower()
    return min(sum(low.count(s.lower()) for s in BUILD_SIGNALS), 400)


def _is_noise(path: str) -> bool:
    return path.startswith(NOISE_PREFIXES)

#: The files whose content a proposal may cite: the engine's docs and its backend recipes. A quote that
#: is not in one of these is not documentation.
#: `Path.match` does not let `**` cross zero directories, so `docs/*.md` is listed EXPLICITLY: without
#: it a `docs/BUILDING.md` — the page that documents the flags — was invisible to the brief (issue #597).
DOC_GLOBS = ("README.md", "README.rst", "docs/*.md", "docs/*.rst", "docs/**/*.md", "docs/**/*.rst",
             "CMakeLists.txt", "docker/**/Dockerfile*", "Dockerfile*", ".github/**/*.md")


def _show(repo_dir: Path, sha: str, path: str) -> str:
    """One file's content at `sha`, from a blobless clone. Empty when the path is absent."""
    r = subprocess.run(["git", "-C", str(repo_dir), "show", f"{sha}:{path}"],  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def _clone(skill: dict) -> Path:
    """A `--filter=blob:none --no-checkout` clone of the engine's repo (same shape the derive uses)."""
    url = skill["repo"].rstrip("/")
    if "://" in url or url.startswith("git@"):
        url += ".git"
    dest = Path(tempfile.mkdtemp(prefix="llgenie-review-"))
    subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", url, str(dest)],  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                   capture_output=True, text=True, timeout=300, check=True)
    return dest


def _docs(repo_dir: Path, sha: str) -> tuple[dict[str, str], int]:
    """({path: text}, omitted) for the engine's docs at `sha`, ranked and bounded (issue #597).

    Build evidence first — the root `CMakeLists.txt` and the backend Dockerfiles always qualify, then
    whatever scores highest on the vocabulary of building this engine — until `DOC_TOTAL_BUDGET`. The
    count of files the budget left out is returned so the brief can say the input is a selection.
    """
    listing = subprocess.run(["git", "-C", str(repo_dir), "ls-tree", "-r", "--name-only", sha],  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                             capture_output=True, text=True)
    paths = [p for p in listing.stdout.splitlines() if p.strip()]
    matched = []
    for raw in paths:
        path = Path(raw)
        if not any(path.match(glob) or str(path) == glob for glob in DOC_GLOBS):
            continue
        # The noise filter wins over the always-include rule: a Dockerfile inside a benchmark result
        # directory is a bench artefact, not this engine's build evidence (issue #597).
        if _is_noise(raw):
            continue
        matched.append(raw)

    ranked: list[tuple[bool, int, str, str]] = []
    for raw in matched:
        text = _show(repo_dir, sha, raw)
        if text:
            ranked.append((bool(ALWAYS_INCLUDE.search(raw)), _score(text), raw, text))
    # Build evidence first, and within it the ROOT files (the repository's own CMakeLists/Dockerfile)
    # before a nested one; then the highest score, then a stable path order.
    def _root_evidence(row) -> int:
        return 0 if row[0] and "/" not in row[2] else 1

    ranked.sort(key=lambda row: (not row[0], _root_evidence(row), -row[1], row[2]))

    out: dict[str, str] = {}
    total = 0
    omitted = 0
    # Phase 1: the files that PROVE a flag, within their own share of the budget — they may be cut at
    # ALWAYS_BUDGET, but they may not eat the whole brief and starve the prose that explains the arch.
    for always, _score_value, raw, text in ranked:
        if not always:
            continue
        body = text[:ALWAYS_BUDGET]
        if total + len(body) > ALWAYS_TOTAL_BUDGET:
            omitted += 1
            continue
        out[raw] = body
        total += len(body)
    # Phase 2: everything else, highest build-relevance first, until the total budget is spent.
    for always, _score_value, raw, text in ranked:
        if always:
            continue
        body = text[:DOC_BUDGET]
        if total + len(body) > DOC_TOTAL_BUDGET:
            omitted += 1
            continue
        out[raw] = body
        total += len(body)
    return out, omitted


def _params(skill: dict) -> dict:
    """The engine's current build parameters, per backend, as the skill writes them."""
    return {"cmake_flags": skill.get("cmake_flags") or {},
            "hw_flags": skill.get("hw_flags") or {},
            "binary_flags": skill.get("binary_flags") or []}


def brief(engine: str, out: Path | None = None) -> Path:
    """Write `params-review-in.md`: the engine's docs at its pin, its params, and what to answer."""
    skill = es.get_skill(engine)
    sha = skill["pinned"]
    repo_dir = _clone(skill)
    docs, omitted = _docs(repo_dir, sha)
    out = out or Path("params-review-in.md")
    lines = [
        f"# Build-parameter documentation review — {skill['id']} @ {sha[:8]}",
        "",
        f"Pinned upstream: {skill['repo']} @ `{sha}`. Review the parameters THIS repo builds with",
        "against what the engine's own documentation says for each backend.",
        "",
        "## Current build parameters (from skills/engines/" f"{skill['id']}/SKILL.md)",
        "",
        "```yaml",
        *(f"{k}: {json.dumps(v)}" for k, v in _params(skill).items()),
        "```",
        "",
        "## Upstream documentation at this pin",
        "",
        (f"{len(docs)} file(s) selected by build relevance"
         + (f"; {omitted} omitted for the {DOC_TOTAL_BUDGET // 1000} KB budget" if omitted else "")
         + ". This is a SELECTION of the tree, not all of it."),
        "",
        *(f"### {path}\n\n```\n{text}\n```\n" for path, text in docs.items()),
        "## What to answer",
        "",
        "For every parameter the documentation requires (or recommends, or marks per-arch) that the",
        "current parameters do not carry, write ONE line per parameter:",
        "",
        '`PROPOSE <backend> <-DFLAG or -DFLAG=value> DOC <repo-relative path> "<quote from that file>" WHY <reason>`',
        "",
        "- the backend must be one of the engine's backends (`cuda`, `rocm`, `vulkan`, `cpu`, `metal`)",
        "  or `common`;",
        "- the flag must be exactly what the documentation uses (CMake `-D` form, `NAME=VALUE` when the",
        "  docs give a value);",
        "- the quote must be copied verbatim from the named file, because the host checks it and DROPS",
        "  any proposal whose quote or flag is not there;",
        "- if the documentation says nothing you can quote, write `NO REVIEW: <reason>` and propose",
        "  nothing. Reporting nothing is a correct answer; an uncited flag is not.",
        "",
    ]
    out.write_text("\n".join(lines))
    print(f"[params-review] {skill['id']}: {len(docs)} documentation file(s) at {sha[:8]} -> {out}")
    return out


def parse_proposals(text: str) -> list[dict]:
    """The agent's `PROPOSE` lines, in order. Malformed lines are ignored (and counted by the caller)."""
    out = []
    for line in (text or "").splitlines():
        m = PROPOSE.match(line.strip())
        if m:
            out.append(m.groupdict())
    return out


def _flags_in(value: str) -> set[str]:
    """The `-DNAME` tokens already present in one cmake_flags string."""
    return set(re.findall(r"-D[A-Za-z0-9_]+", value or ""))


def validate(proposals: list[dict], docs: dict[str, str], skill: dict) -> tuple[list[dict], list[str]]:
    """Split the proposals into (accepted, rejected-with-reason). Pure, so the rule is testable.

    A proposal is accepted ONLY when its flag and its quoted evidence both appear in the named
    upstream file, and the backend is one this engine builds. Everything else is dropped and said out
    loud — an uncited flag is exactly what this leg exists to refuse.
    """
    accepted: list[dict] = []
    rejected: list[str] = []
    backends = list(skill.get("backends") or []) + ["common"]
    for p in proposals:
        backend, flag, doc, quote = p["backend"], p["flag"], p["doc"], p["quote"]
        if backend not in backends:
            rejected.append(f"{backend} {flag}: `{backend}` is not one of this engine's backends "
                            f"({', '.join(backends)})")
            continue
        if doc not in docs:
            rejected.append(f"{backend} {flag}: no upstream file `{doc}` at this pin")
            continue
        text = docs[doc]
        # A CMake flag is `-DNAME=value`; the upstream file names it `NAME` (option(...)/set(...)),
        # so the DOCUMENTED test is on NAME, and the "already present" test is on the full `-DNAME`.
        bare = flag.split("=", 1)[0].removeprefix("-D")
        if not bare or bare not in text:
            rejected.append(f"{backend} {flag}: `{bare}` does not appear in `{doc}`")
            continue
        if " ".join(quote.split()) not in " ".join(text.split()):
            rejected.append(f"{backend} {flag}: the quoted evidence is not in `{doc}`")
            continue
        current = (skill.get("cmake_flags") or {}).get(backend) or \
                  ((skill.get("cmake_flags") or {}).get("common") or "" if backend != "common" else "")
        if f"-D{bare}" in _flags_in(current):
            rejected.append(f"{backend} {flag}: already in the params for `{backend}`")
            continue
        accepted.append(p)
    return accepted, rejected


def apply_accepted(engine: str, accepted: list[dict], dry: bool = False) -> list[str]:
    """Append the accepted flags to the skill's `cmake_flags.<backend>`. The skill is the writer."""
    path = es.SKILLS_DIR / engine / "SKILL.md"
    text = path.read_text()
    changed: list[str] = []
    for p in accepted:
        backend, flag = p["backend"], p["flag"]
        # The frontmatter line for this backend: `  <backend>: "-DA=ON -DB=ON"` under cmake_flags.
        block = re.search(r"(?ms)^cmake_flags:\n(?P<body>(?:[ \t]+.*\n)+)", text)
        if not block:
            raise SystemExit(f"[params-review] {engine}: SKILL.md has no cmake_flags block to extend")
        line = re.search(rf'(?m)^(?P<ind>[ \t]+){re.escape(backend)}:[ \t]*(?P<val>"[^"]*"|[^\n]*)\n',
                         block.group("body"))
        if not line:
            raise SystemExit(f"[params-review] {engine}: cmake_flags has no `{backend}` line; "
                             f"refusing to invent one")
        old_val = line.group("val").strip()
        quoted = len(old_val) >= 2 and old_val[0] == '"' and old_val[-1] == '"'
        inner = old_val[1:-1] if quoted else old_val
        # The skill writes these strings quoted (a value may contain spaces); keep the shape.
        new_val = f'"{(inner + " " + flag).strip()}"' if quoted else (inner + " " + flag).strip()
        text = text.replace(line.group(0), f"{line.group('ind')}{backend}: {new_val}\n", 1)
        changed.append(f"{backend} +{flag}")
    if changed and not dry:
        path.write_text(text)
    return changed


def section(engine: str, accepted: list[dict], rejected: list[str]) -> str:
    """The `Documentation review` section the bump PR carries."""
    lines = ["## Documentation review", ""]
    if not accepted and not rejected:
        lines += ["No documentation-sourced parameter was proposed for this pin: the derived params "
                  "stand as they are.", ""]
        return "\n".join(lines)
    if accepted:
        lines += [f"Applied from the engine's own documentation ({len(accepted)}):", ""]
        for p in accepted:
            lines.append(f"- `{p['backend']}` **{p['flag']}** — `{p['doc']}`: \"{p['quote'][:160]}\"")
        lines.append("")
    if rejected:
        lines += [f"Proposed but **not applied** ({len(rejected)}) — each was refused by the host "
                  "because the documentation does not support it:", ""]
        lines += [f"- {r}" for r in rejected]
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("command", choices=["brief", "apply"])
    ap.add_argument("--engine", required=True)
    ap.add_argument("--file", default="params-review.md", help="the agent's proposals")
    ap.add_argument("--section", default="params-review-section.md", help="where the PR section goes")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)

    if a.command == "brief":
        brief(a.engine)
        return 0

    skill = es.get_skill(a.engine)
    sha = skill["pinned"]
    repo_dir = _clone(skill)
    docs, _omitted = _docs(repo_dir, sha)
    text = Path(a.file).read_text() if Path(a.file).exists() else ""
    if not text.strip():
        print(f"[params-review] {a.engine}: the review leg wrote no {a.file}; nothing to apply")
        Path(a.section).write_text(section(a.engine, [], []))
        return 0
    proposals = parse_proposals(text)
    accepted, rejected = validate(proposals, docs, skill)
    changed = apply_accepted(a.engine, accepted, dry=a.dry) if accepted else []
    if changed and not a.dry:
        # The skill is the writer: regenerate the params and per-arch Dockerfiles from it.
        subprocess.run(["make", "generate-engine-params", f"ENGINE={a.engine}"],  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                       capture_output=True, text=True, timeout=300)
        print(f"[params-review] {a.engine}: regenerated params/Dockerfiles for {', '.join(changed)}")
    Path(a.section).write_text(section(a.engine, accepted, rejected))
    print(f"[params-review] {a.engine}: {len(accepted)} applied, {len(rejected)} rejected "
          f"({len(proposals)} proposal(s)); section -> {a.section}")
    for line in rejected:
        print(f"[params-review]   dropped: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
