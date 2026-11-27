# Tasks — re-pin two drifted model-chain members (#3026)

- [x] Re-pin `nous-qwen4max` and `fallback_providers[2]` from `qwen/qwen4-max:free` to `tencent/hy4-flash:free`; the deliberate duplicate is declared by `model.documented_duplicate_issue: 3026` and both slots use the catalog-equal 1048576 budget (the referee requires equality, not `>=`).
- [x] Change `stepfun/step-3.7-flash:free` `context_window` from 262144 to 256000, keeping the id.
- [x] Run `make apply-hermes-base-config` (`--all` is a script flag; the make target applies to every lane) so every profile home and the agent image re-read the chain.
- [x] Verify `make check-agent-model-catalog` rc=0 against the live catalog, `make agent-image-profiles-check` rc=0, and no `262144` remains in the base chain. The separately-tracked #3087 absence is declared under `model.catalog_known_absent`; an undeclared absence still reds.
- [x] OpenSpec validation passes and the reviewable PR closes #3026 with the stamps and acceptance checklist.
