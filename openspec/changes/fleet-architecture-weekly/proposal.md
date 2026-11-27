# Change: the documented bot fleet has a CI roster gate and a weekly review lane

## Why

Issue #3106: `docs/ARCHITECTURE.md` is meant to document every llgenie bot and how the lanes work
together, but nothing in CI measured that claim against `agents/manifest.json`. A profile can be
added to the manifest (issue #791) and quietly stay absent from the fleet doc forever — the same
doc/tree drift the architecture census gate catches for the code census, but unguarded for the bot
roster. CI has no live Hermes profiles (#928), so the only honest source is the tree copy.

The owner also asked for a weekly Hermes-agent review that suggests architecture improvements
without editing code. That review must have a collision-free clock, a bounded agent leg, an
owner/collaborator guard before any secret, and one deduped issue as its only output.

## What Changes

- `scripts/check_fleet_roster.py check` reads `agents/manifest.json` and the
  `## Host lane fleet` subsection of `docs/ARCHITECTURE.md`, and fails naming every manifest profile
  absent from that subsection. The check is a **subset**: `manifest <= documented`; an extra name in
  the doc is allowed because rosters are meant to grow.
- `make check-fleet-roster` is a public `## help` target and is chained into `make check-docs`, so a
  fleet-doc change is judged by the same gate that judges the rest of the docs.
- `.github/workflows/fleet-architecture-review.yml` adds a Monday 03:43Z clock (minute 43 was
  collision-free at measured main `412b84f02`), a `workflow_dispatch` dry input, explicit
  `timeout-minutes` on both jobs (#2317), an owner/collaborator guard before any secret, and one
  static non-cancelling concurrency group. Its failure is routed through the dated exemption in
  `tests/fixtures/workflow-run-exemptions.json` because the reactor is manual-only (#2293).
- `scripts/fleet_architecture.py` provides the deterministic halves: `brief` reads only the tree
  doc, manifest and lane `SOUL.md` files; `publish` files ONE marker-deduped refined issue from the
  agent's suggestions, and nothing at all when there is no suggestion or an open issue already
  carries the marker. The single Hermes leg may write only the suggestions file: no code, workflow,
  gate, `SOUL.md`, branch, commit or merge.
