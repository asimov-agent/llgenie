"""Issue #2836: the published agent image froze 2025 snapshots of its upstreams.

Hermetic pins for the four chain corrections that keep the published image
current at build time: the docker CLI stage, the Python build-toolchain
upgrade, the apt upgrade of inherited debs, and the Hermes install args that
keep the unused browser/computer-use toolchains out of the published image.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEST_DOCKERFILE = REPO / "containers" / "test" / "Dockerfile"
AGENT_DOCKERFILE = REPO / "containers" / "agent" / "Dockerfile"
INSTALL_SCRIPT = REPO / "scripts" / "install_hermes_ci.sh"


def test_test_image_docker_cli_is_current():
    # Given the test image's Dockerfile
    text = TEST_DOCKERFILE.read_text(encoding="utf-8")

    # When the docker CLI COPY stages are read
    copies = re.findall(r"COPY --from=(docker:\S+) ", text)

    # Then both copies pin the current CLI stage and the superseded one is gone
    assert copies == ["docker:29-cli", "docker:29-cli"], text
    assert "docker:27-cli" not in text


def test_test_image_upgrades_build_toolchain():
    # Given the test image's pip layers, in build order
    text = TEST_DOCKERFILE.read_text(encoding="utf-8")
    upgrade = text.find("pip install --no-cache-dir --upgrade pip setuptools wheel")
    lock = text.find("-r /tmp/requirements.txt")

    # Then the toolchain upgrade lands before the locked install
    assert upgrade != -1, "the test image must upgrade pip/setuptools/wheel"
    assert lock != -1 and upgrade < lock, "the upgrade must precede the locked install"


def test_agent_apt_layer_upgrades_inherited_debs():
    # Given the agent image's runtime apt layer
    text = AGENT_DOCKERFILE.read_text(encoding="utf-8")
    m = re.search(r"apt-get update; \\\s*\n(?:.*\n)*?\s*apt-get install", text)

    # Then the layer upgrades inherited debs between update and install
    assert m, "no apt update->install layer found"
    assert "apt-get upgrade -y" in m.group(0), m.group(0)


def test_hermes_install_skips_unused_toolchains():
    # Given the agent image's Hermes install args
    text = AGENT_DOCKERFILE.read_text(encoding="utf-8")
    arg = re.search(r'ARG HERMES_INSTALL_ARGS="([^"]*)"', text)
    env = re.search(r"^ENV HERMES_INSTALL_URL=.*?(?:\n.*?)*?HERMES_INSTALL_ARGS",
                    text, re.M)

    # Then the default skips both toolchains and the env exports it to the install step
    assert arg and "--skip-browser" in arg.group(1) and "--skip-computer-use" in arg.group(1), \
        "the published image must default to skipping the unused toolchains"
    assert env, "HERMES_INSTALL_ARGS must reach the install step via ENV"


def test_install_script_forwards_hermes_args():
    # Given the CI Hermes install seam
    text = INSTALL_SCRIPT.read_text(encoding="utf-8")

    # Then the installer receives the forwarded flag list
    assert re.search(r"bash -s -- \$\{HERMES_INSTALL_ARGS:-\}", text), \
        "install_hermes_ci.sh must forward HERMES_INSTALL_ARGS to install.sh"


def test_agent_image_stages_profile_import_chain():
    """check_agent_profiles.py imports frontmatter() from check_agent_skills.py at import time,
    and the agent image's build-time provisioning step imports that chain transitively. The
    module must be a hashed build input AND COPY'd into the image's bin dir, or the provisioning
    step dies with ModuleNotFoundError (the latent main breakage issue #2836 caught)."""
    import scripts.ci_images as ci_images  # noqa: PLC0415  (the real seam)

    staged = {p.name for p in ci_images.inputs("agent", REPO)}
    assert "check_agent_skills.py" in staged, sorted(staged)

    text = AGENT_DOCKERFILE.read_text(encoding="utf-8")
    assert re.search(
        r"COPY check_agent_skills\.py /opt/llgenie/bin/check_agent_skills\.py", text
    ), "the Dockerfile must COPY check_agent_skills.py beside the other profile modules"
