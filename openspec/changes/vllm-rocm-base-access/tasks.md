# Tasks — vllm-rocm-base-access (#2553)

- [x] `scripts/engine_skills.py::render_variant` attaches `base_access` only to the declaring
      variant; `_base_access_run` renders the directory-only chmod RUN; `render_dockerfile`
      inserts it between the service-user RUN and `USER 1000:1000`
      (proven: cuda `4c1f3eee` / cpu `524f7326` `_image_hash` byte-identical before/after,
      rocm moves `db98981b` → `ba13b1d7`, measured on the branch)
- [x] `skills/engines/vllm/SKILL.md` `container.rocm` declares `base_access: ["/opt/python"]`;
      cuda/cpu declare nothing (proven: regenerated params carry the key in the rocm variant only)
- [x] `make generate-engine-params` rc=0; generated diff touches exactly
      `containers/engines/dockerfiles/vllm/Dockerfile.rocm` + `containers/engines/params/vllm.json`
- [x] New lock `test_vllm_rocm_opens_its_root_only_base_venv_for_uid_1000` green:
      `pytest tests/test_engine_skills.py tests/test_engine_image_matrix.py` rc=0 — 136/136
      in the `llgenie/test` container
- [x] Lane-lag fix proven on the committed tree: `test_an_engine_with_no_base_copy_is_deferred`
      now composes `{synthetic} ∪ cpp.retagged_engine_ids(base)` (measured
      `{"brand-new-engine", "vllm"}` on this branch); `pytest tests/test_ci_publish_order.py
      tests/test_check_engine_pins_published.py` (host-only live gate deselected) rc=0 — 43/43
      at head `0d61cda70`
- [x] `make openspec-validate NAME=vllm-rocm-base-access` exits 0
      (proven: rc=0, "Change 'vllm-rocm-base-access' is valid")
- [x] `make changes-index` rc=0 with fragment
      `docs/changes.d/2026-11-12-vllm-rocm-base-access-2553.md` (proven: rc=0 at head `0d61cda70`)
- [x] The stamped PR pair carries the gate-required `AGENTS:`/`BASE:` lines: `make
      bot-stamp-body` emits the pair and `make check-pr-agents-line PR_BODY=<stamped body>
      PR_BASE=origin/main` returns rc=0 (proven: stamped pair `AGENTS:
      1e7daa279655068e215e66ab505b4764d0228a99 94708b 1400l` + `BASE:`;
      `[check-pr-hygiene] OK: the AGENTS: line is reachable from both head and base`, rc=0).
      (PR CI-green / mergeStateStatus CLEAN / auto-merge-armed are standing loop duties
      tracked by `ci-verdict` + auto-merge, not a task this change can tick itself.)
