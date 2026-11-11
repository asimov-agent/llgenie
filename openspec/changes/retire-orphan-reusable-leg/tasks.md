# Tasks: retire-orphan-reusable-leg

- [x] 1. Delete `.github/workflows/agent-leg.yml` (the only caller-less workflow).
- [x] 2. Prove the finding clears: `make code-review-scan` no longer reports `reusable-orphan/agent-leg.yml`.
- [x] 3. Prove the fleet gates stay green without it: `make lint check-workflows check-wiring` rc=0.
- [x] 4. Docs: `agent-wiki/2026-11-11-retire-orphan-reusable-leg-2443.md` + `docs/changes.d/2026-11-11-retire-orphan-reusable-leg-2443.md` + `make changes-index`; `make check-docs`.
- [x] 5. Every local gate green at the final head: openspec-validate valid + `make lane-preflight` OK (the checklist ticked the moment these local proofs held).
