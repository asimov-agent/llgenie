"""The binary smoke probes what the engine DOCUMENTS (issue #2573).

Fleet run #645 (engine-build.yml run 43206254966) reddened `engine-build-mlx-cpu`
because the probe set was pinned to `["-h", "--version"]` while the generated
manifest documents mlx/cpu as `flags ["--help"], probe "help"` — mlx_lm.server is
argparse and has no --version. The smoke now reads the documented set from the
generated manifest (image path) / skill front matter (host path), keeps the pinned
pair as the documented-nothing default (#2319), bounds the vocabulary, and keeps
the device-probe skip. No docker and no engine build run here: the subprocess is
the external system and the assertion is on the probe set the smoke built.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

from scripts import engine_smoke as smoke  # noqa: E402  (conftest puts scripts/ on the path)

# The image path does `import engine_image as ei` inside binary_smoke; conftest's
# single import root (tests/conftest.py) makes this the SAME module object.
import engine_image as ei  # noqa: E402

MANIFEST = REPO / "containers" / "engines" / "binaries.json"


def _capture(monkeypatch) -> list[str]:
    """Stub the probe subprocess; record every flag the smoke attempted."""
    probes: list[str] = []

    def fake_run(cmd, *a, **kw):
        tail = cmd[-1]
        for marker in (' 2>&1',):
            tail = tail.split(marker)[0]
        probes.append(tail.rsplit(" ", 1)[-1].strip('"'))
        return subprocess.CompletedProcess(cmd, 0, stdout="answered", stderr="")

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)
    return probes


def _manifest(monkeypatch, entries: dict) -> None:
    """Stand in for the committed generated manifest for these variants."""
    monkeypatch.setattr(ei, "binary_manifest",
                        lambda engine, variant: entries[(engine, variant)])


def _spec(engine: str, variant: str) -> dict:
    return {"id": engine, "variant": variant,
            "tag": f"llgenie/{engine.replace('.', '-')}:{variant}"}


def test_image_path_probes_only_the_manifest_documented_flags(monkeypatch):
    """Given the real mlx/cpu entry (flags ["--help"], probe "help"), when the
    image smoke builds its probe set, then --version is never attempted.

    # Given/When/Then per the change spec: mlx_lm.server answers --help only.
    """
    _manifest(monkeypatch, {("mlx", "cpu"): {
        "binary": "mlx_lm.server", "flags": ["--help"], "probe": "help"}})
    probes = _capture(monkeypatch)
    assert smoke.binary_smoke(spec=_spec("mlx", "cpu")) == 0
    assert probes == ["--help"], probes


def test_image_path_probes_both_when_the_manifest_documents_both(monkeypatch):
    """llama.cpp/cpu documents ["--version", "--help"]: both are probed, in order."""
    _manifest(monkeypatch, {("llama.cpp", "cpu"): {
        "binary": "llama-server", "flags": ["--version", "--help"], "probe": "flags"}})
    probes = _capture(monkeypatch)
    assert smoke.binary_smoke(spec=_spec("llama.cpp", "cpu")) == 0
    assert probes == ["--version", "--help"], probes


def test_manifest_documenting_nothing_keeps_the_pinned_default(monkeypatch):
    """#2319's pair survives as the default when the manifest documents no flags."""
    _manifest(monkeypatch, {("mystery", "cpu"): {"binary": "mystery-server"}})
    probes = _capture(monkeypatch)
    assert smoke.binary_smoke(spec=_spec("mystery", "cpu")) == 0
    assert probes == ["-h", "--version"], probes


def test_device_probe_variant_is_still_skipped(monkeypatch):
    """vllm/cuda (probe: device) is skipped unchanged: no flag is attempted."""
    _manifest(monkeypatch, {("vllm", "cuda"): {
        "binary": "vllm", "flags": ["--version", "--help"], "probe": "device"}})
    probes = _capture(monkeypatch)
    assert smoke.binary_smoke(spec=_spec("vllm", "cuda")) == 0
    assert probes == [], probes


def test_documented_flag_outside_the_vocabulary_fails_closed(monkeypatch):
    """A manifest that documents a non version/help flag is refused, naming the variant."""
    _manifest(monkeypatch, {("rogue", "cpu"): {
        "binary": "rogue-server", "flags": ["--dump-config"], "probe": "flags"}})
    probes = _capture(monkeypatch)
    assert smoke.binary_smoke(spec=_spec("rogue", "cpu")) == 1
    assert probes == [], "a vocabulary violation must not probe anything"


def test_skill_path_honors_the_per_backend_map(monkeypatch):
    """The host path smokes the map entry for the backend being smoked, not the union."""
    skill = {"id": "vllm", "binary_flags": {"cuda": ["--version"], "cpu": ["--version", "--help"]}}
    probes = _capture(monkeypatch)
    rc = smoke.binary_smoke(skill=skill, p={"binary": "vllm", "backend": "cuda"})
    assert rc == 0
    assert probes == ["--version"], probes


def test_skill_documenting_nothing_uses_the_pinned_default(monkeypatch):
    skill = {"id": "mystery"}
    probes = _capture(monkeypatch)
    rc = smoke.binary_smoke(skill=skill, p={"binary": "mystery-server", "backend": "cpu"})
    assert rc == 0
    assert probes == ["-h", "--version"], probes


def test_the_committed_manifest_is_in_vocabulary_and_mlx_cpu_is_help_only():
    """The gate canary against the REAL generated manifest on this tree: every
    documented set stays inside the version/help vocabulary, and mlx/cpu is
    --help only — the exact entry fleet run #645 could not satisfy with --version."""
    engines = json.loads(MANIFEST.read_text()).get("engines") or {}
    assert engines, "containers/engines/binaries.json carries no engines"
    for engine, variants in engines.items():
        for variant, entry in variants.items():
            documented = [str(f) for f in (entry.get("flags") or [])]
            assert all(f in smoke.DOCUMENTED_FLAG_VOCAB for f in documented), \
                f"{engine}/{variant} documents {documented} outside the vocabulary"
    mlx = (engines.get("mlx") or {}).get("cpu") or {}
    assert mlx.get("flags") == ["--help"], mlx
    assert smoke._documented_probe_set(mlx.get("flags"), "mlx/cpu") == ["--help"]
