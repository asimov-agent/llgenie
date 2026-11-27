# Tasks: the documented bot fleet has a CI roster gate and a weekly review lane

## 1. The roster gate

- [x] `scripts/check_fleet_roster.py check` reads the tree's `agents/manifest.json` and the
      `## Host lane fleet` subsection of `docs/ARCHITECTURE.md`; a missing subsection is a finding.
- [x] The gate is a subset check (`manifest <= documented`), exits 1 naming each missing profile,
      and exits 0 when every profile is present (proved with fixture docs at 412b84f02).
- [x] `make check-fleet-roster` exists with a `## help` line and is chained into `make check-docs`.

## 2. The weekly review lane

- [x] `.github/workflows/fleet-architecture-review.yml` declares Monday 03:43Z (`43` verified
      collision-free at main `412b84f02`), a `workflow_dispatch.dry` input, `timeout-minutes` on
      both jobs, the owner/collaborator guard before secrets, and one static non-cancelling group.
- [x] `scripts/fleet_architecture.py brief` reads only `docs/ARCHITECTURE.md`,
      `agents/manifest.json` and `agents/*/SOUL.md` (tree copy only, #928).
- [x] `scripts/fleet_architecture.py publish` files one marker-deduped refined issue, nothing when
      the suggestions file is empty or an open issue carries the marker, and never edits code.
- [x] The lane is added to `SCHEDULE_ALLOW` with a dated rationale and to the manual-only
      `workflow_run` exemption fixture with a dated reason (#2293).

## 3. Gate proof

- [x] `make -s check-workflows` rc=0 including the digest-pinned actionlint/shellcheck leg.
- [x] `make -s check-ci-discipline` rc=0 in `llgenie/test:latest`.
- [x] A `43` minute collision scan over `.github/workflows/*.yml` reports only this lane.
