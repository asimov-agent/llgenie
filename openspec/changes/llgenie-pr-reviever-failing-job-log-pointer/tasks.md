# Tasks — llgenie-pr-reviever failing-job-log-read pointer

- [x] Add a SKILL.md pointer row and a dedicated `references/read-the-failing-job-log-pointer.md`
      under `agents/llgenie-pr-reviever/` naming the implementer-lane canonical
      `red-bot-gate-read-the-failing-job-log.md` (merged via #1840) per #1791-AC3/#1849.
- [x] Add change-note triad (agent-wiki + docs/changes.d fragment + CHANGES.md row) per #1123.
- [x] Add this openspec change dir so the `agents/`-touching diff satisfies
      `make check-pr-openspec-change` (#1807 presence half).
- [x] Validate: `make check-pr-openspec-change` (via this change), `make check-docs`,
      `make lint`, `make check-agent-skills`.
- [x] PR body names the issue it implements against; does NOT close #1849 (five-lane rollout,
      this is pr-reviever's vehicle only).
