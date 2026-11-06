# llgenie-bot-orchestration: version the 2026-11-06 orchestration-safety rules into the shared-union-worktree reference (#1877)

The planner profile's `llgenie-bot-orchestration` skill gains a versioned-in-repo reference,
`agents/llgenie-planner/skills/llgenie-bot-orchestration/references/shared-union-worktree-safety.md`,
a byte-identical copy of the live staged reference. It documents two orchestration-safety rules
learned 2026-11-06 during #1696/#1874 dispatch so future lanes (rebase, pipeline-maintainer,
planner) follow them from the profile rather than rediscovering them from incidents:

- **Re-measure live `main` from the canonical remote, never trust a lane's asserted tip** — the
  rebase lane announced an "authoritative release ref" onto `a2ecc5b6` claiming "parent == live",
  while a fresh `git fetch origin/main` showed the true tip had advanced to `d62f3a5e` (`a2ecc5b6`
  was 2 behind, its cited push-base `760a5037` was 5 behind). Before relaying or acting on any
  "authoritative ref / push-base" claim, fetch and compute `git rev-list --count <base>..origin/main`
  yourself; the live tip is the fetched sha, never a number in a DM.
- **Anchor guard diagnosis to the LIVE vehicle head / live run, not a lane's cited run sha** — the
  pipeline-maintainer repeatedly diagnosed #1874 from run `42255199390@a5bf076d` (superseded) while
  the vehicle had advanced to `9f3ef6c8`. Read the PR's current `headRefOid` + that head's newest
  run first; a stale run rollup (or a lane's cited non-existent job id) is not the board.

Every pre-existing entry of the reference is preserved verbatim (no loss). No `scripts/`, `tests/`,
or `.github/workflows/` change — reference/skill-doc uplevel only. No #1696 wire push, no engine/code
change, no merge/arm (#1088).
