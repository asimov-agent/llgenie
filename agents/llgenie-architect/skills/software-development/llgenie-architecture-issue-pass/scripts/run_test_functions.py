#!/usr/bin/env python3
"""Run test_*.py functions with a LIVE capsys stand-in, when pytest is unavailable or silent.

Usage (from the repo root, with a python that has the repo's test deps):

    python3 scripts/run_test_functions.py tests/test_ci_scope.py tests/test_ci_scope_trigger.py

Why this exists: a hand-rolled `capsys` that returns an empty buffer AFTER the call fails every test that
prints, and pytest installed but emitting nothing (exit 2, zero bytes) tells you nothing at all. This runs
the functions directly and reports `ran=N failed=M` plus each failure, so a red is attributable.

Two limits, both deliberate:
- functions taking `tmp_path`, `monkeypatch`, `capsys` or any other fixture are SKIPPED and named, never
  silently passed over — a skipped case is not a green case;
- it does not import conftest.py; if a test needs a repo fixture, run it under the real runner instead.
"""
from __future__ import annotations

import contextlib
import importlib
import inspect
import io
import sys
import types
from pathlib import Path


class LiveCapsys:
    """`capsys` stand-in whose buffer is readable DURING the call, so prints are captured."""

    def __enter__(self):
        self.buf = io.StringIO()
        self._ctx = contextlib.redirect_stdout(self.buf)
        self._ctx.__enter__()
        return self

    def __exit__(self, *exc):
        self._ctx.__exit__(*exc)
        return False

    def readouterr(self):
        return types.SimpleNamespace(out=self.buf.getvalue(), err="")


FIXTURE_NAMES = {"tmp_path", "monkeypatch", "capsys", "capfd", "request", "tmp_path_factory"}


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    root = Path.cwd()
    sys.path[:0] = [str(root / "tests"), str(root / "scripts")]

    ran = failed = 0
    skips: list[str] = []
    failures: list[tuple[str, str]] = []
    for target in argv:
        module = importlib.import_module(Path(target).stem)
        for name, fn in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("test_"):
                continue
            params = list(inspect.signature(fn).parameters)
            if params and set(params) & FIXTURE_NAMES:
                skips.append(f"{module.__name__}::{name}")
                continue
            try:
                if params:
                    with LiveCapsys() as cap:
                        fn(cap)
                else:
                    with contextlib.redirect_stdout(io.StringIO()):
                        fn()
                ran += 1
            except Exception as exc:  # noqa: BLE001 — a failure is data here
                failed += 1
                failures.append((f"{module.__name__}::{name}", f"{type(exc).__name__}: {exc}"))

    print(f"ran={ran} failed={failed} skipped={len(skips)}")
    for name, err in failures:
        print(f"  FAIL {name}\n       {err}")
    for name in skips:
        print(f"  SKIP {name} (needs a fixture; run it under the real runner)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
