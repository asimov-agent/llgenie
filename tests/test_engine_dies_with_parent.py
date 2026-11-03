#!/usr/bin/env python3
"""An engine container started for a test dies when that test exits (issue #1669).

The generated launcher backgrounds `docker run`. A non-interactive shell does not
SIGHUP that job when it exits, so the container used to stay up after the test.
The launcher now watches its parent and removes the container when the parent is
gone. A pytest session removes only the `llgenie-*` containers that appeared
during the session.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
import textwrap
import time

import scripts.install_engine_launchers as iel


def test_generated_launchers_die_when_their_parent_exits():
    """Both start scripts watch the parent and remove `$name` on the way out."""

    # Given a generated engine launcher and the llama-server shim
    launcher = iel.launcher("llama.cpp", "cuda", "llgenie/llama-cpp:test", "/models")
    shim = iel.llama_server_shim("llgenie/llama-cpp:test", "cpu")

    # When their cleanup is read
    # Then each watches the parent that started it and removes the named container
    for body in (launcher, shim):
        assert 'kill -0 "$parent"' in body, body
        assert '[ "$now" != "$parent" ]' in body, body
        assert 'kill -TERM "$self"' in body, body
        assert 'rm -f "$name"' in body, body
        assert "EXIT INT TERM HUP" in body, body
        assert 'wait "$child"' in body, body


def test_a_backgrounded_launcher_removes_its_container_when_the_parent_exits(tmp_path):
    """The parent shell exits. The launcher must follow and `docker rm` the container."""

    # Given a launcher whose docker is a log, and a parent that backgrounds it and exits
    log = tmp_path / "docker.log"
    docker = tmp_path / "docker"
    docker.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$DOCKER_LOG\"\n")
    docker.chmod(docker.stat().st_mode | stat.S_IEXEC)
    script = tmp_path / "llgenie-engine-demo"
    watch = iel.die_when_parent_dies("docker", interval="0.1")
    script.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        "name=llgenie-demo-9\n"
        + watch
        + "sleep 30 &\n"
        + "child=$!\n"
        + "wait \"$child\"\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
    env["DOCKER_LOG"] = str(log)

    # When a parent starts the launcher, lets it record that parent, then exits
    starter = textwrap.dedent(f"""\
        import os, subprocess, time
        subprocess.Popen([{str(script)!r}], env=os.environ,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.3)
        os._exit(0)
        """)
    parent = subprocess.run(
        [sys.executable, "-c", starter],
        env=env, check=False, timeout=5,
    )
    assert parent.returncode == 0

    # Then the launcher removes the container instead of leaving it running
    deadline = time.time() + 4
    seen = ""
    while time.time() < deadline:
        seen = log.read_text() if log.exists() else ""
        if "rm -f llgenie-demo-9" in seen:
            return
        time.sleep(0.05)
    raise AssertionError(f"container was not removed: {seen!r}")


def test_pytest_removes_only_containers_the_session_started():
    """A server that was already up stays up. One the session created is removed."""

    # Given one container from before the session and one the session started
    def run(args, **kw):
        if args[:3] == ["docker", "ps", "-aq"]:
            return subprocess.CompletedProcess(args, 0, stdout="already\nstarted-here\n")
        removed.append(args)
        return subprocess.CompletedProcess(args, 0)

    removed: list = []

    # When the session finishes
    gone = iel.stop_new_engine_containers({"already"}, run=run)

    # Then only the container this session started is removed
    assert gone == ["started-here"]
    assert removed == [["docker", "rm", "-f", "started-here"]]
