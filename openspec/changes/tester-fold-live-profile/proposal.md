# Tester lane live-profile fold

## Why
The llgenie-tester agent-profile in the tree is smaller than the live profile: its skill scripts and references (notably `scripts/fold-live-profile.py` and three reference files) exist only live, so `make sync-agent-profile PROFILE=llgenie-tester` is truncation-unsafe and issue #2475's fold PR (#2476) had no spec-tracked home. AGENTS.md requires every change to be spec-tracked change-first.

## What Changes
- Version the live-only tester-lane files live→tree under `agents/llgenie-tester/` (fold script + references), keeping the fold script byte-identical to the live copy except the gate-sanctioned `# proc-allow:` marker on the subprocess-spawning line so `check-proc-gate` passes.
- Carry the change with this OpenSpec change so the presence gate `check-pr-openspec-change` sees an `openspec/changes/<name>/` diff.

## Impact
- Spec: new capability `tester-profile-folding`.
- Code: `agents/llgenie-tester/**` files only; no change to inference-engine behaviour or CI semantics.
