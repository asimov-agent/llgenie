# Tasks

- [x] 1. E10 reads the destination tag passed into `derive`, and `bump()` passes `new_ref` for a tag pin
- [x] 2. Archive apply unpacks the release, links `bin/{id}`, and sets `binary` and `detect`
- [x] 3. Hermetic tests: destination tag, skill tag when no `ref` is passed, empty destination release, branch bump, apply of binary and detect
- [x] 4. OpenSpec change `fix-engine-bump-destination-release` for issue #171
- [x] 5. README states that the release read is the destination tag
- [x] 6. The unchanged-matrix unit check compares HEAD to itself, so bump PRs #165 #166 #167 #168 are not red for having moved a pin
- [x] 7. One install-kind case and one matrix case for each of tensorfold, strata, llama.cpp and llama.cpp-prism, both inside `make test-unit`
- [x] 8. Those cases run real plan, derive, pin and apply against a local git remote and release JSON files, including the unhappy edges (old-tag archives, missing checksum, missing backend archive, already current, pre-release, backward tag, branch at tip, failed tag lookup, two pins, non-image file)
- [x] 9. `AGENTS.md` states that a business-logic test never mocks the system under test. Only an external call may be stood in, and an end-to-end test does not stand that call in either
