# 2026-10-31 — fold the security curator's lesson patches into the security profile's skill

Closes #1171: the security curator lane's live-captured lessons were added on the running
`~/.hermes/profiles/llgenie-security/` copy but never folded back into the versioned tree under
`agents/llgenie-security/`. The two copies silently diverged — the live profile carried the newer
behaviour and the tree's users never saw it. This change folds those patches into the tree's
`security-scan-ops` skill and its references so the versioned copy is the superset again.

## What changed

- `agents/llgenie-security/skills/security-scan-ops/SKILL.md`
  - The disabled-workflow guidance now covers proving the *tree* clean at a named sha while the
    workflow is off (`git worktree add <tmp> <sha>` + `make sbom && make security-scan TOOL=trivy`),
    and makes explicit that a tree-local scan is evidence for the issue comment, NOT the `cleared`
    close path — the finding still needs the workflow's run id and stays OPEN until then.
  - Dropped the `#1010 fence-before-block` lint lesson from this skill: it is the 
    `llgenie-security/SOUL.md` lane's splice rule, not this ops skill's.
  - The `references/agent-soul-versioning.md` pointer now also names the curator ledger as the
    writer of live drift (`actor:curator` in `~/.hermes/profiles/<p>/skills/.curator_ledger.jsonl`)
    and the fold-over-a-rulebook union rule.
- `agents/llgenie-security/skills/security-scan-ops/references/agent-soul-versioning.md`
  - New: how to name the live ledger's writer instead of assuming a human or cron.
  - New: fold live-ahead content into the tree; never byte-copy it over a rulebook (a strict-superset
    copy deletes a tree-only section, and the next one-way sync deletes it from live too).
- `agents/llgenie-security/skills/security-scan-ops/references/security-issue-review.md`
  - New `## Proving a finding set clean while the pipeline is disabled` section: the pinned-scanner
    command sequence, the `0 finding(s) recorded` line as a publishable result, and the two free
    checks (fix present in the tree without trusting a body; the trust-boundary `:rw` vs `:ro` peek).

Issue: #1171 · PR: #1191
