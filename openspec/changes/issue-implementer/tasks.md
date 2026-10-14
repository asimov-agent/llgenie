# Tasks

- [x] 1. `scripts/issue_implementer.py` with `count`, `dispatch` and `open-pr` (stdlib only): the cap query argv, the deterministic pick, the claim marker comment, the branch slug, `issue.md`, and the draft-free PR open that links the issue and never merges
- [x] 2. `tests/test_issue_implementer.py` with a `gh` on `PATH` recording argv exactly: the cap boundary (3 → exit 0 nothing; 2 → proceeds) is a named test, plus pick, claim, branch slug, and PR-open argv assertions — 8 tests, all passing on the host
- [x] 3. Makefile: `issue-bot-dispatch`, `issue-bot-open-pr`, `implement-issue`, `hermes-smoke`, in `.PHONY` and the help text
- [x] 4. `.github/workflows/issue-bot.yml`: label `agent:implement` / daily schedule / `workflow_dispatch`, owner-or-collaborator guard, concurrency one-at-a-time, run the agent, push the branch, open the PR, report the outcome on the issue
- [x] 5. Wiring: `scripts/issue_implementer.py` is reachable from `make issue-bot-dispatch` / `issue-bot-open-pr`, `tests/test_issue_implementer.py` is in `make test-unit`, every `make` call in the new workflow names an existing target
- [x] 6. README documents the dispatcher, the cap, the labels, and the workflow
- [x] 7. Host verification: `make lint` and `make openspec-validate NAME=issue-implementer` exit 0, and `tests/test_issue_implementer.py` passes. The container run (`llgenie/test:latest`) and the live one-issue E2E (label → claim → branch → OpenSpec → code → make gates → PR open, with the cap counter in the run log) run on the workflow's merge to `main`, where `NOUS_API_KEY` and `BUMP_TOKEN` exist — they cannot run on a keyless host.
- [x] 8. Run the agent INSIDE the bots' agent image (issues #238/#248): `implement-issue` and
      `hermes-smoke` ensure the image (pull the published one for these inputs, else build the
      same Dockerfile), then run the host recipes inside it with `NOUS_API_KEY`/`GH_TOKEN` as
      run-time env. The runner never installs Hermes — the workflow had no install step at all,
      so the implementer died on "command not found" before this. Verified by running the image
      (Hermes v0.22.0 + git 2.47 + gh 2.102) and by resolving `make -n implement-issue` and
      `make -n _implement-issue` inside the container, where the host recipe is the agent call.
