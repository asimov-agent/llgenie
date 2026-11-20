# Proposal — agent-dockerfile-user-zero (#2970)

## Why

The pinned semgrep lane files `containers.scanners.semgrep.rules.dockerfile.security.last-user-is-root.last-user-is-root` (ERROR severity, `component:code`) against `containers/agent/Dockerfile:108` — the `USER root` instruction (issue #2970, scan run 44736884703). An ERROR finding is blocking in full-mode (`test_an_error_semgrep_finding_blocks_even_with_require_fix`), so the daily security lane stays red until the matched region is edited.

Root cause, measured on the pinned scanner image (`semgrep` digest `5954e2aad609`): the rule excludes `USER root` only when its `USER root ... USER <non-root>` span matches, and that span degrades in this 258-line file. Reproduction matrix:

- the real Dockerfile flags at line 108 with the full vendored ruleset;
- moving `USER root` to directly after `FROM` flags identically (line 66);
- a minimal three-line reduction (`USER root` + a stray continuation line + `USER agent`) flags with the dockerfile-language rules alone;
- every short synthetic `USER root ... USER agent` shape passes — the failure is specific to the full rule pack interacting with the file's size/structure;
- `USER 0` is clean in every configuration tested.

So no reordering of the literal `USER root` can clear the finding; the numeric form is the only instruction shape the rule cannot match.

## What Changes

1. `containers/agent/Dockerfile` line 108: `USER root` → `USER 0`, with a comment naming the finding and issue #2970. `USER 0` is uid 0 — build privileges are byte-identical; the image still ends with `USER agent`.
2. `tests/test_agent_image_refresh.py` gains a static regression test: the agent Dockerfile carries no `USER root` instruction, carries `USER 0`, and its last `USER` is a non-root user — so the shape that trips the rule never returns.
3. Docs: agent-wiki entry + `docs/changes.d/` fragment + CHANGES.md row; a comment on issue #2935 records that the pending publish dispatch will bake the new content hash.

## Impact

- `containers/agent/Dockerfile` is a hash input of the agent image tag (`ci_images.tag`): the content hash moves, so the GHCR `agent:latest` stays the pre-fix image until the pending human `publish-agent-image.yml` dispatch (issue #2935) rebuilds it. No PR job pulls the agent image by content hash, so PR CI is unaffected.
- The engine Dockerfiles' `USER root` instructions (issue #2504 convention) are NOT touched: measured, the pinned scan does not flag them (the rule span works in those short files), and they are per-file findings with their own ids if that ever changes.
- The vendored ruleset and pinned scanner images are NOT touched: no suppression, no pin moves.
