# Testing — the no-skip contract, and how a tracked defect is recorded

The test suite is discovered, not enumerated: `make test-unit` runs every `tests/test_*.py` minus the
dated exclusions in `tests/fixtures/unit-suite.json` (each with a reason, an issue and a date), all
inside the `llgenie/test` image so the gate is byte-identical on the host and in CI. `make ci-unit`
runs it with the registry, skill, Strata, engine-param and trend-list gates beside it.

## No skips, ever — and no `xfail` either

A skipped test is a **loud FAILURE**, not a silent skip, and `xfail` is a **skip**. This repository
has no "known failure" bucket in its gate: a green run must mean every test ran and passed, so a
broken prerequisite can never pass CI while the real behaviour is unverified.

The rule is enforced in `tests/conftest.py`, and it is stated once, above the hooks:

- a **SKIP** is any report pytest marks `skipped`, in any phase and from any cause — `pytest.skip()`,
  `@pytest.mark.skipif`, a conditional skip inside a test, or an `xfail` marker whose test failed
  (pytest reports that as `skipped` with `wasxfail` set);
- an **XFAIL** is not an exemption. Both hooks ask the single `_skip_violation()` predicate, so an
  exemption added to one hook alone reds `tests/test_no_skip_guard.py` and names the hook;
- `pytest_runtest_logreport` owns the call-phase verdict (the failure lands on the test that skipped);
  `pytest_report_teststatus` owns every phase, because a setup-, teardown- or module-level skip
  produces no call-phase report at all;
- `pytest_sessionfinish` makes the exit status follow the contract: mutating a report's outcome only
  changes what the terminal prints, so a recorded violation turns a would-be green session red.

A test that takes an `xfail` marker is still a skipped test, so `make test-unit` exits 1 with
`TEST SKIPPED — no skips allowed (AGENTS.md)` and a `NO-SKIP GUARD: … skipped test(s) failed this
run` line naming it.

## A tracked defect: assert its current behaviour — do not skip it

When a defect is known, tracked in an issue, and its fix is not this change, the test stays in the
gate and asserts the defect's **current** behaviour, with a comment naming the issue:

```python
def test_matrix_residue_is_still_wrong_1073():
    """Locks the behaviour #1073 tracks. Fixing #1073 MUST red this test."""

    # Given the matrix the ternary bug still produces
    row = matrix(models, hardware="RTX 4090")

    # When/Then  the residue is asserted, not skipped: the fix turns this red
    assert row["source"] == "fallback"      # #1073: should be "hub"
```

Fixing the defect reds that test, so its deletion is **forced mechanically** rather than remembered,
and nobody has to trust a marker to disappear on its own. If a prerequisite is genuinely absent, the
answer is not a skip either: provision it (`make download-test-model`, `make install`, `LLAMA_SERVER`)
or assert a behaviour that can run — for example the error message the code returns when it is
missing.
