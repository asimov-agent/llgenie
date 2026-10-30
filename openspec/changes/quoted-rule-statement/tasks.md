# quoted-rule-statement — tasks

- [x] 1. Measure all three candidate mechanisms against all seven committed SOULs (plus #921's
      architect SOUL, the live statement+quote case) and record which one loses no legitimate
      statement. — strip quoted spans: every stated rule survives in all seven, and the architect
      SOUL drops 3 raw matches to 2 (statement kept, quotation removed). Imperative-form and
      exact-heading rejected on that measurement.
- [x] 2. `scripts/check_agent_profiles.py`: add `stated_text()` (fenced blocks, blockquote lines and
      `"…"` spans removed) and match a declared rule against the stated text only, with a separate
      `standing-rule-quoted` finding that names the file.
- [x] 3. Report a manifest entry with `rules: []` as `UNPROTECTED` in `check` and in `report`,
      without failing the gate. — five of the seven committed profiles are named; exit stays 0.
- [x] 4. `tests/test_agent_profiles.py`: quoting-only (span / fence / blockquote) fails, stating-only
      passes, stating+quoting passes, `rules: []` is reported unprotected; the committed-tree tests
      assert a stated rule, not a raw occurrence. — `48 passed` in `llgenie/test:latest`.
- [x] 5. Red-then-green proof on a real tree: delete a stated rule while leaving its quotation → gate
      RED naming the SOUL; restore → GREEN. Confirm the pre-change gate stayed GREEN through it. —
      old gate exit 0 over the sabotage, new gate exit 1 on
      `FAIL standing-rule-quoted: agents/llgenie-planner/SOUL.md`, restore exit 0 both.
- [x] 6. `make check-agent-profiles`, the new test module, `make lint`, `make check-docs`,
      `make check-wiring`, `make check-workflows` and `make openspec-validate NAME=quoted-rule-statement`
      all exit 0.
- [x] 7. Makefile help line + `docs/BOTS.md` describe the statement/quotation distinction;
      `agent-wiki/` note and the `CHANGES.md` row are added in the same commit.
