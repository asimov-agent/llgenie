#!/usr/bin/env python3
"""The weekly catalog check keeps the Hermes model chain honest (issue #2930).

`check_agent_model_catalog.py` reads the chain from `agents/hermes-base-config.yaml`,
compares it with a Nous catalog payload, and files ONE deduped issue on drift. The
catalog endpoint and `gh` are external systems: the tests drive the REAL
`chain_members`/`compare`/`issue_text`/filing code over fixtures with `gh` replaced by a
recording function, and the fetch is proven hermetic with a replaced `urlopen`. No test
touches the network.
"""
from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
# No sys.path seam here: tests/conftest.py is the ONE import root (issue #796/#1101) — a test file
# inserting scripts/ itself adds a NEW recorded import root and the check-import-roots gate refuses it.

from scripts import check_agent_model_catalog as CAM  # noqa: E402
from scripts import issue_body  # noqa: E402  (the one issue shape, issue #745)

REAL_CONFIG = ROOT / "agents" / "hermes-base-config.yaml"


def _members_from_config(config: Path) -> dict[str, dict]:
    return CAM.chain_members(config)


def _catalog(models: list[dict]) -> Path:
    import tempfile
    path = Path(tempfile.mkdtemp()) / "catalog.json"
    path.write_text(json.dumps({"object": "list", "data": models}), encoding="utf-8")
    return path


def _catalog_for(config_members: dict[str, dict], *, drop: tuple[str, ...] = (),
                 drift: dict[str, int] | None = None) -> list[dict]:
    models = []
    for mid, info in config_members.items():
        if mid in drop:
            continue
        budget = info["budgets"][0][1] if info["budgets"] else 1024
        published = (drift or {}).get(mid, budget)
        models.append({"id": mid, "context_length": published})
    return models


class FakeGh:
    """`gh` replaced by a recorder; the script's filing code stays real."""

    def __init__(self, search_hits=None, existing_body=""):
        self.calls: list[list[str]] = []
        self.search_hits = search_hits or []
        self.existing_body = existing_body
        self.patched: dict[int, str] = {}

    def __call__(self, args: list[str]) -> str:
        self.calls.append(list(args))
        joined = " ".join(args)
        if "search/issues" in joined:
            return json.dumps({"items": self.search_hits})
        if "--jq" in joined and ".body" in joined:
            number = int(args[1].rsplit("/", 1)[-1])
            return self.patched.get(number, self.existing_body)
        if "-X" in args and "PATCH" in args:
            path_arg = next(a for a in args if "/issues/" in a)
            number = int(path_arg.split("/issues/")[1].split("/")[0])
            body_arg = next(a for a in args if a.startswith("body="))
            self.patched[number] = body_arg.removeprefix("body=")
            return ""
        if "labels" in joined and "POST" in joined:
            return ""
        if args[:2] == ["repo", "view"]:
            return "octo/repo\n"
        if "issue" in args and "create" in args:
            return "https://github.com/octo/repo/issues/4242\n"
        if args[0] == "api" and joined.endswith(".[].name"):
            return "agent:implement\n"
        raise AssertionError(f"unexpected gh call: {joined}")


# ---------------------------------------------------------------- the chain read

def test_the_real_config_chain_is_read_completely():
    members = _members_from_config(REAL_CONFIG)
    ids = set(members)
    assert "meituan/longcat-2.5:free" in ids          # primary (issue #2929)
    assert "deepseek/deepseek-v4-flash-0731" in ids   # the paid last resort
    assert {"tencent/hy4-flash:free", "stepfun/step-3.7-flash:free",
            "qwen/qwen4-max:free", "upstage/solar-mini4:free"} <= ids
    for mid, info in members.items():
        assert info["budgets"], f"{mid} carries no context_window budget"


def test_a_config_declaring_no_models_refuses_to_pass_vacuously(tmp_path):
    cfg = tmp_path / "empty.yaml"
    cfg.write_text("model:\n  provider: custom\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _members_from_config(cfg)
    assert "vacuously" in str(exc.value)


# ---------------------------------------------------------------- the comparison

def test_a_full_catalog_is_green(capsys):
    members = _members_from_config(REAL_CONFIG)
    models = _catalog_for(members)
    findings = CAM.compare(members, models)
    assert findings == []
    out = capsys.readouterr().out
    assert out.count("member ") == len(members)
    assert "matches published context_length" in out


def test_a_missing_member_is_named_with_candidates(capsys):
    members = _members_from_config(REAL_CONFIG)
    models = _catalog_for(members, drop=("upstage/solar-mini4:free",))
    findings = CAM.compare(members, models)
    assert len(findings) == 1
    line = findings[0]
    assert line.startswith("FINDING: upstage/solar-mini4:free")
    assert "is not in the catalog" in line
    assert "current :free candidates:" in line and "meituan/longcat-2.5:free" in line


def test_a_budget_divergence_names_both_numbers(capsys):
    members = _members_from_config(REAL_CONFIG)
    models = _catalog_for(members, drift={"tencent/hy4-flash:free": 131072})
    findings = CAM.compare(members, models)
    assert findings == ["FINDING: tencent/hy4-flash:free budget 1048576 != "
                        "published context_length 131072"]


def test_conflicting_budgets_inside_the_config_are_a_finding(tmp_path):
    cfg = tmp_path / "split.yaml"
    cfg.write_text(yaml.safe_dump({
        "model": {"default": "m1:free", "context_window": 1000},
        "fallback_providers": [{"model": "m1:free", "context_window": 2000}],
    }), encoding="utf-8")
    members = _members_from_config(cfg)
    findings = CAM.compare(members, [{"id": "m1:free", "context_length": 1000}])
    assert findings and "conflicting context_window budgets" in findings[0]


# ---------------------------------------------------------------- the main() paths

def test_main_green_exit_zero_with_a_saved_catalog(capsys, tmp_path):
    members = _members_from_config(REAL_CONFIG)
    cat = _catalog(_catalog_for(members))
    rc = CAM.main(["--catalog", str(cat), "--repo", "octo/repo"])
    assert rc == 0
    assert "catalog check: OK" in capsys.readouterr().out


def test_main_dry_run_prints_the_body_and_calls_no_gh(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(CAM, "run_gh", _no_gh)
    members = _members_from_config(REAL_CONFIG)
    cat = _catalog(_catalog_for(members, drop=("qwen/qwen4-max:free",)))
    rc = CAM.main(["--catalog", str(cat), "--dry-run"])
    assert rc == 1
    out = capsys.readouterr().out
    body = out[out.index(CAM.MARKER):]
    headings = issue_body.headings(body)
    assert headings == list(issue_body.SECTIONS), headings
    assert body.startswith(CAM.MARKER)
    assert "qwen/qwen4-max:free" in body and "agent-model-catalog-check" in body


def _no_gh(args: list[str]) -> str:
    raise AssertionError(f"dry-run touched gh: {args}")


def test_findings_file_one_issue_with_the_label_proven_back(monkeypatch, capsys):
    fake = FakeGh(search_hits=[])
    monkeypatch.setattr(CAM, "run_gh", fake)
    members = _members_from_config(REAL_CONFIG)
    cat = _catalog(_catalog_for(members, drop=("stepfun/step-3.7-flash:free",)))
    rc = CAM.main(["--catalog", str(cat), "--repo", "octo/repo"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "filed #4242" in out
    create = next(c for c in fake.calls if "create" in c)
    assert CAM.MARKER in " ".join(create)  # the marker rides in the body it created
    assert any("labels" in " ".join(c) and "agent:implement" in " ".join(c)
               for c in fake.calls)


def test_a_later_run_UPDATES_the_open_marker_issue_instead_of_duplicating(monkeypatch, capsys):
    fake = FakeGh(search_hits=[{"number": 77}],  # search hits name no `pull_request` key for issues
                  existing_body="old body\n" + CAM.MARKER)
    monkeypatch.setattr(CAM, "run_gh", fake)
    members = _members_from_config(REAL_CONFIG)
    cat = _catalog(_catalog_for(members, drop=("stepfun/step-3.7-flash:free",)))
    rc = CAM.main(["--catalog", str(cat), "--repo", "octo/repo"])
    assert rc == 1
    assert "updated #77" in capsys.readouterr().out
    joined = [" ".join(c) for c in fake.calls]
    assert not any("create" in c for c in joined), "the dedupe must never file a second issue"
    assert any("-X PATCH" in c for c in joined), "the body write goes over REST (#2673)"
    assert 77 in fake.patched and CAM.MARKER in fake.patched[77]


def test_a_failed_dedupe_search_files_nothing_blind(monkeypatch):
    def broken(args: list[str]) -> str:
        if "search/issues" in " ".join(args):
            raise RuntimeError("gh api search failed")
        return "octo/repo\n"
    monkeypatch.setattr(CAM, "run_gh", broken)
    members = _members_from_config(REAL_CONFIG)
    cat = _catalog(_catalog_for(members, drop=("upstage/solar-mini4:free",)))
    with pytest.raises(SystemExit) as exc:
        CAM.main(["--catalog", str(cat), "--repo", "octo/repo"])
    assert "files nothing blind" in str(exc.value)


def test_a_transport_failure_files_nothing_and_exits_loud(monkeypatch, capsys):
    def refuse(request, timeout=None):
        raise urllib.error.URLError("catalog down")
    monkeypatch.setattr(CAM.urllib.request, "urlopen", refuse)
    with pytest.raises(SystemExit) as exc:
        CAM.fetch_catalog("https://example.invalid/v1/models")
    assert "files nothing" in str(exc.value)


# ---------------------------------------------------------------- the hermetic promise

def test_the_fetch_sends_no_authorization_header(monkeypatch):
    seen: dict = {}

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"data": [{"id": "x", "context_length": 1}]}).encode()

    def capture(request, timeout=None):
        seen["headers"] = dict(request.headers)
        return Resp()

    monkeypatch.setattr(CAM.urllib.request, "urlopen", capture)
    CAM.fetch_catalog("https://example.invalid/v1/models")
    assert not any(k.lower() == "authorization" for k in seen["headers"])
    import re
    source = (ROOT / "scripts" / "check_agent_model_catalog.py").read_text(encoding="utf-8")
    code = re.sub(r'""".*?"""', "", source, flags=re.S)          # docstrings carry the promise in prose
    code = "\n".join(l for l in code.splitlines() if not l.strip().startswith("#"))
    assert "Authorization" not in code
    assert "environ" not in code, "the check reads no credential"


# ---------------------------------------------------------------- the wiring

def _workflow(name: str) -> dict:
    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))


def test_the_check_is_the_last_step_of_the_registry_sync_sync_job():
    wf = _workflow("registry-sync.yml")
    jobs = wf["jobs"]
    sync = next(j for j in jobs.values()
                if any("check-agent-model-catalog" in (s.get("run") or "")
                       for s in j["steps"]))
    step_names = [s.get("name", "") for s in sync["steps"]]
    idx = next(i for i, n in enumerate(step_names) if "check-agent-model-catalog" in n)
    assert idx == len(step_names) - 1, (
        "the catalog check must come AFTER 'Open / update the sync PR': a red finding "
        "may not forfeit the sync PR (the #775 lesson)")
    step = sync["steps"][idx]
    assert step["run"].strip() == "make check-agent-model-catalog"
    assert "secrets.GITHUB_TOKEN" in json.dumps(step["env"])
    assert not any(k in json.dumps(step["env"])
                   for k in ("BUMP_TOKEN", "NOUS", "HF_TOKEN")), "the step carries no secret"


def test_the_weekly_cron_and_the_make_target_survive_the_wiring():
    wf = _workflow("registry-sync.yml")
    on = wf.get("on") or wf.get(True) or {}
    crons = list(on.get("schedule") or [])
    assert {"cron": "19 5 * * 1"} in crons
    out = __import__("subprocess").run(
        ["make", "-n", "check-agent-model-catalog"], cwd=ROOT,
        capture_output=True, text=True).stdout
    assert "scripts/check_agent_model_catalog.py" in out


def test_the_producer_and_layers_are_registered():
    assert ("scripts/check_agent_model_catalog.py", "issue_text") in issue_body.PRODUCERS
    layers = json.loads((ROOT / "scripts" / "package-layers.json").read_text(encoding="utf-8"))
    assert "check_agent_model_catalog" in layers["groups"]["Bots and automation"]
    assert any(e["from"] == "check_agent_model_catalog" and e["to"] == "proc"
               for e in layers["allowed_edges"])
