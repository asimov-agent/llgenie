# Running the containerized suite (and monitoring it)

How to run `make test` / `make validate` inside the test image as a background job
and know, reliably, whether it is actually running — the TUI's signals lie.

## Launch pattern

Run the whole gate chain in ONE background command that appends an explicit
`rc=` line per stage to a log file, so completion is a fact in the log, not a
guess from the UI:

```bash
cd <worktree> && make openspec-check >/tmp/o.log 2>&1; echo "openspec=$?" >>/tmp/o.log; \
  make lint >>/tmp/o.log 2>&1; echo "lint=$?" >>/tmp/o.log; \
  (make test >/tmp/t.log 2>&1; echo "rc=$?" >>/tmp/t.log)
```

`make test` echoes the `docker run` line, so the log's first line tells you the
exact image and env the suite ran under.

## The TUI's background uptime is not a state

A background session shown as "starting 0 s" can be minutes in or already done —
the field is never updated for these jobs. Never trust it. The authoritative
signals, in order:

- `ps -o pid,etime,stat -p <pid>` — process alive and how long (ELAPSED).
- `docker ps --filter ancestor=<test-image>:latest` — the suite's container up.
- the `rc=` / `openspec=` / `lint=` lines the command itself appended to its log.

## A frozen log is not a hung process

`docker run` without a TTY block-buffers the container's stdout, so module
output only flushes when the buffer fills — the log can sit unchanged for
minutes while the suite runs. Before declaring a hang, check `docker top <id>`
for live child processes (e.g. `git ls-remote` from a probe test) and the
container's `Up` time.

## A timed-out tool call orphans the container

Killing the `make`/`docker run` client (a tool timeout, an interrupt) does NOT
stop the container — `docker run --rm` keeps running after its client dies, and
each orphan burns CPU indefinitely. After any interrupted run, sweep:

```bash
docker ps --filter ancestor=<test-image>:latest   # list
docker kill <id> …                                # kill every container but the live one
```

## A worktree cut before a merge runs the OLD Makefile chain

A worktree cut from an older base carries that base's `_test` recipe. If a
runner/CI change merged after the cut, the branch's `make test` still runs the
old chain (slow, streaming, noisy) — and CI will run the branch's own tree, so
the old chain is what gets validated. Merge the base into the branch BEFORE the
final verification run so you test the tree CI will actually run.
