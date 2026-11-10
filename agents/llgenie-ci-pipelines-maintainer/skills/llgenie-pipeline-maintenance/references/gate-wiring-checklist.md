# Adding or changing a gate / make target in llgenie — the obligatory touch-points

A new or renamed gate, or a new user-facing make target, touches several files that are EACH checked by a
different gate. Missing any one reds a gate on *every* PR, not just yours. Do all of these in the same
atomic commit:

1. **Makefile** — add the target, add it to `.PHONY`, and wire it into the aggregate that runs it:
   `ci-unit` for a fast pre-push/tree-only check, or the PR `scope` suite for a PR-context check. A
   target listed in `.PHONY` but absent from the aggregate never runs.
2. **`scripts/issue_bot_gates.py`** — classify the gate as FAST or DEFERRED with a one-line reason.
   `tests/test_issue_bot_gates.py::test_the_real_tree_is_wired` fails on any gate wired into an aggregate
   but left unclassified. Rule of thumb: a gate that reads PR-owned state (PR body, head branch, commit
   range) does not exist before the push, so it is DEFERRED; a gate that reads only the working tree is
   FAST.
3. **`docs/BOTS.md`** — document every user-facing make target (one carrying a `##` help line).
   `make check-docs`, run from the PR `scope` gate, reds on an undocumented target. A target with no
   `##` help line is internal and needs no doc entry — but the moment you add `##`, add the doc row in
   the same commit.
4. **`docs/ARCHITECTURE.md`** — name the gate in the ci-unit / scope gate roster ("Every gate added to
   this list must also be classified FAST or DEFERRED").
5. **Change note** — add the `docs/changes.d/` note pair and its `CHANGES.md` row per the repo
   convention.

Prove the wiring locally before pushing, in the pinned container with the worktree mounted:

    python3 scripts/check_docs.py check           # rc=0
    python3 scripts/issue_bot_gates.py check       # OK: N fast / M deferred
    python3 -m pytest tests/test_issue_bot_gates.py tests/test_check_docs.py -q

If a `scope` run reds with "check-docs -> make <target> is undocumented", it is this checklist, not the
new gate's logic — do not weaken the gate to go green.

## A new make target + a workflow step that calls it — FOUR guards fire in SEQUENCE

Wiring a repo-logic script into a workflow step trips four SEPARATE gates, and CI reports them one per
run — discovering them there costs four full cycles (~15–20 min each), because each run only names its own
violation and the next appears after the fix. Run all four on the host in ONE pass before the push:

1. **Inline-script guard** (`tests/test_code_review.py::test_the_real_tree_has_no_inline_script_call`, from
   AGENTS.md "every command a CI workflow runs must be a make target"). A step whose `run:` invokes
   `python3 scripts/<x>.py …` inline is rejected; the step must call `make <target>` and the target's
   recipe holds the python invocation. Do not keep both spellings.
2. **check-docs** — the new target carries a `##` help line (user-facing), so it must be documented in
   README.md (or recorded in `docs-exceptions.json`). An empty `docs-exceptions.json` means the honest fix
   is a README row, never an exemption added to go green.
3. **check-wiring** — the target must be listed in the `Makefile`'s `.PHONY:` block. A `##` target absent
   from `.PHONY` reds `check-wiring` ("not in .PHONY") on the scope run.
4. **import-roots ratchet** (`python3 scripts/check_import_roots.py ratchet`) — a test that imports the
   module must use `from scripts import <mod> as <alias>`, never `sys.path.insert(0, "scripts")` + a bare
   `import <mod>`; the ratchet counts `sys-path`/`bare` and reds when either rises above the recorded
   baseline (pytest passing does not mean the job passes — see `references/import-roots-one-root-guard.md`).

One host command proves the whole nexus green (each rc=0):

```sh
make check-workflows check-docs check-wiring lint changes-index
python3 scripts/check_import_roots.py ratchet
python3 scripts/lint_linefeeds.py
python3 -m pytest tests/test_code_review.py::test_the_real_tree_has_no_inline_script_call \
  <your-domain-test>.py tests/test_import_roots.py -q
```

A green `pytest` of your own module proves NONE of these four — they are independent gates that each name
only their own violation, so a serial CI discovery loop is a self-inflicted four-cycle cost.

## Wiring a PR-BODY-reading gate into a workflow step

A gate that validates the PR body (`agents-line`, `check-pr-closing`) needs the LIVE body handed to the
make target at step-run time. Two failures follow from wiring it naively:

- **The make target reads `$(PR_BODY)` from the ENVIRONMENT, so the step must `export` it.** A `make
target PR_BODY=…` argument is not enough when the recipe itself invokes the script with `--body-file
"$(PR_BODY)"`. Measured: a step that fetched the body but did not `export PR_BODY` handed the recipe an
empty string, the recipe passed `--body-file ""`, and the script's `Path("")` resolved to `.` →
`IsADirectoryError`. Mirror the working sibling step (`check-pr-closing` does `export PR_BODY=…` then
`make <target>`); do not re-invent the mechanism.
- **A body-less event (a push to main) has no PR to validate.** Guard the call so it runs only when a
body exists (`if [ -n "$PR_BODY" ]; then …; else echo "no PR body — nothing to validate"; fi`), and keep
the skip a loud NON-RED note, never a silent pass.

**The gate fires on its OWN author's PR first — that first red is your live proof, not a setback.** A
PR-body gate wired into the required workflow evaluates the PR that introduces it: if your own body omits
the required line, the run reds `make <the-new-target>` on your PR before any other PR. That is the
exact defect the gate exists to catch, demonstrated end-to-end. Fix it the intended way — run `make
bot-preflight`, cite what it writes into the body (`AGENTS: <sha> <bytes>b <lines>l` plus a `BASE:` line),
re-push — rather than weakening the step. An `AGENTS:` sha must be reachable from BOTH head and base
(`git merge-base --is-ancestor <sha> origin/main`); a cite to an unrelated or stale commit fails the gate.

Exercise the changed path directly before trusting CI: `make <target> PR_HEAD=<head> PR_BASE=origin/main
PR_BODY=<file>` against a PASS body (rc 0, "reachable from both head and base") and a FAIL body (rc
nonzero, the "no `AGENTS:` line" refusal) proves both outcomes locally in one turn.

## Pre-push: exercise the aggregate's TRAILING gates, not only your modules

`make ci-unit` ends with a chain of `$(MAKE) check-*` shape gates. A run can print `2957 passed` for the
discovered suite and still be RED on a trailing target that shape-checks the script you just wrote
(`check-proc-gate` is the usual culprit: a bare `subprocess.run(` in `scripts/` outside `scripts/proc.py`,
because a `# proc-allow:` tag on a continuation line is ignored — the gate matches per physical line).
Before claiming a fix green, run the failing target's payload in-container (`python3 scripts/check_proc_gate.py
check`) and read the job log for the make target + `file:line`. A green test module is not a green
`make ci-unit`. See `references/proc-gate-and-subprocess-policy.md`.

## Test shape reviewers expect for a new gate

A fixture PAIR plus a control: a RED fixture that reproduces the actual defect GitHub silently tolerated
(must fail), a GREEN fixture of the correct shape (must pass), and a control case proving the gate does
not fire on out-of-scope input. The RED fixture must be the real-world body that slipped through, not a
synthetic one — a gate only ever run on inputs it rejects has demonstrated nothing.

## Merged-but-incomplete

If the gate lands but a wiring item above is missing, the fix is a FOLLOW-UP PR against the new main tip
(docs + classification + the damaged line), never a revert of the merged gate and never a force-push of
the merged branch.
