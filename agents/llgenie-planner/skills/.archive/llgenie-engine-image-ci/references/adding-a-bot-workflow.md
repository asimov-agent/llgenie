# Adding a scheduled / dispatchable bot workflow to llgenie

A new bot is a workflow + a deterministic script + an optional single agent leg + tests +
docs. Six repository gates read what you write, and each one has a shape it expects. Work the
list in this order; every command below is the gate the CI job actually runs.

## 1. Pick a slot the guard will accept

`tests/test_bot_pipeline_isolation.py` derives the bot set from the workflow directory (any
`schedule:` is a bot) and fails on a shared `(minute, weekday)` slot or a missing/shared
`concurrency:` group.

- Every bot declares `concurrency: {group: <its own name>, cancel-in-progress: false}`.
- An **hourly** bot (`fix-bot`, `issue-refiner`, `queued-alarm`) reserves its minute on all
  seven weekdays. Derive the reserved set from the crons; do not hand-copy a list:
  `grep -h 'cron:' .github/workflows/*.yml`.
- A 6-hourly bot (`*/6 * * *`) still owns its minute on every weekday, so it must also avoid
the hourly minutes, not only the daily/weekly ones.
- Comment the slot in the cron line (`# every 6 hours, its own slot`) and put the same claim
in the header without writing a bare `HH:MM UTC` the dispatch-form guard will compare against
the cron.

## 2. `check_dispatch_forms` — the dispatch dialog is the interface

`make check-dispatch-forms` (inside `ci-unit`) requires, for every file with
`workflow_dispatch:`:

- `name:` = `<identifier> — <what the run does, and its bound>`; the part after the separator
  must be long enough to describe the work, and it must not repeat the file stem.
- Every input has a `description:` (>= 10 chars, written as an instruction) **and** a
  `default:` or `required: true`.
- A `# Trigger surface:` / `# Flow:` / `# Never:` header block. `Flow:` must name real
  `make` targets (`MAKE_IN_FLOW` resolves them against the Makefile) — a target that does not
  exist is a violation.
- Any `HH:MM UTC` in the header must match a cron in the same file. Omit the clock wording if
  the schedule is an interval.
- The README's generated table must match: regenerate with
  `make check-dispatch-forms report` (target id `dispatch-forms-report`) and paste between the
  `<!-- dispatch-forms:begin -->` / `<!-- dispatch-forms:end -->` markers.

## 3. The agent leg: one seam, one make target per stage

- `require_env.py <KEYS>` as the first recipe line, then `scripts/ci_images.py ensure agent`,
then `$(call scrubbed_run, $(RUNTIME) run ... $(AGENT_IMAGE) bash -lc 'make _<internal>')`.
- Forward credentials with `$(AGENT_SHELL_FORWARD)`; the workflow proves them with
`make agent-shell-keys-check AGENT_SHELL_CHECK_KEYS="..."`.
- **Never forward a non-credential variable with `-e NAME`.** `tests/test_agent_shell_keys.py`
reads every `-e [A-Z_]+` in an agent leg as a credential the agent's shell must be proven to
see, so a path or a brief name forwarded that way reds the suite. Pass it as a make variable
in the container command instead: `bash -lc 'make _leg DOC="$(DOC)"'` (make expands it before
`docker run`).
- The agent writes exactly one file. Enforce it in the deterministic publish step
(`git status --porcelain --untracked-files=no`, refuse anything but the target file); do not
trust the prompt alone.

## 4. The producer text gates

`make check-pr-hygiene` and `make check-pr-authors` parse the SOURCE of any file under
`scripts/`, the workflows, and the Makefile that can commit or open a PR. They read text, not
your intent:

- **PR body:** `--body-file -` (stdin) is read as the literal placeholder `-` and fails. Pass
the rendered body with `--body` and a variable (`"--body", pr_body`) so the guard sees a real
value.
- **Commit body:** `git commit -m <subject> -m <body>` in one call is fine; a lone `-m` without
a body part fails.
- **Author identity:** `git config user.name "Asimov Agent"` +
`git config user.email support@docondee.com` before the commit is the shape the parser reads
whole. An inline Python argv identity (`"-c", "user.name=Asimov Agent"`) is truncated to the
first token (`Asimov`) and reported as off-allowlist — a false positive in the guard, so use
`git config` in producers rather than fighting it.

## 5. Retired names are scanned in NEW files too

`tests/test_rename_llgenie_serve.py` greps live files (docs included) for the retired
`llama_serve` module name. A freshly written `docs/*.md` or README section that mentions it
reds the suite even though nothing executable changed. Say "the launcher" and
`scripts/llgenie_serve.py`.

## 6. Quiet-by-default and never-merge

- Decide drift deterministically (git state, a marker, a run stamp) and make the no-op case
print `action=none` and exit 0. A 6-hourly cadence without a drift check files ~4 issues/day.
- Before filing, check for an already-open PR with the bot's branch prefix and report
`action=pending` instead — otherwise two runs in one review window double-file.
- Refuse loudly on: target file missing / under a real size floor, checkout not `main`, tracked
edits outside the target file. State the refusal in the OpenSpec scenario and test it.
- No producer ever merges or pushes to `main`; the PR is the deliverable.

## 7. Verification order (do not reorder)

1. Focused pytest from the host venv, so a broken shape costs seconds:
   `$HOME/llama-gguf-tools/.venv/bin/python -m pytest tests/test_<new>.py -q`
2. The structural gates in one batch:
   `make check-wiring check-docs check-workflows check-dispatch-forms check-pr-hygiene check-pr-authors lint`
3. Full `make test-unit` LAST, after every edit. It runs ~13-14 minutes on the host.
   Redirect it to a file and poll the file — `make test-unit | tail -40` buffers everything
   until exit and shows nothing while it runs:
   `(make test-unit > /tmp/unit.log 2>&1; echo EXIT=$? >> /tmp/unit.log) &`
   A suite started before your last edits proves nothing; kill and re-run it.
4. `make openspec-validate NAME=<change>` and `make openspec-tasks-check NAME=<change>`; tick
each task only after its command exited 0.

Expect the full suite to catch what focused tests cannot: a new leg's `-e` list, a retired
module name in new prose, a Makefile shape change. Treat those failures as real and fix them
in the branch (a separate `fix(...)` commit is fine), never by loosening the guard.

## 8. The docs a bot change owes

- OpenSpec change first: `proposal.md`, `specs/<cap>/spec.md` (Given/When/Then scenarios, each
with a `- **Test:** tests/test_x.py::test_y` line), `tasks.md`.
- A README section with the `make` invocations, plus the regenerated dispatch table.
- `agent-wiki/<date>-<name>.md` naming the issue and the PR.
- Every new public make target needs a `##` help line, a `.PHONY` entry, and its name in the
README (`check-wiring` + `check-docs`).
