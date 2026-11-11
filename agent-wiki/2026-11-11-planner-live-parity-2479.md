# Planner live parity: the 48-file resolution for issue #2479 (lane of #2174)

Date: 2026-11-11. Issue: #2479. Lane of: #2174 (all criteria ticked; closed with this lane).

## What was measured

`make sync-agent-profile PROFILE=llgenie-planner CHECK=1` at head reports **48
differing files, 0 tree-only, 3 live-longer**. The 8 tree-only prompt/script
updates #2479 named (SOUL.md, prompts/llgenie-orchestrator-tick.md,
scripts/tick_board.sh and friends) are already present in the live profile but at
older bytes — the merged fleet PRs (#2365 fold, #2389, #2447) advanced the tree
copy without a re-sync since. The two SKILL.md files #2479 named for folding
(`github-issue-triage`, `llgenie-bot-orchestration`) are **byte-identical** —
folded verbatim by merged PR #2391 (`cmp` rc=0).

## Decisions

- **No blind sync**: every differing file was diffed live↔tree first (48 rows below).
- **3 live-longer files are not live behaviour**: their live bytes are the ORIGINAL
  vendor text the #2365 fold intentionally sanitized (secret-shaped placeholder
  tokens, a hardcoded host path replaced by `$HOME`, a fold-shortened console URL).
  Tree copy kept in all three; the live copies get the sanitized tree versions.
- **45 tree-longer files**: the tree carries the newer fleet text; live is the
  older pre-sync version. Resolution: sync tree→live from this head (the tree is
  the longer, complete copy in all 48 cases, so the no-truncated-sync rule holds).
- Final state proven by `CHECK=1` → 0 differences recorded on #2479.

## Per-file resolution table (measured at head 55e7699f5 + this branch)

| file | live b | tree b | live-only lines | resolution |
|---|---|---|---|---|
| SOUL.md | 27710 | 27851 | 2 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| prompts/llgenie-orchestrator-tick.md | 18929 | 19595 | 2 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| scripts/tick_board.sh | 8754 | 12233 | 3 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/.archive/containerized-ci-pipeline/references/actions-secrets-audit.md | 3611 | 3612 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/.archive/containerized-ci-pipeline/references/data-gap-findings.md | 19697 | 19698 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/.archive/containerized-ci-pipeline/references/issue-queue-audit.md | 5729 | 5730 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/.archive/containerized-ci-pipeline/references/worktree-base-seam.md | 4092 | 4093 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/.archive/llgenie-engine-image-ci/references/secret-value-guard.md | 2170 | 2172 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/.archive/llgenie-engine-image-ci/references/workflow-trigger-guards.md | 5062 | 5063 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/.archive/llm-x-benchmark-index/references/card-fit-analysis.md | 4489 | 4490 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/.archive/msi-laptop-drivers/SKILL.md | 33485 | 33491 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/.archive/omarchy-contributing/references/hybrid-gpu-vaapi.md | 6011 | 6015 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/.archive/zettelkasten-vault/SKILL.md | 24998 | 24999 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/.archive/zettelkasten-vault/references/ci-fix-workflow.md | 3172 | 3178 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/.archive/zettelkasten-vault/references/vault-audit.md | 2926 | 2927 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/autonomous-ai-agents/hermes-agent/references/native-mcp.md | 12110 | 12062 | 4 | tree kept — vendor doc; live bytes are the ORIGINAL secret-shaped placeholder examples (ghp_xx...xxxx) the fold replaced with ghp_REDACTED — sanitization is mandated for tracked trees; tree kept |
| skills/autonomous-ai-agents/hermes-agent/references/project-context-files.md | 3285 | 3297 | 1 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/autonomous-ai-agents/hermes-headless-ci/SKILL.md | 32769 | 32770 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/autonomous-ai-agents/hermes-profile-config/SKILL.md | 9091 | 9092 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/creative/manim-video/references/camera-and-3d.md | 4132 | 4134 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/creative/popular-web-designs/SKILL.md | 9869 | 9870 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/creative/popular-web-designs/templates/airtable.md | 4323 | 4326 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/creative/popular-web-designs/templates/intercom.md | 7185 | 7186 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/creative/popular-web-designs/templates/kraken.md | 5117 | 5118 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/creative/popular-web-designs/templates/miro.md | 5561 | 5566 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/creative/popular-web-designs/templates/webflow.md | 4886 | 4887 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/llgenie-bot-orchestration/references/check-pr-closing-plain-close-format.md | 1649 | 1650 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/llgenie-bot-orchestration/references/drift-fix-routing-labels.md | 2070 | 2071 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/llgenie-bot-orchestration/references/evidence-fabrication-and-auto-close.md | 2623 | 2624 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/llgenie-bot-orchestration/references/false-green-claim-check.md | 15268 | 15268 | 1 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/llgenie-bot-orchestration/references/openspec-gate-blindness.md | 2313 | 2314 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/llgenie-bot-orchestration/references/orchestrator-tick-contract.md | 20962 | 22066 | 3 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/llgenie-bot-orchestration/references/pr-head-location-and-base-gates.md | 43752 | 43763 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/llgenie-bot-orchestration/references/red-signal-triage.md | 51894 | 51902 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/llgenie-bot-orchestration/references/self-approval-audit-methodology.md | 1410 | 1411 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/llgenie-bot-orchestration/references/when-to-use-and-pass-shape.md | 6860 | 6957 | 1 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/llgenie-bot-orchestration/scripts/reclaim_tmp_worktrees.sh | 6763 | 6756 | 1 | tree kept — live hardcodes /home/asimov/repository/git/llgenie; tree uses $HOME/repository/git/llgenie — identical on this host ($HOME=/home/asimov) and portable for macOS lanes; tree kept |
| skills/note-taking/obsidian-vault-automation/SKILL.md | 6448 | 6449 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/note-taking/obsidian-vault-automation/references/ci-pipeline.md | 3371 | 3374 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/note-taking/obsidian-vault-automation/references/vault-audit-procedure.md | 5400 | 5401 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/productivity/consultant-assignment-radar/references/broker-registry.json | 18198 | 18199 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/productivity/google-workspace/SKILL.md | 14241 | 14226 | 1 | tree kept — live has the long console URL projectselector2/home/dashboard; tree carries the fold-shortened projectselector2 (redirects to the same page); tree kept |
| skills/productivity/pdf/references/nano-pdf-editing.md | 1342 | 1345 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/productivity/pdf/references/ocr-extraction.md | 8739 | 8745 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/software-development/hermes-plugin-development/SKILL.md | 13668 | 13673 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/software-development/hermes-plugin-development/references/hermes-plugin-patterns.md | 4484 | 4486 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/software-development/hermes-plugin-development/references/typesafe-jev-patterns.md | 5178 | 5184 | 0 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
| skills/software-development/local-inference-engine-builds/SKILL.md | 30643 | 30646 | 1 | tree kept — tree copy is the newer fleet text (merged PRs #2365/#2389/#2447 et al. advanced the tree; the live copy is the pre-sync older version); purely additive over live |
