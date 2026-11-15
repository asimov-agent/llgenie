"""`test-clean`'s orphan sweep lives in scripts/test_clean.py now (issue #2675, #800 criterion 5).

The 15-line shell recipe (mk/tests.mk at origin/main@dcfb96b7df) moved into the entry point;
the target recipe became the thin wrapper. The only external seam of the sweep is the runtime
CLI call (docker or nerdctl), so the fake below records those argv lines while the sweep's
decision logic — keep running tests, remove stopped test containers, skip foreign images, skip
inspect failures — is exercised exactly as shipped, quirks and all:

- the sweep never uses `--filter ancestor` (docker lacks it),
- the image test greps raw `inspect -f {{.Image}}` output for the `llgenie/test` marker; an
  inspect failure yields "" and the container is skipped,
- the running test greps `inspect -f {{.Running}}` for `false`; an inspect failure yields the
  fallback "false", i.e. the base recipe's `|| echo false` removes it,
- a currently-RUNNING test container is never removed.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
from conftest import makefiles_text  # noqa: E402  (include-resolving reader, #2459)
from scripts import test_clean

IDS = ["c1", "c2", "c3", "c4", "c5"]
IMAGES = {"c1": "llgenie/test:latest", "c2": "llgenie/test:latest",
          "c3": "sha256:deadbeef", "c4": "llgenie/test:latest", "c5": "llgenie/test:latest"}
RUNNING = {"c1": True, "c2": False, "c3": False, "c4": True}  # c5's inspect FAILS


class _Runtime:
    """A recorded stand-in for `docker|nerdctl ps|inspect|rm` (the sweep's only external seam)."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kw):
        self.calls.append(list(argv))
        out, rc = "", 0
        if argv[1:3] == ["ps", "-a"]:
            out = "\n".join(IDS) + "\n"
        elif argv[1] == "inspect":
            cid = argv[-1]
            if cid == "c5" and argv[3] == "{{.Running}}":
                rc = 1  # inspect FAILS -> the sweep must fall back to "false"
            elif argv[3] == "{{.Image}}":
                out = IMAGES[cid] + "\n"
            else:
                out = ("true" if RUNNING[cid] else "false") + "\n"
        return type("Proc", (), {"returncode": rc, "stdout": out})()


def _recipe(target: str) -> str:
    mk = makefiles_text(REPO)
    m = re.search(rf"^{target}:[^\n]*\n((?:[ \t].*\n)*)", mk, re.M)
    assert m, f"{target} target not found in the flattened Makefile"
    return m.group(1)


def test_the_test_clean_recipe_is_the_thin_wrapper_of_the_entry_point():
    # Given the flattened Makefile at this head
    tab_lines = [l for l in _recipe("test-clean").splitlines() if l.startswith("\t")]
    # Then it is one line carrying the make variables through as arguments
    assert len(tab_lines) == 1, tab_lines
    assert tab_lines[0].strip() == (
        '@python3 scripts/test_clean.py --runtime "$(RUNTIME)" --test-img "$(TEST_IMG)"')


def test_the_sweep_removes_only_stopped_test_image_containers(monkeypatch):
    # Given a runtime with: a RUNNING test container (c1), a STOPPED test container (c2),
    # a foreign image (c3), a running inspect-failure container (c4 by ps, inspect ok),
    # and a test container whose Running-inspect FAILS (c5)
    fake = _Runtime()
    monkeypatch.setattr(test_clean.subprocess, "run", fake)
    # When the sweep runs
    removed = test_clean.sweep("docker")
    # Then only the stopped test-image containers are removed:
    # c2 (stopped test), c5 (inspect-failed running -> "false" fallback, the base's `|| echo false`)
    assert removed == ["c2", "c5"]
    rm_calls = [a for a in fake.calls if a[1] == "rm"]
    assert [a[-1] for a in rm_calls] == ["c2", "c5"]
    # and the sweep never passed --filter ancestor to the runtime (docker lacks it)
    assert not any("--filter" in a for a in fake.calls)


def test_the_sweep_skips_containers_whose_image_inspect_fails(monkeypatch):
    # Given a container whose image-inspect fails mid-run (image fallback "" -> not a test image)
    def fake(argv, **kw):
        out, rc = "", 0
        if argv[1:3] == ["ps", "-a"]:
            out = "x1\n"
        elif argv[1] == "inspect" and argv[3] == "{{.Image}}":
            rc = 1
        return type("Proc", (), {"returncode": rc, "stdout": out})()

    monkeypatch.setattr(test_clean.subprocess, "run", fake)
    # When the sweep runs
    removed = test_clean.sweep("nerdctl")
    # Then the half-inspected container is left alone (the base greps an empty string)
    assert removed == []


def test_main_reports_the_prune_with_the_make_test_img_name(monkeypatch, capsys):
    # Given an empty runtime
    monkeypatch.setattr(test_clean.subprocess, "run",
                        lambda argv, **kw: type("Proc", (), {"returncode": 0, "stdout": ""})())
    # When the wrapper's main runs with the make variables
    rc = test_clean.main(["--runtime", "docker", "--test-img", "llgenie/test:latest"])
    # Then the closing report names the test image (the recipe's final echo, preserved)
    assert rc == 0
    assert capsys.readouterr().out.strip() == "Pruned stopped orphaned llgenie/test:latest containers."
