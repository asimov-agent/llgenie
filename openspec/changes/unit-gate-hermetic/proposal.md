# The unit gate is hermetic: live-Hub work gets its own target

## Why

`make test-unit` is the gate every change runs, on Linux and macOS, in CI and on a laptop. Three of its
tests left the machine:

- `tests/test_trend_pick.py::test_readme_links_answer_and_a_broken_copy_is_caught` — answers every link
  in the README's trend table over the live Hub and GitHub;
- `tests/test_trend_pick.py::test_the_vendored_registry_links_all_answer` — checks every link the
  vendored registry carries against the live Hub;
- `tests/test_trend_pick.py::test_select_downloads_a_missing_model_for_real` — downloads the picked
  model's full GGUF from the Hub (hundreds of MB) and asserts it lands on disk.

Measured on 2026-10-21 (`make test-unit` on this host):

```
........................................................................ [ 98%]
............Timeout (0:05:00)!
Thread 0x00007f79e05bd380 (most recent call first):
  File "/usr/local/lib/python3.11/subprocess.py", line 550 in run
  File "/repo/tests/test_trend_pick.py", line 412 in _cli
  File "/repo/tests/test_trend_pick.py", line 493 in test_select_downloads_a_missing_model_for_real
...
4911 passed, 3 deselected in 1187.27s (0:19:47)
```

The run stalled for five minutes and still reported **passed**: `pytest.ini` sets only
`faulthandler_timeout = 300`, which prints a dump and keeps going — a dump is not a verdict, and the
suite went from ~13 to ~20 minutes with nothing to point at. Four minutes earlier, on another branch, the
same gate went red with fifteen `HTTP Error 429: Too Many Requests` from the Hub while the tree was fine:
a network flake reds a hermetic gate, and a green gate can hide a hang (issue #438).

## What Changes

- **`tests/fixtures/unit-suite.json`** — the three live checks are de-selected from the hermetic suite by
  **exact node id** (the roster's `deselect`, a dated decision with a reason naming the owning target;
  never a `-k` expression), so `make test-unit` no longer contains a Hub download or a link crawl.
- **`make test-hub-live`** — the target that owns them: it runs exactly those three node ids in the test
  image, `.PHONY`, documented in the README's command list.
- **`tests/test_hub_live_target.py` (new)** — pins both halves: the node ids are out of the gate
  (`unit_tests.deselected`), the target names exactly them and is phony, every de-selection in the
  roster still names a test that exists (a renamed test cannot silently shrink the gate), and each
  reason names its owning target.
- **`README.md` + `agent-wiki/`** — the hermetic rule and the new target.

## Impact

- `make test-unit` is hermetic again: no Hub crawl, no multi-hundred-MB download, so a `429` can no
  longer red it and a stall cannot hide in it.
- The live checks still run — with their own name, on demand, through `make test-hub-live`.
- `test-hub-live` is intentionally **not** in `ci-unit`: this change makes the gate honest, it does not
  newly require network in CI.
