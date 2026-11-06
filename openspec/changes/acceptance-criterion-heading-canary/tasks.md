# Tasks

- [x] Reproduce: on the pre-fix `check_pr_acceptance`, a `## Fix (acceptance criteria)` issue returns `OK` (new test reds)
- [x] Add the canary: when canonical `## Acceptance criteria` is empty but `- [ ]` boxes exist, scan headings and report them (exit 1)
- [x] Keep the canonical path and `section_body` exact-match unchanged
- [x] Guard-prove: 14 tests on `test_check_pr_acceptance.py` (12 original + 2 new), 26 across both acceptance files, all green
- [x] Change-note trio + `docs/BOTS.md` row; check-docs / lint / wiring / workflows green
