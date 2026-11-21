"""Issue #2996: the alias-lag heal is a registry-side manifest move, not a build.

Covers scripts/engine_alias_move.py (make engine-alias-move):
  * the happy move spells `docker buildx imagetools create -t <repo>:<variant>
    <repo>@<digest>` — the ONLY command shape (no build, no engine run) — and
    prints MOVED only when the post-move alias digest equals the pin digest;
  * a malformed contract (missing field, non-sha256:64hex digest, suffix that
    contradicts the committed exact-tag formula) is refused with exit 2 and
    ZERO registry calls;
  * an imagetools failure or a post-move digest mismatch exits 1 loudly;
  * the seam: the gate's emitted [aliasmove] line feeds the mover's fields
    unchanged (gate and mover share engine_image.resolve's tag formula);
  * the wiring: mk/engines.mk wires the target, registry-liveness.yml heals
    the [aliasmove] cells BEFORE the fleet gate and keeps the build dispatch
    for manifest-unknown ([select]) cells only.
"""
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The repo's ONE import root is tests/conftest.py (issue #796): no file-local
# sys.path entry and no bare scripts/ imports here (the import-roots ratchet,
# issue #1101, refuses a new root in a new test file).
import scripts.engine_alias_move as am  # noqa: E402
import scripts.engine_image as ei  # noqa: E402
import scripts.check_engine_pins_published as cpp  # noqa: E402

REGISTRY = "ghcr.io/asimov-agent"
PIN = "sha256:" + "b" * 64


def _cell():
    """(engine, variant, suffix, alias target) spelled with the committed formula."""
    engine, variant = "mlx", "cpu"
    tag = ei.resolve(engine, None, variant)["tag"]
    repo = f"{REGISTRY}/{tag.rpartition(':')[0]}"
    return engine, variant, tag.split(":")[-1], f"{repo}:{variant}"


def _recorder(post_digest: str | None):
    """Fake run+probe pair: records the exact commands, resolves the alias to post_digest."""
    ran: list[list[str]] = []
    probes: list[str] = []

    def run(cmd, **kw):
        ran.append(list(cmd))
        return subprocess.CompletedProcess(list(cmd), 0, "", "")

    def probe(ref):
        probes.append(ref)
        return (post_digest, "") if post_digest else ("", "no manifest")

    return ran, probes, run, probe


def test_a_lagging_alias_is_moved_by_manifest_and_verified(capsys):
    """Happy path: imagetools create is the only command (no build), and MOVED prints
    only because the post-move alias digest equals the pin digest."""
    engine, variant, suffix, target = _cell()
    ran, probes, run, probe = _recorder(PIN)
    rc = am.move_alias(engine, variant, suffix, PIN, registry=REGISTRY,
                       run=run, probe=probe)
    out = capsys.readouterr().out
    assert rc == 0
    assert ran == [["docker", "buildx", "imagetools", "create",
                    "-t", target, f"{target.rpartition(':')[0]}@{PIN}"]], \
        "the heal is exactly a manifest re-point of the alias to the pin digest"
    assert f"[alias-move] MOVED {target} -> {PIN}" in out
    assert probes == [target], "the moved alias is verified through the gate's probe"


def test_imagetools_failure_reds_without_verification(capsys):
    """A refused registry write stays red and never claims a move."""
    engine, variant, suffix, target = _cell()
    ran: list[list[str]] = []
    probes: list[str] = []

    def run(cmd, **kw):
        ran.append(list(cmd))
        return subprocess.CompletedProcess(list(cmd), 1, "", "denied")

    def probe(ref):
        probes.append(ref)
        return PIN, ""

    rc = am.move_alias(engine, variant, suffix, PIN, registry=REGISTRY,
                       run=run, probe=probe)
    out = capsys.readouterr().out
    assert rc == 1
    assert "imagetools create exited 1" in out
    assert probes == [], "a failed move must not be re-probed as if it happened"


def test_post_move_digest_mismatch_reds(capsys):
    """The registry accepted a move to the WRONG digest: FAIL loudly, no MOVED."""
    engine, variant, suffix, target = _cell()
    ran, probes, run, probe = _recorder("sha256:" + "9" * 64)
    rc = am.move_alias(engine, variant, suffix, PIN, registry=REGISTRY,
                       run=run, probe=probe)
    out = capsys.readouterr().out
    assert rc == 1
    assert "post-move digest" in out and PIN in out
    assert "MOVED" not in out


def test_malformed_digest_is_refused_before_any_registry_call(capsys):
    engine, variant, suffix, _ = _cell()
    ran, probes, run, probe = _recorder(PIN)
    rc = am.move_alias(engine, variant, suffix, "sha256:tooshort",
                       registry=REGISTRY, run=run, probe=probe)
    assert rc == 2
    assert "not sha256:<64 hex>" in capsys.readouterr().out
    assert ran == [] and probes == [], "a malformed contract must touch nothing"


def test_suffix_contradicting_the_committed_formula_is_refused(capsys):
    """A [aliasmove] line whose suffix is not the committed exact-tag suffix for this
    cell is rejected before any registry write (contract-first, #2567 class)."""
    engine, variant, _real, _ = _cell()
    ran, probes, run, probe = _recorder(PIN)
    rc = am.move_alias(engine, variant, "ffffffff-eeeeeeee-cuda", PIN,
                       registry=REGISTRY, run=run, probe=probe)
    assert rc == 2
    assert "contradicts the committed exact-tag formula" in capsys.readouterr().out
    assert ran == [] and probes == []


def test_missing_field_is_refused(capsys):
    engine, variant, suffix, _ = _cell()
    ran, probes, run, probe = _recorder(PIN)
    rc = am.move_alias(engine, variant, suffix, "", registry=REGISTRY,
                       run=run, probe=probe)
    assert rc == 2
    assert "DIGEST is missing" in capsys.readouterr().out
    assert ran == []


def test_cli_refuses_a_bad_contract_without_registry_calls(capsys):
    """make engine-alias-move's CLI half forwards to the same refusal."""
    rc = am.main(["--engine", "mlx", "--variant", "cpu",
                  "--suffix", "x", "--digest", "nope"])
    assert rc == 2


def test_the_gates_aliasmove_line_feeds_the_mover_fields_unchanged(tmp_path, capsys):
    """Seam test: run the gate over a lagging alias, take the EXACT [aliasmove] line
    it emits, and feed those fields to the mover — the digest and suffix the gate
    prints pass the mover's contract, and the mover spells the same alias ref."""
    engine, variant = "mlx", "cpu"
    pin64 = "sha256:" + "a" * 64
    tag = ei.resolve(engine, None, variant)["tag"]
    pin_ref = f"{REGISTRY}/{tag}"
    alias_ref = f"{REGISTRY}/{tag.rpartition(':')[0]}:{variant}"

    def fake(ref):
        if ref == pin_ref:
            return pin64, ""
        if ref == alias_ref:
            return "sha256:" + "c" * 64, ""
        return "", "no manifest"

    rc = cpp.check_committed(digest=fake, registry=REGISTRY, root=tmp_path,
                             cells=[(engine, variant)], alias_check=True)
    gate_out = capsys.readouterr().out
    assert rc == 1
    lines = sorted({tuple(ln.split()) for ln in gate_out.splitlines()
                    if ln.startswith("[aliasmove] ")})
    assert len(lines) == 1, \
        "the :<variant> lag and the same cell's :latest lag (#2988) emit the ONE " \
        "identical heal line — the liveness step dedupes it with sort -u"
    _, mv_engine, mv_variant, mv_suffix, mv_digest = lines[0]

    ran, probes, run, probe = _recorder(mv_digest)
    rc2 = am.move_alias(mv_engine, mv_variant, mv_suffix, mv_digest,
                        registry=REGISTRY, run=run, probe=probe)
    assert rc2 == 0, "the gate's emitted fields must be mover-valid as printed"
    assert probes == [alias_ref]


def test_make_target_and_liveness_heal_are_wired():
    """make engine-alias-move exists with the four fields, and registry-liveness
    consumes ONLY [aliasmove] lines with it, before the fleet gate; the build
    dispatch stays for [select] (manifest-unknown) cells."""
    mk = (REPO / "mk" / "engines.mk").read_text()
    assert re.search(r"^engine-alias-move:", mk, re.MULTILINE), \
        "engine-alias-move must be a Makefile target (workflows may not call scripts directly)"
    assert "scripts/engine_alias_move.py" in mk
    wf = (REPO / ".github/workflows/registry-liveness.yml").read_text()
    heal = wf.index("heal alias-lagging cells")
    gate = wf.index("full-fleet committed-tag pin-validity gate")
    dispatch = wf.index("dispatch engine-build push=true")
    assert heal < gate, "alias lag must be healed before the gate re-probes it"
    heal_region = wf[heal:gate]
    assert "[aliasmove]" in heal_region and "make engine-alias-move" in heal_region
    assert "publisher.outputs.publisher_still_running" in heal_region, \
        "the heal defers while a same-head publisher is in flight (#2592)"
    assert "secrets.GITHUB_TOKEN" in heal_region, \
        "the heal logs into GHCR with the job token, engine-build.yml's pattern (#1843)"
    assert "packages: write" in wf, "manifest moves need the same-repo packages:write scope"
    dispatch_region = wf[dispatch:]
    assert "[select]" in dispatch_region, "manifest-unknown cells keep the build dispatch"
