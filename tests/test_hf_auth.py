"""Every Hugging Face call sends the repo token (issue #153).

The token is the environment, else the HF_TOKEN= line in ~/.zshrc or ~/.bashrc.
CI injects the Actions secret as HF_TOKEN. A non-Hub URL never receives it.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import yaml

import scripts.hf_auth as auth
import scripts.install_engine_launchers as il

REPO = Path(__file__).resolve().parent.parent


def test_env_token_is_sent_only_to_the_hub(monkeypatch):
    """A bearer token goes on Hub requests and nowhere else."""

    # Given a token in the environment and none in a login rc
    monkeypatch.setenv("HF_TOKEN", "hf_envtoken")
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)

    # When requests are built for the Hub and for GitHub
    hub = auth.authorize(urllib.request.Request("https://huggingface.co/api/models?search=qwen"))
    other = auth.authorize(urllib.request.Request("https://github.com/asimov-agent/llgenie"))

    # Then only the Hub request carries the bearer token
    assert hub.get_header("Authorization") == "Bearer hf_envtoken"
    assert other.get_header("Authorization") is None


def test_bashrc_token_is_used_when_the_environment_is_empty(monkeypatch, tmp_path):
    """The login rc fills the token when CI and the shell did not export it."""

    # Given no token in the environment and HF_TOKEN= in ~/.bashrc
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".bashrc").write_text('export PATH="$HOME/bin:$PATH"\nexport HF_TOKEN="hf_fromrc"\n')

    # When the token is resolved and applied to a child environment
    child = {}
    auth.apply_env(child)

    # Then the rc value is what the hf CLI would see
    assert auth.hf_token() == "hf_fromrc"
    assert child["HF_TOKEN"] == "hf_fromrc"
    assert child["HUGGING_FACE_HUB_TOKEN"] == "hf_fromrc"


def test_start_scripts_forward_hf_token():
    """Engine containers receive HF_TOKEN, loaded from the rc when unset."""

    # Given a generated engine start script and the llama-server shim
    body = il.launcher("ollama", "cpu", "t", "/m")
    shim = il.llama_server_shim("t", "cpu")

    # When their docker run lines are read
    # Then both load the rc if HF_TOKEN is empty and pass -e HF_TOKEN (value not on argv)
    for script in (body, shim):
        assert 'for _ll_rc in "$HOME/.zshrc" "$HOME/.bashrc"' in script
        assert "-e HF_TOKEN" in script
        assert "hf_" not in script


def test_workflows_inject_the_actions_secret():
    """Every workflow that can call the Hub exports the HF_TOKEN secret."""

    # Given the CI workflows
    names = ("ci.yml", "pipeline.yml", "published.yml", "engine-bump.yml", "registry-sync.yml")
    docs = {name: yaml.safe_load((REPO / ".github" / "workflows" / name).read_text()) for name in names}

    # When their workflow env and reusable-workflow calls are read
    # Then each workflow sets HF_TOKEN from the Actions secret
    for name, doc in docs.items():
        assert doc["env"]["HF_TOKEN"] == "${{ secrets.HF_TOKEN }}", name

    # And the reusable workflows are given that secret
    ci = docs["ci.yml"]["jobs"]
    for job in ("linux", "macos", "linux-published"):
        assert ci[job]["secrets"] == "inherit", job
