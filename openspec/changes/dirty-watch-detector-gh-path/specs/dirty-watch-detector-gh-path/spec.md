# dirty-watch-detector-gh-path

## ADDED Requirements

### Requirement: the dirty-watch detector resolves its own binaries

`dirty-detector.py` MUST resolve `gh` and `git` without relying on the invoking process's PATH. When
neither PATH nor the fallback directories yield the binary it MUST fall back to the bare name, so a
genuine absence still surfaces as a `FileNotFoundError` naming that binary rather than a wrong guess.

The quiet path MUST remain byte-identical across runs, and the conflict path MUST continue to print
`measured at main <sha>`.

#### Scenario: the detector runs under cron's minimal PATH

- **Given** an environment where PATH excludes the mise shims directory (`env -i PATH=/usr/bin:/bin`)
- **When** `dirty-detector.py` runs from the tree path
- **Then** it prints `conflicting: ...` or `conflicting: none` and exits 0, instead of raising
  `FileNotFoundError: 'gh'`

#### Scenario: the quiet contract is unchanged

- **Given** a board with no conflicting PRs
- **When** the detector runs twice in succession
- **Then** both runs emit byte-identical output, so the cron gate keeps suppressing quiet ticks
