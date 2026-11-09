"""The engine install/serve legs run only on a PUBLISHING engine-build run (#1027 / #844).

With published.yml retired and engine-build the sole producer, the "only install/serve
published images when this run actually published" gate moved here: the install-leg
(make test-engine-install) and the serve-leg (make test-published-engine) run per row ONLY
when `inputs.push == 'true'` — the producer's own answer to "did this run publish an image?" —
and never on the `none` placeholder row (#828). Fail closed: push=false publishes nothing, so
neither leg may run; the none row builds nothing and runs no install/serve step."""
from __future__ import annotations

import sys

import yaml
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EB = REPO / ".github/workflows/engine-build.yml"


def _eb_job() -> dict:
    return yaml.safe_load(EB.read_text())["jobs"]["build"]


def _legs():
    steps = _eb_job()["steps"]
    install = [s for s in steps if "make test-engine-install" in (s.get("run") or "")]
    serve = [s for s in steps if "make test-published-engine" in (s.get("run") or "")]
    return install, serve


def test_the_install_and_serve_legs_run_only_when_this_run_publishes():
    """Fail closed (issue #844 / #1027): push=false publishes nothing, so neither leg may run.
    The serve leg is now a BINARY check on the just-published image (issue #2319); the serve
    conformance test itself is host-only."""
    install, serve = _legs()
    assert install and serve, (len(install), len(serve))
    for s in install + serve:
        gate = s.get("if") or ""
        assert "inputs.push == 'true'" in gate, (s.get("name"), gate)
        assert "matrix.engine != 'none'" in gate, (s.get("name"), gate)


def test_the_none_placeholder_row_never_runs_the_legs():
    """#828: the placeholder row builds nothing and must not run an install/serve step."""
    install, serve = _legs()
    for s in install + serve:
        assert "none" in (s.get("if") or "")


def test_the_install_leg_installs_versions_and_uninstalls_the_just_published_image():
    """Install + the installed launcher's engine version + uninstall (no product `llgenie --dry` — the
    producer is product-LESS #1027; the product tool installs and dry-runs in pipeline.yml's ci-install)."""
    mk = (REPO / "Makefile").read_text()
    recipe = mk.split("\ntest-engine-install:", 1)[1].split("\n\n", 1)[0]
    for needle in ("engine-install", "test-built-engine", "ci-install-uninstall"):
        assert needle in recipe, needle
    assert "ci-install-dry" not in recipe, "the producer install-leg must not call the product-only ci-install-dry (#1196)"


def test_the_serve_leg_serves_the_published_image():
    """Pull the just-published image (digest == :ARCH) and verify the BINARY answers -h/--version only
    (issue #2319) — no server starts in CI. The serve conformance test is host-only (make test-engine-host)."""
    mk = (REPO / "Makefile").read_text()
    recipe = mk[mk.index("test-published-engine:"):mk.index("push-engine:")]
    assert "pull-published" in recipe
    assert "test_published_engine_binary.py" in recipe
    assert "$(MAKE) test-engine-image" in recipe  # test-engine-image runs the -h/--version binary probe
    # no --serve INVOCATION in CI (the recipe's prose may mention the host-only make command):
    # the check is that engine_smoke --serve is not called as a command line.
    assert "--serve;" not in recipe and "--serve " not in recipe.splitlines()[-2]


def test_the_dispatch_push_defaults_to_false():
    """A dispatch that says nothing builds + verifies but never publishes nor installs."""
    wf = yaml.safe_load(EB.read_text())
    on = wf.get("on") if "on" in wf else wf.get(True)
    assert str(on["workflow_dispatch"]["inputs"]["push"]["default"]) == "false", on["workflow_dispatch"]["inputs"]["push"]


def test_the_push_gated_legs_come_after_the_row_pushes():
    """Both legs are ordered after `make push-engine` — they act on the just-published image."""
    steps = _eb_job()["steps"]
    runs = [s.get("run", "") for s in steps if s.get("run")]
    i_push = next(i for i, r in enumerate(runs) if "make push-engine ENGINE=" in r)
    i_serve = next(i for i, r in enumerate(runs) if "make test-published-engine ENGINE=" in r)
    i_install = next(i for i, r in enumerate(runs) if "make test-engine-install ENGINE=" in r)
    assert i_push < i_serve < i_install, (i_push, i_serve, i_install)
