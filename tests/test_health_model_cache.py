"""Issue #356 pins: the health model lands in the SHARED stage HOME and survives.

`make download-test-model` used to fetch the 0.43 GB health model into the test
container's throwaway HOME, so `make test-health` re-fetched it into $(CI_HOME)
and $(CI_HOME_CLEAN) wiped it at every stage boundary — `make loop` paid the
download twice. These tests lock the three seams that make the loop fetch once:

1. the per-branch MODEL_CACHE_RUN macros run the downloader with HOME=$(CI_HOME)
   (Linux: uid-mapped container, checkout mounted at its own path),
2. the download-test-model recipe creates $(CI_HOME) first and runs through
   MODEL_CACHE_RUN,
3. both CI_HOME_CLEAN variants keep the `models` subtree while wiping the rest.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAKEFILE = (REPO / "Makefile").read_text()
TESTS_MK = (REPO / "mk" / "tests.mk").read_text()
HARNESS = (REPO / "scripts" / "loop_harness.py").read_text()
DOWNLOADER = (REPO / "scripts" / "download_test_model.py").read_text()

DARWIN_BRANCH = re.search(r"ifeq \(\$\(HOST_OS\),Darwin\)\n(.*?)\nelse\n", MAKEFILE, re.S).group(1)
LINUX_BRANCH = re.search(r"\nelse\n(.*?)\nendif\n", MAKEFILE[MAKEFILE.index("ifeq ($(HOST_OS),Darwin)"):], re.S).group(1)


def _recipe(name: str, text: str) -> str:
    m = re.search(rf"^{name}:.*\n((?:\t.*\n|\n(?=\t))*)", text, re.M)
    assert m, f"target {name} not found"
    return m.group(1)


def test_model_cache_run_linux_maps_home_and_own_path_mount():
    m = re.search(r"^MODEL_CACHE_RUN := (.*)$", LINUX_BRANCH, re.M)
    assert m, "Linux MODEL_CACHE_RUN missing"
    body = m.group(1)
    assert '-e HOME="$(CI_HOME)"' in body
    assert '-u "$(shell id -u):$(shell id -g)"' in body  # uid mapping (issue #2563 lesson), not -u root
    assert '-v "$(ROOT)":"$(ROOT)":rw' in body  # mounted AT ITS OWN PATH like the engine stages
    assert "$(TEST_IMG)" in body


def test_model_cache_run_darwin_sets_home_natively():
    m = re.search(r"^MODEL_CACHE_RUN := (.*)$", DARWIN_BRANCH, re.M)
    assert m, "Darwin MODEL_CACHE_RUN missing"
    assert 'env HOME="$(CI_HOME)"' in m.group(1)


def test_download_recipe_creates_ci_home_and_uses_the_cache_run():
    recipe = _recipe("download-test-model", TESTS_MK)
    assert '$(MODEL_CACHE_RUN)' in recipe
    assert '$(TEST_RUN)' not in recipe  # no throwaway-HOME run left
    lines = [l.strip() for l in recipe.strip().splitlines()]
    assert lines[0] == '@mkdir -p "$(CI_HOME)"'


def test_ci_home_clean_keeps_models_in_both_branches():
    d = re.search(r"^CI_HOME_CLEAN := (.*)$", DARWIN_BRANCH, re.M)
    l = re.search(r"^CI_HOME_CLEAN := (.*)$", LINUX_BRANCH, re.M)
    assert d and l
    assert '! -name models' in d.group(1)
    assert '! -name models' in l.group(1)
    # the Linux clean still runs as root (issue #2563: root-written trees need a root rm)
    assert "-u root" in l.group(1)


def test_download_stage_and_idempotence_stay_wired():
    assert '["make", "download-test-model"]' in HARNESS  # loop stage 1 still provisions the cache
    assert "already present" in DOWNLOADER  # present-file short-circuit the reuse depends on


def test_stage_brackets_still_call_the_clean_macro():
    installs = (REPO / "mk" / "install.mk").read_text()
    engines = (REPO / "mk" / "engines.mk").read_text()
    assert installs.count("$(CI_HOME_CLEAN)") >= 2
    assert engines.count("$(CI_HOME_CLEAN)") >= 2
