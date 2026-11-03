# dated deferred decisions for the Metal-only engines uzu and Inco Splash (issue #1654)

The live `registry-sync` store (2026-10-31, 117 models / 45 registry engines) names two engines the
committed tree has no decision for: `uzu` (github.com/trymirai/uzu) and `Inco Splash`
(github.com/incoai/splash). Both are Metal-only Apple-Silicon engines: Metal cannot run inside
llgenie's Linux image, and the Apple-Silicon platform is already served natively by the `mlx` engine,
so the two are added to `data/unsupported-engines.json` as dated `deferred` decisions (2026-11-03,
issue #1654) matching the established record shape (`decision` / `decided` / `reason` / `issue` /
`backend` / `upstream`). `data/engine-skill-gap.json` is regenerated.

Coupling note: the committed registry at base (`generated_utc 2026-10-27`, 43 engines) does not yet
name either engine — they exist only in the live 2026-10-31 store that has not landed in `main`.
`engine_skill_gap.py` reports a decision whose engine the committed registry lacks as `stale`, so the
decision-only branch is red on `check-engine-skill-gap` until the store lands. Per the repo's own
#229 pattern these ride the store-sync vehicle (`#687` contract: store + `unsupported-engines.json` +
re-rendered `engine-skill-gap.json` in one commit); the branch `fix/1654-decisions` holds the authored
decisions ready for that PR.

#1654
