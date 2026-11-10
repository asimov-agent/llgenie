# PR hygiene gates for `agents/` (skill / SOUL) vehicles

A lane-behaviour vehicle edits `SOUL.md` or `skills/**` under `agents/<profile>/`. That is
**product code**, not docs, and the guard's PR-hygiene gates treat it that way. Run every gate
locally at the amended head *before* the force-push — a gate you discover on the wire costs a
full CI round-trip and a second force-push.

## Which gates fire, and the fix for each

| Gate | Why it fires | Fix |
|---|---|---|
| `check-pr-closing` | the commit **subject** ends `(#N)`, or the body uses a resolving verb on `#N` | drop the bare `(#N)` suffix from the subject, or genuinely close it |
| `check-pr-openspec-change` | an `agents/` change adds no `openspec/changes/<slug>/` | add the change dir (proposal + tasks + spec delta) |
| change-note trio | any `agents/` file changed | `agent-wiki/` note + `docs/changes.d/` fragment + CHANGES.md index |
| `SYNC:` body line | `agents/` (not docs-only) | run the profile sync, then put `SYNC: <profile> …` in the body |

## `check-pr-closing` has NO negation parsing — this is the trap

The gate reads a resolution claim from the commit **subject** ending `(#N)` and from resolving
verbs in the body. It does **not** parse a negation. Writing "does not close #N because …" in the
body *or* in the commit message does **not** clear a subject-derived claim — the subject claim is
independent and still fails. Two working exits only:

1. **Remove the `(#N)` suffix from the subject** (the usual fix when the PR references an issue
   without resolving it), or
2. Actually close the issue (make the claim true).

Confirm locally by invoking the gate script against the current head + edited body; do not infer
from reading the source that a note will be honoured.

## `agents/` changes need their own openspec change

Do not argue that a skill edit is "docs-only". It is not — an `agents/` change is product code.
Scaffold a change dir and fill it: `openspec/changes/<slug>/{proposal.md,tasks.md,specs/…}` with
`openspec validate` green. Mirroring the change dir of an already-merged PR of the same class is
the fastest correct template. The escape hatch is an `OPENSPEC: <name>` line in the body — prefer
the real change dir, since the reviewer expects it.

## Never pass a body with backticks through `--body "…"`

In a double-quoted shell string the shell performs **command substitution on backticks**: the
PR/issue body silently loses every code-quoted value (they are executed as commands, fail, and are
replaced by empty strings) while `gh` still exits 0 and prints a comment URL. The post looks
successful and is wrong.

- Always `write_file` the body, then `gh pr create --body-file` / `gh issue comment --body-file`.
- If a mangled body already landed, read it back
  (`gh api repos/<o>/<r>/issues/comments/<id> --jq .body`) and post a short correction comment;
  do not delete-and-repost a comment a reviewer may already cite.

## Polling CI without burning the turn

Do **not** hand-roll a `while true` loop over `gh pr view --json statusCheckRollup | jq`. That shape
breaks in three ways: stdout buffering drops the tick lines, a `jq` null-key edge case exits the
loop silently, and `conclusion` vs `status` confusion reports a bogus all-green. It also floods the
turn with results and hides the one fact you need.

Use exit-code-driven polling instead:

```sh
# rc 0 = green, 8 = pending, anything else = a failure
until gh pr checks <N> -R <owner>/<repo> >/dev/null; do
  [ $? -eq 8 ] || break
  sleep 30
done
```

Or, for the actual verdict, one API call is enough — no loop needed:

```sh
gh api repos/<owner>/<repo>/commits/<sha>/check-runs \
  --jq '.check_runs[] | "\(.name) \(.status) \(.conclusion)"'
```

`status != completed` is *pending*; `conclusion` is the verdict. Never call a PR green off a stale
rollup — re-read `headRefOid` each pass, because a force-push moves the head and the old greens
belong to the dead sha.

## `gh pr checks` / `gh pr view` need a repo context

Run them from inside a git worktree, or pass `-R <owner>/<repo>`. From a bare directory they fail
with `failed to run git: fatal: not a git repository` — a *cwd* problem, not an auth or API problem.
Change directory or add `-R`; do not re-auth.

## Scaffolding openspec via docker leaves root-owned files

A docker-run openspec launcher writes files as root in the bind mount; `chown` then needs a password.
Remove the scaffold with a root container against the same mount (`docker run --rm -v "$PWD":/w
alpine rm -rf /w/<path>`) rather than fighting sudo, then create the change dir by hand with the
editing tools.
