"""The engine capacity mapper is the sync-time guard rail (issue #1214).

`data/engine-capabilities.json` is the docs-cited table of what each engine REALLY
supports (archs + formats + ternary). Every claim the tree makes — a skill's
`backends:`/`formats:` front-matter, a params `variants` key, a ternary-capable file
routed to a non-ternary engine — must be a SUBSET of the mapper. A faulty trending-store
entry, or a human backend drift, reds HERE, not at a later build or a serve hang.

Each test below forces one claim to leave the mapper and asserts the exact finding names
it — proving the gate is not vacuous.
"""
from __future__ import annotations

import json
from pathlib import Path

import scripts.check_engine_capabilities as ccc
import scripts.engine_skills as es

REPO = Path(__file__).resolve().parent.parent
MAPPER = REPO / "data" / "engine-capabilities.json"
PARAMS = REPO / "containers" / "engines" / "params"


def _mapper_entry(engine: str, **over) -> dict:
    """One engine's mapper row from the committed table, with `over` applied."""
    doc = json.loads(MAPPER.read_text())
    row = dict(doc["engines"][engine])
    row.update(over)
    return row


def _sku(tmp: Path, name: str, content: str) -> Path:
    d = tmp / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(content)
    return d


def _run(skills_root: Path, mapper: dict, params: Path, monkeypatch) -> list[str]:
    """Run check() against synthetic skills/mapper/params, return the findings."""
    imp = json.dumps({"engines": mapper})
    monkeypatch.setattr(ccc, "CAPABILITIES", params / "_mapper.json")
    (params / "_mapper.json").write_text(imp)
    monkeypatch.setattr(ccc, "PARAMS", params)
    # Patch the EXACT module object ccc uses (ccc.es is `engine_skills` on sys.path,
    # not the `scripts.engine_skills` the test imports) and SKILLS_DIR (module global
    # load_skills reads) so a synthetic skills tree is what `es.load_skills()` returns.
    monkeypatch.setattr(ccc.es, "SKILLS_DIR", skills_root)
    return ccc.check()


MAPPER_DOC = json.loads(MAPPER.read_text())
ENGINES = dict(MAPPER_DOC["engines"])
_SKILL = (
    "---\nid: {eid}\nengine: \"{eid}\"\nservable: true\n"
    "backends: [{bs}]\nformats: [{fs}]\nos: [linux]\nquants: [F32, F16]\n---\n"
)


def test_real_tree_passes(monkeypatch):
    """The committed tree is already a docs-cited subset of the mapper."""
    real_root = es.engines_root()
    findings = ccc.check()  # real skills + real params + committed mapper
    assert findings == [], findings


def test_e1_skill_backend_not_in_mapper(monkeypatch, tmp_path):
    """A skill claiming a backend the engine does not support must red."""
    skills = tmp_path / "s"
    _sku(skills, "ollama", _SKILL.format(eid="ollama", bs="rocm, cuda, sycl, cpu", fs="gguf"))
    findings = _run(skills, {"ollama": _mapper_entry("ollama")}, tmp_path, monkeypatch)
    assert any("E1" in f and "sycl" in f for f in findings), findings


def test_e2_skill_format_not_in_mapper(monkeypatch, tmp_path):
    """A skill claiming a model format the engine cannot read must red."""
    skills = tmp_path / "s"
    _sku(skills, "ollama", _SKILL.format(eid="ollama", bs="cuda, cpu", fs="gguf, safetensors"))
    findings = _run(skills, {"ollama": _mapper_entry("ollama")}, tmp_path, monkeypatch)
    assert any("E2" in f and "safetensors" in f for f in findings), findings


def test_e3_params_variant_not_in_mapper(monkeypatch, tmp_path):
    """A generated params variant for an arch the engine does not support must red."""
    skills = tmp_path / "s"
    _sku(skills, "ollama", _SKILL.format(eid="ollama", bs="cuda, cpu", fs="gguf"))
    (tmp_path / "ollama.json").write_text(json.dumps(
        {"id": "ollama", "variants": {"cuda": {}, "cpu": {}, "rocm": {}}}))
    # The committed ollama row DOES include rocm, so force a mapper that does not.
    findings = _run(skills, {"ollama": _mapper_entry("ollama", archs=["cuda", "cpu"])},
                    tmp_path, monkeypatch)
    assert any("E3" in f and "rocm" in f for f in findings), findings


def test_e4_ternary_on_non_ternary_engine(monkeypatch, tmp_path):
    """A non-ternary engine whose skill declares a Prism-only ternary type must red."""
    skills = tmp_path / "s"
    body = _SKILL.format(eid="llama.cpp", bs="cuda, cpu", fs="gguf").replace(
        "quants: [F32, F16]", "quants: [PQ2_0, PTQ1_0, F32, F16]")
    _sku(skills, "llama.cpp", body)
    findings = _run(skills, {"llama.cpp": _mapper_entry("llama.cpp", ternary=False)},
                    tmp_path, monkeypatch)
    names = "\n".join(findings)
    assert "PQ2_0" in names and "not mark it ternary" in names, findings


def test_e4_ternary_quants_ok_when_mapper_says_ternary(monkeypatch, tmp_path):
    """TQ1_0/TQ2_0 are UPSTREAM ternary (stock llama.cpp serves them): they must NOT red,
    and the Prism-only PQ2_0/PTQ1_0 must be allowed only when the mapper marks ternary."""
    # stock style: TQ1_0/TQ2_0 declared, mapper ternary=False -> no E4 finding
    skills = tmp_path / "s"
    stock = _SKILL.format(eid="llama.cpp", bs="cuda, cpu", fs="gguf").replace(
        "quants: [F32, F16]", "quants: [TQ1_0, TQ2_0, F32, F16]")
    _sku(skills, "llama.cpp", stock)
    findings = _run(skills, {"llama.cpp": _mapper_entry("llama.cpp", ternary=False)},
                    tmp_path, monkeypatch)
    assert not any("E4" in f for f in findings), findings


def test_e4_prism_ternary_allowed(monkeypatch, tmp_path):
    """The PrismML fork declares ternary and the mapper marks it ternary -> no red."""
    skills = tmp_path / "s"
    body = _SKILL.format(eid="llama.cpp-prism", bs="cuda, cpu", fs="gguf").replace(
        "quants: [F32, F16]", "quants: [PQ2_0, PTQ1_0, F32, F16]")
    _sku(skills, "llama.cpp-prism", body)
    findings = _run(skills, {"llama.cpp-prism": _mapper_entry("llama.cpp-prism")},
                    tmp_path, monkeypatch)
    assert not any("E4" in f for f in findings), findings


def test_e5_missing_engine_and_missing_row(monkeypatch, tmp_path):
    """A shipped skill with no mapper row, and a mapper engine with no skill, both red."""
    skills = tmp_path / "s"
    _sku(skills, "brandnew", _SKILL.format(eid="brandnew", bs="cuda", fs="gguf"))
    # mapper has only ollama (present) + a phantom engine with no skill
    m = {"ollama": _mapper_entry("ollama"),
         "phantom": _mapper_entry("ollama", formats=["gguf"])}
    findings = _run(skills, m, tmp_path, monkeypatch)
    names = "\n".join(findings)
    assert "E5" in names and "brandnew" in names and "phantom" in names, findings
