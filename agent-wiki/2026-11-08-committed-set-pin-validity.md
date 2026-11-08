# 2026-11-08 — committed-set engine-cell pin validity guard (issue #2190)

The #1622 pin-publish gate (`make check-engine-pins-published`) only fires for engines THIS PR repins.
A committed pin whose image was never rebuilt after its bump — tensorfold/cuda at `ef27f74f` (#1519),
never published, while `ghcr.io/.../tensorfold:ef27f74f-*` 404'd — sat on main with NO PR moving it, so
the repin-only gate never redded. Issue #2190 is that silent-committed publish-gap.

- `scripts/check_engine_pins_published.py` grows a committed-set sweep: `committed_cells()` enumerates
  every (engine, variant) the committed params declare buildable (all backends, non-disabled), and
  `check_committed()` probes each exact tag's manifest — exit 1 when any committed cell resolves no
  registry image. `--all` (`make check-engine-pins-valid`) runs the sweep; the interactive/repin
  `check --base` is unchanged and still hermetic (no repin => no network).
- The sweep is pinned by hermetic sabotage tests (`test_committed_red_...` / `test_committed_green_...`):
  a committed tag that 404s reds the sweep, the identical tag once published greens it — and a
  `@pytest.mark.network` live test (`test_every_committed_engine_cell_tag_is_published_live`, ci-network,
  issue #1000) holds the real committed set against GHCR on every live run.
- The tensorfold/cuda publish-gap itself is fixed by republishing THAT one cell (engine-build `push=true`
  at the committed pin), the engine-build producer's job — never a local build.

Implements issue #2190.
