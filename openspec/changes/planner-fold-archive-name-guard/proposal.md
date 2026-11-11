# Planner fold: name-guard allowance for archived skill snapshots

## Why
The live→tree planner fold (issue #2262, PR #2365) moves the planner's archived skills into
`agents/llgenie-planner/skills/.archive/` **byte-identically**. Six snapshots date from the era
spelling the retired CLI module `llama_serve`; the rename guard (`scripts/module_name_guard.py`,
issues #251/#573/#816) judged them live files and reddened `make check-module-names`, while
rewriting them would break the fold's parity rule. One genuinely live skill
(`software-development/local-inference-engine-builds/SKILL.md`) also still pointed at
`scripts/llama_serve.py`.

## What Changes
- `scripts/module_name_guard.py`: `ALLOWED_PREFIXES` gains `agents/llgenie-planner/skills/.archive/`
  — archived fold snapshots join `agent-wiki/` and `openspec/changes/` as dated history (with why).
- The live SKILL.md offender is re-pointed to `scripts/llgenie_serve.py` (live text must name the
  current module; no exemption).
- Test docstring updated to state the third history class. No spec delta (fold-change precedent:
  `agent-profile-fold-2177` carries proposal+tasks only).
