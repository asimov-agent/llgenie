# A PR's commits are authored by Andy Holst or Asimov Agent — and by no one else (issue #345)

## Why

A commit's author is the attribution a reader trusts: `git log`, `git blame` and `git bisect` all
answer "who wrote this" from it. On this repository the same two identities appear under several
different names, and one of them is what the CURRENT git config authors as, so "who wrote this" is
already ambiguous. Measured on `main` (`git log --all --format='%an <%ae>' | sort | uniq -c | sort -rn`):

```
    182 Asimov Agent <support@docondee.com>
    108 Andy Holst <andy.holst@protonmail.com>
     51 Andy <andy.holst@protonmail.com>
     50 Mr. Asimov <support@docondee.com>
     46 andyholst <andy.holst@protonmail.com>
     37 github-actions[bot] <andy.holst@protonmail.com>
     11 asimov-agent <asimov-agent@users.noreply.github.com>
      7 Hermes Agent <agent@asimov.local>
      2 asimov-agent <asimov@users.noreply.github.com>
      2 andyholst <andyholst@users.noreply.github.com>
      1 llama-ai-agent <agent@llama-ai>
```

Two facts make this a live defect rather than history:

* the ONE open PR carried a commit authored `Andy <andy.holst@protonmail.com>` — a name outside the
  allowlist, on a branch that would land on `main` (#344 was open when this change was written and
  merged as `6601051`; #170 is still open);
* this checkout's own git config authors as `andyholst`, so the next commit made here is off the
  allowlist too (`git config --local user.name` → `andyholst`; the global config says `Andy Holst`).

A reviewer reading `git log` cannot tell whether `Andy`, `Andy Holst` and `andyholst` are one person or
three, and the repo's own automation commits as `github-actions[bot]`, `llgenie fix-bot` and whatever
`gh api user --jq .login` resolves to — every PR those bots open is authored off the allowlist. The
rule this change enforces is simple: **only `Andy Holst <andy.holst@protonmail.com>` and
`Asimov Agent <support@docondee.com>` may author a PR's commits.**

## What changes

- **`scripts/check_pr_authors.py`** (`check` / `report`) — the guard. It reads the commits a PR ADDS
  (`git rev-list --no-merges <base>..<head>`) and fails on an author whose name is not exactly
  `Andy Holst` or `Asimov Agent`, or whose email is not the one that belongs to that name. It also
  reads each commit's `Co-authored-by:` trailers, because a co-author's name is attribution too. The
  static half checks that `AGENTS.md` still states the rule and that the repository's own producers
  assign an allowed identity. Stdlib only, so `ci-unit` runs it on the host on Linux and macOS alike.
- **`make check-pr-authors` / `make pr-authors-report`** — the gate and its read-only twin, the first
  wired into `ci-unit` after `check-pr-hygiene`, both declared in `.PHONY`.
- **`tests/test_pr_authors.py`** — the non-mocked suite: real git repositories in `tmp_path`, real
  identities via `git -c user.name=... -c user.email=...`, real `git rev-list` output. No stubbed git,
  no monkeypatched subprocess. Wired into `make test-unit`, which `ci.yml` runs.
- **`AGENTS.md`** — the durable section: the two allowed identities, the exact-name rule, the
  `Co-authored-by:` rule, and the remediation for a branch that is already authored off the allowlist.
- **`README.md`** — the two make targets.
- **`agent-wiki/`** — the work record naming issue #345.

## Impact

A PR's commit range is now gated on the author identity: a commit authored `Andy`, `andyholst`,
`Mr. Asimov`, `github-actions[bot]` or any other name fails `ci-unit` and names the offending commit,
its author and the identity to set. The merge commit GitHub writes on `main` is out of scope by
construction — merges are skipped and the range is bounded to the PR's own commits — so the gate can
never fail on history it did not create.

The static half keeps the guard green on the automation's own PRs: a workflow that assigns a literal
identity outside the allowlist is a violation, and one whose identity resolves at run time
(`$(gh api user --jq .login)`) is reported and accepted, because the one token this automation runs as
is an allowed identity and the alternative — red on every bump PR — is what makes a guard get switched
off.

## Not covered

- **No historical rewrite of `main`.** The ~350 commits authored off the allowlist stay as they are;
  this change governs PRs from here on. Normalising published history would invalidate every published
  engine-image digest and is a separate decision.
- **The two open PR branches that are already off the allowlist are not re-authored here** — #170
  carries `Andy <andy.holst@protonmail.com>`. Re-authoring someone else's branch rewrites SHAs, so it
  is tracked as its own work item, **#346**, named as a linked item per AGENTS.md.
