"""Hermetic unit tests for scripts/engine_bump_restamp.py (issue #3054).

The leg reads the bump facts off each open `chore/engine-bump-*` PR's LIVE body, classifies the bump
against the pin `main` actually carries, and re-stamps only a `pending` bump through the composer ->
`make bot-stamp-body` -> `make bot-body-write` chain. Every test here drives the leg through a fake
`proc`: no network, no `gh`, no write to a real pull request.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("GITHUB_TOKEN", "test-token-hermetic")

import scripts.engine_bump_restamp as eb  # noqa: E402
from scripts.engine_bump_pr_body import ACCEPTANCE_HEADING, DEFAULT_OPENSPEC, render_body  # noqa: E402

OLD = "0123456789abcdef0123456789abcdef01234567"
NEW = "89abcdef0123456789abcdef0123456789abcdef"
OTHER = "ffffffffffffffffffffffffffffffffffffffff"
HEAD = "1234567890123456789012345678901234567890"
RUN = "46145735521"


def _body(*, engine="ollama", ref="v0.13.0", old=OLD, new=NEW, review="", hard_fail="",
          deps="", glue_defect=False, stamp=True, acceptance=True, openspec=DEFAULT_OPENSPEC):
    """A bump body in the composer's shape, optionally carrying the #3054 defect."""
    text = render_body(engine=engine, ref=ref, old_sha=old, new_sha=new, run_id=RUN,
                       author=eb.DEFAULT_AUTHOR, repo_slug=eb.DEFAULT_REPO,
                       openspec=openspec or DEFAULT_OPENSPEC,
                       hard_fail=hard_fail, deps=deps, review_section=review)
    if not openspec:
        # The composer asserts its own reference line (it cannot compose without one), so the missing
        # reference is made by REMOVING the line the composer appended.
        text = text.replace(f"\n\nOPENSPEC: {DEFAULT_OPENSPEC}\n", "\n")
    if glue_defect:
        # The measured shape: the review heading glued onto the change name (`…pin-images## Documentation review`).
        text = text.replace(f"OPENSPEC: {openspec}\n", f"OPENSPEC: {openspec}## Documentation review\n")
    if not acceptance:
        text = text.replace(ACCEPTANCE_HEADING, "## Notes")
    if stamp:
        text += "\nAGENTS: 4d999e3 109563b 1602l\n"
    return text


class FakeProc:
    """Stands in for `proc` (issue #797): answers the leg's gh/python commands and records every call."""

    class ProcError(Exception):
        pass

    def __init__(self, prs, bodies, pins, checks=None, stamp_ok=True, write_ok=True,
                 head_pin=NEW, variants=None, matrix=None):
        self.prs = prs
        self.bodies = dict(bodies)
        self.pins = dict(pins)
        self.checks = checks or {}
        self.stamp_ok = stamp_ok
        self.write_ok = write_ok
        # Evidence the leg reads at the PR HEAD: the pin the head's skill/params carry, the
        # `engine-build-<engine>-<variant>` check-run rows, and the variants the matrix asks for.
        self.head_pin = head_pin
        self.variants = {k: dict(v) for k, v in (variants or {}).items()}
        self.matrix = dict(matrix or {})
        self.blobs: dict[str, str] = {}  # blob sha -> file text
        self.calls: list[list[str]] = []

    def _find(self, cmd, needle):
        return next((i for i, a in enumerate(cmd) if needle in a), None)

    def run_text(self, cmd, timeout=None):
        self.calls.append(list(cmd))
        head = " ".join(cmd[:3])
        if head.startswith("gh pr list"):
            return json.dumps(self.prs)
        if head.startswith("gh pr view"):
            if "files" in cmd:  # pr_files(): the changed paths at the head
                engines = sorted(self.pins)
                paths = ["containers/engines/params/ollama.json", "skills/engines/ollama/SKILL.md"]
                for e in engines:
                    paths += [f"containers/engines/{e}/Dockerfile",
                              f"containers/engines/params/{e}.json",
                              f"skills/engines/{e}/SKILL.md"]
                return "\n".join(paths)
            return self.bodies[cmd[3]]
        if head.startswith("gh pr checks"):
            return json.dumps(self.checks.get(cmd[3], []))
        if cmd[0] == "gh" and cmd[1] == "api":
            url = cmd[self._find(cmd, "repos/") or 2]
            if "/contents/" in url and "?ref=" in url:
                # issue #3054: the contents endpoint with `?ref=<sha>` served main's older blob for
                # #3033's head on one call and the head blob on the next. Head reads go by git object.
                raise AssertionError(f"head file reads must go through the git blob API: {cmd}")
            if "/git/trees/" in url:
                ref = url.split("/git/trees/")[1].split("?")[0]
                m = re.search(r'select\(\.path == "([^"]+)"\)', " ".join(cmd))
                path = m.group(1) if m else ""
                blob = hashlib.sha1(f"{path}@{ref}".encode()).hexdigest()
                self.blobs[blob] = self._file_text(path)
                return blob
            if "/git/blobs/" in url:
                sha = url.split("/git/blobs/")[1]
                return base64.b64encode(self.blobs[sha].encode()).decode()
            if "/check-runs" in url:
                rows = []
                for engine, variants in (self.variants or
                                         {e: {"cpu": ("success", "45242586633")}
                                          for e in sorted(self.pins)}).items():
                    for variant, (conclusion, run_id) in variants.items():
                        rows.append("\t".join([
                            f"engine-build-{engine}-{variant}", conclusion,
                            f"https://github.com/o/r/actions/runs/{run_id}/job/1"]))
                return "\n".join(rows)
            engine = cmd[2].split("/engines/")[1].split("/")[0]
            md = f"---\nname: {engine}\npinned: {self.pins[engine]}\n---\n\n# {engine}\n"
            return base64.b64encode(md.encode()).decode()
        if cmd[:3] == ["make", "-s", "engine-build-matrix"]:
            engine = next(a.split("=", 1)[1] for a in cmd if a.startswith("ENGINE="))
            variants = self.matrix.get(engine) or sorted(
                self.variants.get(engine) or {"cpu": ()})
            return json.dumps({"include": [{"engine": engine, "variant": v} for v in variants]})
        raise AssertionError(f"unexpected run_text call: {cmd}")

    def _file_text(self, path: str) -> str:
        engine = re.search(r"engines/(?:params/)?([^/.]+)", path).group(1)
        if path.endswith("SKILL.md"):
            return f"---\nname: {engine}\npinned: {self.head_pin}\n---\n\n# {engine}\n"
        return json.dumps({"engine": engine, "pinned": self.head_pin})

    def run_checked(self, cmd, timeout=None):
        self.calls.append(list(cmd))
        if self._find(cmd, "bot_preflight.py") is not None:  # the stamp authority, by name
            if not self.stamp_ok:
                raise self.ProcError("stamp refused")
            return "stamped ok\nAGENTS: 4d999e3 109563b 1602l"
        if self._find(cmd, "pr_body_write.py") is not None:  # the guarded write seam, by name
            if not self.write_ok:
                raise self.ProcError("seam refused: a heading would be dropped")
            i = self._find(cmd, "--pr")
            assert i is not None, f"the seam is called with --pr: {cmd}"
            n = self._find(cmd, "--new")
            assert n is not None, f"the seam is called with the rendered body: {cmd}"
            # What the seam actually does: the live body BECOMES the proposed one, so the leg's
            # post-write re-read has something real to re-read.
            with open(cmd[n + 1], encoding="utf-8") as fh:
                self.bodies[cmd[i + 1]] = fh.read()
            return f"wrote body for #{cmd[i + 1]}"
        if cmd[:3] == ["gh", "pr", "close"]:
            return f"closed #{cmd[3]}"
        if cmd[0] == "gh" and "pr" in cmd and "edit" in cmd:
            raise AssertionError(f"the leg must never issue a raw gh pr edit: {cmd}")
        raise AssertionError(f"unexpected run_checked call: {cmd}")


def _install(monkeypatch, fake):
    monkeypatch.setattr(eb, "proc", fake)
    return fake


def _pr(number=3030, branch="chore/engine-bump-ollama-3054"):
    return {"number": number, "title": f"chore(engine): bump {branch}", "headRefName": branch,
            "headRefOid": HEAD}


def _checks(name="engine-bump-test-image", bucket="fail", run_id=RUN):
    return [{"name": name, "bucket": bucket, "link": f"https://github.com/x/y/actions/runs/{run_id}/job/1"}]


class TestReadFacts:
    def test_glued_openspec_line_is_the_named_defect(self):
        # Given a live body whose OPENSPEC line carries the review heading glued to the change name
        bump = eb.BumpPr(number="3030", title="t", branch="chore/engine-bump-ollama", head_sha=HEAD)
        problems = eb.read_facts(bump, _body(glue_defect=True))
        # When the facts are read, the bump is still understood and the defect is named
        assert bump.defect == "glued OPENSPEC line"
        assert problems == []
        assert bump.engine == "ollama" and bump.ref == "v0.13.0"
        assert bump.old_sha == OLD and bump.new_sha == NEW
        # And the glued heading is no longer a line start, so no review section survives on it
        assert bump.review == ""

    def test_a_composer_body_round_trips_with_no_defect(self):
        # Given a body that the #3050 composer rendered
        bump = eb.BumpPr(number="3034", title="t", branch="chore/engine-bump-tensorfold", head_sha=HEAD)
        review = "## Documentation review\n\n- params unchanged against upstream defaults."
        problems = eb.read_facts(bump, _body(review=review))
        # When the facts are read back off it, nothing is missing and no defect is reported
        assert problems == []
        assert bump.defect == ""
        assert bump.review == review
        assert bump.review.endswith("upstream defaults.")

    def test_review_section_is_cut_before_the_stamp_lines(self):
        # Given a body whose review section is followed by the AGENTS/BASE stamp pair
        body = _body(review="## Engine params review\n\n- llama.cpp params kept.") + "BASE: 4d999e3\n"
        bump = eb.BumpPr(number="3033", title="t", branch="chore/engine-bump-llama", head_sha=HEAD)
        eb.read_facts(bump, body)
        # Then the review stops at the stamp, so the stamp is never embedded twice
        assert "BASE:" not in bump.review and "AGENTS:" not in bump.review
        assert bump.review.endswith("llama.cpp params kept.")

    def test_missing_openspec_reference_is_named(self):
        # Given a body with no OPENSPEC line at all
        bump = eb.BumpPr(number="3031", title="t", branch="chore/engine-bump-vllm", head_sha=HEAD)
        eb.read_facts(bump, _body(openspec=""))
        # Then the defect is reported instead of guessed
        assert bump.defect == "no resolvable OPENSPEC reference"

    def test_missing_acceptance_section_is_named(self):
        # Given a body whose own acceptance checklist is gone
        bump = eb.BumpPr(number="3035", title="t", branch="chore/engine-bump-edge0", head_sha=HEAD)
        eb.read_facts(bump, _body(acceptance=False))
        assert bump.defect == "no own acceptance criteria section"

    def test_compare_shas_win_and_a_disagreement_is_reported(self):
        # Given a pin line whose 8-char old pin disagrees with the compare URL
        body = _body().replace(f"`{OLD[:8]}` ->", "`deadbeef` ->")
        bump = eb.BumpPr(number="3032", title="t", branch="chore/engine-bump-prism", head_sha=HEAD)
        problems = eb.read_facts(bump, body)
        # Then the full compare shas are used and the disagreement is named
        assert bump.old_sha == OLD and bump.new_sha == NEW
        assert any("disagrees with the pin line" in p for p in problems)


class TestClassifyAgainstMain:
    def _bump(self):
        return eb.BumpPr(number="3030", title="t", branch="chore/engine-bump-ollama", head_sha=HEAD,
                         old_sha=OLD, new_sha=NEW)

    def test_pending_when_main_holds_the_old_pin(self):
        assert eb.classify_against(self._bump(), OLD) == eb.PENDING

    def test_landed_when_main_holds_the_new_pin(self):
        assert eb.classify_against(self._bump(), NEW) == eb.LANDED

    def test_superseded_when_main_moved_to_a_third_pin(self):
        assert eb.classify_against(self._bump(), OTHER) == eb.SUPERSEDED

    def test_unknown_pin_is_never_re_stamped(self):
        # Given a pin main's skill file does not report
        bump = self._bump()
        assert eb.classify_against(bump, "") == "unknown-pin"
        assert bump.kind != eb.PENDING


class TestLaneRuns:
    def test_newest_run_and_failing_jobs_come_from_the_pr_checks_rows(self, monkeypatch):
        fake = _install(monkeypatch, FakeProc([_pr()], {}, {}))
        fake.checks = {"3030": _checks(run_id="111") + _checks(name="guard", run_id="222222")}
        monkeypatch.setattr(eb.proc, "run_text", fake.run_text)
        run_id, failing = eb.lane_runs(eb.DEFAULT_REPO, "3030")
        assert run_id == "222222"
        assert failing == ["engine-bump-test-image", "guard"]

    def test_a_checks_failure_reports_no_run_id(self, monkeypatch):
        class Boom(FakeProc):
            def run_text(self, cmd, timeout=None):
                raise RuntimeError("gh pr checks exploded")

        _install(monkeypatch, Boom([_pr()], {}, {}))
        assert eb.lane_runs(eb.DEFAULT_REPO, "3030") == ("", [])


class TestProcessDryRun:
    """Dry by default: a dry run prints the classification and issues no body write or close call."""

    def _fake(self, pins=None, checks=None):
        return FakeProc([_pr()], {"3030": _body(glue_defect=True)},
                        pins if pins is not None else {"ollama": OLD},
                        checks if checks is not None else {"3030": _checks()})

    def test_dry_run_makes_no_github_mutation_call(self, monkeypatch, tmp_path, capsys):
        fake = _install(monkeypatch, self._fake())
        tally = eb.process(eb.DEFAULT_REPO, apply=False, close_superseded=False, out_dir=tmp_path)
        # Then the tally reports no writes/closes and no stamp/write/close command was issued
        assert tally["written"] == 0 and tally["closed"] == 0
        assert tally["refused"] == 0 and tally["unstamped"] == 0
        assert tally[eb.PENDING] == 1
        flat = [" ".join(c) for c in fake.calls]
        assert not any("pr_body_write.py" in c for c in flat), flat
        assert not any("bot_preflight.py" in c for c in flat), flat
        assert not any("gh pr close" in c for c in flat), flat
        # And the line names the engine, the kind, main's pin, the lane run and the defect
        out = capsys.readouterr().out
        assert "#3030 engine=ollama pending" in out
        assert f"main-pin={OLD[:8]}" in out and f"run={RUN}" in out
        assert "defect=glued OPENSPEC line" in out
        assert "red-lane=engine-bump-test-image" in out

    def test_dry_run_still_prints_the_rendered_body_path(self, monkeypatch, tmp_path, capsys):
        _install(monkeypatch, self._fake())
        eb.process(eb.DEFAULT_REPO, apply=False, close_superseded=False, out_dir=tmp_path / "drafts")
        drafted = list((tmp_path / "drafts").glob("pr-*-body.md"))
        assert len(drafted) == 1
        text = drafted[0].read_text()
        # The draft is composer-shaped: OPENSPEC on its own line, its own acceptance checklist
        assert "\nOPENSPEC: publish-changed-pin-images\n" in text
        assert ACCEPTANCE_HEADING in text
        assert "## Documentation review" not in text.split(f"OPENSPEC: {DEFAULT_OPENSPEC}")[1]
        assert f"body={drafted[0]}" in capsys.readouterr().out

    def test_no_open_bump_pr_is_not_an_error(self, monkeypatch, tmp_path, capsys):
        _install(monkeypatch, FakeProc([], {}, {}))
        tally = eb.process(eb.DEFAULT_REPO, apply=False, close_superseded=False, out_dir=tmp_path)
        assert tally["written"] == 0 and tally["closed"] == 0
        assert "no open chore/engine-bump-* pull requests" in capsys.readouterr().out

    def test_main_only_lists_bump_branches(self, monkeypatch, tmp_path):
        prs = [_pr(3030), _pr(999, branch="feat/some-worker-lane")]
        fake = FakeProc(prs, {"3030": _body(glue_defect=True)}, {"ollama": OLD}, {"3030": _checks()})
        _install(monkeypatch, fake)
        eb.process(eb.DEFAULT_REPO, apply=False, close_superseded=False, out_dir=tmp_path)
        assert all("999" not in " ".join(c) for c in fake.calls)


class TestProcessApply:
    """Apply mode: composer -> `make bot-stamp-body` authority -> `make bot-body-write` seam, in that order."""

    def _fake(self, **kw):
        return FakeProc([_pr()], {"3030": _body(glue_defect=True)}, {"ollama": OLD},
                        {"3030": _checks()}, **kw)

    def test_apply_writes_only_through_the_guarded_seam_after_the_stamp(self, monkeypatch, tmp_path, capsys):
        fake = _install(monkeypatch, self._fake())
        tally = eb.process(eb.DEFAULT_REPO, apply=True, close_superseded=False, out_dir=tmp_path)
        flat = [" ".join(c) for c in fake.calls]
        stamps = [i for i, c in enumerate(flat) if "bot_preflight.py" in c and "--stamp" in c]
        writes = [i for i, c in enumerate(flat) if "pr_body_write.py" in c]
        assert len(stamps) == 1 and len(writes) == 1
        # When: the stamp authority runs before the write seam, on the rendered body
        assert stamps[0] < writes[0]
        assert "--stamp" in flat[stamps[0]] and str(tmp_path / "pr-3030-body.md") in flat[stamps[0]]
        assert "--repo" in flat[writes[0]] and "--new" in flat[writes[0]] and "--pr 3030" in flat[writes[0]]
        # Then: one body written, and no raw gh pr edit anywhere
        assert tally["written"] == 1 and tally["refused"] == 0 and tally["unstamped"] == 0
        assert not any("gh pr edit" in c for c in flat), flat
        # And the post-write re-read confirms the reference is resolvable
        out = capsys.readouterr().out
        assert "re-read after the write: OPENSPEC=resolvable" in out

    def test_a_refused_stamp_writes_nothing(self, monkeypatch, tmp_path, capsys):
        fake = _install(monkeypatch, self._fake(stamp_ok=False))
        tally = eb.process(eb.DEFAULT_REPO, apply=True, close_superseded=False, out_dir=tmp_path)
        assert tally["unstamped"] == 1 and tally["written"] == 0
        flat = [" ".join(c) for c in fake.calls]
        assert not any("pr_body_write.py" in c for c in flat), flat
        assert "the stamp authority refused" in capsys.readouterr().out

    def test_a_refused_seam_keeps_the_live_body(self, monkeypatch, tmp_path, capsys):
        _install(monkeypatch, self._fake(write_ok=False))
        tally = eb.process(eb.DEFAULT_REPO, apply=True, close_superseded=False, out_dir=tmp_path)
        assert tally["refused"] == 1 and tally["written"] == 0
        assert "the guarded seam refused the write" in capsys.readouterr().out

    def test_a_pending_bump_with_no_lane_run_is_skipped(self, monkeypatch, tmp_path, capsys):
        fake = FakeProc([_pr()], {"3030": _body(glue_defect=True)}, {"ollama": OLD}, {"3030": []})
        _install(monkeypatch, fake)
        tally = eb.process(eb.DEFAULT_REPO, apply=True, close_superseded=False, out_dir=tmp_path)
        # When: the bump lane has no run id for the live head, Then nothing is stamped or written
        assert tally["written"] == 0 and tally["pending"] == 1
        assert "SKIP=no lane run id" in capsys.readouterr().out
        assert not any("pr_body_write.py" in " ".join(c) for c in fake.calls)

    def test_an_unknown_pin_bump_is_never_written(self, monkeypatch, tmp_path):
        fake = FakeProc([_pr()], {"3030": _body(glue_defect=True)}, {"ollama": ""}, {"3030": _checks()})
        _install(monkeypatch, fake)
        tally = eb.process(eb.DEFAULT_REPO, apply=True, close_superseded=True, out_dir=tmp_path)
        assert tally["unknown-pin"] == 1 and tally["written"] == 0 and tally["closed"] == 0
        assert not any("pr_body_write.py" in " ".join(c) for c in fake.calls)


class TestProcessCloseOvertaken:
    def test_landed_and_superseded_close_with_the_pin_evidence(self, monkeypatch, tmp_path, capsys):
        prs = [_pr(3033, "chore/engine-bump-llama"), _pr(3034, "chore/engine-bump-tensorfold")]
        bodies = {"3033": _body(engine="llama.cpp", old=OLD, new=NEW),
                  "3034": _body(engine="tensorfold", old=OLD, new=NEW)}
        fake = FakeProc(prs, bodies, {"llama.cpp": NEW, "tensorfold": OTHER},
                        {"3033": _checks(), "3034": _checks()})
        _install(monkeypatch, fake)
        tally = eb.process(eb.DEFAULT_REPO, apply=True, close_superseded=True, out_dir=tmp_path)
        # Then: both overtaken bumps close, each with main's live pin as the comment evidence
        assert tally[eb.LANDED] == 1 and tally[eb.SUPERSEDED] == 1 and tally["closed"] == 2
        closes = [c for c in fake.calls if c[:3] == ["gh", "pr", "close"]]
        assert len(closes) == 2
        assert any(NEW[:12] in " ".join(c) for c in closes) and any(OTHER[:12] in " ".join(c) for c in closes)
        assert not any("pr_body_write.py" in " ".join(c) for c in fake.calls)
        assert not any("gh pr merge" in " ".join(c) for c in fake.calls)
        assert "closed as overtaken" in capsys.readouterr().out

    def test_close_superseded_without_apply_closes_nothing(self, monkeypatch, tmp_path):
        fake = FakeProc([_pr(3033, "chore/engine-bump-llama")],
                        {"3033": _body(engine="llama.cpp")}, {"llama.cpp": NEW}, {"3033": _checks()})
        _install(monkeypatch, fake)
        tally = eb.process(eb.DEFAULT_REPO, apply=False, close_superseded=True, out_dir=tmp_path)
        assert tally["closed"] == 0
        assert not any(c[:3] == ["gh", "pr", "close"] for c in fake.calls)

    def test_a_landed_bump_is_not_re_stamped(self, monkeypatch, tmp_path):
        fake = FakeProc([_pr(3033, "chore/engine-bump-llama")],
                        {"3033": _body(engine="llama.cpp", glue_defect=True)}, {"llama.cpp": NEW},
                        {"3033": _checks()})
        _install(monkeypatch, fake)
        tally = eb.process(eb.DEFAULT_REPO, apply=True, close_superseded=True, out_dir=tmp_path)
        assert tally["written"] == 0 and tally["closed"] == 1
        assert not any("pr_body_write.py" in " ".join(c) for c in fake.calls)


class TestHostOnlyWiring:
    def test_the_restamp_leg_is_host_run_and_claims_no_ci_coverage(self):
        # Given the gate's rule (issue #237): a `documents` entry excuses a document CI NEVER reaches.
        # The leg now carries a test, so CI reaches it, and the entry would be a stale claim.
        data = json.loads((eb.REPO_ROOT / "tests" / "fixtures" / "host-only-wiring.json").read_text())
        assert "scripts/engine_bump_restamp.py" not in data["documents"], (
            "scripts/engine_bump_restamp.py has a test, so check-wiring counts it as CI-reachable: "
            "a host-only `documents` entry for it is stale and has to be deleted"
        )
        # When: the target exists and its `##` help line claims no CI coverage...
        mk = (eb.REPO_ROOT / "mk" / "engines.mk").read_text(encoding="utf-8")
        m = re.search(r"^engine-bump-restamp:.*$", mk, re.M)
        assert m is not None, "the leg has to be reachable through a make target"
        claims_ci = re.compile(r"^\s*CI\b|\bCI job\b|\bCI pipelines\b|\(CI\b|\bFails CI\b")
        assert not claims_ci.search(m.group(0)), f"the help line claims CI coverage: {m.group(0)}"
        # ...and NO CI workflow names it: no clock may rewrite an OPEN PR body on a schedule (issue #3054).
        named = sorted(p.name for p in (eb.REPO_ROOT / ".github" / "workflows").glob("*.y*ml")
                       if "engine-bump-restamp" in p.read_text(encoding="utf-8"))
        assert named == [], f"a CI clock runs the host remediation leg: {named}"

    def test_the_restamp_module_is_placed_in_the_scripts_layering(self):
        # Given scripts/package-layers.json places every module (issue #795)
        layers = json.loads((eb.REPO_ROOT / "scripts" / "package-layers.json").read_text())
        # When the re-stamp leg is looked up, Then it sits with the bump family and its proc/gate edges are stated
        assert "engine_bump_restamp" in layers["groups"]["Product path"], (
            "the leg belongs with the engine_bump family it re-runs, not in a group of its own"
        )
        edges = {(e["from"], e["to"]) for e in layers["allowed_edges"]}
        assert ("engine_bump_restamp", "proc") in edges, "the leg runs gh/make through the ONE subprocess policy"
        assert ("engine_bump_restamp", "check_pr_hygiene") in edges, (
            "the leg reads the hygiene gate's own OPENSPEC_REF instead of spelling the reference again"
        )

class TestHeadEvidence:
    """A ticked box names evidence the leg read at the PR HEAD (issue #3054)."""

    def _fake(self, **kw):
        return FakeProc([_pr()], {"3030": _body(glue_defect=True)}, {"ollama": OLD},
                        {"3030": _checks()}, **kw)

    def _bump(self):
        bump = eb.open_bump_prs(eb.DEFAULT_REPO)[0]
        bump.problems = eb.read_facts(bump, eb.live_body(eb.DEFAULT_REPO, bump.number))
        return bump

    def test_head_file_reads_go_through_the_git_blob_api_not_a_contents_ref(self, monkeypatch):
        fake = _install(monkeypatch, self._fake())
        # Because: `contents/<path>?ref=<sha>` served main's older blob for #3033's head on one call
        # and the head blob on the next, so a head read by ref is not a deterministic read.
        ev = eb.read_evidence(eb.DEFAULT_REPO, self._bump())
        flat = [" ".join(c) for c in fake.calls]
        assert not any("/contents/" in c and "?ref=" in c for c in flat), flat
        assert any("/git/trees/" in c for c in flat), flat
        assert any("/git/blobs/" in c for c in flat), flat
        assert ev.skill_pin == NEW and ev.params_names_pin
        assert ev.skill_blob and ev.params_blob

    def test_a_green_variant_proves_the_image_item_with_its_workflow_run_id(self, monkeypatch):
        variants = {"ollama": {"cpu": ("success", "45242586633"), "cuda": ("success", "45245255181")}}
        fake = _install(monkeypatch, self._fake(variants=variants, matrix={"ollama": ["cpu", "cuda"]}))
        bump = self._bump()
        ev = eb.read_evidence(eb.DEFAULT_REPO, bump)
        items, not_covered, refusals = eb.prove(eb.DEFAULT_REPO, bump, ev, {})
        assert refusals == [] and not_covered == []
        assert len(items) == 3 and all(i.startswith("- [x]") for i in items)
        image = items[-1]
        # Then the proof is the workflow run id from the check run's own url, flagged with the head
        assert "run=45242586633" in image and "run=45245255181" in image
        assert HEAD in image
        # and never the `gh pr checks` suite id, which 404s at gh api actions/runs/<id>
        assert RUN not in image

    def test_a_variant_that_finished_red_is_refused_not_ticked(self, monkeypatch):
        variants = {"ollama": {v: ("failure", f"452425866{i}") for i, v in
                               enumerate(["cpu", "cuda", "rocm", "vulkan"])}}
        fake = _install(monkeypatch, self._fake(variants=variants,
                               matrix={"ollama": ["cpu", "cuda", "rocm", "vulkan"]}))
        bump = self._bump()
        ev = eb.read_evidence(eb.DEFAULT_REPO, bump)
        items, not_covered, refusals = eb.prove(eb.DEFAULT_REPO, bump, ev, {})
        # Then no image box is ticked and every red arch is named as a refusal
        assert not any("build and run tests" in i for i in items), items
        assert len(refusals) == 4
        assert all("conclusion=failure" in r and "--deferred" in r for r in refusals), refusals
        assert not_covered == []

    def test_a_variant_the_matrix_asks_for_and_nobody_ran_is_a_gap(self, monkeypatch):
        variants = {"ollama": {v: ("success", f"452425866{i}") for i, v in
                               enumerate(["cpu", "cuda", "rocm"])}}
        fake = _install(monkeypatch, self._fake(variants=variants,
                               matrix={"ollama": ["cpu", "cuda", "rocm", "vulkan"]}))
        bump = self._bump()
        ev = eb.read_evidence(eb.DEFAULT_REPO, bump)
        items, not_covered, refusals = eb.prove(eb.DEFAULT_REPO, bump, ev, {})
        assert any("no engine-build-vulkan check run reported" in g for g in ev.gaps), ev.gaps
        assert not any("build and run tests" in i for i in items), items
        assert any("vulkan" in r for r in refusals), refusals

    def test_a_deferred_gap_is_a_not_covered_line_naming_its_issue(self, monkeypatch):
        variants = {"ollama": {v: ("failure", f"452425866{i}") for i, v in
                               enumerate(["cpu", "cuda", "rocm", "vulkan"])}}
        fake = _install(monkeypatch, self._fake(variants=variants,
                               matrix={"ollama": ["cpu", "cuda", "rocm", "vulkan"]}))
        bump = self._bump()
        ev = eb.read_evidence(eb.DEFAULT_REPO, bump)
        items, not_covered, refusals = eb.prove(eb.DEFAULT_REPO, bump, ev, {"ollama": "3065"})
        # Then the gap moves to `## Not covered` naming the side issue, and stays unticked
        assert len(not_covered) == 1 and "#3065" in not_covered[0], not_covered
        assert all(g in not_covered[0] for g in ev.gaps if g.startswith("engine-build")), not_covered
        assert refusals == []
        assert len(items) == 2 and not any("build and run tests" in i for i in items), items

    def test_a_deferred_bump_is_written_with_its_not_covered_section(self, monkeypatch, tmp_path):
        variants = {"ollama": {v: ("failure", f"452425866{i}") for i, v in
                               enumerate(["cpu", "cuda", "rocm", "vulkan"])}}
        fake = _install(monkeypatch, self._fake(variants=variants,
                               matrix={"ollama": ["cpu", "cuda", "rocm", "vulkan"]}))
        tally = eb.process(eb.DEFAULT_REPO, apply=True, close_superseded=False, out_dir=tmp_path,
                           deferred={"ollama": "3065"})
        assert tally["written"] == 1, tally
        text = (tmp_path / "pr-3030-body.md").read_text()
        assert "## Not covered" in text and "#3065" in text
        assert "build and run tests at the new pin" not in text
        flat = [" ".join(c) for c in fake.calls]
        assert any("bot_preflight.py" in c and "--stamp" in c for c in flat), flat
        assert any("pr_body_write.py" in c for c in flat), flat

    def test_an_undeferred_gap_writes_nothing(self, monkeypatch, tmp_path):
        variants = {"ollama": {v: ("failure", f"452425866{i}") for i, v in
                               enumerate(["cpu", "cuda", "rocm", "vulkan"])}}
        fake = _install(monkeypatch, self._fake(variants=variants,
                               matrix={"ollama": ["cpu", "cuda", "rocm", "vulkan"]}))
        tally = eb.process(eb.DEFAULT_REPO, apply=True, close_superseded=False, out_dir=tmp_path)
        assert tally["written"] == 0 and tally["unproven"] == 1, tally
        flat = [" ".join(c) for c in fake.calls]
        assert not any("pr_body_write.py" in c for c in flat), flat
        assert not any("bot_preflight.py" in c for c in flat), flat

