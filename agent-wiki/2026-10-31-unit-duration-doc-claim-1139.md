# Reconcile linux/unit duration doc claims with the #1139 measurement

The documented duration of `linux / unit` in `scripts/git_identity.py` and the
`2026-10-29-author-identity-seam` agent-wiki said "30+ minutes". The #1139 measurement
(2026-10-31, over the last 8 succeeded `linux / unit` legs) is **p50 = 11.9 min, p95 = 12.2 min**
(run ids in llgenie#1139 comment 6548600081). The "30+ minutes" figure was an artifact of #817
runner-starvation concurrency, not the steady state.

This change corrects the two doc claims to the measured band (~12 min, p95 12.2) with the
measurement reference, so the docs no longer assert a false duration. The `check_pr_authors`
ordering fact (it runs at the END of the leg) is unchanged — only the elapsed-time figure is
corrected. No gate, timeout, or CI policy is touched; the #1139 recommendation (scheduling, not a
timeout change) is unchanged.
