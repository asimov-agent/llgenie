## PR-hygiene gates a `fix(engines)` PR must clear (learned lands #1863, run locally BEFORE push)

Three gates read the LIVE PR body and the COMMITTED head tree — run every one locally (`../llama-gguf-tools/.venv/bin/python`) and get green BEFORE pushing:

- **`check-pr-closing` (guard):** a body `Closes #N` must appear as the SAME adjacent close in the COMMIT MESSAGE (`Closes #N.` in the amend body), not just the PR body. `python3 scripts/check_pr_closing.py check --head fix/... --base $(git merge-base origin/main HEAD) --rev HEAD --title "..." --body-file body.md` reproduces the remote guard.

- **`check-pr-agents-line` (guard/scope):** the `AGENTS:` line must cite the AGENTS.md sha measured at `origin/main` (`make bot-preflight` prints `AGENTS: <origin/main sha> 91766b 1363l` + `BASE: <same sha> (== origin/main at open)`), NOT the PR head sha and NOT hand counts. Then `gh pr edit` the body; since body edits DON'T rerun CI, `gh run rerun` the guard/scope at the unchanged head.

- **`check-pr-openspec-change` (guard/scope) + `ci-openspec` (linux):** an implementing PR that adds no `openspec/changes/` file and names no active change reds. Create `openspec/changes/<kebab>/` (`.openspec.yaml`, `proposal.md`, `tasks.md`, `specs/<kebab>/spec.md`). `spec.md` MUST use `#### Scenario:` blocks (`- **Given**` / `- **When**` / `- **Then**` + `- **Test:**`) — a bare `WHEN/THEN` paragraph fails `openspec validate` ("must include at least one scenario"). Verify: `docker run --rm -v $PWD:/repo -w /repo llgenie/openspec:latest openspec validate --changes` (327 items, 0 fail).

- **Commit shape:** land the note+fragment+CHANGES.md AND the openspec dir in the SAME amend as the code (check-docs diffs the committed tree), verify all local gates (closing, docs, census, openspec-tasks, engine tests) green at the FINAL head, then force-push (`--force-with-lease --force-if-includes`) and wait the full 16-check verdict — guards are fastest, `linux / unit` is the ~12m tail.
