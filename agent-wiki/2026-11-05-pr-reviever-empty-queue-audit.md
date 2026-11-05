# Empty-queue own-domain audit encoded in the PR-reviewer SOUL

Issue [#1775](https://github.com/asimov-agent/llgenie/issues/1775) (fleet open contract, owner 2026-11-01, folded into planner SOUL via #1245): an operational lane with an empty reactive queue is never "done" — it must run a bounded own-domain continuous-improvement audit and produce its own next finding.

As measured at `0dcbda8a`, `agents/llgenie-pr-reviever/SOUL.md` had **zero** encoding of the idle-audit duty (`grep -icE 'empty queue|own-domain|audit|continuous|idle|review-process'` → 0). The planner SOUL names this lane's domain: **review-process gaps** — where the review pipeline misses a defect (the #840 commit-author check, a dirty-vs-green misread, an un-armed auto-merge).

This change adds the dedicated SOUL section **Empty-queue own-domain audit (fleet open contract, owner 2026-11-01)**: when no PR is delegated, the reviewer audits its own domain, files findings as refined six-section issues routed through the normal queue (never this auditing lane's own implement pass), and records a clean audit as `re-audited at <sha>, no findings`. A live PR always outranks the audit.
