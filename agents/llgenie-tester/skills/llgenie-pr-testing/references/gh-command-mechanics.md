# gh command mechanics inside this lane

Rules for driving `gh` from `execute_code` and `terminal` without losing turns to quoting or PATH.

## PATH

- The `execute_code` kernel does not necessarily inherit shell shims: resolve the binary once with `command -v gh` in `terminal` and reuse that absolute path (`~/.local/share/mise/shims/gh` on this host). A `command not found` there is a PATH fact, not a broken tool.
- `terminal` is the safer place for anything with a body, heredoc, backticks or newlines.

## Quoting: keep jq out of f-strings

- Never interpolate a jq filter containing braces inside a Python f-string: it raises `SyntaxError: f-string: expecting '='`. Same hazard for object keys like `{name}`.
- Build the command by concatenation with a plain variable: define `JQ` as a normal string, then concatenate it into the shell command.
- Prefer `--json a,b,c --jq '...'` on `gh` itself over piping into a separate `jq` process.

## Posting bodies: file, then read back

- `gh issue comment --body` with an inline, shell-interpolated multi-line body (backticks, `**`, newlines) can exit 0 and post nothing. Write the body to a file first and pass `--body-file <path>` from `terminal`, using a quoted heredoc delimiter so `$` and backticks are not expanded.
- Never trust exit 0 for a post: read `comments[-1]` back (`id`, `createdAt`, first line of `body`) and confirm it is the new one.

## Opening the PR from this lane's fork (`origin` is upstream)

In this lane's checkouts `origin` is the **upstream** (`asimov-agent/llgenie`) and a separate remote
(`fork` = `andyholst`) holds the fork. Push the branch to **both** so a re-run and the PR agree
(`git push --force-with-lease origin <branch>` then `git push --force-with-lease fork <branch>`), but
the PR head ref must name the **fork owner** — `gh pr create --repo asimov-agent/llgenie --head
andyholst:<branch>` — because a bare branch name resolves to an upstream branch that does not exist
and the create fails or targets the wrong remote. Verify the head landed: `gh api
repos/asimov-agent/llgenie/pulls/<n> --jq .head.sha` must equal the sha you just pushed.

**Order matters, and the error lies about the cause.** Pushing only to upstream and then creating with
`--head andyholst:<branch>` fails `GraphQL: Head sha can't be blank, Base sha can't be blank, No commits
between asimov-agent:main and andyholst:<branch>, Head ref must be a branch`. Read that as *"the branch
is not on the head repo"*, NOT "the branch is stale/empty": push to `fork` first, then create. Confirm
with `git ls-remote fork | grep <branch>` before calling `gh pr create`.

PR body-header gates (`AGENTS:`/`BASE:`/`SYNC:`/`OPENSPEC:`), the `check-pr-acceptance`/`check-pr-closing` close-claim rules, `git reset --soft origin/main` corruption, and the `$HOME` writing rule: `references/pr-body-gates.md`.

## When execute_code keeps failing on quoting, stop retrying

An `execute_code` cell that raises `SyntaxError: unterminated f-string literal` (or a similar quoting
error) on a `gh`+`jq` one-liner will usually raise it again on the next attempt — the loop warning will
fire. After **one** retry, switch technique instead of rephrasing: write the whole script to a file
(`write_file /tmp/<task>.py`) and run it with `terminal python3 /tmp/<task>.py`. Same for multi-line
bodies: heredoc into a file, pass `--body-file`, never inline interpolation.

## Verdict primitives

- `gh run view <id> --json status,conclusion,headSha` is the only verdict primitive: `cancelled`, `queued` and a stale head are all "no verdict". Judge jobs, not the run — a run-level `cancelled` can hide a genuinely failed job.
- Logs stay readable when 0 bytes come back: `gh api repos/<o>/<r>/actions/jobs/<id>/logs --allow-escape-sequences | sed 's/\x1b\[[0-9;]*m//g'`. `--log-failed` refuses while the *run* is in flight even when the job has finished.

## Waiting without burning the turn

- Arm a background watcher (`terminal(background=true, notify=true)`) rather than polling inline. Poll `gh pr view <n> --json headRefOid`; exit on `HEAD_MOVED to <sha>` or when the target run reports `conclusion == success` (report `FULL_GREEN@<sha>` with the run id).
- "Has the rebase landed?" is a git question: `git merge-base --is-ancestor origin/main origin/pr-<n>; echo $?` — 0 = the PR head contains main (rebase landed), 1 = not yet, 128 = bad sha/ref.
- `gh run list --branch <headRefName>` is how you find the runs for a PR that is not yet showing them in `gh pr checks`.

## "Blocked-on-rebase-lane" verification dispatches

When a dispatch says "re-verify once the rebased head onto <main-sha> lands":

1. Prove the state with the ancestor check above rather than eyeballing `gh pr view`; rc 1 means the rebase has NOT landed, no matter what the PR head sha looks like.
2. Post a prep/blocked bookend on the issue (read-only — no push, no implement, no merge/arm) listing the per-criterion evidence you will gather at the new head, and mark `blocked-on-rebase-lane`.
3. Arm the ancestor-check watcher and stop; do not start verifying against the pre-rebase head, because every number you record there is a measurement of the old tree.
4. When a dispatch names a runtime criterion, verify it from the **producer** run's cell job at the new head, not the pr-trigger waiter job that only polls for the producer.
