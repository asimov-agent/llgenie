"""Registry hygiene sweep (issue #2914): the superseded fixed-name buildx cache tags.

Hermetic: every registry probe (`checker`, `deleter`, `version_lookup`, `digest_resolver`) is
injected — no docker call, no network, no GHCR. The candidate set is derived from the same repo
constants the live image naming uses, so it tracks the registry's real population."""
from __future__ import annotations

import pytest

import scripts.ci_images as ci_images
import scripts.engine_image as engine_image
import scripts.engine_skills as engine_skills
import scripts.registry_cache_orphans as rco

REG = ci_images.registry()


def test_candidates_cover_every_live_namespace():
    """Every helper, backend base, and engine×variant cell has its fixed-name candidate."""
    cands = set(rco.candidate_refs())
    for name in ci_images.IMAGES:
        assert f"{REG}/llgenie/{name}:buildcache" in cands
    for backend in engine_skills.BACKENDS:
        assert f"{REG}/llgenie/base-{backend}:buildcache" in cands
    for cell in engine_image.matrix():
        pkg = cell["engine"].replace(".", "-")
        assert f"{REG}/llgenie/{pkg}:buildcache-{cell['variant']}" in cands


def test_every_candidate_is_a_fixed_name_cache_tag():
    for ref in rco.candidate_refs():
        tag = ref.rsplit(":", 1)[-1]
        assert rco.ORPHAN_TAG_RE.match(tag), ref


def test_guard_refuses_live_and_content_keyed_refs():
    for bad in (
        f"{REG}/llgenie/test:abc123def456-buildcache",            # keyed helper cache (#2911)
        f"{REG}/llgenie/vllm:1.2.3-abcdef01-cuda-buildcache",     # keyed cell cache (#2891)
        f"{REG}/llgenie/test:latest",                              # an ordinary image tag
    ):
        with pytest.raises(SystemExit):
            rco.assert_orphan(bad)


def test_split_ref_names_owner_and_package():
    assert rco.split_ref(f"{REG}/llgenie/test:buildcache") == ("asimov-agent", "llgenie/test")
    assert rco.split_ref(f"{REG}/llgenie/llama-cpp:buildcache-cuda") == ("asimov-agent", "llgenie/llama-cpp")
    assert rco.split_ref(f"https://{REG}/llgenie/base-cuda:buildcache") == ("asimov-agent", "llgenie/base-cuda")


def test_report_lists_only_existing_orphans():
    hits = {f"{REG}/llgenie/test:buildcache", f"{REG}/llgenie/base-cuda:buildcache"}
    orphans = rco.run_report(checker=lambda ref: ref in hits)
    assert sorted(orphans) == sorted(hits)


def test_gc_without_yes_deletes_nothing():
    hits = {f"{REG}/llgenie/test:buildcache"}
    calls: list[tuple[str, str, int]] = []
    rc = rco.run_gc(checker=lambda ref: ref in hits, deleter=lambda *c: calls.append(c),
                    version_lookup=lambda ref, digest: 1, digest_resolver=lambda ref: "sha256:x",
                    assume_yes=False)
    assert rc == 1
    assert calls == []


def test_gc_deletes_exactly_the_orphans_and_verifies_zero():
    live = {f"{REG}/llgenie/test:buildcache", f"{REG}/llgenie/vllm:buildcache-cpu"}
    deleted: list[tuple[str, str, int]] = []

    def deleter(owner: str, pkg: str, version: int) -> None:
        deleted.append((owner, pkg, version))
        live.discard(f"{REG}/{pkg}:" + ("buildcache" if pkg != "llgenie/vllm" else "buildcache-cpu"))

    rc = rco.run_gc(checker=lambda ref: ref in live, deleter=deleter,
                    version_lookup=lambda ref, digest: 42, digest_resolver=lambda ref: "sha256:x",
                    assume_yes=True)
    assert rc == 0
    assert {d[1] for d in deleted} == {"llgenie/test", "llgenie/vllm"}
    assert all(d[0] == "asimov-agent" for d in deleted)


def test_gc_reports_failure_when_a_delete_leaves_an_orphan():
    live = {f"{REG}/llgenie/test:buildcache"}
    rc = rco.run_gc(checker=lambda ref: ref in live,
                    deleter=lambda owner, pkg, version: None,  # deletes nothing
                    version_lookup=lambda ref, digest: 42, digest_resolver=lambda ref: "sha256:x",
                    assume_yes=True)
    assert rc == 2


# --- digest_of: the REAL parser against imagetools inspect output (#2922) ---

# The three-line inspect header captured verbatim from GHCR on main c564764c —
# `docker buildx imagetools inspect ghcr.io/asimov-agent/llgenie/agent:buildcache`.
CAPTURED_IMAGETOOLS = (
    "Name:      ghcr.io/asimov-agent/llgenie/agent:buildcache\n"
    "MediaType: application/vnd.oci.image.index.v1+json\n"
    "Digest:    sha256:c5299a4136c4473606ff8eeedefd28ace2c783c05ee1f7e974b88de08bd36650\n"
)
LEGACY_INSPECT = "digest: sha256:c5299a4136c4473606ff8eeedefd28ace2c783c05ee1f7e974b88de08bd36650\n"
NO_DIGEST_INSPECT = "Name:      ghcr.io/asimov-agent/llgenie/agent:buildcache\nMediaType: application/vnd.oci.image.index.v1+json\n"


class _Out:
    def __init__(self, text: str):
        self.stdout, self.stderr, self.returncode = text, "", 0


def test_digest_of_reads_the_captured_padded_imagetools_format(monkeypatch):
    # When  the imagetools inspect output is the real padded `Digest:` alignment
    monkeypatch.setattr(rco, "run_ok", lambda cmd: _Out(CAPTURED_IMAGETOOLS))

    # Then  digest_of resolves the full content digest
    assert rco.digest_of(f"{REG}/llgenie/agent:buildcache") == (
        "sha256:c5299a4136c4473606ff8eeedefd28ace2c783c05ee1f7e974b88de08bd36650")


def test_digest_of_still_reads_the_legacy_single_space_form(monkeypatch):
    # Given the old imagetools output with exactly one space after the colon
    monkeypatch.setattr(rco, "run_ok", lambda cmd: _Out(LEGACY_INSPECT))

    # When  digest_of parses it
    assert rco.digest_of(f"{REG}/llgenie/agent:buildcache") == (
        "sha256:c5299a4136c4473606ff8eeedefd28ace2c783c05ee1f7e974b88de08bd36650")


def test_digest_of_refuses_a_no_digest_output(monkeypatch):
    # Given  an inspect output with no digest line (index header only)
    monkeypatch.setattr(rco, "run_ok", lambda cmd: _Out(NO_DIGEST_INSPECT))

    # When  digest_of cannot find a digest
    with pytest.raises(SystemExit, match="no digest for"):
        rco.digest_of(f"{REG}/llgenie/agent:buildcache")
