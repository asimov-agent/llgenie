# Working under a commit-author allowlist guard

For an llgenie gate that fails when a PR's commits are authored by anyone outside an explicit
allowlist (name must match **exactly** AND carry the address that belongs to it). The rules below
apply to writing such a guard and to committing work into a branch it governs.

## Commit with an explicit identity, never from inherited git config

A worktree cut from a checkout inherits the checkout's `git config user.name/user.email`, which can be an
OFF-list spelling (the short `andyholst` login, a bot role name, the token owner's handle at runtime).
Do not trust config in a guarded repo; set the identity per commit:

```bash
git -c user.name="Andy Holst" -c user.email="andy.holst@protonmail.com" commit ...
```

or set it once in the worktree (`git config user.name ...`) before committing. A branch already off the
allowlist is remediated with `git rebase --reset-author` (or `git commit --amend --reset-author`)
followed by a `--force-with-lease` push to its OWN PR branch — never force-push shared or `main` history.
A rewrite that makes the audit resolution ambiguous also gets a co-author trailer when it is attribution
shared between the two allowed identities.

An off-list commit on a branch you do NOT own (another agent's or a bot's branch) is not yours to
rewrite — force-pushing it rewrites someone else's history. Keep the guard red on that branch and file
the re-authoring as its own linked issue rather than folding it into the current change; the current
PR ships only its own scope and names the deferred branch in `Not covered`.

## The scope a correct guard does NOT flag

- **Merge commits** — their author is the merge machinery (e.g. `GitHub <noreply@github.com>`), not the
  PR, so skip `git rev-list --merges`. The range is `--no-merges <base>..<head>`.
- **Commits reachable from the base branch** — someone else's already-landed work; history on `main` is
  out of scope and must NOT be rewritten (normalising published history invalidates published image
  digests).
- **A `Co-authored-by:` trailer is author attribution too** — read every trailer under its own finding
  key, not just the commit author.
- **Producer workflows author commits too.** A producer that stamps a LITERAL off-list identity fails the
  guard. A RUNTIME-resolved value (`gh api user --jq .login` as `user.name`) stamps the token owner's
  LOGIN — not an allowed name spelling — so pin the author identity explicitly while keeping the PUSH/PR
  token (`BUMP_TOKEN`) separate, so the PR still opens under a real account and CI starts.

## A scanner that reads source text matches its own source

A guard that greps committed text for identity-like assignments finds its OWN docstring and example/
evidence strings as violations (measured on one repo: 12 of 21 findings were the guard matching its own
source). Explicitly exclude the guard's own source file from the scan.

When extracting a name out of a text value, a regex that tries the bare alternative before the quoted
form captures only the first token of `"llgenie fix-bot"` (→ `llgenie`) and an unquoted YAML
`AUTHOR: Asimov Agent` reads only `Asimov` — both of which flag an ALLOWED value as a violation, or
hide a violating one. Handle quoted AND unquoted forms and strip surrounding quotes where the value is
read; pin each form (quoted multi-word, unquoted multi-word) with its own test.

## The test pattern that locks a commit-author guard honestly

Build a real git repo in `tmp_path`, commit with real identities via `git -c user.name=... -c
user.email=...`, create real merge commits, and run the guard's own functions against the real
`git rev-list --no-merges` output — never a stubbed rev-list or a pre-parsed author list. One case per
spec scenario plus a spec-completeness (scope) case, each body marked `# Given / # When / # Then`.
Hermetic (no network), but exercises the real `git` so a change to `git rev-list` output shape breaks
the test rather than a mock.

Beyond the unit tests, prove the gate fires end-to-end on a scratch clone: run the guard's CLI against a
real repo with an allowed author (rc=0) and with an off-list author (rc=1 naming the sha and the
remediation). A gate that passes its unit tests but never fires on a real repo is unproven — the
falsification run is the evidence the gate actually blocks.
