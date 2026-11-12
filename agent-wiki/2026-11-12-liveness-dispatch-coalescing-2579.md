# 2026-11-12 — liveness-dispatch-coalescing (#2579 / PR #2580)

Registry-liveness multi-cell waves no longer flood the `engine-build-push` concurrency
group. The dispatch step validates the `[select]` contract first, then dispatches ONE
full-matrix `push=true` sweep when more than one cell is missing, and the #2567 per-cell
named-field dispatch only when exactly one cell is missing. Evidence: the 8-run wave
43211663538..43211688780 (#2570 mechanism) and the 663/664 + 666-671 dispatch pairs.

Verified: `make check-workflows` OK, `make check-wiring` OK (421 docs), module
`tests/test_check_engine_pins_published.py` 20/20 hermetic in the test container (the
host-only live-fleet test deselected — 2 cells legitimately unpublished mid-sweep);
new lock `test_the_dispatch_coalesces_a_multi_cell_wave_into_one_sweep`; #2259/#2561/#2567
locks unchanged and green; `make openspec-validate NAME=liveness-dispatch-coalescing` rc=0.

Status: PR to main with `closes #2579`; wave behaviour proven live on the next multi-cell
liveness fire (one sweep run instead of N dispatches).
