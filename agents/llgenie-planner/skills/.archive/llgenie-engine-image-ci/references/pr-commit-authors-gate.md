# The commit-author gate (issue #345) — `make check-pr-authors`

A PR's commits may be authored by exactly two identities and no others:

```
Andy Holst <andy.holst@protonmail.com>
Asimov Agent <support@docondee.com>
```

`scripts/check_pr_authors.py` (`make check-pr-authors`, run inside `ci-unit`) reads the commits a PR
ADDS (`git rev-list --no-merges <base>..<head>`, `PR_BASE`/`PR_HEAD`, default `origin/main..HEAD`) plus
every `Co-authored-by:` trailer, and fails on any other author. `Andy`, `andyholst`, `Mr. Asimov`,
`github-actions[bot]`, `llgenie fix-bot`, `Hermes Agent`, `asimov-agent` and `llama-ai-agent` all FAIL;
so does `Andy Holst <someone@else.example>` (the name must carry its own address). Merge commits and
commits reachable from the base branch are out of scope by construction, so the gate never fails on
history it did not create — including the merge commit GitHub writes on `main`.

## What this means when you commit here

- **A bare `git commit` reds your branch.** The repo-local `user.name` is `andyholst` while the global
  one says `Andy Holst`. Commit with `git -c user.name="Andy Holst" -c user.email="andy.holst@protonmail.com" commit`,
  and re-author an existing branch with `git rebase --reset-author` (or `git commit --amend --reset-author`)
  then `git push --force-with-lease` on your OWN PR branch.
- **Verify before you push:** `make check-pr-authors` from the branch. `make pr-authors-report` prints
  every commit in the range with its verdict and the identity each producer assigns.
- **The six commit-authoring workflows author as `Asimov Agent`** (`fix-bot`, `issue-bot`, `rebase-bot`,
  `engine-bump`, `engine-bump-rebase`, `registry-sync`). The bump/sync pair keeps `BUMP_TOKEN` for the
  push and the PR — that is what makes CI start (issue #136) — and only the git AUTHOR is pinned,
  because `gh api user --jq .login` stamped the token owner's LOGIN (`asimov-agent`), which is not an
  allowed spelling. Keep that split when you touch one.
- **`AGENTS.md` carries the rule** and `check_agents_mandate` fails if the section
  (`## A PR's commits are authored by Andy Holst or Asimov Agent — no one else`) is deleted.

## Building a guard that scans producers: the self-match trap

`check_producers` reads every file that can author a commit — `.github/workflows/*.yml`, the
`Makefile`, `scripts/**` — and fails on a literal off-allowlist identity. Three things cost time:

1. **The guard matches its own source.** The docstring, the regexes and the remediation text a finding
   carries all NAME identities as data, so the guard reports itself (measured: 12 of 21 findings on the
   repo's own tree were `check_pr_authors.py` matching itself). Exclude the guard's own file
   (`Path(__file__).resolve()`) with a comment saying WHY, and pin it with a test that asserts the file
   is excluded AND that the raw text WOULD have matched — otherwise the exclusion looks like a shortcut.
2. **Read a quoted value whole.** A regex whose bare alternative comes first reads `"llgenie fix-bot"`
   as the single token `llgenie`. Try the quoted alternative FIRST.
3. **Read a `GIT_AUTHOR_NAME:` env value to end-of-line.** YAML needs no quotes for a space, so
   `GIT_AUTHOR_NAME: Asimov Agent` unquoted reads as the bare token `Asimov` — which flags an ALLOWED
   identity as a violation. The `GIT_(AUTHOR|COMMITTER)_(NAME|EMAIL)\s*[:=]` shape runs to EOL (a `#`
   comment is not part of the value); `git config user.name "x"` / `user.name="x"` use the
   quoted-or-token shape. Deduplicate the shapes with a set before reporting, so one assignment is one
   finding.

## Verification discipline that paid off

- 27 non-mocked tests: real git repositories in `tmp_path`, real identities via
  `git -c user.name=... -c user.email=...`, a real merge commit, the real `git rev-list` output.
- Prove the gate FIRES end to end, not only in unit tests: clone the tree to scratch, commit as
  `Andy Holst` (expect exit 0), add a commit authored `Andy` (expect exit 1 naming the sha), and check
  a non-git directory yields a loud `range` finding rather than a silent pass.
- `make test-unit` in the container takes ~17.5 min (4717 tests); budget for it rather than assuming a
  hang. Run it in the background with notify while you finish the docs.
