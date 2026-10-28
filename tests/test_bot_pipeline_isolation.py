"""Each bot runs on its own isolated pipeline: no two bots share a cron slot, and every bot
has its own concurrency group (issue #275, resolves #271/#272).

The bots are separate workflow *files*, but they still stepped on each other: two cron pairs
shared a minute (`engine-bump-rebase` daily 05:17 vs `registry-sync` Mon 05:17; `engine-bump`
Mon 06:23 vs `issue-bot` daily 06:23), and three bot workflows declared no `concurrency:`
group at all, so a manual dispatch could run beside a scheduled run.

This pins the isolation to the live workflow files: every scheduled bot's cron is expanded
into the set of `(minute, weekday)` slots it owns, and no slot may be owned by more than one
bot. The check is deliberately about the SLOT, not the hour, so the hourly bots
(`fix-bot` at :17, `queued-alarm` at :07/:37) are held to it too — a daily bot on minute 17
would collide with the hourly fix-bot every day.

**The scope is DERIVED, never listed (issue #301).** #275 wrote the bot set as a hand-kept
tuple of six filenames, so the three bots merged afterwards (`rebase-bot` #246, `issue-refiner`
#264, `code-review-bot` #269) were outside the guard entirely: the guard could not fail for a
bot it did not know, and `issue-bot` (`23 6 * * *`) and `rebase-bot` (`23 */6 * * *`) silently
shared minute :23 — both starting at 06:23 UTC every day, the exact failure #271/#272 were
filed for. A guard whose scope is a hand-written list stops protecting the moment someone adds
a file, so this one reads the workflow directory: ANY workflow with a `schedule:` is a bot and
is held to the rule, whether or not anyone remembered to mention it here.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WF = REPO / ".github" / "workflows"

_MINUTES = range(60)
_HOURS = range(24)
_WEEKDAYS = range(7)  # 0 = Sunday .. 6 = Saturday (GitHub's cron)


def _load(name: str) -> dict:
    return yaml.safe_load((WF / name).read_text())


def _on(wf: dict) -> dict:
    """The workflow's `on:` block. YAML 1.1 reads the bare key `on` as the boolean True,
    so accept both spellings rather than depending on the loader."""
    on = wf.get("on") or wf.get(True)
    return on if isinstance(on, dict) else {}


def _schedules(wf: dict) -> list[str]:
    """Every cron string in the workflow's `on.schedule` (empty when it has none)."""
    return [str(e["cron"]) for e in (_on(wf).get("schedule") or [])
            if isinstance(e, dict) and "cron" in e]


def _expand(field: str, domain: range) -> set[int]:
    """One cron field to the set of values it matches (`*`, `a,b`, `a-b`, `a/step`)."""
    values: set[int] = set()
    for part in field.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            step = int(s)
        if part == "*":
            lo, hi = domain.start, domain.stop - 1
        elif "-" in part:
            lo, hi = (int(x) for x in part.split("-", 1))
        else:
            lo = hi = int(part)
        values.update(range(lo, hi + 1, step))
    return values & set(domain)


def _scheduled_workflows() -> tuple[str, ...]:
    """Every workflow that declares a `schedule:` — the bots, read from the tree.

    This is the whole point of #301: the scope comes from the filesystem, so a bot merged
    tomorrow is inside the guard without anyone editing this module.
    """
    return tuple(sorted(p.name for p in WF.glob("*.yml") if _schedules(_load(p.name))))


#: The bots, DERIVED (never a literal list — see the module docstring, issue #301).
BOT_WORKFLOWS = _scheduled_workflows()


def _slots(cron: str) -> set[tuple[int, int]]:
    """The (minute, weekday) pairs a classic 5-field cron owns — the hour is irrelevant to a
    shared-slot collision."""
    fields = cron.split()
    assert len(fields) == 5, f"not a 5-field cron: {cron!r}"
    minute_f, _hour_f, _dom, _month, dow_f = fields
    minutes = _expand(minute_f, _MINUTES)
    weekdays = _expand(dow_f, _WEEKDAYS) if dow_f != "*" else set(_WEEKDAYS)
    return {(m, w) for m in minutes for w in weekdays}


def _runs_every_hour(cron: str) -> bool:
    """True when the cron fires at its minute in EVERY hour — the shape that reserves a
    minute on all seven weekdays."""
    fields = cron.split()
    return len(fields) == 5 and _expand(fields[1], _HOURS) == set(_HOURS)


def _reserved_minutes() -> set[int]:
    """The minutes the every-hour bots hold on all seven weekdays, derived from the crons.

    A daily/weekly bot landing on one of these collides with an every-hour bot every day,
    so it must pick another minute. Derived, so adding an every-hour bot reserves its
    minute automatically.
    """
    minutes: set[int] = set()
    for name in BOT_WORKFLOWS:
        for cron in _schedules(_load(name)):
            if _runs_every_hour(cron):
                minutes |= _expand(cron.split()[0], _MINUTES)
    return minutes


def _concurrency(wf: dict):
    """(group, cancel-in-progress) or None when the workflow declares no group."""
    conc = wf.get("concurrency")
    if conc is None:
        return None
    if isinstance(conc, dict):
        return conc.get("group"), conc.get("cancel-in-progress")
    return conc, None


def test_the_scope_is_derived_from_the_workflow_files():
    """The bot set is read from the tree, not hand-listed (issue #301).

    A narrowed list is the defect that let three bots go unchecked, so pin the derivation
    itself: every workflow with a `schedule:` is in scope, and the known bots are there.
    """
    # Given the workflows on disk, and the ones that declare a schedule
    derived = _scheduled_workflows()

    # Then the guard's scope is exactly that — a hand-narrowed list fails here
    assert set(BOT_WORKFLOWS) == set(derived), (
        "BOT_WORKFLOWS must be derived from the workflow files, not hand-listed "
        f"(issue #301): scope={sorted(BOT_WORKFLOWS)} disk={sorted(derived)}"
    )

    # And it is not vacuous: the bots that exist today are all in scope
    assert len(BOT_WORKFLOWS) >= 9, f"only {len(BOT_WORKFLOWS)} scheduled bots found: {BOT_WORKFLOWS}"
    for known in ("issue-bot.yml", "rebase-bot.yml", "issue-refiner.yml", "code-review-bot.yml"):
        assert known in BOT_WORKFLOWS, f"{known} declares a schedule but is out of scope"


def test_no_workflow_shares_a_minute():
    """No two bots own the same (minute, weekday) slot."""
    # Given the scheduled bots' crons, expanded into their owned (minute, weekday) slots
    owners: dict[tuple[int, int], str] = {}
    collisions: list[str] = []

    # When each slot is claimed by a second bot
    for name in BOT_WORKFLOWS:
        for cron in _schedules(_load(name)):
            for slot in _slots(cron):
                prior = owners.get(slot)
                if prior and prior != name:
                    collisions.append(
                        f"minute {slot[0]}, weekday {slot[1]}: owned by both {prior} and {name}"
                    )
                owners[slot] = name

    # Then no slot is shared
    assert not collisions, "bot cron slots collide:\n  " + "\n  ".join(sorted(set(collisions)))


def test_every_bot_has_its_own_concurrency_group():
    """Every bot declares a concurrency group, and no two bots share a group."""
    # Given each bot workflow's concurrency block
    seen: dict[str, str] = {}
    dupes: list[str] = []

    for name in BOT_WORKFLOWS:
        conc = _concurrency(_load(name))

        # Then it names a group and never cancels an in-progress run
        assert conc is not None, f"{name}: no concurrency group (a dispatch can overlap a run)"
        group, cancel = conc
        assert isinstance(group, str) and group.strip(), f"{name}: empty concurrency group"
        assert cancel is False, (
            f"{name}: cancel-in-progress must be false so a queued run is not cancelled"
        )

        # And the group is the bot's own, not shared with another bot
        prior = seen.get(group)
        if prior and prior != name:
            dupes.append(f"group {group!r} used by both {prior} and {name}")
        seen[group] = name

    assert not dupes, "bot concurrency groups collide:\n  " + "\n  ".join(dupes)


def test_the_hourly_bots_minutes_are_not_reused():
    """A daily/weekly bot must not land on a minute an every-hour bot reserves every day."""
    # Given the minutes the every-hour bots reserve on all seven weekdays
    reserved = _reserved_minutes()
    assert reserved, "no every-hour bot found — the reservation set cannot be empty"

    # When a bot that does NOT run every hour is read
    for name in BOT_WORKFLOWS:
        crons = _schedules(_load(name))
        if any(_runs_every_hour(c) for c in crons):
            continue
        for cron in crons:
            for minute, _weekday in _slots(cron):
                # Then it must not reuse a reserved minute
                assert minute not in reserved, (
                    f"{name}: minute {minute} is reserved by an every-hour bot "
                    f"({sorted(reserved)}), issue #275/#301"
                )


def _even_minutes(cron: str) -> list[int]:
    """The minutes a cron fires at that are NOT odd — the slots GitHub drops (issue #560).

    `queued-alarm.yml` recorded the reason first: `an odd minute; GitHub drops top-of-hour runs`
    (#275, #301). Measured 2026-10-23: `auto-merge.yml`'s `*/30 * * * *` produced 0 `schedule` runs
    of 66 while every odd-minute cron in the same repository fired normally.
    """
    return sorted(m for m in _expand(cron.split()[0], _MINUTES) if m % 2 == 0)


def test_every_cron_minute_is_odd():
    """No bot is scheduled on an even minute, because GitHub drops those slots (issue #560)."""
    # Given every cron in the tree, expanded to the minute values it fires at
    seen: list[str] = []
    offenders: list[str] = []

    # When each one is checked for an even minute
    for name in BOT_WORKFLOWS:
        for cron in _schedules(_load(name)):
            seen.append(cron)
            even = _even_minutes(cron)
            if even:
                offenders.append(f"{name}: {cron!r} fires at minute(s) {even}")

    # Then the guard is not vacuous, and the helper rejects the shape it exists to catch
    assert seen, "no cron found in any workflow — the guard would verify nothing"
    assert _even_minutes("*/30 * * * *") == [0, 30], (
        "the guard must catch `*/30 * * * *`: :00/:30 is the slot auto-merge's sweep sat on for 0 runs"
    )

    # And no workflow in the tree lands on one
    assert not offenders, (
        "cron minute(s) are even, and GitHub drops those slots (issue #560). "
        "Pick an odd minute:\n  " + "\n  ".join(offenders)
    )


def test_the_auto_merge_sweep_stays_scheduled():
    """`auto-merge`'s recheck sweep keeps a working schedule (issue #560).

    The always()-on-CI-completion retry (#558) is not a substitute: a deferral that clears with no
    push at all — an approving review, a `do-not-merge` label removed, a secret added — is retried by
    the cron and by nothing else.
    """
    # Given the auto-merge workflow, its schedule and its source
    name = "auto-merge.yml"
    workflow = _load(name)
    text = (WF / name).read_text()
    crons = _schedules(workflow)

    # Then it is still scheduled, twice an hour, on odd minutes
    assert crons, f"{name} declares no schedule: the recheck sweep would never retry a deferral"
    assert len(crons) == 1, f"{name} should own exactly one cron, found {crons}"
    minutes = sorted(_expand(crons[0].split()[0], _MINUTES))
    assert len(minutes) == 2, f"{name}: expected a 30-minute cadence, got {crons[0]!r}"
    assert not _even_minutes(crons[0]), (
        f"{name}: {crons[0]!r} lands on an even minute — that slot produced 0 runs (issue #560)"
    )

    # And the scheduled run drives the ONE sweep entry point, through the merge gate's own job
    assert "\n  recheck:" in text, f"{name}: the schedule must drive the `recheck` job"
    assert 'make auto-merge-recheck REPO="$REPO"' in text, (
        f"{name}: the sweep must go through `make auto-merge-recheck`, never a second merge path"
    )


# ---- green ⇒ merged is permanent policy: the merge gate cannot be removed (issue #874) ----------

#: The ONE file that merges a green pull request (its own header records why it is not a job in `ci.yml`).
AUTO_MERGE = "auto-merge.yml"

#: Triggers that fire BY THEMSELVES the moment a pull request's run finishes. `schedule` and
#: `workflow_dispatch` are BACKSTOPS, never the trigger: a workflow reachable only by a cron slot or by
#: hand merges nothing until that slot arrives or a human clicks it, which is the pause #874 forbids.
PR_COMPLETION_TRIGGERS = ("workflow_run", "check_suite")


def _triggers(wf: dict) -> set[str]:
    """The event names the workflow's `on:` block declares."""
    return set(_on(wf))


def test_the_auto_merge_workflow_is_in_the_tree_and_keeps_its_name():
    """Deleting the merge workflow is a red test, not a silently thinner pipeline (issue #874).

    The `name:` is load-bearing, not cosmetic: GitHub matches `on.workflow_run.workflows` against a
    workflow's top-level `name:` verbatim and takes no wildcard, so a rename stops every roster that
    names it from matching (#349 — a rename left rebase-bot's failures routed nowhere for a week).
    """
    # Given the merge workflow's path
    path = WF / AUTO_MERGE

    # Then  it exists, parses, and is still called `auto-merge`
    assert path.is_file(), (
        f"{path} is gone: a green PR would then never be merged, and no run would go red for it "
        f"(issue #874 — this behaviour may not be removed from the pipelines)")
    workflow = _load(AUTO_MERGE)
    assert workflow.get("name") == "auto-merge", (
        f"{AUTO_MERGE}: top-level `name:` is {workflow.get('name')!r}, not 'auto-merge' — a rename "
        f"breaks every `workflow_run.workflows` roster that names it (matched verbatim, no wildcard)")


def test_auto_merge_fires_by_itself_when_a_pr_run_completes():
    """Green ⇒ merged runs on its own; a manual-only or cron-only workflow is the pause, not the gate.

    Issue #874 was filed after the merge path was switched off by hand and nothing in the tree failed:
    the file was present, the workflow was `disabled_manually`, and PRs simply accumulated. A hermetic
    test cannot read the repository's own enable state (that is the GitHub API and an owner action), so
    this pins the half that lives in the tree — the file, an AUTOMATIC trigger on the CI run finishing,
    and a `merge` job that still demands a pull-request run that concluded `success`. Delete any of them
    and `ci-unit` is red instead of the behaviour going quiet.
    """
    # Given the merge workflow, its triggers and its merge job
    workflow = _load(AUTO_MERGE)
    on = _on(workflow)
    jobs = workflow.get("jobs") or {}
    problems: list[str] = []

    # When  every property that makes it merge a green PR with no human in the loop is checked
    automatic = _triggers(workflow) & set(PR_COMPLETION_TRIGGERS)
    if not automatic:
        problems.append(
            f"`on:` declares {sorted(_triggers(workflow))} and no automatic PR-completion trigger "
            f"({', '.join(PR_COMPLETION_TRIGGERS)}): a green PR is then merged by nobody until a cron "
            f"slot or a human arrives")
    if "workflow_run" in automatic:
        block = on.get("workflow_run")
        run: dict = block if isinstance(block, dict) else {}
        watched = [str(w) for w in (run.get("workflows") or [])]
        if "CI" not in watched:
            problems.append(
                f"`on.workflow_run.workflows` is {watched}: it must name `CI`, the workflow whose "
                f"green run authorises the merge")
        kinds = [str(t) for t in (run.get("types") or [])]
        if "completed" not in kinds:
            problems.append(
                f"`on.workflow_run.types` is {kinds}: without `completed` it never hears the run finish")
    merge_job = jobs.get("merge")
    if not isinstance(merge_job, dict):
        problems.append("the `merge` job is gone: nothing decides a merge any more")
    else:
        cond = str(merge_job.get("if") or "")
        for needle, why in (("workflow_run", "it is the run-completion gate"),
                            ("pull_request", "a push run on main has no PR to merge"),
                            ("conclusion == 'success'", "a red run must never reach the merge")):
            if needle not in cond:
                problems.append(f"the `merge` job's `if:` no longer requires {needle!r} ({why})")

    # Then  every property holds, and the failure names ALL of the ones that do not
    assert not problems, (
        f"{AUTO_MERGE} no longer merges a green PR by itself (issue #874):\n  "
        + "\n  ".join(problems))


if __name__ == "__main__":  # pragma: no cover - manual probe
    print(json.dumps({n: _schedules(_load(n)) for n in BOT_WORKFLOWS}, indent=2))
