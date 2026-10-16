# A PR's commits are authored by Andy Holst or Asimov Agent — and by no one else (#345)

Implemented by PR [#351](https://github.com/asimov-agent/llgenie/pull/351) (issue #345); the deferred
half is [#346](https://github.com/asimov-agent/llgenie/issues/346).

## Why

The same two identities are recorded under several names in this repository's history, and one of them
is what the checkout's own git config authors as:

```
git log --all --format='%an <%ae>' | sort | uniq -c | sort -rn
    182 Asimov Agent <support@docondee.com>
    108 Andy Holst <andy.holst@protonmail.com>
     51 Andy <andy.holst@protonmail.com>
     50 Mr. Asimov <support@docondee.com>
     46 andyholst <andy.holst@protonmail.com>
     37 github-actions[bot] <andy.holst@protonmail.com>
     11 asimov-agent <asimov-agent@users.noreply.github.com>
      7 Hermes Agent <agent@asimov.local>
      1 llama-ai-agent <agent@llama-ai>
```

A reader of `git log` cannot tell whether `Andy`, `Andy Holst` and `andyholst` are one person or three,
and the repo's own automation commits as `github-actions[bot]`, `llgenie fix-bot` and whatever
`gh api user --jq .login` resolves to. A github-actions[bot] PR is also held for approval before its own
CI starts (`tests/test_engine_bump.py::test_bump_pr_uses_owner_pat`, run 38113858713) — this rule is the
general form of the same concern. One open PR carried a commit authored `Andy` (#170; #344 carried
`andyholst` and merged as `6601051` while this change was being written).

## What landed

- **`scripts/check_pr_authors.py`** (new, stdlib only) — `check` / `report`.
  - `commits_in_range` reads `git rev-list --no-merges <base>..<head>`: the commits a PR ADDS. A merge
    commit's author is the merge machinery, and a commit reachable from the base is someone else's
    landed work, so neither is reported — the gate cannot fail on history it did not create.
  - `check_commits` fails when a commit's author name is not exactly `Andy Holst` or `Asimov Agent`, or
    when its email is not the one that belongs to that name, and reads every `Co-authored-by:` trailer
    under its own finding key (a co-author's name is attribution too).
  - `check_producers` reads every file that can author a commit (`.github/workflows/*.yml`, the
    `Makefile`, `scripts/**`) and fails on a literal off-allowlist identity. A value resolved at run time
    is reported and accepted; the guard's own source is excluded, because it NAMES identities as data
    and would otherwise match itself (measured: 12 of the 21 findings on this repository's own tree were
    `check_pr_authors.py` matching its own docstring and evidence text).
  - `check_agents_mandate` requires the `AGENTS.md` section, so the rule cannot be deleted silently.
- **`make check-pr-authors`** / **`make pr-authors-report`**, the first wired into `ci-unit` after
  `check-pr-hygiene`, both in `.PHONY`. `PR_BASE` / `PR_HEAD` bound the range (`origin/main` / `HEAD`).
- **`tests/test_pr_authors.py`** (new, in `make test-unit`): 27 cases, none mocked — real git
  repositories in `tmp_path`, real identities via `git -c user.name=... -c user.email=...`, real merge
  commits, the real `git rev-list` output. One case per spec scenario plus the spec-completeness case.
- **The repository's own producers are on the allowlist**: `fix-bot.yml`, `issue-bot.yml`,
  `rebase-bot.yml`, `engine-bump.yml`, `engine-bump-rebase.yml` and `registry-sync.yml` now author as
  `Asimov Agent <support@docondee.com>`. The bump/sync pair keeps `BUMP_TOKEN` for the push and the PR,
  so the PR is still opened by a real account and CI starts (issue #136) — only the git AUTHOR is pinned,
  because `gh api user --jq .login` stamped the token owner's LOGIN (`asimov-agent`), which is not an
  allowed spelling and would have failed the gate on the bump PR itself.
  `tests/test_engine_bump.py::test_bump_pr_uses_owner_pat` and `::test_sync_pr_uses_owner_pat` assert the
  new property (owner PAT **and** an allowed author identity) instead of the old `gh api user`.
- **`AGENTS.md`** — the durable section: the two identities, the exact-name rule, the
  `Co-authored-by:` rule, the scope (merges and base commits out of scope), the remediation for a branch
  already off the allowlist, and the two make targets.
- **`README.md`** — the two targets in the command list plus the rule and the scope.
- **`openspec/changes/pr-commit-authors/`** — proposal, spec (every scenario Given/When/Then + a
  `Test:` line), tasks.

## Verification

- **`tests/test_pr_authors.py`: 27 passed** (gguf venv, `pytest -q`), including the strict cases the rule
  turns on: `andyholst`, `Andy`, `Mr. Asimov`, `github-actions[bot]`, `llgenie fix-bot`, `Hermes Agent`,
  and `Andy Holst <someone@else.example>`.
- **`tests/test_engine_bump.py`: 71 passed** — the two workflow assertions updated in the same commit.
- **`make check-pr-authors` exits 0 on this tree** and its report shows all twelve producer identities
  `OK`; `make pr-authors-report` prints each commit's verdict.
- **The gate fires end to end, not only in unit tests.** On a scratch clone of this tree the CLI was
  run over a real range: with only a commit authored `Andy Holst` it prints `OK` and exits **0**; with
  one commit authored `Andy` added it exits **1** and names the sha, the author, the two allowed
  identities and the remediation (`git config user.name "Andy Holst"` → `git rebase --reset-author` →
  `git push --force-with-lease`).
- **The regex gaps found while proving it:** a quoted name read as its first token (`"llgenie fix-bot"` →
  `llgenie`), and an unquoted YAML `GIT_AUTHOR_NAME: Asimov Agent` read as `Asimov` — which would have
  flagged an ALLOWED identity. Both are pinned by their own tests.
- `make lint`, `make check-wiring`, `make check-docs`, `make check-pr-hygiene`, `make check-workflows`,
  `make check-dispatch-forms`, `make openspec-validate NAME=pr-commit-authors`.

## Note

Two consequences the issue states plainly rather than hiding: the open PR **#170** carries a commit
authored `Andy` and will fail this gate until it is re-authored (tracked as **#346**, not done here,
because re-authoring rewrites someone else's branch), and **history on `main`** is not rewritten — the
~350 commits authored off the allowlist stay, since normalising published history would invalidate every
published engine-image digest.
