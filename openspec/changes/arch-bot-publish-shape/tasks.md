# Tasks: arch-bot-publish-shape

- [x] 1. `scripts/architecture_bot.py`: shared `acceptance_items(doc, head)` + proven builders
      + `render_commit_body` (marker, completion line, ticked mirrors, `closes #<issue>`).
- [x] 2. `render_pr`: add the `## Acceptance criteria` mirror, `AGENTS: <sha> <bytes>b <lines>l`
      (AGENTS.md stats read at the base tip) and `BASE: <sha> (== origin/main at open)`; closes
      line stays last.
- [x] 3. `publish` reorder: draft issue → branch + pair + commit (new commit body) → edit the
      issue body to the ticked mirrors naming the commit sha → push → open the PR.
- [x] 4. Update the script module docstring and the `architecture-bot.yml` header comment to
      state the new publish shape.
- [x] 5. `tests/test_architecture_bot.py` in place: commit text closes + ticked mirrors + no
      `- [ ]` box; issue edit recorded before `pr create`; proven names the commit sha; PR body
      carries AC section + AGENTS + BASE. Fake-gh serves the issue edit call.
- [x] 6. Module tests green through the container test gate; `make lint`, `make check-wiring`,
      `make check-docs` rc=0.
- [x] 7. `agent-wiki/` note + `docs/changes.d/` row + `CHANGES.md` index for the change.
- [x] 8. Commit, push, open the PR against upstream main with the issue/PR/commit mirrors
      aligned; verify the live issue body and PR body on the wire carry the ticked mirrors.
