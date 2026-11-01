# 2026-11-01 — security lane own-domain idle audit (option 2 of the #1282 dispatch)

Work record: own-domain continuous-improvement audit of the security-scan pipeline, run as option 2 of the
planner dispatch on #1282/#1284 (the #1282 dispatch anchor's (b) path). Branch
`agents/security-idle-audit-record`; PR closes nothing alone — references #1282 and #1375.

## What and why

The planner re-dispatched #1282+#1284 and offered two gate-free slices: (1) a bake-at-build re-pin of the
semgrep rule set, or (2) the security own-domain standing audit (scan-coverage / dependency-pin validity /
rule-set freshness / admission-gate coverage), recording findings-or-clean. Option 1 was measured
infeasible-honest (see below), so this pass ran option 2.

## The measured facts (audited at `origin/main b5851814`)

- **Admission-gate — CLEAN.** `.github/workflows/security-scan.yml`: `on: schedule + workflow_dispatch`
  only (no `push:`/`pull_request`); verdict `continue-on-error: true`; reporting steps
  `if: always() && hashFiles('security-reports/*') != ''`; last step
  `if: always() && steps.verdict.outcome == 'failure'`. The scan cannot red a PR (#738 contract).
- **Severity policy — CLEAN.** `data/security-policy.json`: `pr_fail_on: []`,
  `enforce_events: [schedule, workflow_dispatch]`, `fail_on: [critical, high]`, `require_fix: true`.
- **Scanner pinning — CLEAN.** `containers/scanners/digests.json` digest-style refs + pinned versions
  (grype `0.121.0-r0`, semgrep `1.165.0-r0`, trivy `0.70.0-r5`).
- **Dependency-pin validity sweep — no new finding.** Each engine install-string pin resolved against its
  exact reachable index: vllm/cuda and vllm/cpu `torch==2.13.0` (`uv pip compile --refresh` exit 0 on
  `https://download.pytorch.org/whl/cu130` and `/whl/cpu`); freetoken/rocm `torch==2.11.*` and
  `torch==2.12.0` wheels present on `/whl/rocm7.2`; freetoken/cuda `torch>=2.14,<2.15`, `litert-lm==0.18.1`,
  `ziglang==0.17.0` all present on PyPI. The historical #1252/#1262 unsat (`torch==2.12.0+rocm7.14.0`, no
  such build on any index) is no longer in the tree — already corrected.

## Gaps found (already-tracked, re-confirmed, not re-filed)

- Scan-coverage (engine install-string pins invisible to scan set) → **#1282**.
- Rule-set freshness (semgrep `p/default` unpinned live alias on main) → **#1284**.

## Option-1 assessment (why the bake-at-build was not forced)

`semgrep 1.165.0 --config p/default` resolves the pack from a **live drifting registry alias** on every
run (in-image `--validate` → 1,074 rules; no deterministic dump to a file — the tool writes no resolved-pack
artifact to its cache; measured). A build-time re-resolution therefore either re-introduces the drift #1284
exists to close, or substitutes a different deterministic source (`semgrep-rules@<commit>`) that changes
p/default rule parity — a scan-coverage decision the owner must make, not one to smuggle in as the unblock.
That scoped redesign is filed separately as **#1375**.

## Proof

- Audited sha: `origin/main @ b5851814` (fetched `git rev-parse origin/main`).
- Dep-pin commands: `uv pip compile -q --refresh req.txt --index-url <exact-index> -o /dev/null` (exit 0 =
  SAT) + index-existence `curl` probes for the slow torch/rocm pins.
- Verdict: `re-audited at b5851814 · no new findings · differentials above`.
- #1282/#1284 implementations preserved on `agent/issue-1282-1284-security @ 20a3ad90` (local, unpushed),
  parked on the fork push-protection GH013 owner bypass; nothing lost, nothing smuggled, never merged
  (owner-gate #1088).
