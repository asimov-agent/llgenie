#!/usr/bin/env python3
"""Issue #2259 regression: a cell failure must not abort the engine-build sweep's later cells.

A params edit that changes an install line (but not the `pinned` field) retags every backend cell of
an engine. If the producer aborts on the first cell failure, the later cells keep their NEW hash with
NO image built — a committed tag that 404s on GHCR while cpu carries the new tag (measured: vllm cpu
`3a4d82f5-13c5a9c8` published, cuda `…-9be509b4` / rocm `…-5772a26a` absent for five days, #1682/#1684).

`engine_image.collect()` is the build-and-collect form: every cell is attempted, a success is built,
a failure is NAMED and does not stop the next cell, and the exit is 0 only when every cell succeeded.
"""
from __future__ import annotations

import scripts.engine_image as ei


# Snapshot the real engine_image callables once; every fake below restores them so a shared pytest
# session never leaks a monkeypatched build/matrix/resolve into a sibling test module.
_ORIG = {"build": ei.build, "matrix": ei.matrix, "resolve": ei.resolve}


def _fake_matrix(rows):
    ei.matrix = lambda ci=False, engine="", arch="", **k: rows


def _fake_build(rcs):
    """Return a `build` that consumes a (variant -> rc) map and records the attempts in order."""
    order = []
    def build(spec, force=False, push=False):
        order.append((spec["variant"], push))
        return rcs.get(spec["variant"], 0)
    ei.build = build
    return order


def _restore():
    ei.build, ei.matrix, ei.resolve = _ORIG["build"], _ORIG["matrix"], _ORIG["resolve"]


def _spec(engine, variant):
    return {"id": engine, "backend": variant, "variant": variant,
            "tag": f"llgenie/{engine}:pin-abcdef12-{variant}"}


def test_a_cell_failure_named_and_successes_built(monkeypatch, capsys):
    """cpu fails, cuda+rocm must still be attempted, and the run names the failure + returns 1."""
    try:
        rows = [{"engine": "vllm", "variant": "cpu"}, {"engine": "vllm", "variant": "cuda"},
                {"engine": "vllm", "variant": "rocm"}]
        _fake_matrix(rows)
        order = _fake_build({"cpu": 1, "cuda": 0, "rocm": 0})   # cpu (first) fails
        ei.resolve = lambda e, b=None, v=None: _spec(e, v)

        rc = ei.collect("vllm", push=False)

        captured = capsys.readouterr()
        out, err = captured.out, captured.err
        # every later cell was still attempted — the sweep does NOT abort on cpu
        assert order == [("cpu", False), ("cuda", False), ("rocm", False)], \
            f"sweep must try all cells, got {order}"
        assert "2 ok, 1 failed" in out, f"collect must tally successes and failures: {out!r}"
        assert "vllm/cpu" in out, f"the failed cell must be named by engine/variant: {out!r}"
        assert rc == 1, "any failed cell must make the collect sweep exit non-zero"
        assert "FAIL collect vllm/cpu" in err, f"the failure must reach stderr: {err!r}"

        # push is respected: when set, a successful cell is still pushed; the report is on stdout.
        rows2 = [{"engine": "vllm", "variant": "cpu"}, {"engine": "vllm", "variant": "cuda"}]
        _fake_matrix(rows2)
        order2 = _fake_build({"cpu": 1, "cuda": 0})
        ei.resolve = lambda e, b=None, v=None: _spec(e, v)
        rc2 = ei.collect("vllm", push=True)
        assert ("cuda", True) in order2, "a successful cell under push=true must be pushed"
        assert rc2 == 1
    finally:
        _restore()


def test_pinned_unchanged_but_install_changed_still_repins(monkeypatch, tmp_path):
    """The `pinned` field is a red herring: a params edit that changes an install line without
    moving the pin MUST still be seen as a repin (the trigger keys on the params FILE, so it fires).
    Lock it so a future refactor cannot regress the trigger back to only looking at `pinned`."""
    import scripts.check_engine_pins_published as cpp

    # Build a throwaway repo: one params file whose `pinned` is equal on base and head, but whose
    # cuda install line differs.
    root = tmp_path / "repo"
    params_dir = root / "containers" / "engines" / "params"
    params_dir.mkdir(parents=True)
    base = {"id": "vllm", "pinned": "3a4d82f569a9f57054ba81633e9b6c73b34b51fe",
            "variants": {"cpu": {"install": ["a"]}, "cuda": {"install": ["torch==2.13.0"]}}}
    head = {"id": "vllm", "pinned": "3a4d82f569a9f57054ba81633e9b6c73b34b51fe",
            "variants": {"cpu": {"install": ["a"]}, "cuda": {"install": ["torch==2.14.0"]}}}
    import json, subprocess
    (params_dir / "vllm.json").write_text(json.dumps(base))
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], check=True)
    base_oid = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
    (params_dir / "vllm.json").write_text(json.dumps(head))

    ids = cpp.repinned_engine_ids(base_oid, root)
    assert "vllm" in ids, (
        "an install-line change at an unchanged `pinned` MUST count as a repin (issue #2259)")
