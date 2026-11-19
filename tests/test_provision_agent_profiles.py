#!/usr/bin/env python3
"""Hermetic tests for scripts/provision_agent_profiles.py (issue #2165).

The gate is the point: provisioning every lane's `agents/<profile>/` into its
Hermes home must be idempotent, must leave a profile's own files (memory,
state.db, .env, live-only skills) untouched, must have NO delete path, and the
post-provision comparison must FAIL when any provisioned file differs (naming
profile + path) and GREEN after a re-provision. All tests run against a
temporary home, never a live ~/.hermes profile.

The negative control is the acceptance criterion exactly: provision into $TMPH,
mutate one file, prove `--check` reddens, re-provision, prove it greenns.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from conftest import makefiles_text  # noqa: E402  (the include-resolving Makefile reader)

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "provision_agent_profiles.py"


def _run(dest, *flags):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--dest", str(dest), *flags],
        capture_output=True,
        text=True,
        env={**os.environ, "HERMES_PROFILE_HOME": str(dest / "llgenie-tester")},
        timeout=180,
    )


def _profiles_count():
    import json  # noqa: PLC0415
    m = json.loads((REPO / "agents" / "manifest.json").read_text())
    return len(m["profiles"])


def _make_seam(dest, *flags):
    """Run the REAL make target the rebuild invokes (the wiring, not the script)."""
    env_flags = " ".join(f"{f}" for f in flags)  # CHECK=1 style
    cmd = f"make -C {REPO} provision-agent-profiles DEST={dest} {env_flags}"
    return subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True,
                          env={**os.environ, "HERMES_PROFILE_HOME": str(dest / "llgenie-tester")},
                          timeout=300)


def test_make_seam_provisions_and_gates(tmp_path):
    # The AC "wired where install/setup runs, so a rebuild cannot skip it": the
    # actual make target (which `install` depends on), not just the script.
    n = _profiles_count()
    r = _make_seam(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert len([p for p in tmp_path.iterdir() if p.is_dir()]) == n
    gate = _make_seam(tmp_path, "CHECK=1")
    assert gate.returncode == 0, gate.stdout + gate.stderr
    # negative control through the seam: a removed SOUL.md reds the make gate
    (tmp_path / "llgenie-tester" / "SOUL.md").unlink()
    red = _make_seam(tmp_path, "CHECK=1")
    assert red.returncode != 0
    assert "llgenie-tester" in (red.stdout + red.stderr)


def test_install_invokes_provisioning(tmp_path):
    # The real wiring: `make install` depends on `provision-agent-profiles`.
    mk = makefiles_text(REPO)  # `install:` now lives behind `include mk/install.mk` (#2461)
    assert "install: bash-check venv-install engine-launchers link test-built-engine smoke provision-agent-profiles" in mk


def test_provisions_every_lane_and_is_idempotent(tmp_path):
    n = _profiles_count()
    r1 = _run(tmp_path)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    lanes = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(lanes) == n, (len(lanes), n)
    # every lane got a SOUL.md (behaviour, not empty)
    for lane in lanes:
        assert (lane / "SOUL.md").exists(), lane
    # a second provision is a no-op: identical output tree, rc 0
    before = {p.name: (p / "SOUL.md").read_bytes() if (p / "SOUL.md").exists() else b""
              for p in lanes}
    r2 = _run(tmp_path)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    for lane in lanes:
        assert (lane / "SOUL.md").read_bytes() == before[lane.name]


def test_fresh_empty_home_matches_tree_exactly_after_provision(tmp_path):
    r = _run(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    gate = _run(tmp_path, "--check")
    assert gate.returncode == 0, gate.stdout + gate.stderr


def test_every_lane_home_carries_the_base_model_chain(tmp_path):
    """Issue #2929: the provisioner lands agents/hermes-base-config.yaml, through the seam,
    into EVERY lane profile's config.yaml — identical chain in all of them, read back."""
    import json  # noqa: PLC0415
    import yaml  # noqa: PLC0415
    dest = tmp_path / "profiles"
    r = _run(dest)
    assert r.returncode == 0, r.stderr
    names = [p["name"] for p in json.loads((REPO / "agents" / "manifest.json").read_text())["profiles"]]
    for name in names:
        cfg = dest / name / "config.yaml"
        assert cfg.is_file(), f"{name} has no config.yaml — the chain did not land"
        data = yaml.safe_load(cfg.read_text())
        assert data["model"]["default"] == "meituan/longcat-2.5:free"
        assert data["model"]["aliases"]["nous-longcat"]["model"] == "meituan/longcat-2.5:free"
        order = [e["model"] for e in data["fallback_providers"]]
        assert order[-1] == "deepseek/deepseek-v4-flash-0731", f"{name}: {order}"
    assert "carry the base chain" in r.stdout, r.stdout


def test_a_lane_chain_mutation_reddens_the_check_and_reprovision_greens(tmp_path):
    """Negative control (the AC exactly): mutate one lane's model id in its home config,
    `--check` reddens naming CHAIN FAIL + the lane; a re-provision restores the ONE home's chain."""
    import json  # noqa: PLC0415
    import yaml  # noqa: PLC0415
    dest = tmp_path / "profiles"
    assert _run(dest).returncode == 0
    name = json.loads((REPO / "agents" / "manifest.json").read_text())["profiles"][0]["name"]
    cfg = dest / name / "config.yaml"
    data = yaml.safe_load(cfg.read_text())
    data["model"]["aliases"]["nous-longcat"]["model"] = "meituan/longcat-2.4:free"
    cfg.write_text(yaml.safe_dump(data))

    r = _run(dest, "--check")
    assert r.returncode != 0, "a drifted lane chain must redden the provision gate"
    assert "CHAIN FAIL" in r.stderr, r.stderr
    assert name in r.stderr, r.stderr

    assert _run(dest).returncode == 0, "re-provision must restore the chain"
    restored = yaml.safe_load(cfg.read_text())["model"]["aliases"]["nous-longcat"]["model"]
    assert restored == "meituan/longcat-2.5:free"


def test_gate_reds_on_mutation_and_greens_after_reprovision(tmp_path):
    # The rebuild case: a profile whose tree-carried SOUL.md is MISSING (a fresh
    # or partial home — the exact silent failure #2165 exists for, since a missing
    # SOUL.md produces no error) must red the gate and be restored by provisioning.
    _run(tmp_path)
    target = tmp_path / "llgenie-tester" / "SOUL.md"
    orig = target.read_bytes()
    target.unlink()  # simulate the "home started without the tree's SOUL.md" case
    red = _run(tmp_path, "--check")
    assert red.returncode != 0, "gate must red on a missing tree-carried file"
    assert "llgenie-tester" in (red.stdout + red.stderr)
    assert "SOUL.md" in (red.stdout + red.stderr)
    # re-provisioning restores the missing file and the gate turns green.
    _run(tmp_path)
    green = _run(tmp_path, "--check")
    assert green.returncode == 0, green.stdout + green.stderr
    assert (tmp_path / "llgenie-tester" / "SOUL.md").read_bytes() == orig


def test_live_only_edit_stays_a_finding_not_silently_overwritten(tmp_path):
    # A profile file carrying a line that exists ONLY in the live copy is a
    # finding, never something provisioning silently re-takes: re-provisioning
    # must NOT delete that line, and the gate keeps it red until deliberately merged.
    _run(tmp_path)
    target = tmp_path / "llgenie-tester" / "SOUL.md"
    with open(target, "a") as fh:
        fh.write("\n# live-only line that the tree does not carry\n")
    # re-provisioning is refused for this file (a live-only edit is protected)
    _run(tmp_path)
    assert "# live-only line that the tree does not carry" in target.read_text()
    # the gate stays red: the profile diverges from the tree on a live-only edit
    red = _run(tmp_path, "--check")
    assert red.returncode != 0, "a live-only edit is a finding, not silently re-taken"


def test_profile_own_files_survive_provisioning(tmp_path):
    _run(tmp_path)
    i_am = tmp_path / "llgenie-tester"
    (i_am / ".env").write_text("GITHUB_TOKEN=redacted")
    live_skill = i_am / "skills" / "live-only-skill" / "SKILL.md"
    live_skill.parent.mkdir(parents=True, exist_ok=True)
    live_skill.write_text("# a live-only skill, never in the tree\n")
    _run(tmp_path)  # provisioning again must not touch them
    assert (i_am / ".env").read_text() == "GITHUB_TOKEN=redacted"
    assert (i_am / "skills" / "live-only-skill" / "SKILL.md").exists()


def test_no_delete_path(tmp_path):
    # a provisioned file that is later NOT in the tree is never deleted by
    # provisioning (the copy is one-way, tree is source; deletion is never a lane's act)
    _run(tmp_path)
    kept = tmp_path / "llgenie-tester" / "skills" / "keep-me" / "SKILL.md"
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.write_text("# keep me\n")
    _run(tmp_path)
    assert kept.exists(), "provisioning must never delete a live-only file"
    # and it is NOT reported as a tree match (it's a live-only finding), i.e.
    # --check does not fail on a *superset* — agent_profile_sync's check is
    # one-way (tree files must match); a live-only extra is a finding, not a red.
    gate = _run(tmp_path, "--check")
    assert gate.returncode == 0, gate.stdout + gate.stderr


# ---- --resolve: copied is not loadable (issue #2669) -------------------------------------------

def _prov():
    import scripts.provision_agent_profiles as prov  # noqa: PLC0415  (the real seam)
    return prov


def test_tree_skill_names_reads_every_skill_the_lane_carries():
    """The resolution proof's denominator is the TREE — but the skills Hermes can actually
    resolve from that tree on this platform (measured against the CLI, issue #2836): hidden
    trees (`.archive/…`) are skipped by Hermes' loader and macOS-only skills are hidden on
    Linux, so demanding either would make the proof un-green forever; and the identity is the
    frontmatter `name` Hermes' table shows, not the directory name. The planner's
    orchestration skill — present in the tree yet unresolvable in the live profile when #2669
    was filed — must still be named by this function."""
    prov = _prov()
    names = prov.tree_skill_names(REPO / "agents", "llgenie-planner")
    assert names, "the planner lane's tree carries SKILL.md files; the seam must enumerate them"
    assert any("orchestration" in n for n in names), names
    # archived trees are not carried fleet behaviour: the loader skips hidden directories.
    assert "tar-gpg" not in names and "browser-drm" not in names, names
    # a macOS-only skill is not carried by a proof that runs on Linux.
    assert "apple-notes" not in names and "imessage" not in names, names
    # identity is the skill's own frontmatter name.
    assert "pi" in names, names  # dir pi-delegate declares `name: pi`
    assert "vault-cron-workflow" in names, names  # dir obsidian-vault-automation
    assert "pi-delegate" not in names and "obsidian-vault-automation" not in names, names
    # an environments-gated skill the fleet never activates is not demanded (sdlc-review, #2836).
    assert "sdlc-review" not in names, names


def test_environment_gated_skill_is_carried_only_where_the_environment_is_active(tmp_path, monkeypatch):
    """`environments:` is a relevance gate resolved against the runtime context: a kanban-only
    skill is invisible to a fleet profile listing (kanban never activates there) but demanded
    when the kanban context IS active; an unknown tag fails open exactly like Hermes' detector."""
    prov = _prov()
    agents = tmp_path / "agents"
    kb = agents / "lane" / "skills" / "kanban-only" / "SKILL.md"
    kb.parent.mkdir(parents=True)
    kb.write_text("---\nname: kanban-only\ndescription: x\nenvironments:\n  - kanban\n---\n# x\n")
    unknown = agents / "lane" / "skills" / "anywhere-tag" / "SKILL.md"
    unknown.parent.mkdir(parents=True)
    unknown.write_text("---\nname: anywhere-tag\ndescription: x\nenvironments: [totally-unknown]\n---\n# x\n")
    monkeypatch.delenv("HERMES_KANBAN_TASK", raising=False)
    monkeypatch.delenv("HERMES_KANBAN_BOARD", raising=False)
    assert prov.tree_skill_names(agents, "lane") == ["anywhere-tag"]
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "1")
    assert prov.tree_skill_names(agents, "lane") == ["anywhere-tag", "kanban-only"]


def test_no_lane_tree_carries_a_kanban_gated_skill():
    """A skill gated `environments: [kanban]` is hidden from every fleet profile listing: fleet
    provisioning writes no profile toolset config and AGENTS.md bars kanban lanes on the host, so
    a lane carrying one carries behaviour the fleet can never activate — the agent image build
    failed on exactly this (planner's devops/sdlc-review, issue #2836). The tree rejects it."""
    prov = _prov()
    offenders = [
        str(md.relative_to(REPO / "agents"))
        for lane_dir in sorted((REPO / "agents").iterdir())
        if (base := lane_dir / "skills").is_dir()
        for md in base.rglob("SKILL.md")
        if not any(p.startswith(".") for p in md.relative_to(base).parts)
        and "kanban" in prov._environments_gate(md)
    ]
    assert not offenders, f"lanes carrying kanban-gated skills: {offenders}"


def test_hidden_skill_trees_are_not_carried_behaviour(tmp_path):
    """`.archive/` (or any dot-directory) under a lane's skills is invisible to Hermes' loader;
    the proof must not count it (issue #2836: 24 archived planner skills made the agent image
    build un-green)."""
    prov = _prov()
    agents = tmp_path / "agents"
    live = agents / "lane" / "skills" / "live-skill" / "SKILL.md"
    live.parent.mkdir(parents=True)
    live.write_text("# live\n")
    archived = agents / "lane" / "skills" / ".archive" / "old-skill" / "SKILL.md"
    archived.parent.mkdir(parents=True)
    archived.write_text("# old\n")
    assert prov.tree_skill_names(agents, "lane") == ["live-skill"]


def test_platform_gated_skill_is_carried_only_on_a_matching_platform(tmp_path):
    """A skill whose frontmatter `platforms:` excludes this OS is hidden by Hermes on purpose:
    the proof skips it here but must carry it when the gate names this platform."""
    prov = _prov()
    agents = tmp_path / "agents"
    gated = agents / "lane" / "skills" / "mac-only" / "SKILL.md"
    gated.parent.mkdir(parents=True)
    gated.write_text("---\nname: mac-only\ndescription: x\nplatforms: [macos]\n---\n# x\n")
    ok = agents / "lane" / "skills" / "everywhere" / "SKILL.md"
    ok.parent.mkdir(parents=True)
    ok.write_text("---\nname: everywhere\ndescription: x\nplatforms: [linux, macos, windows]\n---\n# x\n")
    assert prov.tree_skill_names(agents, "lane") == ["everywhere"]
    assert prov._platform_carried({"platforms": "[macos]"}) is (prov._CURRENT_PLATFORM == "macos")
    assert prov._platform_carried({}) is True


def test_no_lane_tree_carries_the_same_skill_identity_twice():
    """Hermes resolves a lane's skills by identity; two trees with the same frontmatter name
    collide, and Hermes surfaces one as a category-qualified label (`software-development/…`)
    which the resolution table proof cannot match — a data defect, exactly the one that broke
    the agent image build in issue #2836 (a flattened root copy beside its category copy)."""
    prov = _prov()
    offenders = []
    for lane_dir in sorted((REPO / "agents").iterdir()):
        base = lane_dir / "skills"
        if not base.is_dir():
            continue
        from collections import Counter
        counter = Counter()
        for md in base.rglob("SKILL.md"):
            if any(part.startswith(".") for part in md.relative_to(base).parts):
                continue
            fm = prov.frontmatter(md) or {}
            if not prov._platform_carried(fm):
                continue
            counter[fm.get("name") or md.parent.name] += 1
        dupes = sorted(n for n, c in counter.items() if c > 1)
        if dupes:
            offenders.append((lane_dir.name, dupes))
    assert not offenders, f"lanes carrying a duplicate skill identity: {offenders}"


def test_resolve_reports_every_tree_skill_the_lister_does_not_resolve(tmp_path):
    """resolve_skills pairs (lane, skill) for each tree skill absent from the lane's resolved
    list; a lister that resolves everything returns []. This is the exact red/green pair the
    agent image build relies on."""
    prov = _prov()
    agents = tmp_path / "agents"
    for skill in ("alpha-skill", "beta-skill"):
        p = agents / "lane" / "skills" / skill / "SKILL.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# rule\n")
    assert prov.resolve_skills(agents, ["lane"], lambda n: "alpha-skill") == [("lane", "beta-skill")]
    assert prov.resolve_skills(agents, ["lane"],
                               lambda n: "alpha-skill\nbeta-skill") == []


def test_elided_table_names_count_as_resolved():
    """`hermes skills list` elides long names at its column width; a prefix + ellipsis is a hit.
    A near-match that is NOT a prefix-ellipsis (a different skill sharing the stem) is not."""
    prov = _prov()
    assert prov._skill_resolved("│ containerized-repo-… │", "containerized-repo-maintainer")
    assert not prov._skill_resolved("containerized-other-maintainer", "containerized-repo-maintainer")
    assert not prov._skill_resolved("", "containerized-repo-maintainer")


def test_cli_resolve_greens_when_every_lane_skill_resolves(tmp_path, monkeypatch, capsys):
    """In-process CLI run against the REAL tree with an injected lister that resolves every tree
    skill: rc 0 and the resolve line prints. The agent image build invokes exactly this path."""
    prov = _prov()
    agents = REPO / "agents"
    monkeypatch.setattr(prov, "hermes_lane_skills",
                        lambda name: "\n".join(prov.tree_skill_names(agents, name)))
    rc = prov.main(["--root", str(REPO), "--dest", str(tmp_path), "--resolve"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "resolve: every skill" in out


def test_cli_resolve_reds_when_a_lane_skill_is_unresolved(tmp_path, monkeypatch, capsys):
    """A lane whose skills never resolve (the state the Dockerfile `cp -r` loop could ship):
    rc 1, naming the lane and the skill — never a silent pass."""
    prov = _prov()
    monkeypatch.setattr(prov, "hermes_lane_skills", lambda name: "")
    rc = prov.main(["--root", str(REPO), "--dest", str(tmp_path), "--resolve"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "RESOLVE FAIL" in err
    assert "orchestration" in err  # a real planner tree skill the empty lister cannot resolve


def test_cli_resolve_aborts_when_the_resolver_is_missing(tmp_path, monkeypatch, capsys):
    """No hermes CLI means no proof: exit 2 naming the cause, never a skipped proof that looks
    green (the same no-silent-pass contract the gate uses for a missing manifest)."""
    prov = _prov()
    monkeypatch.setattr(prov.shutil, "which", lambda p: None)
    rc = prov.main(["--root", str(REPO), "--dest", str(tmp_path), "--resolve"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "hermes CLI" in err


def test_agent_image_installs_lanes_through_this_seam_not_a_private_copy():
    """#2669's core claim, checked in the repo: the agent image's lane install RUNS this seam
    with --resolve, the seam + its imported modules are hashed image inputs (a change to the
    installer moves the image tag), and the private inline `cp -r` loop is gone from the Dockerfile's
    executable lines."""
    import scripts.ci_images as ci  # noqa: PLC0415

    df = (REPO / "containers" / "agent" / "Dockerfile").read_text()
    live = [ln for ln in df.splitlines() if not ln.strip().startswith("#")]
    live_text = "\n".join(live)
    assert "provision_agent_profiles.py" in live_text and "--resolve" in live_text
    assert "cp -r" not in live_text, "the second install path must not survive in the image"
    for script in ("scripts/provision_agent_profiles.py", "scripts/agent_profile_sync.py",
                   "scripts/check_agent_profiles.py"):
        assert script in ci.IMAGES["agent"][1], f"{script} must be a hashed agent-image input"
    assert "scripts/agent_lanes_check.py" in ci.IMAGES["agent"][1]
