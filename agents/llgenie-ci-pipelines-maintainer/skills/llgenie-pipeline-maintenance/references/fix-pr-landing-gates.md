# Landing a fix PR in llgenie: the local gate battery

The pipeline fix itself is half the work; the other half is the commit-body contract and the documentation gates that red a bot PR after the change is correct. Run the whole battery locally before pushing — a red found in CI costs a push cycle and un-arms auto-merge.

## 1. Cut the branch from the sha you fetched now, and cite that base

```bash
git fetch origin main          # canonical upstream is asimov-agent/llgenie
git switch -c fix/<issue>-<slug> origin/main
```

When the clone's `origin` is a fork, `origin/main` can be a **stale** ref while the branch was really cut from upstream `main`. The diff then balloons and `sync-line` / `agents-line` red for no reason. Resolve the true base explicitly:

```bash
git merge-base <base-tip> HEAD      # must equal the branch's first parent
```

Run every gate with `--base <that sha>`, and write the same sha into the commit's `BASE:` line.

## 2. The commit-body lines, and the gate each one satisfies

| Line | Shape | Gate |
|---|---|---|
| subject | `type(area): ... (closes #N)` | `check-pr-closing` needs an **adjacent** closing keyword; `Issue: #N` alone is a claim, not a close |
| `AGENTS:` | `AGENTS: <ancestor-sha> <bytes>b <lines>l` | `agents-line`: the sha must be reachable from **both** head and base; stats are of `AGENTS.md` at that sha |
| `BASE:` | `BASE: <sha> (== origin/main at open)` | `check-pr-base` |
| `SYNC:` | `SYNC: <profile> make sync-agent-profile PROFILE=<profile>` | `sync-line`: required for **every** changed `agents/<profile>/**` path |
| `OPENSPEC:` | `OPENSPEC: <active-change-name>` | `openspec-change`, bot PRs only |

`OPENSPEC:` must be **at line start** — the matcher is anchored `^OPENSPEC:`, so the same token appended to the end of another line silently fails. Confirm the name is an active change by listing `openspec/changes/` names; never invent one.

Verify with the real code paths, not by eye:

```bash
python3 scripts/check_pr_hygiene.py openspec-change --head "$HEAD" --base "$BASE" --body-file /tmp/msg.txt
python3 scripts/check_pr_hygiene.py agents-line    --head "$HEAD" --base "$BASE" --body-file /tmp/msg.txt
python3 scripts/check_pr_hygiene.py sync-line      --head "$HEAD" --base "$BASE" --body-file /tmp/msg.txt
python3 scripts/check_pr_closing.py check --body-file /tmp/msg.txt --head "$(git branch --show-current)" --base "$BASE" --rev HEAD
python3 scripts/check_pr_base.py    check --base "$BASE" --rev HEAD
```

Read each `rc=`, never the tail of a pipe. `_active_change_names(...)` takes a `pathlib.Path`, not a string — passing `'.'` raises `TypeError`.

## 3. Change-note trio for a NOTE_SURFACE change

A diff touching `scripts/*` or `agents/**/skills/*` (tests are exempt) owes a note, or `check-docs` reds:

1. `agent-wiki/<stem>.md` — the note.
2. `docs/changes.d/<stem>.md` — one fragment row; the stem must match a note stem.
3. `make changes-index` — regenerate `CHANGES.md` from the fragments (never hand-edit `CHANGES.md`).

Then `make check-docs`; it reports the fragment count and the census ancestor, and both must be clean.

## 4. `check-pr-acceptance` is a designed hold, not a bug

A bot PR that closes an issue whose `## Acceptance criteria` are still unticked reds `check-pr-acceptance`. Do **not** self-tick (verdict-gated). Legitimate outcomes:

- A reviewer's verdict write-back ticks them — the red is the gate doing its job; wait rather than work around it.
- A criterion the change genuinely does **not** meet is declared in the PR body under `## Not covered`, phrased to match that criterion's **leading three words** (normalised) — the exemption matches on that anchor, so any other wording still reds.
- A criterion the change **does** satisfy must never be declared out of scope just to go green.

When the only red is this gate and the code is guard-proven, say so explicitly instead of weakening the gate.

## 5. Run the repo's own Python in its image

The host venv may lack repo deps (`yaml`, …). Run tests and parses in the test image:

```bash
docker run --rm -u root -e PYTHONPATH=/repo/scripts \
  -v "$PWD":/repo:rw -w /repo -e HOME=/root llgenie/test:latest \
  python -m pytest tests/test_<new_guard>.py tests/test_<sibling>.py -q
```

After editing a workflow, parse it in that image (`yaml.safe_load`) and print each job's `timeout-minutes` — a YAML typo in a `timeout-minutes` addition is otherwise invisible until CI.

## 6. Prove the guard, then keep the commit clean

- Run a new rule on the **unfixed** tree first: it must name the exact violation (e.g. `<workflow>::<job>` has no `timeout-minutes`); then fix and get zero. A rule only ever run on the fixed tree has demonstrated nothing.
- Search the test tree for any assertion on the shape you changed (an old header line, a job count, a `.PHONY` list) before pushing — an exact-list assertion reds on a correct new addition; prefer subset checks.
- Write the commit message to `/tmp` and use `git commit -F`; never `git add` a scratch file such as `commitmsg.txt`. Check `git show --stat` shows exactly the expected files before pushing.
