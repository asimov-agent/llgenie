# Tasks

- [x] 1. `derive` reports python and apt packages added at the new sha
- [x] 2. Covered python requirements are not a hard-fail; uncovered ones are named
- [x] 3. New apt packages append to an existing `apt:` list
- [x] 4. `dpkg-shlibdeps -O` names `libc6` for a compiled binary
- [x] 5. A missing binary whose path contains the version is `missing`
- [x] 6. The bump PR body includes the dependency line
- [x] 7. `make openspec-validate NAME=engine-bump-dependencies` exits 0
- [x] 8. `AGENTS.md`, the issue, and the PR state why, when, and what for the `apt:` key
- [x] 9. The unit test renders the Dockerfile and checks the install line before a bump
- [x] 10. A release pin compares the old tag's files to the new tag's files
- [x] 11. One fixture runs `bump` through pin and apply and does not commit
