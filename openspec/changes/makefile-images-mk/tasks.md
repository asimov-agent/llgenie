# Tasks: makefile-images-mk

## 1. Baseline
- [x] 1.1 Record the pre-split baseline at the PR base: `make -qp` filtered target list, `make help`, declared-target grep count
- [x] 1.2 Confirm the 9-target images roster has zero overlap with the ci (#2458), bots (#2460) and security (#2459) rosters

## 2. Split
- [x] 2.1 Extract the 9 image-domain target blocks (target header → next target header/section banner, tracking recipe continuation lines) byte-identically into `mk/images.mk`
- [x] 2.2 Append `include mk/images.mk` after `mk/bots.mk`; leave banners, variables (`VARIANT_IMG`/`VARIANT_RUN`), `help`/`.PHONY`/DEFAULT_GOAL in the top Makefile

## 3. Parity
- [x] 3.3 `make -qp` filtered target lists identical to baseline except make's own record of the new include; `make help` byte-identical; every moved block byte-identical to its `origin/main` text; zero targets declared in both files
- [x] 3.4 New `tests/test_makefile_images_mk_split.py` pins membership, byte-identity, no-dual-declaration, help identity

## 4. Docs + gates
- [x] 4.1 `docs/ARCHITECTURE.md` `mk/` row names `images.mk` citing #2678; `docs/changes.d/` row + CHANGES.md index; agent-wiki entry
- [x] 4.2 `make check-wiring`, `make check-docs`, `make openspec-tasks-check` green; full `make test-unit` green at head
