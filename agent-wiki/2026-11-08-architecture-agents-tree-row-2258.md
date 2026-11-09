# docs/ARCHITECTURE.md gains the agents/** layout row and a reconciled census

## What was verified

- Refreshed the census at `ee8679e6` (the dispatch main tip, taken from the API) and added `agents/`
  to the enumerated line-items: `agents/` = 391 tracked files (13 HOST-profile dirs plus
  `manifest.json`, `README.md`, `standing-rules.md` and `fleet-block-exemptions.json`). The nine
  named content dirs sum to 3892; the remaining 77 tracked files (`.github/`, `.hermes/`, `tools/`,
  `docker-compose-files/`, `bots/` and the root-level files) are now stated, so the 3969-tracked-files
  headline reconciles from its own line items.
- Added the `agents/` row to the Repository-layout table describing the one-directory-per-profile
  tree, its manifest, and the `make sync-agent-profile` / `scripts/provision_agent_profiles.py`
  materialisation path — the S2 (`agents/**`) structural surface is no longer invisible to the map.
- The refresh surfaced five pre-existing staleness claims that the census at the fresh sha enforces
  (`openspec` 395→402 changes, `agent-wiki` 675→689 entries, `tests` 235→242 `test_*.py` files, plus
  `check_gitleaks_pin.py` and `check_tick_prompt.py` unmapped from the §Scripts table) — all
  reconciled so `make check-architecture-census` passes at `ee8679e6`.
- `make check-architecture-census` → `OK — census measured at ee8679e6 (tracked=3969, testspp=242,
  changes=402)`, exit 0; `make check-docs` → `ok` on all three sub-gates, exit 0.

## What is at stake

A layout map that omits the tree's largest unnamed group leaves a reader unable to learn where
host-agent behaviour lives, how it is gated (`make check-agent-profiles`) and how it is synced. A
census that left 448 of its files unaccounted-for could not reconcile from its own line items, so a
reader could not trust the headline.

## Index

- Issue: #2258 (this PR implements the architecture-doc change)
