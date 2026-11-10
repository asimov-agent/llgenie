#!/usr/bin/env python3
"""Detect the 'retry killed by what it retries' shape across workflow files.

Two findings, both of which look green in CI today and are invisible in a status badge:

  1. WORKFLOW LEVEL CONCURRENCY. A top-level `concurrency:` block with `cancel-in-progress: true`
     cancels EVERY job in the run. If the workflow also contains a job that depends on another and
     runs unconditionally (a recheck / retry / recovery pass), that retry is cancelled along with the
     attempt it exists to recover. Fix: job-level groups — the superseding job keeps
     `cancel-in-progress: true`, the retry job gets its own group with `cancel-in-progress: false`.

  2. A RETRY JOB'S WAIT BUDGET. A retry that decides N items while each decision may block for B
     seconds runs for N*B. Print the job's `timeout-minutes` so a human can check N x B fits; the
     probe cannot know the bound, only that the risk exists.

Usage:
    python3 scripts/check-workflow-concurrency-shape.py [WORKFLOW_GLOB ...]

Defaults to `.github/workflows/*.yml` in the current directory. Exit code 1 means at least one
workflow carries finding 1; finding 2 is advisory.
"""
from __future__ import annotations

import glob
import re
import sys


def strip_comments(text: str) -> str:
    """Drop full-line `#` comments so YAML prose cannot satisfy or defeat a structural check."""
    return "\n".join("" if line.lstrip().startswith("#") else line for line in text.splitlines())


def top_level_concurrency(text: str) -> str | None:
    """The workflow-level `concurrency:` block, if any. Column-1 match only."""
    m = re.search(r"^concurrency:\s*\n((?:[ \t]+.*\n)+)", strip_comments(text), re.M)
    return m.group(1) if m else None


def jobs(text: str) -> dict[str, str]:
    """Split the `jobs:` mapping into {job_name: body}."""
    body = strip_comments(text)
    start = re.search(r"^jobs:\s*\n", body, re.M)
    if not start:
        return {}
    out: dict[str, str] = {}
    cur: str | None = None
    buf: list[str] = []
    for line in body[start.end():].splitlines():
        m = re.match(r"^  ([A-Za-z0-9_.-]+):\s*$", line)
        if m:
            if cur:
                out[cur] = "\n".join(buf)
            cur, buf = m.group(1), []
        elif cur is not None:
            buf.append(line)
    if cur:
        out[cur] = "\n".join(buf)
    return out


def job_concurrency(job_body: str) -> str | None:
    m = re.search(r"^    concurrency:\s*\n((?:[ \t]+.*\n)+)", job_body, re.M)
    return m.group(1) if m else None


def job_timeout(job_body: str) -> int | None:
    m = re.search(r"^    timeout-minutes:\s*(\d+)\s*$", job_body, re.M)
    return int(m.group(1)) if m else None


def retry_jobs(all_jobs: dict[str, str]) -> dict[str, str]:
    """Jobs that DEPEND on another job and run unconditionally — a recovery/retry pass."""
    out: dict[str, str] = {}
    for name, body in all_jobs.items():
        needs = re.search(r"^    needs:\s*(.+)$", body, re.M)
        always = re.search(r"^    if:\s*always\(\)", body, re.M)
        if needs and always:
            out[name] = body
    return out


def check(path: str) -> tuple[list[str], list[str]]:
    text = open(path, encoding="utf-8").read()
    hard: list[str] = []
    soft: list[str] = []

    all_jobs = jobs(text)
    retries = retry_jobs(all_jobs)
    top = top_level_concurrency(text)

    if top and retries and "cancel-in-progress: true" in top:
        hard.append(
            f"{path}: workflow-level `concurrency` with `cancel-in-progress: true` cancels the "
            f"entire run, including the retry job(s) {sorted(retries)}. Move the superseding group "
            f"onto the deciding job and give each retry job its own group with "
            f"`cancel-in-progress: false`."
        )

    for name, body in retries.items():
        own = job_concurrency(body)
        if own and "cancel-in-progress: false" not in own:
            hard.append(
                f"{path}: retry job `{name}` declares its own concurrency without "
                f"`cancel-in-progress: false` — a newer run can cancel the recovery pass."
            )
        budget = job_timeout(body)
        if budget:
            soft.append(
                f"{path}: retry job `{name}` has timeout-minutes: {budget} — confirm its item cap "
                f"x per-item wait fits inside it (N x B < timeout)."
            )

    if not top and retries and not any(job_concurrency(b) for b in all_jobs.values()):
        soft.append(
            f"{path}: no concurrency declared anywhere although retry job(s) {sorted(retries)} "
            f"exist — confirm supersession of the deciding job is intentional."
        )
    return hard, soft


def main(argv: list[str]) -> int:
    patterns = argv[1:] or [".github/workflows/*.yml"]
    paths: list[str] = []
    for pat in patterns:
        paths.extend(sorted(glob.glob(pat)))
    if not paths:
        print(f"no workflow files matched {patterns}", file=sys.stderr)
        return 2

    hard_total = 0
    for path in paths:
        try:
            hard, soft = check(path)
        except OSError as exc:
            print(f"[skip] {path}: {exc}", file=sys.stderr)
            continue
        for line in hard:
            print(f"[FAIL] {line}")
        for line in soft:
            print(f"[note] {line}")
        hard_total += len(hard)

    print(f"[workflow-concurrency] {len(paths)} workflow(s) checked, {hard_total} failure(s)")
    return 1 if hard_total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
