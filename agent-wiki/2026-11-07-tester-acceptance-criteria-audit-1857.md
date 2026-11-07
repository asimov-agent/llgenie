# llgenie-tester — #1857: own-domain continuous-improvement audit (acceptance-criteria executability), clean pass

- **Date:** 2026-11-07 · **Issue:** #1857 (`continuous-improvement`, planner dispatch comment 6700617203)
- **Branch:** `agent/issue-1857-acceptance-criteria` (from `origin/main` `23cb793c`)
- **PR:** the ready-for-review PR closing #1857 (opened separately)

## The audit (measured at `23cb793c`)

Scope per #1857 ACs: (1) annotate each open `agent:refined`/`agent:implement` issue's acceptance
criteria with an executable verification path on the issue thread; (2) measure the last ~10 merged
PRs' criteria and count those ticked without a named run id; (3) file genuine findings as refined
six-section issues, or record a clean audit.

## AC1 — executable verification paths on all open refined/implement threads

14 open `agent:refined`+`agent:implement` issues probed; **all 14 carry an executable path** — a
`make` target, a unit-test file, or a workflow `run=` id — named on the thread (make/test/run token
counts below). The one genuine gap was **#227** (VRAM-range filter), whose thread named no
verification path; I annotated it in this pass (comment 6700674071): `make sync-registry` +
`git diff --exit-code data/models.json` + `make check-registry(check-registry-keys)` /
`tests/test_registry_keys.py` for the additive-only criterion, and `make test-unit` VRAM-range
cases for the filter (per the #1858 acceptance-tick evidence rule). No other thread was bare.

| issue | make | test | run= |
|-------|------|------|-----|
| #1888 | 1 | 6 | 1 |
| #1875 | 5 | 0 | 5 |
| #1859 | 0 | 5 | 0 |
| #1854 | 19 | 0 | 0 |
| #1852 | 5 | 0 | 1 |
| #1845 | 2 | 0 | 1 |
| #1843 | 6 | 1 | 2 |
| #1796 | 13 | 2 | 1 |
| #1745 | 25 | 0 | 15 |
| #1684 | 10 | 0 | 0 |
| #1645 | 13 | 0 | 0 |
| #1624 | 3 | 0 | 0 |
| #1558 | 11 | 0 | 5 |
| #227 | 16 | 3 | 0 |

## AC2 — last ~10 merged PRs: ticked-without-run-id = 0

Last 10 merged (1890, 1887, 1883, 1881, 1878, 1876, 1874, 1872, 1868, 1866) and each linked issue's
ticked acceptance criteria, counting "named" only when the tick carries `run=<id>` / `proven:` /
workflow-run citation:

| PR | closes | ticks | named |
|----|--------|-------|-------|
| #1890 | #1889 | 4 | 4 |
| #1887 | #1886 | 4 | 4 |
| #1883 | #1882 | 1 | 1 |
| #1881 | #1880 | 1 | 1 |
| #1878 | #1877 | 3 | 3 |
| #1876 | #1282 | 4 | 4 |
| #1874 | #1867 | 3 | 3 |
| #1872 | #1871 | 3 | 3 |
| #1868 | #1865 | 3 | 3 |
| #1866 | #1858 | 3 | 3 |

**ticked-without-named-run-id = 0 / 29 ticks.** All named. The #1858 acceptance-tick rule is holding.

## AC3 — outcome: `re-audited at 23cb793c, no new findings`

No genuine acceptance-criteria gap beyond the one annotation closed in-pass (#227). #1859 remains
open (premature umbrella close, routed via implement queue) — a prior finding, not surfaced anew
here. Read-only; no script/test/workflow edited (I test, I don't author their fixes).

## Ships

- `agent-wiki/2026-11-07-tester-acceptance-criteria-audit-1857.md` (new)
- `docs/changes.d/2026-11-07-tester-acceptance-criteria-audit-1857.md` (new)
- `CHANGES.md` (regenerated index row)

No merge/arm (#1088).
