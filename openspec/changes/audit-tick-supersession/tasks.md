# Tasks: audit-tick-supersession

- [x] 1. `scripts/audit_acceptance_ticks.py` implements `audit`,
      `render_supersede_note`, `notes`, and `post` per the spec delta
      (GraphQL paging, live run states, per-head `head_green` survey,
      supersession exclusion, marker idempotence).
- [x] 2. `tests/test_audit_acceptance_ticks.py` locks: stale classification,
      green-cited exclusion, supersession exclusion, note renderer shape,
      per-head green-survey lines, covered-criteria parsing, post idempotence,
      proc-seam rule (fake-gh fixtures) — 8 passed in the llgenie/test image.
- [x] 3. `scripts/package-layers.json` registers the new script
      ("Bots and automation" + `audit_acceptance_ticks → proc` edge);
      `make test-unit`-classified suites stay green (targeted run + CI).
- [x] 4. Makefile targets `audit-ticks`, `audit-ticks-notes`,
      `audit-ticks-post` wired; `make check-wiring` green.
- [x] 5. `make audit-ticks` re-measured the whole closed-issue corpus with the
      repo tool (1308 closed issues, 311 ticked criteria citing runs, 172
      unsuperseded stale across 44 issues) and, after the sweep, reported 0
      unsuperseded stale ticks (rc=0, roster: 0 stale / 172 superseded) with
      the counting method recorded.
- [x] 6. `make audit-ticks-post` posted the 44 supersession notes idempotently;
      wire read-back showed 44 `SUPERSEDE-2288` comments (exactly one per
      issue, zero anomalies) and zero issue-body edits (ticks unchanged).
- [x] 7. Docs pairing: agent-wiki entry + `docs/changes.d` fragment +
      `docs/BOTS.md` section + `make changes-index`; `make check-docs`,
      `make lint`, `make openspec-validate` green.
- [x] 8. Commit + push + PR with the three-mirror acceptance wording; issue
      #2631 AC ticked on the wire with replayable proven (4 `- [x]` items with
      `proven:`/rc= evidence, wire read-back 2026-11-13).
