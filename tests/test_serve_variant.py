"""make serve-variant starts one built binary on its own port.

Locks the scenario "a second variant server does not take another server's port"
in openspec/changes/feat-server-clone-build/specs/llama-server-build/spec.md.
"""
from __future__ import annotations

import json
import socket

import scripts.serve_variant as sv


def test_free_port_is_bindable_and_not_a_chosen_busy_port():
    """PORT omitted picks a port the caller can bind."""

    # Given a port that is already taken
    busy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    busy.bind(("127.0.0.1", 0))
    busy.listen(1)
    taken = busy.getsockname()[1]

    # When a free port is chosen
    port = sv.free_port()

    # Then it is a different port and can be bound
    assert port != taken
    assert sv.port_is_free(port)
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", port))
    probe.close()
    busy.close()


def test_taken_port_is_reported_not_free():
    """An explicit PORT that is in use is refused."""

    # Given a listening socket
    busy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    busy.bind(("127.0.0.1", 0))
    busy.listen(1)
    taken = busy.getsockname()[1]

    # When the port is checked
    free = sv.port_is_free(taken)

    # Then it is not free, so the target will not bind over it
    assert free is False
    busy.close()


def test_serve_argv_uses_the_given_port_and_omits_n_gpu_layers_by_default():
    """llama-server's own default decides whether a GPU is used."""

    # Given a built binary, the 0.5B model, and a chosen port
    binary = "/opt/llama-server"
    model = "/models/qwen.gguf"

    # When the launch command is built with no NGL override
    cmd = sv.serve_argv(binary, model, 18080)

    # Then it binds that port and does not pass --n-gpu-layers
    assert cmd[cmd.index("--port") + 1] == "18080"
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"
    assert "--n-gpu-layers" not in cmd
    assert cmd[cmd.index("-m") + 1] == model


def test_stop_signals_only_the_recorded_pid(tmp_path, monkeypatch):
    """Stopping a variant does not look for other llama-server processes."""

    # Given a recorded variant pid
    state = tmp_path / "serve-prism-cuda.json"
    state.write_text(json.dumps({"pid": 4242, "port": 49217}))
    signaled = []
    monkeypatch.setattr(sv, "_alive", lambda pid: pid == 4242 and not signaled)

    def _kill(pid, sig):
        signaled.append((pid, sig))

    # When the recorded server is stopped
    result = sv.stop_recorded(state, kill=_kill)

    # Then only that pid is signaled and the state file is removed
    assert result["stopped"] is True
    assert signaled[0][0] == 4242
    assert not state.exists()



