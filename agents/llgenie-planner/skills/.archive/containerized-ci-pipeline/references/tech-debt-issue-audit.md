# Auditing a tech-debt backlog (issue triage / verdicts)

For a repo whose open issues are mostly `tech-debt`/`data-gap-analysis` tickets filed against robotically-emitted findings, the recurring job is "check out latest `master`, look over the open tech-debt issues one at a time, and say which still make sense."

## Procedure

1. `git fetch origin && git checkout origin/master` (or a worktree off the fetched tip). The issue bodies may predate current code by hundreds of commits — never trust them.
2. Read each issue's claimed defect, then **run the claim** — grep the current tree, exercise the code, probe the image. A body is rot; the code and its tests are truth.
3. Classify every issue into exactly one verdict; do not leave a grey "maybe":
   - **still-valid** — the code still does the thing the body describes (or a worse variant of it).
   - **stale** — the premise is gone (a prerequisite binary is now present), or the numbers a body cites have moved enough that its headline is wrong.
   - **partial** — the core defect holds but the body needs a rewrite (old counts, a narrower/handed claim, the fix landed partially). Retitle, don't close.
   - **fixed** — reproduce green / grep finds the seam the body says is missing; safe to close with a note.
4. Group the verdict list by subsystem (pipeline, bots/queue, release/contracts, PR-closure, guard-hygiene, data, search) so the report is scannable rather than 60 flat lines.
5. Offer to close the stale/fixed ones and to batch the cheapest genuine fixes, in priority order.

## Pitfalls

- **A checklist issue named by a guard row is verified by counting hits for that test's symbol in AGENTS.md's `§8` table.** `grep -c <test_name> AGENTS.md` → `0` proves the governing regression watch is still missing; `≥1` means it landed. The row text is the contract for these issues.
- **Issue bodies rot asymmetrically**: some were fixed quietly, some were made *worse*. Always re-read the current code path, not the PR referenced in the body (that PR may have landed and the fix been reverted or drifted).
- **`sed -n "s/^key=//p"`-style claims: check the ACTUAL oneline the writer prints.** A generic `s/^<key>=//p` over a line like `issue=266 position=-1 window=…` still traps the tail — the specific form named in the body may be stale while the class of bug is alive.
- **Pipe-loss when probing the image**: `docker run … | tail -1` forces the pipeline exit code to the tail command (0). To judge a probe result, drop the pipe or capture the docker exit code separately — a `ModuleNotFoundError` shown through a pipe read as success.
- **Hermes internals in the agent image live on the uv-tool venv path, not the default `sys.path`.** `docker run … python3 -c 'import hermes'` fails even though `hermes --version` works. Find source with `grep -rl '<symbol>' /root/.hermes/hermes-agent`; probe e.g. `tools/code_execution_env.py` there. An "import fails" probe can be a false negative for the very thing you are checking.
- **An issue that fixes an AGENTS.md guard row can have every code seam green while the file is still unupdated** — the guard-issue family (#310-style "add a preventive test/row", AGENTS rule 6f/6g) is closed only by the row existing, so count the row, not the code.
- Distinguish a *data* gap from a *contract/analysis* gap: an analysis that counts only model-level keys (`[m.get('id') for m in models if not m.get(key)]`) will keep reporting measurement-level values (per-run weight/context/storage) as missing even after they are backfilled on the measurements. Read the analyser's scope before calling a gap "unfilled" — it may live on as an artefact of the scope, which is itself the finding.
