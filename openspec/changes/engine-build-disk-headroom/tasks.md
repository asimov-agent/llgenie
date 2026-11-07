# engine-build-disk-headroom — tasks

- [x] replace the `Free disk` step with a durable `Disk headroom` step that frees the docker/buildx layer cache + big toolchain dirs, measures `FREE_DISK_GB`, and fails fast below the `LLGENIE_DISK_FLOOR_GB` floor (issue #1893).
- [x] `test_every_cell_has_a_fail_fast_disk_headroom_gate` + `test_disk_gate_frees_the_giant_layer_cache_before_the_build`; mutation-proved (fail on base `faef07fa`, pass on fix head).
- [x] YAML parses; `make check-workflows` RC=0; `test_engine_build_workflow.py` 13 passed; engine suite 30 passed.
- [x] Docs trio per #1123: `agent-wiki/` note + `docs/changes.d/` fragment; openspec spec + proposal + tasks.
