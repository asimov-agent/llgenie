#!/usr/bin/env python3
"""`make check-strata-models` proves the map WITHOUT leaving the machine (#519).

The step used to shallow-fetch github.com/Niko1221/Strata at the pinned commit on EVERY
`ci-unit` run: a GitHub hiccup reddened the gate while the tree was fine — the #437 failure
(fetch-based checks flaking on runner networking) walking back in through a sibling step.
The fix splits the seam:

  * `sync` writes the map AND vendors the pinned source (setup.py + the import surface its
    module-level imports need) with a per-file sha256 manifest — the ONLY target that fetches;
  * `check` re-derives the map from the VENDORED source and proves the chain from the manifest
    (pin match, every file hash, no smuggled file) — never `git`, never a socket;
  * `check-live` keeps the old fetch-then-compare as the explicit upstream audit
    (`make check-strata-models-live`), the only check path that may fetch.

The sabotage proof: with `checkout` and `subprocess.run` monkeypatched to raise, the hermetic
`check` still passes on the committed chain — if ANY step fetched, the test would crash.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from scripts import strata_models as SM

HF_FAMILY = "https://huggingface.co/ISTA-DASLab/Fixture-GGUF/resolve/" \
            "ed59f92082b1e93c0e96d60a8b11aab089b52f09/{q}/"

SETUP_PY = f'''
FAMILIES = {{
    "qwen": {{"name": "Qwen", "tag": "qwen", "title": "Qwen Fix", "by": "ISTA-DASLab",
              "about": "fixture", "hf": "{HF_FAMILY}",
              "file": "fix-{{q}}-0000{{i}}-of-00002.gguf", "shards": 2}},
}}

MODELS = {{"IQ3_XXS": {{"download_gb": 9.5, "ram_gb": 16, "families": ["qwen"]}}}}

HF_REVISIONS = {{"ISTA-DASLab/Fixture-GGUF": "ed59f92082b1e93c0e96d60a8b11aab089b52f09"}}


def main():
    raise SystemExit("setup.py must not run its installer when imported")
'''


def _no_fetch(monkeypatch):
    """Sabotage every exit from the process: a fetch would crash instead of flake."""
    def _boom(*args, **kwargs):
        raise AssertionError("a hermetic `check` must not spawn a subprocess or clone")
    monkeypatch.setattr(SM, "checkout", _boom)
    monkeypatch.setattr(subprocess, "run", _boom)


def _sync(tmp_path, monkeypatch):
    """Fixture tree: a fake checkout -> sync writes map + vendor + manifest."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "setup.py").write_text(SETUP_PY)
    out = tmp_path / "data" / "strata_models.json"
    vendor = tmp_path / "data" / "vendor" / "strata"
    _no_fetch(monkeypatch)  # sync FROM --src must not fetch either
    assert SM.main(["sync", "--src", str(src), "--out", str(out), "--vendor", str(vendor)]) == 0
    return src, out, vendor


def test_sync_writes_map_vendor_and_manifest(tmp_path, monkeypatch):
    # Given a checkout, When sync runs, Then all three artifacts exist and the manifest pins them
    src, out, vendor = _sync(tmp_path, monkeypatch)
    assert out.exists() and (vendor / "setup.py").exists()
    assert (vendor / "setup.py").read_text() == SETUP_PY
    man = json.loads((vendor / "manifest.json").read_text())
    url, ref, sha = SM.pinned()
    assert man["url"] == url and man["ref"] == ref and man["pinned"] == sha
    assert man["files"]["setup.py"] == hashlib.sha256(SETUP_PY.encode()).hexdigest()
    for name, want in man["files"].items():
        assert hashlib.sha256((vendor / name).read_bytes()).hexdigest() == want, name


def test_check_is_green_and_never_fetches(tmp_path, monkeypatch):
    # Given a synced fixture tree whose every process spawn is sabotage,
    src, out, vendor = _sync(tmp_path, monkeypatch)
    # When  the hermetic check runs, Then it is green WITHOUT reaching anywhere
    assert SM.main(["check", "--out", str(out), "--vendor", str(vendor)]) == 0


def test_the_committed_chain_is_consistent_and_hermetic(monkeypatch):
    """The real ACs of #519 on the real tree: committed vendor -> green, with zero process spawns."""
    _no_fetch(monkeypatch)
    assert SM.main(["check"]) == 0  # default data/strata_models.json + data/vendor/strata/
    man = json.loads((ROOT / "data" / "vendor" / "strata" / "manifest.json").read_text())
    url, ref, sha = SM.pinned()
    assert man["pinned"] == sha and man["ref"] == ref
    committed = json.loads((ROOT / "data" / "strata_models.json").read_text())
    assert committed["pinned"] == sha, "map and vendor name the same pin"


def test_a_hand_edited_map_is_refused(tmp_path, monkeypatch, capsys):
    src, out, vendor = _sync(tmp_path, monkeypatch)
    bad = json.loads(out.read_text())
    bad["models"]["IQ3_XXS"]["ram_gb"] = 1
    out.write_text(json.dumps(bad, indent=2) + "\n")
    assert SM.main(["check", "--out", str(out), "--vendor", str(vendor)]) == 1
    err = capsys.readouterr().err
    assert "differs from" in err and "make sync-strata-models" in err


def test_a_stale_vendor_pin_is_refused(tmp_path, monkeypatch, capsys):
    """A bump that moved the skill's pin without re-running sync is a stale vendor, not a pass."""
    src, out, vendor = _sync(tmp_path, monkeypatch)
    man = json.loads((vendor / "manifest.json").read_text())
    man["pinned"] = "0" * 40
    (vendor / "manifest.json").write_text(json.dumps(man, indent=2) + "\n")
    assert SM.main(["check", "--out", str(out), "--vendor", str(vendor)]) == 1
    err = capsys.readouterr().err
    assert "was made for pin" in err and SKILL_NAMES in err


def test_a_tampered_vendored_file_is_refused(tmp_path, monkeypatch, capsys):
    src, out, vendor = _sync(tmp_path, monkeypatch)
    (vendor / "setup.py").write_text(SETUP_PY + "\n# edited\n")
    assert SM.main(["check", "--out", str(out), "--vendor", str(vendor)]) == 1
    assert "does not hash to the manifest" in capsys.readouterr().err


def test_a_smuggled_vendored_file_is_refused(tmp_path, monkeypatch, capsys):
    """An extra module could satisfy an import the pinned source never ran — the manifest says no."""
    src, out, vendor = _sync(tmp_path, monkeypatch)
    (vendor / "strata_control").mkdir(parents=True, exist_ok=True)
    (vendor / "strata_control" / "evil.py").write_text("X = 1\n")
    assert SM.main(["check", "--out", str(out), "--vendor", str(vendor)]) == 1
    assert "never recorded" in capsys.readouterr().err


def test_a_missing_vendor_is_refused_and_names_the_repair(tmp_path, capsys):
    out = tmp_path / "m.json"
    src = tmp_path / "src"
    src.mkdir()
    (src / "setup.py").write_text(SETUP_PY)
    out.write_text(json.dumps(SM.extract(src), indent=2) + "\n")
    assert SM.main(["check", "--out", str(out),
                    "--vendor", str(tmp_path / "nope")]) == 1
    assert "make sync-strata-models" in capsys.readouterr().err


def test_check_live_is_the_only_check_path_that_fetches(tmp_path, monkeypatch):
    """`check-live` owns the fetch: with checkout pointed at a fixture tree it is green,
    and the hermetic `check` is green with checkout sabotaged (proved above)."""
    src, out, vendor = _sync(tmp_path, monkeypatch)
    calls = []

    def fake_checkout(dest: Path) -> Path:
        calls.append(dest)
        return src

    monkeypatch.setattr(SM, "checkout", fake_checkout)
    assert SM.main(["check-live", "--out", str(out)]) == 0
    assert calls, "check-live must run the fetch the old check ran"


SKILL_NAMES = "skills/engines/strata/SKILL.md"


def test_the_makefile_split_and_ci_step_are_wired():
    """`ci-unit` keeps its step name; the step body fetches nothing; the live audit is a
    separate target; and the engine-bump commit carries the vendor next to the map."""
    engines = (ROOT / "mk" / "engines.mk").read_text()
    step = engines.split("check-strata-models:", 1)[1].split("\n\n", 1)[0]
    assert "scripts/strata_models.py check" in step
    assert "check-live" not in step, "the CI step must not be the fetching one"
    live = engines.split("check-strata-models-live:", 1)[1].split("\n\n", 1)[0]
    assert "scripts/strata_models.py check-live" in live
    assert "check-strata-models-live" in (ROOT / "Makefile").read_text()
    ci_unit = (ROOT / "scripts" / "ci_unit.py").read_text()
    assert "make check-strata-models" in ci_unit
    assert "check-strata-models-live" not in ci_unit, "the unit gate never fetches"
    bump = (ROOT / ".github" / "workflows" / "engine-bump.yml").read_text()
    assert "data/vendor/strata/" in bump, "a bump must commit the regenerated vendor"
