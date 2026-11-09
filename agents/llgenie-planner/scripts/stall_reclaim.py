#!/usr/bin/env python3
"""stall_reclaim.py — detect STALLED kanban workers and release their claims.

Runs safely INSIDE the orchestrator tick: the kanban path sends no signals, so
nothing here can terminate the process tree it runs in.

WHY THIS EXISTS
---------------
A kanban worker can sit alive-but-idle indefinitely: the process exists, it emits
`heartbeat` every minute, and the board reports it `running` — while its log has
not grown for hours. Measured on this host 2026-11-08: four workers at log-age
159/110/88/50 min, all 0.1% CPU, two of the five ever having written a single line
of output. Each held a queue slot, so `kanban dispatch` reported capacity-full and
real work could not be placed on the board.

SIGNALS THAT DO NOT WORK (all measured — do not build on them)
  * `last_heartbeat_at` — reads 0 minutes old for a worker idle 2.5 h.
  * `max_runtime_seconds` — a column whose value is only PRINTED into the worker's
    prompt ("Max runtime: Ns"); nothing enforces it.
  * task status `running` — true whenever the pid is alive.
  * wall-clock age alone — a legitimately long build looks identical.
  * `<kanban>/logs/<task>.log` — gets the session header at spawn and nothing
    after (measured 2026-11-09: `kanbanlog == age` on 8/8 running tasks), so its
    mtime age is the process age, not a work signal.
  * `cpu` alone — a worker blocked on a model API accrues ~1 tick per window, so
    `cpu <= MAX_CPU_TICKS` holds for every healthy worker.

WHAT IT MEASURES INSTEAD — the lane session log and the API-call counter
  For each candidate task, the lane comes from `task_runs.profile`. The signals
  are `$HOME/.hermes/profiles/<lane>/logs/agent.log`'s mtime and the last
  `API call #<N>` in that file. Each verdict is taken from TWO samples >= 60 s
  apart; a task is ACTIVE when EITHER the agent.log mtime advanced across the
  samples OR the API-call counter rose. A task reads STALLED on two CONSECUTIVE
  verdicts before any action.

WHAT IT DOES ON A STALL — `kanban reclaim` (and `kanban block` once the churn cap
trips), the supported release of the claim. No signal is ever sent to a
kanban-worker pid; there is no kill in the kanban path at all. The separate
DM-waiter reaper (`pgrep -f bot_mode_dm.py`) may keep SIGTERM/SIGKILL — it is not a
kanban worker — but it is its own function whose pid source is its own pgrep
enumeration, never a `task_runs` row.

USAGE
  stall_reclaim.py              # dry run: print verdicts, change nothing
  stall_reclaim.py --apply      # reclaim stalled tasks / block churned ones
  STALL_MIN=20 stall_reclaim.py --apply
"""

from __future__ import annotations

import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

KANBAN_HOME = os.environ.get("KANBAN_HOME", os.path.expanduser("~/.hermes"))
LOG_DIR = os.path.join(KANBAN_HOME, "kanban", "logs")
DB = os.environ.get("KANBAN_DB", os.path.join(KANBAN_HOME, "kanban.db"))
PROFILES_HOME = os.path.join(KANBAN_HOME, "profiles")
HERMES_BIN = os.environ.get(
    "HERMES_BIN",
    os.path.expanduser("~/.hermes/hermes-agent/.hermes/bin/hermes"),
)
STALL_MIN = int(os.environ.get("STALL_MIN", "20"))          # minutes
SAMPLE_APART = int(os.environ.get("SAMPLE_APART", "60"))    # seconds between samples
MAX_CPU_TICKS = int(os.environ.get("MAX_CPU_TICKS", "5"))   # utime+stime ticks
MAX_RECLAIMS = int(os.environ.get("MAX_RECLAIMS", "3"))
STATE_WINDOW_H = int(os.environ.get("STATE_WINDOW_H", "6"))
STATE = os.environ.get("STATE", os.path.join(KANBAN_HOME, "kanban", ".stall_reclaims.json"))
DM_STALL_MIN = int(os.environ.get("DM_STALL_MIN", "30"))    # minutes
DM_ENABLED = os.environ.get("DM_ENABLED", "1") != "0"

APPLY = "--apply" in sys.argv[1:]

API_RE = re.compile(r"API call #(\d+)", re.M)
WORKER_MARKERS = ("kanban_worker", "kanban-worker")

YOUNG, ACTIVE, STALLED = "YOUNG", "ACTIVE", "STALLED"


def say(*parts: object) -> None:
    print("[stall-reclaim] " + " ".join(str(p) for p in parts))


# --------------------------------------------------------------------------- #
# read-only probes (real /proc + lane agent.log)                              #
# --------------------------------------------------------------------------- #

def read_cmdline(pid: int) -> Optional[str]:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            raw = f.read()
    except OSError:
        return None
    return raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()


def read_ticks(pid: int) -> Optional[int]:
    """utime+stime from /proc/<pid>/stat (fields 14 and 15, 1-indexed)."""
    try:
        with open(f"/proc/{pid}/stat") as f:
            data = f.read()
    except OSError:
        return None
    # comm may contain parens; split on the LAST ')'
    try:
        rest = data.split(")", 1)[1].split()
        # rest[0]=state, rest[1]=ppid, rest[11]=utime(14), rest[12]=stime(15)
        return int(rest[11]) + int(rest[12])
    except (ValueError, IndexError):
        return None


def pid_alive(pid: int) -> bool:
    # `/proc/<pid>` existence, matching the original `.sh` guard. Never
    # `os.kill(pid, 0)` — the kanban path carries no signal primitive at all.
    return os.path.isdir(f"/proc/{pid}")


def is_kanban_worker_cmd(cmd: Optional[str]) -> bool:
    if not cmd:
        return False
    return any(marker in cmd for marker in WORKER_MARKERS)


def agent_log_path(profile: str) -> str:
    return os.path.join(PROFILES_HOME, profile, "logs", "agent.log")


def read_api_count(path: str) -> Optional[int]:
    """The last `API call #<N>` in the lane's agent.log, or None."""
    try:
        with open(path) as f:
            data = f.read()
    except OSError:
        return None
    matches = API_RE.findall(data)
    return int(matches[-1]) if matches else None


def log_mtime(path: str) -> Optional[float]:
    try:
        return os.stat(path).st_mtime
    except OSError:
        return None


def agent_log_age_min(profile: str, now: float) -> Optional[float]:
    mt = log_mtime(agent_log_path(profile))
    if mt is None:
        return None
    return max(0.0, (now - mt) / 60.0)


# --------------------------------------------------------------------------- #
# classification                                                              #
# --------------------------------------------------------------------------- #

def classify(age_m: float, log_age_m: Optional[float], log_advanced: bool,
             cpu_ticks: int) -> str:
    """The YOUNG/ACTIVE/STALLED matrix over the corrected operands.

    * fresh process (age < STALL_MIN)                -> YOUNG, never a candidate
    * log axis advanced (agent.log mtime advanced OR API counter rose) -> ACTIVE
    * old process + fresh agent.log (age < STALL_MIN but not advanced) -> YOUNG
    * old + stale log + busy CPU (> MAX_CPU_TICKS)   -> ACTIVE
    * old + stale log + idle CPU                     -> STALLED
    """
    if age_m < STALL_MIN:
        return YOUNG
    if log_advanced:
        return ACTIVE
    if log_age_m is not None and log_age_m < STALL_MIN:
        return YOUNG
    if cpu_ticks > MAX_CPU_TICKS:
        return ACTIVE
    return STALLED


# --------------------------------------------------------------------------- #
# sampling and verdict                                                        #
# --------------------------------------------------------------------------- #

@dataclass
class Sample:
    log_mtime: Optional[float]
    api_count: Optional[int]
    cpu_ticks: Optional[int]


def real_sample(pid: int, profile: str) -> Sample:
    return Sample(
        log_mtime=log_mtime(agent_log_path(profile)),
        api_count=read_api_count(agent_log_path(profile)),
        cpu_ticks=read_ticks(pid),
    )


@dataclass
class Worker:
    task_id: str
    pid: Optional[int]
    profile: Optional[str]
    started_at: int  # epoch seconds


@dataclass
class Verdict:
    verdict: str
    age_m: float
    log_age_m: Optional[float]
    api1: Optional[int]
    api2: Optional[int]
    cpu1: Optional[int]
    cpu2: Optional[int]
    samples: int = 2

    def line(self, pid: Optional[int]) -> str:
        age = int(round(self.age_m))
        log = "%.1f" % self.log_age_m if self.log_age_m is not None else "?"
        api = "#%s->#%s" % (self.api1, self.api2)
        cpu = "%st/%st" % (self.cpu1, self.cpu2)
        return "%-7s pid=%s age=%dm log=%sm api=%s cpu=%s samples=%d" % (
            self.verdict, pid, age, log, api, cpu, self.samples)


def verdict_from(worker: Worker, s1: Sample, s2: Sample, now2: float) -> Verdict:
    """One verdict = two samples >= 60 s apart; operands are both samples."""
    age_m = max(0.0, (now2 - worker.started_at) / 60.0)
    log_age_m = None
    if worker.profile and s2.log_mtime is not None:
        log_age_m = max(0.0, (now2 - s2.log_mtime) / 60.0)
    log_advanced = bool(
        (s1.log_mtime is not None and s2.log_mtime is not None
         and s2.log_mtime > s1.log_mtime)
        or (s1.api_count is not None and s2.api_count is not None
            and s2.api_count > s1.api_count)
    )
    cpu1 = s1.cpu_ticks or 0
    cpu2 = s2.cpu_ticks or 0
    cpu_ticks = max(0, cpu2 - cpu1)
    return Verdict(
        verdict=classify(age_m, log_age_m, log_advanced, cpu_ticks),
        age_m=age_m,
        log_age_m=log_age_m,
        api1=s1.api_count,
        api2=s2.api_count,
        cpu1=cpu1,
        cpu2=cpu2,
    )


def two_sample_verdict(worker: Worker, sample_fn: Callable[[Optional[int], Optional[str]], Sample],
                       base_now: Optional[float], delay: float) -> Verdict:
    """Take two samples >= delay seconds apart and return the verdict."""
    s1 = sample_fn(worker.pid, worker.profile)
    if delay > 0:
        time.sleep(delay)
    s2 = sample_fn(worker.pid, worker.profile)
    now2 = base_now + delay if base_now is not None else time.time()
    return verdict_from(worker, s1, s2, now2)


# --------------------------------------------------------------------------- #
# DB candidates (allowlist)                                                   #
# --------------------------------------------------------------------------- #

def running_candidates(db_path: str) -> Iterable[Worker]:
    """task_runs rows whose status is running with a worker_pid — the allowlist."""
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return
    try:
        rows = con.execute(
            "SELECT task_id, worker_pid, profile, started_at "
            "FROM task_runs WHERE status='running' AND worker_pid IS NOT NULL"
        ).fetchall()
    finally:
        con.close()
    for task_id, pid, profile, started_at in rows:
        yield Worker(task_id=task_id, pid=pid, profile=profile, started_at=int(started_at or 0))


# --------------------------------------------------------------------------- #
# the kanban path: `kanban reclaim` / `kanban block` ONLY — no signals         #
# --------------------------------------------------------------------------- #

def reclaim_task(worker: Worker, kind: str) -> bool:
    if kind == STALLED:
        reason = ("stalled: no log growth in agent.log and no API-call advance "
                  f"over 2 samples (pid={worker.pid}) — reclaimed by stall-reclaim")
        cmd = [HERMES_BIN, "kanban", "reclaim", worker.task_id, "--reason", reason]
    else:  # ORPHAN
        reason = f"orphaned claim: worker pid {worker.pid} no longer exists"
        cmd = [HERMES_BIN, "kanban", "reclaim", worker.task_id, "--reason", reason]
    try:
        return subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    except OSError:
        return False


def block_task(worker: Worker, prior: int, log_age_m: Optional[float], cpu: int) -> bool:
    reason = (f"stalled {prior}x in {STATE_WINDOW_H}h and re-stalled after each "
              "reclaim — a structural stall, not a transient one; needs a human. "
              f"Last: no log growth {log_age_m}m, {cpu} cpu ticks.")
    cmd = [HERMES_BIN, "kanban", "block", worker.task_id, reason]
    try:
        return subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    except OSError:
        return False


# --------------------------------------------------------------------------- #
# churn cap — state written only on a real reclaim                            #
# --------------------------------------------------------------------------- #

def reclaim_count(task: str) -> int:
    try:
        with open(STATE) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return 0
    cut = time.time() - STATE_WINDOW_H * 3600
    return sum(1 for t in d.get(task, []) if t >= cut)


def reclaim_record(task: str) -> None:
    try:
        with open(STATE) as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    cut = time.time() - STATE_WINDOW_H * 3600
    for k in list(d):
        d[k] = [t for t in d[k] if t >= cut]
    d.setdefault(task, []).append(time.time())
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(d, f)


# --------------------------------------------------------------------------- #
# the run: two consecutive verdicts before any action                         #
# --------------------------------------------------------------------------- #

def sweep_worker(worker: Worker, now: float, sample_fn: Callable,
                 delay: float, apply: bool,
                 counters: dict) -> None:
    if not worker.pid or not pid_alive(worker.pid):
        say("ORPHAN", f"{worker.task_id} pid={worker.pid} — process gone, claim still held")
        counters["orphan"] += 1
        if apply:
            if reclaim_task(worker, "ORPHAN"):
                say("        reclaimed", worker.task_id)
                counters["reclaimed"] += 1
        return
    cmd = read_cmdline(worker.pid)
    if not is_kanban_worker_cmd(cmd):
        say("SKIP", f"{worker.task_id} pid={worker.pid} — not a kanban worker")
        return

    v1 = two_sample_verdict(worker, sample_fn, now, delay)
    v = v1
    if v1.verdict == STALLED:
        v2 = two_sample_verdict(worker, sample_fn, None, delay)
        say(v1.line(worker.pid))
        say(v2.line(worker.pid))
        if v2.verdict == STALLED:
            v = v2
            counters["stalled"] += 1
            if apply:
                _act_on_stalled(worker, v, counters)
            return
        counters["active"] += 1
        return
    say(v.line(worker.pid))
    if v.verdict == YOUNG:
        counters["young"] += 1
    else:
        counters["active"] += 1


def _act_on_stalled(worker: Worker, v: Verdict, counters: dict) -> None:
    """Kanban verbs only — never a signal. `kanban reclaim`, or `kanban block`
    once the churn cap trips."""
    prior = reclaim_count(worker.task_id)
    if prior >= MAX_RECLAIMS:
        say("        CHURN",
            f"{worker.task_id} already reclaimed {prior}x in {STATE_WINDOW_H}h "
            "— blocking instead of recycling")
        if block_task(worker, prior, v.log_age_m, (v.cpu2 or 0) - (v.cpu1 or 0)):
            say("        blocked", worker.task_id)
            counters["blocked"] += 1
        else:
            say("        WARN block failed for", worker.task_id)
        return
    if reclaim_task(worker, STALLED):
        say("        reclaimed", worker.task_id, f"({prior}+1/{MAX_RECLAIMS})")
        reclaim_record(worker.task_id)
        counters["reclaimed"] += 1
    else:
        say("        WARN reclaim failed for", worker.task_id)


# --------------------------------------------------------------------------- #
# the separate DM-waiter reaper — not a kanban worker                          #
# --------------------------------------------------------------------------- #

def _reap_dm_waiters(apply: bool) -> tuple:
    """SIGTERM/SIGKILL is allowed HERE — these are NOT kanban workers. The pid
    source is this own pgrep enumeration and nothing else; a `task_runs`
    worker_pid never enters this function."""
    stalled = reaped = 0
    if not DM_ENABLED:
        return stalled, reaped
    try:
        out = subprocess.check_output(["pgrep", "-f", "bot_mode_dm.py"])  # proc-allow: pgrep rc=1 on no-match is the probe signal, caught below; #797, DM-reaper only
        pids = [int(p) for p in out.split()]
    except (OSError, subprocess.CalledProcessError, ValueError):
        return stalled, reaped
    for pid in pids:
        if not pid_alive(pid):
            continue
        cmd = read_cmdline(pid)
        if "bot_mode_dm.py" not in (cmd or ""):
            continue
        age_s = _process_elapsed(pid)
        if age_s is None or (age_s / 60) < DM_STALL_MIN:
            continue
        stalled += 1
        say("DM-STALL", f"pid={pid} age={age_s // 60}m — no timeout flag, lane has not answered")
        if not apply:
            say("        (dry run)")
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(2)
            if pid_alive(pid):
                os.kill(pid, signal.SIGKILL)
            if pid_alive(pid):
                say("        WARN pid", pid, "survived")
            else:
                say("        reaped", pid)
                reaped += 1
        except OSError:
            continue
    return stalled, reaped


def _process_elapsed(pid: int) -> Optional[int]:
    try:
        out = subprocess.check_output(["ps", "-o", "etimes=", "-p", str(pid)])  # proc-allow: ps rc=1 on a gone pid is the probe signal, caught below; #797, DM-reaper only
        return int(out.strip())
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# main                                                                        #
# --------------------------------------------------------------------------- #

def run(apply: bool = APPLY, sample_fn: Callable = real_sample,
        delay: float = SAMPLE_APART, db_path: str = DB, now: Optional[float] = None) -> None:
    if now is None:
        now = time.time()
    if not os.path.exists(db_path):
        say("no kanban DB at", db_path)
        return
    candidates = list(running_candidates(db_path))
    if not candidates:
        say("no running workers")
        return
    counters = {"stalled": 0, "active": 0, "young": 0, "orphan": 0,
                "reclaimed": 0, "blocked": 0}
    for worker in candidates:
        sweep_worker(worker, now, sample_fn, delay, apply, counters)
    dm_stalled, dm_reaped = _reap_dm_waiters(apply)
    say("----")
    say("tasks:", f"stalled={counters['stalled']} active={counters['active']} "
        f"young={counters['young']} orphan={counters['orphan']} "
        f"reclaimed={counters['reclaimed']} blocked={counters['blocked']}")
    say("dm:", f"stalled={dm_stalled} reaped={dm_reaped} threshold={DM_STALL_MIN}m")
    say("mode=%s task_threshold=%dm cap=%d/%dh"
        % ("APPLY" if apply else "DRY", STALL_MIN, MAX_RECLAIMS, STATE_WINDOW_H))


if __name__ == "__main__":
    run()
