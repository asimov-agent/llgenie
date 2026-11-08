#!/usr/bin/env python3
"""A serve that never becomes ready must print the engine's OWN log (engine image run).

Measured on #1696 (vllm/cpu, head `8cb8e6f7`, job 128571645259, run 42428390792): the container
stayed Running for the whole 600 s readiness bound and the ONLY lines the job captured were the
launcher banner and the `serve` command — `[engine-image] FAIL llgenie-smoke-vllm-cpu not ready
after 600s; see: docker logs llgenie-smoke-vllm-cpu`. Naming the cause from that was impossible,
because `engine_runner.py serve` redirects the engine's real output to
`$TMPDIR/engine-runner-serve.log` INSIDE the container, `docker logs` carries only the banner, and
`engine_smoke.py` removes the container in a `finally` — so the one file holding the reason is
destroyed before anyone can read it.

The dead-engine rule is: a server that never becomes ready must print why. These tests drive the
REAL `run()` against a fake docker CLI, so the assertion is on behaviour (the in-container log is
dumped before the failure is reported), not on any particular wording.
"""
from __future__ import annotations

import scripts.engine_image as ei

_ENGINE_LOG = (
    "INFO 11-08 00:19:31 api_server.py] Initializing an OpenAI API server\n"
    "ValueError: cpu backend cannot serve model Qwen__Qwen2.5-0.5B-Instruct"
)


class _Result:
    def __init__(self, rc: int = 0, out: str = "") -> None:
        self.returncode, self.stdout, self.stderr = rc, out, ""


def _fake_cli(monkeypatch, engine_log: str = _ENGINE_LOG, logs_tail: str = "[entrypoint] vllm/cpu"):
    """Stub docker: image exists, `docker run -d` succeeds, the container stays Running, and the
    in-container serve log answers. Every call is recorded so a test can assert the dump ORDER."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        return _Result(0)  # `image inspect` -> present; `docker rm -f` -> fine

    def fake_sh(cmd, **kw):
        calls.append(list(cmd))
        if len(cmd) > 2 and cmd[1] == "exec":  # docker exec <name> sh -c 'tail …serve.log'
            return _Result(0, engine_log)
        if len(cmd) > 1 and cmd[1] == "logs":
            return _Result(0, logs_tail)
        return _Result(0, "")

    monkeypatch.setattr(ei.subprocess, "run", fake_run)
    monkeypatch.setattr(ei, "_sh", fake_sh)
    monkeypatch.setattr(ei, "RUNTIME", "docker")
    return calls


def _spec() -> dict:
    return {"id": "vllm", "backend": "cpu", "variant": "cpu",
            "tag": "llgenie/vllm:test-cpu", "port": 11434, "run_args": []}


def test_a_serve_that_never_readies_prints_the_in_container_engine_log(tmp_path, monkeypatch, capsys):
    """The engine's own reason must reach the job log, not die with the container."""
    calls = _fake_cli(monkeypatch)

    # wait=0 makes the readiness loop expire immediately, exercising the timeout path.
    rc = ei.run(_spec(), "/models/smoke", 9999, "llgenie-smoke-vllm-cpu", tmp_path, wait=0)

    out = capsys.readouterr().out
    assert rc == 1, f"a never-ready serve must fail: {rc}"
    assert "ValueError: cpu backend cannot serve" in out, (
        f"the engine's own reason was swallowed — exactly the #1696 blind spot: {out!r}")
    assert "[entrypoint] vllm/cpu" in out, f"the container stdout tail is owed too: {out!r}"
    # Behaviour: the engine log was read from the container BEFORE the failure line was printed.
    dumped = [c for c in calls if len(c) > 2 and c[1] == "exec"]
    assert dumped, f"run() never read the in-container serve log: {calls}"
    assert "engine-runner-serve.log" in " ".join(dumped[0]), (
        f"the dump must target the runner's serve log: {dumped[0]}")


def test_an_empty_engine_log_is_reported_as_absent_not_silent(tmp_path, monkeypatch, capsys):
    """A genuinely silent engine says so — 'not ready' plus nothing must not read as a clean run."""
    _fake_cli(monkeypatch, engine_log="", logs_tail="")

    rc = ei.run(_spec(), "/models/smoke", 9999, "llgenie-smoke-vllm-cpu", tmp_path, wait=0)

    out = capsys.readouterr().out
    assert rc == 1
    assert "EMPTY/absent" in out, (
        f"an engine that produced no output must be named as such: {out!r}")
