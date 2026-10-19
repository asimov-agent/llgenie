"""The downloader survives a Hub throttle instead of reddening the job that used it (issue #385).

NO MOCKS: each test runs the REAL `scripts/hf_download.py` as a subprocess against a REAL
fake-`hf` executable (`tests/fixtures/fake_hf.py`) that is a genuine child process printing
what the real CLI prints on a throttle and exiting non-zero. The waits are real sleeps; the
fake's message names 2 seconds so the suite stays fast, and a `HF_RETRY_PAUSE` of 0.1s proves
the downloader spends the HUB's number, not its own short pause.

Measured in CI (PR #374, PR #372): `hf download` answered

    429 Too Many Requests: you have reached your 'api' rate limit.
    Retry after 202 seconds (0/1000 requests remaining in current 300s window).

and the engine-image job died on the first answer, naming the engine.
"""
from __future__ import annotations

import os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HF_DL = ROOT / "scripts" / "hf_download.py"
FAKE_HF = HERE / "fixtures" / "fake_hf.py"


def _run(tmp: Path, mode: str, filename: str = "model.gguf", *,
         env_extra: dict | None = None, label: str = "throttle") -> dict:
    """Run the REAL hf_download.main() with HF_BIN -> the fake hf, in `mode`."""
    dest = tmp / "dest"
    dest.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({"HF_BIN": str(FAKE_HF), "FAKE_HF_MODE": mode,
                "HF_RETRY_PAUSE": "0.1", "HF_POLL_SECONDS": "0.2",
                "HF_STALL_SECONDS": "90",   # never trip the stall-watch here
                "HF_MAX_RETRY": "3"})
    env.pop("HF_TOKEN", None)              # hermetic: never reach the Hub
    env.update(env_extra or {})
    t0 = time.time()
    proc = subprocess.run([sys.executable, str(HF_DL), "fake/repo", filename, str(dest), label],
                          env=env, capture_output=True, text=True, timeout=120)
    log = dest / f"{label}.progress.log"
    return {"rc": proc.returncode, "stdout": proc.stdout, "elapsed": time.time() - t0,
            "dest": dest, "log_text": log.read_text() if log.exists() else "",
            "attempts": (log.read_text().count("=== attempt ")) if log.exists() else 0}


def test_downloader_waits_the_seconds_the_hub_names(tmp_path):
    """A throttled attempt waits the Hub's own number, then the retry downloads.

    # Given a fake `hf` whose FIRST call answers the Hub's 429 text (Retry after 2 seconds),
    # And  a retry pause of 0.1s (so the pause can never explain a 2s gap),
    # When hf_download.main() runs,
    # Then it completes (rc=0) on the second attempt,
    # And  the wall-clock gap is at least the seconds the Hub named,
    # And  the progress log records the throttle wait.
    """
    r = _run(tmp_path, "throttle-once")

    assert r["rc"] == 0, r["log_text"] + r["stdout"]
    assert r["attempts"] == 2, r["log_text"]
    assert r["elapsed"] >= 2.0, f"waited only {r['elapsed']:.2f}s for a 2-second throttle"
    assert "retrying in 2s" in r["log_text"], r["log_text"]
    assert (r["dest"] / "model.gguf").exists()


def test_an_eternal_throttle_fails_loudly_on_the_bounded_budget(tmp_path):
    """An exhausted Hub window still fails, on the bounded budget, and says so.

    # Given a fake `hf` that throttles on every call, and HF_MAX_RETRY=2
    # When hf_download.main() runs
    # Then it exits non-zero after exactly the budget's attempts
    # And  it prints the loud FAILED line naming the log.
    """
    r = _run(tmp_path, "throttle-forever", env_extra={"HF_MAX_RETRY": "2"})

    assert r["rc"] == 1, r["log_text"]
    assert r["attempts"] == 2, r["log_text"]
    assert "FAILED after 2 attempts" in r["stdout"], r["stdout"]


def test_snapshot_download_fetches_the_whole_repo(tmp_path):
    """`-` in place of the filename fetches the whole repo into the destination.

    # Given a fake `hf` in snapshot mode (the repo has no single file to name),
    # When hf_download.main() runs with `-` as the filename,
    # Then it exits 0 with the repo's files in the destination,
    # And  it needed one attempt (the fresh destination is NOT a finished download).
    """
    r = _run(tmp_path, "snapshot", "-", label="snap")

    assert r["rc"] == 0, r["log_text"] + r["stdout"]
    assert r["attempts"] == 1, r["log_text"]
    assert (r["dest"] / "config.json").exists()
    assert (r["dest"] / "model.safetensors").stat().st_size == 4096
    assert "* (whole repo)" in r["log_text"], r["log_text"]


def test_an_existing_snapshot_is_not_refetched(tmp_path):
    """A snapshot already on disk is a fast path: the downloader does not call the Hub.

    # Given a destination that already holds a whole-repo snapshot,
    # When hf_download.main() runs again with a fake `hf` that would throttle forever,
    # Then it exits 0 without a single attempt (nothing was fetched).
    """
    first = _run(tmp_path, "snapshot", "-", label="snap")
    assert first["rc"] == 0, first["log_text"]

    second = _run(tmp_path, "throttle-forever", "-", label="snap2")

    assert second["rc"] == 0, second["log_text"] + second["stdout"]
    assert second["attempts"] == 0, second["log_text"]
