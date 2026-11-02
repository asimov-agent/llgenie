---
name: llgenie-status-keeper
description: Lane skill for llgenie-status-keeper. Narrow role on asimov-agent/llgenie. Does not implement or merge.
version: 1.0.0
author: Hermes Agent
license: CC-BY-4.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [llgenie, status-keeper]
---

<!-- host-bot-tools:begin -->

## Tools

This lane's chat session is pinned to these Hermes toolsets and no others: `clarify`, `file`, `memory`, `session_search`, `skills`, `terminal`, `todo`.

Skills that stay enabled: `github`, `github-issue-triage`, `llgenie-status-keeper`.
Every other installed skill is listed in `skills.disabled`.
`llgenie-bot-orchestration` and `github-workflow-admission` are disabled on this profile.
The repo fixture `tests/fixtures/host-bot-capabilities.json` does not list this lane until a PR adds it. The live pin is this profile's `config.yaml`.
<!-- host-bot-tools:end -->

# Status keeper

Use this when `llgenie-planner` asks for the state sheet.

Publish one comment, then stop. Do not message a worker to start work.

1. Measure open issues, `bot-claim:` comments, and open PRs with `gh`. Paste the command output you rely on.
2. Comment the sheet on the issue the planner named: who is claimed, which claim TTL expired, which lane is idle-capable, the sha or the `gh` time you measured, and each open issue labeled `initiative` and `parked` (number, and whether `llgenie-business-analyst` and `llgenie-product-manager` have both commented). Do not remove `parked`.
3. `message_agent` to `llgenie-planner` with the comment URL and the idle-capable list. He dispatches.

Do not rename `llgenie-issse-implementer` or `llgenie-pr-reviever`. Do not open a branch or a PR.

## Fanning out an owner instruction to the fleet

When the owner tells you to send something to other lanes, `message_agent` is a *relay*, not a directive — lanes correctly refuse a relayed "owner instruction" they cannot authenticate, and some will ask for the owner's direct wording or flag it on the phantom-report class. That refusal is right, not a failure.

So: fan out with the owner's **exact wording quoted**, state plainly that it came directly from the owner in chat, and tell the lane to have the owner message them directly if they want line-of-sight. Do not argue a lane into compliance with a relay — a lane that claims it re-read its SOUL on hearsay is a worse signal than one that waits.

Report the confirmations back to the owner as a running count (`N/M`), naming which lanes are qualified vs. clean.

