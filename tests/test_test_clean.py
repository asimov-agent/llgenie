"""#800: the test-clean recipe moved into scripts/test_clean.py.

The 15-line `test-clean` recipe was a docker/nerdctl-agnostic loop: list every container, keep the
ones referencing the test image, stop+remove ONLY the stopped/left-over ones (never kill a running
test), never `--filter ancestor` (docker lacks it). These tests drive the real module against a stub
`runtime` binary on PATH (real subprocess, real files) so the policy — prune stopped test-image
containers, leave running ones and non-test containers alone, tolerate an absent runtime — is
proven, not asserted on the recipe text.
"""

from __future__ import annotations

from pathlib import Path

import scripts.test_clean as test_clean  # noqa: E402


def _stub_runtime(root: Path, containers: dict[str, dict[str, str]]) -> Path:
    """A fake docker/nerdctl serving `ps -a -q` and `inspect -f '{Image|Running}'`.

    The stub answers `ps` with the container ids, and each `inspect` from the table keyed on the
    container id and the template (`{{.Image}}`/`{{.Running}}`). Every `rm -f <id>` is appended to
    `root/rm.txt` so the test asserts exactly which containers were removed.
    """
    rows = " ".join(containers)
    cases = []
    for cid, meta in containers.items():
        cases.append(f'        "{cid}") [ "$3" = "{{{{.Image}}}}" ] && echo "{meta["image"]}" || '
                     f'echo "{meta["running"]}";;')
    body = (
        "#!/usr/bin/env bash\n"
        "set -u\n"
        f'if [ "$1" = "ps" ]; then echo "{rows}"; exit 0; fi\n'
        f'if [ "$1" = "rm" ]; then echo "$3" >> {root}/rm.txt; exit 0; fi\n'
        'if [ "$1" = "inspect" ]; then\n'
        "  case \"$4\" in\n"
        + "\n".join(cases) +
        "\n  esac\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n"
    )
    bindir = root / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    stub = bindir / "runtime"
    stub.write_text(body)
    stub.chmod(0o755)
    return bindir


def test_removes_only_stopped_test_containers(tmp_path, monkeypatch):
    """A stopped container referencing the test image is pruned; a running one is left alone."""

    # Given a runtime reporting one stopped test container, one running test container,
    # and one stopped non-test container
    stopped_test, running_test, stopped_other = "c1", "c2", "c3"
    containers = {
        stopped_test: {"image": "ghcr.io/llgenie/test:latest", "running": "false"},
        running_test: {"image": "ghcr.io/llgenie/test:latest", "running": "true"},
        stopped_other: {"image": "busybox", "running": "false"},
    }
    bindir = _stub_runtime(tmp_path, containers)
    monkeypatch.setenv("PATH", f"{bindir}:{__import__('os').environ['PATH']}")

    # When the prune runs
    rc = test_clean.prune("runtime")

    # Then only c1 (stopped, test image) is removed; the running test and the busybox stay
    assert rc == 0
    rm_file = tmp_path / "rm.txt"
    rm_ids = rm_file.read_text().split() if rm_file.exists() else []
    assert rm_ids == [stopped_test]
    assert running_test not in rm_ids and stopped_other not in rm_ids


def test_absent_runtime_prunes_nothing_and_reports_success(tmp_path, monkeypatch):
    """An unreachable runtime (no docker daemon) prunes nothing and returns 0 — exactly the recipe."""

    # Given a PATH with no runtime binary
    bindir = tmp_path / "empty-bin"
    bindir.mkdir(exist_ok=True)
    monkeypatch.setenv("PATH", str(bindir))

    # When the prune runs
    rc = test_clean.prune("thermal-deployer")

    # Then nothing is removed and it still reports a successful (no-op) prune
    assert rc == 0
    assert not (tmp_path / "rm.txt").exists()


def test_runtime_never_uses_filter_ancestor(tmp_path, monkeypatch):
    """The module lists ALL containers first then filters by image — never `--filter ancestor`."""

    # Given a runtime that fails loudly if `--filter` is passed to `ps`
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    stub = bindir / "runtime"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "set -u\n"
        'if [[ "$*" == *"--filter"* ]]; then echo "FILTER-USED" >&2; exit 2; fi\n'
        'if [ "$1" = "ps" ]; then echo c1; exit 0; fi\n'
        'if [ "$1" = "inspect" ]; then echo "false"; exit 0; fi\n'
        'if [ "$1" = "rm" ]; then exit 0; fi\n'
        "exit 1\n"
    )
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{__import__('os').environ['PATH']}")

    # When the prune runs
    rc = test_clean.prune("runtime", image_fragment="llgenie/test")

    # Then it lists with plain `ps -a -q` — no `--filter ancestor` (docker lacks it)
    assert rc == 0
