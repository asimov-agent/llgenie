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


if __name__ == "__main__":  # pragma: no cover - manual probe
    print(json.dumps({n: _schedules(_load(n)) for n in BOT_WORKFLOWS}, indent=2))
