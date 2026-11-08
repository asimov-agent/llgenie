# the scripts/ layering as data, and the gate that holds it (issue #795) — 2026-11-08

**Implements:** issue #795 — `docs/ARCHITECTURE.md` §Scripts has always presented `scripts/` as five
groups (Product path, Security pipeline, Structural gates, CI entrypoints, Bots and automation), but
the grouping lived only in that table: no import and no gate could answer "is this module allowed to
import that one", and the one place the design was already broken was a real cycle —
`scripts/engine_bump.py` imported `engine_params_derive`, and `engine_params_derive` imported
`engine_bump` back **inside a function**, which is why nothing failed and no analysis could see it.

Measured in this change at `origin/main@e51f2fd0` (method: `ast` over every `scripts/*.py`, every
`Import` / `ImportFrom` node, relative and script-mode spellings both resolved to a `scripts/`
module): **151** modules, **122** distinct module-to-module edges — **77** intra-group, **45**
cross-group, **1** cycle. The 45 crossings are the allowlist; each carries the reason the code comment beside it
already gave (the subprocess seam `proc`, the issue-body renderer, the base-ref resolver, the tag
formula, …). This is NOT a strict layering: `gates -> bots` and `bots -> gates` both exist, so the
gate is a declared-edge allowlist, never an abstract "lower layer may not import higher".

Re-measured after the branch was rebased onto `origin/main@ea8c239e` (the run's
`check-pr-base` job refused a branch cut from the old base): 151 modules, the same 45 stated
crossings, still 0 cycles — main had added files, not a `scripts/` module.

## What changed

- **`scripts/package-layers.json`** — the layering as data: `groups` places every module of
  `scripts/` in exactly one of the five groups; `allowed_edges` lists every cross-group import with
  its one-line reason.
- **`scripts/check_package_layers.py`** — `make check-package-layers`, wired into `make ci-unit` and
  classified `DEFERRED` in `scripts/issue_bot_gates.py` (so the #475 static lock stays green). It
  refuses: `cycle` (always, whichever groups it spans), `cross-group` (unstated crossing),
  `stale-edge` (an allowlisted edge the tree lost, an entry whose modules now share a group, or an
  entry with no reason), `unknown-module`, `missing-module`, `duplicate-module`, `unknown-group`,
  and exits **2** — never 0 — when the data cannot be read. `report` prints the census.
- **`scripts/engine_release_archive.py`** — the cycle, broken the honest way. The release-archive
  step both directions need (`_release_assets`, `_native_archives`, `_pip_install`,
  `release_archive_install` and their private HTTP/token helpers) moved out of
  `scripts/engine_bump.py` into this module, which sits below both. `engine_bump` **re-exports** the
  moved names (so the bump module's surface, and the tests that read `eb._release_assets` etc., are
  unchanged); `engine_params_derive` now imports `engine_release_archive` instead of `engine_bump`.
  Verified: `import scripts.engine_params_derive` in a fresh interpreter leaves
  `scripts.engine_bump` out of `sys.modules`, and `python3 scripts/engine_bump.py --help` still runs.
- **`tests/test_package_layers.py`** — 16 tests. Every refusal is proven on a temp tree the test
  builds itself (a real `scripts/` package, real data, a real §Scripts table), because a gate
  asserted only against today's clean tree would pass with every rule deleted.
- **`docs/ARCHITECTURE.md` §Scripts** — states the data file, the target and the broken cycle beside
  the group table, and rows `engine_release_archive.py` and `check_package_layers.py`.

## Decisions

- **The group names are the doc's**, not a new vocabulary: the gate reads the §Scripts table labels
  and refuses a data group the table does not state, so the table and the file cannot drift apart.
- **The gate asserts edges, not layers.** 45 crossings already exist and are legitimate; making the
  tree conform first would have been a rewrite of ~45 imports with no behavioural gain, and the
  issue asked for the border set to be *stated* (a subpackage split is explicitly out of scope).
- **The cycle was moved, not copied.** A re-export keeps one owner; a duplicated helper would have
  satisfied the import graph while leaving two copies of the install-step rule.

Refs: #795 (this issue), #796 (the import-root ratchet, the other half of making a subpackage move
reviewable), #830 (the release-archive step being moved), #2015/#2022 (the §Scripts census gate this
complements — that one holds tree ⊆ named, this one holds the borders between them).
