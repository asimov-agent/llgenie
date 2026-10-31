# An aborted gate read as a clean one

Issue #1134. The defect is not the crash — it is that **a crash and a pass printed the same thing**.

## What was measured

A lane's test `importlib`-loaded a shipped script, which wrote `__pycache__/salvage-four-bucket.cpython-311.pyc` beside it; `sync-agent-profile` copies a skill directory wholesale, so the bytecode reached the live profile. The next gate run then raised:

```
File "scripts/check_agent_profiles.py", line 486, in shrink_findings
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xa7 in position 0
```

**It printed no FAIL.** Every caller that greps for `FAIL` read the abort as a clean board, and one lane drew a wrong conclusion from it in the same session — it reported "the absent-from-tree FAIL is gone" when in fact the gate had stopped running entirely. The moment the cause was removed it resumed reporting findings, including **a 125 KB skill directory existing only on one host**.

## What changed

Two guards, one cause and one backstop:

1. **Excluded by construction** — `__pycache__/` directories and `*.pyc` / `*.pyo` files are skipped before any read. Bytecode is compared by nothing and decoded by nobody, so it should never reach a text comparison at all.
2. **Reported, never raised** — the per-file read is wrapped: an undecodable file produces an `unreadable-live-file` finding naming the path and saying it was **not compared**, instead of aborting the run. If the exclusion is ever beaten by a new artefact type, the result is a visible finding rather than a silent pass.

## Verified, both directions

```
pytest tests/test_agent_profiles.py tests/test_changes_index.py tests/test_check_docs.py  -> 150 passed
negative control 1: remove the __pycache__/.pyc exclusion -> test_bytecode_beside_a_shipped_script_is_skipped_not_decoded FAILS
negative control 2: make the guarded read re-raise        -> test_an_undecodable_file_is_reported_never_raised FAILS
restored                                                  -> 150 passed
```

**The first version of the bytecode test was vacuous and the control caught it.** It built the live counterpart one directory too deep, so the pair was skipped by an earlier `continue` and the test passed with the fix removed. **A test whose fixture never reaches the code under test is decoration** — which is the same failure this issue is about, one level up.

## Why it matters beyond this gate

Four gates on this board produce identical output for "found nothing" and "could not tell": #1086 compared one direction only; #1108 printed `OK` for profiles declaring zero rules; #1123 enforced note→fragment but never change→note; **#1134 aborted and printed no FAIL**. **A check that cannot say "I did not run" is not a check.**
