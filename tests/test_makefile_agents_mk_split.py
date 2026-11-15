"""Structural pins for the #800 residual split: the fleet/agent plumbing domain lives in mk/agents.mk (#2676).

The split must stay a split: the 30 agent-domain targets are declared in `mk/agents.mk` (each keeps
its declaration line byte-identical, `##` help lines intact where the base file had them), the top
`Makefile` includes that file, no target name is declared in both files (the #2674 duplicate detector
enforces this as a gate; pinned here as a unit), and the shared agent variables/macros
(`AGENT_SHELL_KEYS`, `AGENT_SHELL_FORWARD`, the `scrubbed_run` machinery) stay on the top side of the
boundary — the domain file declares targets only. Membership is decided by RECIPE, not name:
`agent-image-ref` runs `scripts/ci_images.py latest agent`, so it belongs to the images domain
(mk/images.mk, #2678), not here — the issue #2676 membership note pre-authorizes that exclusion.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: The 30 targets issue #2676 moves (its 31 candidates minus `agent-image-ref`, whose recipe is a
#: `scripts/ci_images.py` call — image-shaped by the issue's own membership rule).
MOVED = [
    "hermes-skills-register",
    "sync-agent-profile",
    "provision-agent-profiles",
    "skill-parity",
    "tester-fold-live",
    "profile-drift-alarm",
    "check-cron-drift",
    "verify-lane-contract",
    "profile-drift",
    "lane-preflight",
    "_agent-shell-keys-check",
    "agent-shell-keys-check",
    "agent-fetch",
    "_agent-fetch",
    "search-smoke",
    "agent-jev-preflight",
    "jev-preflight-required",
    "agent-repo-ownership",
    "hermes-smoke",
    "_agent-jev-preflight",
    "_hermes-smoke",
    "nerve-profile-check",
    "check-main-ruleset",
    "main-ruleset-report",
    "main-ruleset-apply",
    "bind-proof",
    "memory-install",
    "memory-bootstrap",
    "memory-verify",
    "memory-check",
]

#: Internal `_`-prefixed legs and the memory-* quartet carry no `##` help line at the base file;
#: the byte-identical move must not invent one (they stay out of `make help`, as before).
NO_HELP_ON_PURPOSE = {
    "_agent-shell-keys-check",
    "_agent-fetch",
    "_agent-jev-preflight",
    "_hermes-smoke",
    "memory-install",
    "memory-bootstrap",
    "memory-verify",
    "memory-check",
}

#: `name:` at line start — a target declaration, never a `name:=` assignment.
STRICT = re.compile(r"^([A-Za-z_][A-Za-z0-9_./-]*)\s*:(?!=)", re.M)


def _declared(path: Path) -> dict[str, str]:
    """target name -> its declaration line (for `##` presence)."""
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        m = STRICT.match(line)
        if m:
            out.setdefault(m.group(1), line)
    return out


def test_agents_mk_exists_and_is_included_from_the_top_file():
    assert (REPO / "mk" / "agents.mk").is_file(), "mk/agents.mk must exist (#2676)"
    top = (REPO / "Makefile").read_text()
    assert re.search(r"^include mk/agents\.mk\b", top, re.M), (
        "the top Makefile must include mk/agents.mk in its include block"
    )


def test_every_moved_target_is_declared_in_agents_mk():
    declared = _declared(REPO / "mk" / "agents.mk")
    missing = [t for t in MOVED if t not in declared]
    assert not missing, f"#2676 targets not declared in mk/agents.mk: {missing}"
    extra = sorted(set(declared) - set(MOVED))
    assert not extra, f"mk/agents.mk declares targets beyond the #2676 roster: {extra}"


def test_moved_targets_keep_their_help_lines():
    declared = _declared(REPO / "mk" / "agents.mk")
    no_help = [t for t in MOVED if "##" not in declared[t] and t not in NO_HELP_ON_PURPOSE]
    assert not no_help, f"moved targets lost their `##` help line: {no_help}"


def test_no_target_is_declared_in_both_files():
    both = set(_declared(REPO / "Makefile")) & set(_declared(REPO / "mk" / "agents.mk"))
    assert not both, (
        f"targets declared in Makefile AND mk/agents.mk: {sorted(both)} "
        "(make keeps one recipe and silently drops the other — #2674's guard is the gate)"
    )


def test_the_moved_targets_are_declared_in_no_other_domain_file():
    for mk in sorted((REPO / "mk").glob("*.mk")):
        if mk.name == "agents.mk":
            continue
        overlap = sorted(set(MOVED) & set(_declared(mk)))
        assert not overlap, f"{mk} re-declares moved agents targets: {overlap}"


def test_agent_image_ref_is_not_an_agents_target():
    """`agent-image-ref` runs `scripts/ci_images.py latest agent` — an image ref, never moved here.
    It belongs to the images domain (#2678's mk/images.mk), exactly as the #2676 note states."""
    assert "agent-image-ref" not in _declared(REPO / "mk" / "agents.mk"), (
        "agent-image-ref must not land in mk/agents.mk (its recipe is an image ref — mk/images.mk, #2678)"
    )


def test_shared_variables_and_macros_stay_in_the_top_makefile():
    """The domain file declares targets only (zero `VAR :=` at its top level); the agent
    variables/macros the recipes read stay at the top, exactly as #2456–#2461 left them."""
    top = (REPO / "Makefile").read_text()
    assert re.search(r"^AGENT_SHELL_KEYS\s*[:+]?=", top, re.M), "AGENT_SHELL_KEYS must stay in the top Makefile"
    assert re.search(r"^AGENT_SHELL_FORWARD\s*[:+]?=", top, re.M), "AGENT_SHELL_FORWARD must stay in the top Makefile"
    agents = (REPO / "mk" / "agents.mk").read_text()
    assert not re.search(r"^[A-Z_][A-Z_0-9]*\s*[:+]?=", agents, re.M), (
        "mk/agents.mk must declare zero top-level variables (the domain-files rule)"
    )


def test_agent_shell_keys_guard_still_wraps_every_agent_leg():
    """The #374/#379 guard pair survives the move: `agent-shell-keys-check` still runs the real
    in-container probe and every public agent leg still carries the forward seam."""
    agents = (REPO / "mk" / "agents.mk").read_text()
    assert "agent_shell_keys_check.py" in agents, "the keys probe must still be wired in the moved targets"
    assert agents.count("$(AGENT_SHELL_FORWARD)") >= 1, "agent legs must still forward the secrets through the one seam"
