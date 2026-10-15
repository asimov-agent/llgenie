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
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WF = REPO / ".github" / "workflows"

#: The bots. Each is one scheduled workflow whose runs are a bot's own pipeline.
BOT_WORKFLOWS = (
    "issue-bot.yml",
    "fix-bot.yml",
    "queued-alarm.yml",
    "engine-bump.yml",
    "engine-bump-rebase.yml",
    "registry-sync.yml",
)

#: The minutes an hourly-minute bot reserves on every weekday (must not be reused by a
#: daily/weekly bot). fix-bot: :17; queued-alarm: :07 and :37.
RESERVED_MINUTES = {17, 7, 37}

_MINUTES = range(60)
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


def _slots(cron: str) -> set[tuple[int, int]]:
    """The (minute, weekday) pairs a classic 5-field cron owns — the hour is irrelevant to a
    shared-slot collision."""
    fields = cron.split()
    assert len(fields) == 5, f"not a 5-field cron: {cron!r}"
    minute_f, _hour_f, _dom, _month, dow_f = fields
    minutes = _expand(minute_f, _MINUTES)
    weekdays = _expand(dow_f, _WEEKDAYS) if dow_f != "*" else set(_WEEKDAYS)
    return {(m, w) for m in minutes for w in weekdays}


def _concurrency(wf: dict):
    """(group, cancel-in-progress) or None when the workflow declares no group."""
    conc = wf.get("concurrency")
    if conc is None:
        return None
    if isinstance(conc, dict):
        return conc.get("group"), conc.get("cancel-in-progress")
    return conc, None


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
    """A daily/weekly bot must not land on a minute the hourly bots reserve every day."""
    # Given the minutes the hourly-minute bots reserve on every weekday
    # When a daily/weekly bot's cron is read
    for name in BOT_WORKFLOWS:
        if name in ("fix-bot.yml", "queued-alarm.yml"):
            continue
        for cron in _schedules(_load(name)):
            for minute, _weekday in _slots(cron):
                # Then it must not reuse a reserved minute
                assert minute not in RESERVED_MINUTES, (
                    f"{name}: minute {minute} is reserved by an hourly bot (issue #275)"
                )


if __name__ == "__main__":  # pragma: no cover - manual probe
    print(json.dumps({n: _schedules(_load(n)) for n in BOT_WORKFLOWS}, indent=2))
