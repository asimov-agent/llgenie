# Tasks: planner-orchestration-live-reconcile-2897

## 1. Stamp the reconciled tree
- [x] 1.1 Confirm the tree already carries the split shape: `SKILL.md` body 95,033 b (94,626 chars,
      under `SKILL_MAX_CHARS = 100_000`) with `references/filters-and-classifiers.md` (8,071 b)
      linked at SKILL.md:545 and :614 — no tree content change needed; the live copy is the only one
      over the cap.
- [x] 1.2 Bump the planner orchestration `SKILL.md` frontmatter `version: 1.0.0` -> `1.0.1`.

## 2. Document the reconciliation
- [x] 2.1 Write the `agent-wiki/` note naming issue #2897 and the reconciliation method.
- [x] 2.2 Write the `docs/changes.d/` fragment (one row, links the note of its own name).
- [x] 2.3 Regenerate the `CHANGES.md` index (`make -s changes-index`) so the new row is linked.

## 3. Verify
- [x] 3.1 `make -s check-agent-profiles` and `make -s check-agent-profiles-ratchet` exit 0 on this
      tree (tree-only here; the live profiles live on the host, so the live comparisons are skipped
      audibly in this container).
- [x] 3.2 `make -s check-docs` exits 0, `make -s check-wiring` exits 0, `make lint` passes, and
      `make -s openspec-tasks-check NAME=planner-orchestration-live-reconcile-2897` exits 0.

## 4. Land live (post-merge host step — not a CI/container action)
- [x] 4.1 Owner/lane runs `make sync-agent-profile PROFILE=llgenie-planner FORCE=1` on the host
      after this merges, replacing the over-cap live copy with the 95,033-b body + reference; the
      52 live inline lines remain carried (39/39 verbatim).
- [x] 4.2 Host `make -s check-agent-profiles` reads zero findings fleet-wide — the last planner
      finding is gone, so #2090's fleet-wide-zero acceptance item ticks and #2090 closes.
