"""The shared fake-gh field guard (issue #2975).

`scripts/check_gh_json_fields.py` (issue #515) validates `gh … --json` field
names statically at scan time. This is the runtime twin the proposal deferred:
every fake `gh` the bot tests stand up answers `--json` requests from a canned
blob without ever looking at the requested names, so a refactor that renames a
requested field passes the whole unit suite green while the real bot dies at
the call with `Unknown JSON field: "<name>"` (exit 1) — the #513 failure shape.

`enforce(argv)` reproduces that failure mode inside the harness: it attributes
the gh subcommand the same way the scanner does, validates the requested names
against `tests/fixtures/gh-json-fields.json`, and on violation prints gh's own
error line and exits 1. It fails CLOSED: a `--json` it cannot attribute to a
known subcommand, or whose names the fixture has no list for, is a refusal.

`preamble(tests_dir)` is the one-line install for the heredoc'd fake scripts
the bot tests write to disk: paste it right after the shebang and the fake
gates every `--json` request before it answers anything.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
FIXTURE = TESTS_DIR / "fixtures" / "gh-json-fields.json"

#: first-level gh subcommands whose `--json` has a documented field list
#: (the same roster `scripts/check_gh_json_fields.py` scans).
GH_SUBCOMMANDS = ("pr", "issue", "run")


def load_allowlists(fixture: Path = FIXTURE) -> dict[str, list[str]]:
    data = json.loads(Path(fixture).read_text())
    return {cmd: sorted(fields) for cmd, fields in data["commands"].items()}


def attribute(argv: list[str]) -> str | None:
    """The `<sub1> <sub2>` pair the argv names, mirroring the scanner's
    `_attr_subpair`: after an optional leading `gh` (or a path ending in
    `/gh`), the first token in `GH_SUBCOMMANDS`, then the first following
    non-flag token. None when no guarded subcommand appears at all — a
    `gh search`/`gh api` call is outside the guard's roster (the scanner
    only covers pr|issue|run, and real gh answers `search --json` fine)."""
    strings = [a for a in map(str, argv) if isinstance(a, str)]
    start = 0
    for i, tok in enumerate(strings):
        if tok == "gh" or tok.endswith("/gh"):
            start = i + 1
            break
    for i in range(start, min(start + 4, len(strings))):
        if strings[i] in GH_SUBCOMMANDS:
            sub1 = strings[i]
            for j in range(i + 1, min(i + 3, len(strings))):
                if not strings[j].startswith("--"):
                    return f"{sub1} {strings[j]}"
            return f"{sub1} "
    return None


def json_fields(argv: list[str]) -> list[str] | None:
    """The field names a `--json` argument requests (None when absent)."""
    for idx, tok in enumerate(map(str, argv)):
        if tok == "--json":
            if idx + 1 >= len(argv):
                return []
            return [f for f in str(argv[idx + 1]).split(",") if f]
        if tok.startswith("--json="):
            return [f for f in tok.split("=", 1)[1].split(",") if f]
    return None


def enforce(argv: list[str]) -> int:
    """Gate one fake-gh invocation. Exit 0 when no `--json` is asked, when the
    call names no guarded subcommand (the pr|issue|run roster), or when every
    requested name is on the fixture's list; fail CLOSED on a guarded
    subcommand whose pair the fixture has no list for; on a bad field print
    gh's own `Unknown JSON field: "<name>"` and exit 1."""
    fields = json_fields([str(a) for a in argv])
    if fields is None:
        return 0
    key = attribute([str(a) for a in argv])
    if key is None:
        return 0
    allow = load_allowlists()
    if key not in allow:
        print(
            f'gh_fake: no captured field list for --json request {list(map(str, argv))[:4]!r}',
            file=sys.stderr,
        )
        sys.exit(1)
    for name in fields:
        if name not in allow[key]:
            print(f'Unknown JSON field: "{name}"', file=sys.stderr)
            sys.exit(1)
    return 0


def preamble(tests_dir) -> str:
    """The one line an embedded fake-gh script runs before anything else."""
    return (
        "import sys as _gh_fake_sys; _gh_fake_sys.path.insert(0, "
        f"{str(Path(tests_dir))!r}); import gh_fake; gh_fake.enforce(_gh_fake_sys.argv[1:])"
    )


def module_path() -> str:
    """Absolute path of this module — what a bash fake calls to gate its argv."""
    return str(Path(__file__).resolve())


if __name__ == "__main__":
    sys.exit(enforce(sys.argv[1:]))
