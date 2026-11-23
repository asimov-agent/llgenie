"""Issue #2996 + #3006: the alias-lag heal is a byte-preserving manifest move, not a build.

Covers scripts/engine_alias_move.py (make engine-alias-move):
  * the happy move FETCHES the pin manifest verbatim (`docker buildx imagetools
    inspect --raw <repo>@<digest>` — the ONLY command shape, no build, no engine
    run, and never `imagetools create`, which re-wraps the manifest into a list
    and can never carry the pin digest (#3006)) and PUBLISHES the exact bytes to
    `<name>/manifests/<variant>` with the manifest's own mediaType as
    Content-Type; MOVED prints only when the post-move alias digest equals the
    pin digest;
  * a fetch whose bytes do not hash to the pin is never published anywhere;
  * a refused manifest PUT is loud and is never re-probed as if it happened;
  * a malformed contract (missing field, non-sha256:64hex digest, suffix that
    contradicts the committed exact-tag formula) is refused with exit 2 and
    ZERO registry calls;
  * the seam: the gate's emitted [aliasmove] line feeds the mover's fields
    unchanged (gate and mover share engine_image.resolve's tag formula);
  * the wiring: mk/engines.mk wires the target, registry-liveness.yml heals
    the [aliasmove] cells BEFORE the fleet gate, exports BOTH GHCR_LOGIN_TOKEN
    and GHCR_LOGIN_USER to the mover through env: (#361, #3006), and keeps the
    build dispatch for manifest-unknown ([select]) cells only.
"""
import hashlib
import inspect as pyinspect
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The repo's ONE import root is tests/conftest.py (issue #796): no file-local
# sys.path entry and no bare scripts/ imports here (the import-roots ratchet,
# issue #1101, refuses a new root in a new test file).
import scripts.engine_alias_move as am  # noqa: E402
import scripts.engine_image as ei  # noqa: E402
import scripts.check_engine_pins_published as cpp  # noqa: E402

REGISTRY = "ghcr.io/asimov-agent"
MANIFEST_TYPE = "application/vnd.docker.distribution.manifest.v2+json"

# A single-manifest fixture exactly like the measured pin (issue #3006: the pin
# is a plain manifest.v2+json; `imagetools create` re-published it as a
# manifest.list.v2+json under a NEW digest, so the heal could never verify).
MANIFEST_BYTES = json.dumps({
    "schemaVersion": 2,
    "mediaType": MANIFEST_TYPE,
    "config": {"mediaType": "application/vnd.oci.image.config.v1+json",
               "digest": "sha256:" + "1" * 64, "size": 7000},
    "layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                "digest": "sha256:" + "2" * 64, "size": 123456}],
}, indent=4).encode()
PIN = "sha256:" + hashlib.sha256(MANIFEST_BYTES).hexdigest()


def _cell():
    """(engine, variant, suffix, alias target) spelled with the committed formula."""
    engine, variant = "mlx", "cpu"
    tag = ei.resolve(engine, None, variant)["tag"]
    repo = f"{REGISTRY}/{tag.rpartition(':')[0]}"
    return engine, variant, tag.split(":")[-1], f"{repo}:{variant}"


def _recorder(post_digest: str | None, body: bytes = MANIFEST_BYTES):
    """Fake run+probe+put triple: records every call, publishes nothing real."""
    ran: list[list[str]] = []
    probes: list[str] = []
    puts: list[tuple[str, str, bytes, str, str]] = []

    def run(cmd, **kw):
        ran.append(list(cmd))
        return subprocess.CompletedProcess(list(cmd), 0, body.decode(), "")

    def probe(ref):
        probes.append(ref)
        return (post_digest, "") if post_digest else ("", "no manifest")

    def put(name_path, tag, put_body, media_type, host):
        puts.append((name_path, tag, put_body, media_type, host))
        return 201, "sha256:ignored"

    return ran, probes, puts, run, probe, put


def test_a_lagging_alias_is_moved_byte_preservingly_and_verified(capsys):
    """Happy path (#3006): fetch the pin raw, PUT the EXACT bytes with the
    manifest's own mediaType, verify through the gate's probe, print MOVED."""
    engine, variant, suffix, target = _cell()
    repo = target.rpartition(":")[0]
    ran, probes, puts, run, probe, put = _recorder(PIN)
    rc = am.move_alias(engine, variant, suffix, PIN, registry=REGISTRY,
                       run=run, probe=probe, put=put)
    out = capsys.readouterr().out
    assert rc == 0
    assert ran == [["docker", "buildx", "imagetools", "inspect", "--raw",
                    f"{repo}@{PIN}"]], \
        "the heal fetches the pin manifest verbatim — the ONLY command shape"
    assert all("create" not in cmd for cmd in ran), \
        "imagetools create re-wraps the manifest into a list (#3006); it is never used"
    name_path = repo.partition("/")[2]
    assert puts == [(name_path, variant, MANIFEST_BYTES, MANIFEST_TYPE, "ghcr.io")], \
        "the PUT carries the fetched bytes BYTE-IDENTICALLY, the variant tag, and " \
        "the manifest's own mediaType as Content-Type"
    assert f"[alias-move] MOVED {target} -> {PIN}" in out
    assert probes == [target], "the moved alias is verified through the gate's probe"


def test_fetch_that_is_not_the_pin_is_never_published(capsys):
    """Issue #3006's safety rail: the fetched bytes are hashed against the pin
    BEFORE any write; a mismatch publishes nothing anywhere."""
    engine, variant, suffix, target = _cell()
    ran, probes, puts, run, probe, put = _recorder(
        PIN, body=b'{"schemaVersion": 2, "mediaType": "' + MANIFEST_TYPE.encode() + b'"}')
    rc = am.move_alias(engine, variant, suffix, PIN, registry=REGISTRY,
                       run=run, probe=probe, put=put)
    out = capsys.readouterr().out
    assert rc == 1
    assert "refusing to publish them anywhere" in out
    assert puts == [], "bytes that hash elsewhere must never reach the registry"
    assert probes == [], "a move that never happened must not be re-probed"


def test_manifest_without_mediatype_is_refused(capsys):
    """A PUT without the exact Content-Type lets the registry re-serialize the
    manifest — a fetch that names no mediaType is refused before any write."""
    engine, variant, suffix, _ = _cell()
    body = b'{"schemaVersion": 2}'  # hashes to its own pin, names no mediaType
    pin = "sha256:" + hashlib.sha256(body).hexdigest()
    ran, probes, puts, run, probe, put = _recorder(pin, body=body)
    rc = am.move_alias(engine, variant, suffix, pin, registry=REGISTRY,
                       run=run, probe=probe, put=put)
    out = capsys.readouterr().out
    assert rc == 1
    assert "names no mediaType" in out
    assert puts == [] and probes == []


def test_fetch_failure_reds_without_verification(capsys):
    """A refused fetch stays red, writes nothing, and never claims a move."""
    engine, variant, suffix, target = _cell()
    ran: list[list[str]] = []
    probes: list[str] = []
    puts: list = []

    def run(cmd, **kw):
        ran.append(list(cmd))
        return subprocess.CompletedProcess(list(cmd), 1, "", "denied")

    def probe(ref):
        probes.append(ref)
        return PIN, ""

    def put(*a):
        puts.append(a)
        return 201, ""

    rc = am.move_alias(engine, variant, suffix, PIN, registry=REGISTRY,
                       run=run, probe=probe, put=put)
    out = capsys.readouterr().out
    assert rc == 1
    assert "inspect --raw exited 1" in out
    assert probes == [] and puts == [], \
        "a failed fetch must not be written or re-probed as if it happened"


def test_refused_put_reds_without_reprobe(capsys):
    """The registry said no to the manifest write: FAIL with the status, and the
    alias is not re-probed as if the write had landed."""
    engine, variant, suffix, target = _cell()
    ran, probes, _puts, run, probe, _put = _recorder(PIN)

    def put(name_path, tag, body, media_type, host):
        return 403, "denied by scope"

    rc = am.move_alias(engine, variant, suffix, PIN, registry=REGISTRY,
                       run=run, probe=probe, put=put)
    out = capsys.readouterr().out
    assert rc == 1
    assert "manifest PUT refused" in out and "403" in out
    assert probes == []


def test_post_move_digest_mismatch_reds(capsys):
    """The registry accepted a move to the WRONG digest: FAIL loudly, no MOVED."""
    engine, variant, suffix, target = _cell()
    ran, probes, puts, run, probe, put = _recorder("sha256:" + "9" * 64)
    rc = am.move_alias(engine, variant, suffix, PIN, registry=REGISTRY,
                       run=run, probe=probe, put=put)
    out = capsys.readouterr().out
    assert rc == 1
    assert "post-move digest" in out and PIN in out
    assert "MOVED" not in out


def test_malformed_digest_is_refused_before_any_registry_call(capsys):
    engine, variant, suffix, _ = _cell()
    ran, probes, puts, run, probe, put = _recorder(PIN)
    rc = am.move_alias(engine, variant, suffix, "sha256:tooshort",
                       registry=REGISTRY, run=run, probe=probe, put=put)
    assert rc == 2
    assert "not sha256:<64 hex>" in capsys.readouterr().out
    assert ran == [] and probes == [] and puts == [], \
        "a malformed contract must touch nothing"


def test_suffix_contradicting_the_committed_formula_is_refused(capsys):
    """A [aliasmove] line whose suffix is not the committed exact-tag suffix for this
    cell is rejected before any registry write (contract-first, #2567 class)."""
    engine, variant, _real, _ = _cell()
    ran, probes, puts, run, probe, put = _recorder(PIN)
    rc = am.move_alias(engine, variant, "ffffffff-eeeeeeee-cuda", PIN,
                       registry=REGISTRY, run=run, probe=probe, put=put)
    assert rc == 2
    assert "contradicts the committed exact-tag formula" in capsys.readouterr().out
    assert ran == [] and probes == [] and puts == []


def test_missing_field_is_refused(capsys):
    engine, variant, suffix, _ = _cell()
    ran, probes, puts, run, probe, put = _recorder(PIN)
    rc = am.move_alias(engine, variant, suffix, "", registry=REGISTRY,
                       run=run, probe=probe, put=put)
    assert rc == 2
    assert "DIGEST is missing" in capsys.readouterr().out
    assert ran == [] and puts == []


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
    tag = ei.resolve(engine, None, variant)["tag"]
    pin_ref = f"{REGISTRY}/{tag}"
    alias_ref = f"{REGISTRY}/{tag.rpartition(':')[0]}:{variant}"

    def fake(ref):
        if ref == pin_ref:
            return PIN, ""
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
    assert mv_digest == PIN, "the gate emits the pin digest the mover must re-publish"

    ran, probes, puts, run, probe, put = _recorder(mv_digest)
    rc2 = am.move_alias(mv_engine, mv_variant, mv_suffix, mv_digest,
                        registry=REGISTRY, run=run, probe=probe, put=put)
    assert rc2 == 0, "the gate's emitted fields must be mover-valid as printed"
    assert probes == [alias_ref]
    assert puts and puts[0][1] == variant and puts[0][2] == MANIFEST_BYTES


def test_make_target_and_liveness_heal_are_wired():
    """make engine-alias-move exists with the four fields, and registry-liveness
    consumes ONLY [aliasmove] lines with it, before the fleet gate; the mover's
    token exchange reads GHCR_LOGIN_USER beside GHCR_LOGIN_TOKEN through env:
    (#3006, #361); the build dispatch stays for [select] (manifest-unknown) cells."""
    mk = (REPO / "mk" / "engines.mk").read_text()
    assert re.search(r"^engine-alias-move:", mk, re.MULTILINE), \
        "engine-alias-move must be a Makefile target (workflows may not call scripts directly)"
    assert "scripts/engine_alias_move.py" in mk
    src = (REPO / "scripts" / "engine_alias_move.py").read_text()
    assert '"imagetools", "create"' not in src, \
        "the mover must never use imagetools create: it re-wraps the manifest into a " \
        "list and the moved tag can then never equal the pin digest (#3006)"
    assert '"imagetools", "inspect", "--raw"' in src
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
    assert "GHCR_LOGIN_USER" in heal_region and "GHCR_LOGIN_TOKEN" in heal_region, \
        "the mover's manifest-PUT token exchange authenticates through the SAME env " \
        "credential as the docker login, never inline run: text (#361, #3006)"
    assert "packages: write" in wf, "manifest moves need the same-repo packages:write scope"
    dispatch_region = wf[dispatch:]
    assert "[select]" in dispatch_region, "manifest-unknown cells keep the build dispatch"


# --- issue #3010: the LIVE fetch seam must capture, or the byte gate hashes b'' ---

def test_the_default_fetch_seam_is_the_capturing_policy():
    """The live heal hashed EMPTY bytes because move_alias's default fetch seam was
    proc.run_live, whose own docstring states stdout/stderr on the returned process
    are None (it streams, it never captures). The default seam must be the capturing
    policy proc.run_ok."""
    default_run = pyinspect.signature(am.move_alias).parameters["run"].default
    assert default_run is am.proc.run_ok, \
        "the default fetch seam must capture stdout (proc.run_ok); the streaming seam " \
        "proc.run_live leaves stdout None and the byte gate then hashes b'' (#3010)"
    src = (REPO / "scripts" / "engine_alias_move.py").read_text(encoding="utf-8")
    assert "= proc.run_live" not in src, \
        "no signature default may bind the streaming seam: the heal path must capture"


def test_a_non_capturing_seam_is_refused_by_name_not_hashed(capsys):
    """stdout=None (the run_live shape) is a named refusal — 'the fetch seam captured
    nothing' — never a digest mismatch: #3010's live failure line read 'the fetched
    bytes hash to sha256:e3b0c442…', the SHA-256 of the empty string."""
    engine, variant, suffix, _target = _cell()
    _ran, probes, puts, _run, probe, put = _recorder(PIN)

    def streaming(cmd, **kw):
        return subprocess.CompletedProcess(list(cmd), 0, None, None)

    rc = am.move_alias(engine, variant, suffix, PIN, registry=REGISTRY,
                       run=streaming, probe=probe, put=put)
    out = capsys.readouterr().out
    assert rc == 1
    assert "the fetch seam captured nothing" in out
    assert "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" not in out, \
        "an empty capture must never masquerade as a digest mismatch"
    assert puts == [] and probes == [], "a refused seam hashes nothing and writes nothing"

    def empty(cmd, **kw):
        return subprocess.CompletedProcess(list(cmd), 0, "", "")

    rc = am.move_alias(engine, variant, suffix, PIN, registry=REGISTRY,
                       run=empty, probe=probe, put=put)
    out = capsys.readouterr().out
    assert rc == 1 and "the fetch seam captured nothing" in out
    assert puts == [] and probes == []


def test_the_real_capture_policy_passes_the_byte_gate_end_to_end(tmp_path, capsys):
    """The capture policy is proven against a REAL subprocess: the fetch command is
    swapped for a stub emitting the pin manifest's exact bytes, executed through the
    actual proc.run_ok; the byte gate passes on captured bytes and the PUT body is
    byte-identical (no docker, no registry)."""
    engine, variant, suffix, target = _cell()
    repo = target.rpartition(":")[0]
    name_path = repo.partition("/")[2]
    stub = tmp_path / "stub_inspect.py"
    stub.write_text(f"import sys\nsys.stdout.buffer.write({MANIFEST_BYTES!r})\n",
                    encoding="utf-8")
    _ran, probes, puts, _r, probe, put = _recorder(PIN)

    def seam(cmd, **kw):
        return am.proc.run_ok([sys.executable, str(stub)])

    rc = am.move_alias(engine, variant, suffix, PIN, registry=REGISTRY,
                       run=seam, probe=probe, put=put)
    out = capsys.readouterr().out
    assert rc == 0 and f"[alias-move] MOVED {target} -> {PIN}" in out
    assert puts == [(name_path, variant, MANIFEST_BYTES, MANIFEST_TYPE, "ghcr.io")], \
        "the captured bytes pass the byte gate and reach the PUT byte-identically"
