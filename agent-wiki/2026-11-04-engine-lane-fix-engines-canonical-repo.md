# 2026-11-04 — engine-lane fix(engines) PRs branch on the canonical repo, not the fork (#1698)

The owner-directed rule change (2026-11-03) that an engine-lane `fix(engines)` change must open its
PR branch on `asimov-agent/llgenie` **in-repo**, never the `andyholst` fork. This note records the
SOUL + skill change that carries the rule into the versioned tree.

- New **SOUL.md** rule: a `fix(engines)` PR branches on the CANONICAL repo — `engine-build-pr-trigger`
  refuses a foreign (fork) head ("a foreign-head bump cannot trigger a push=true dispatch"), so a
  fork-headed engine PR can never run the producer that builds and publishes its cells. Open the
  branch on `asimov-agent/llgenie` in-repo (push to `origin`, not the fork), and read the PR's
  `head.repo.full_name` back = `asimov-agent/llgenie` before relying on any trigger.
- The `llgenie-engine-improver` **SKILL.md** + its three reference files (`ci-run-watching`,
  `engine-image-cells`, `proving-and-pitfalls`) carry the fuller live reference files into the
  versioned tree, plus the `# proc-allow` discipline for new `scripts/*.py` files in engine PRs.

Reference points: #1568 failed exactly this way (fork head refused); #1696 is the same fix
re-opened in-repo and is the live example.

Implements issue #1698 (PR #1697).
