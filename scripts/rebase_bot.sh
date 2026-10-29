#!/usr/bin/env bash
# Bring ONE pull request back onto `main` (issue #246): rebase, let the agent resolve a conflict,
# verify the result structurally, push with --force-with-lease to the PR's OWN head remote.
#
# It never merges and never leaves the rebase half-done silently: a conflict the agent cannot
# resolve stops the run with the reason on the PR.
#
# Env:
#   PR            the pull request number (for the comment and the report)
#   HEAD_BRANCH   the PR's branch
#   HEAD_REPO     owner of the PR's head repository (the fork, or this repo)
#   REPO          owner/name of the repository
#   ORIGIN        git remote for REPO                 (default: origin)
#   FORK_REMOTE   git remote for HEAD_REPO when it is not REPO (default: fork)
#   AGENT_CMD     how to ask the agent; the prompt is fed on STDIN (default: make rebase-bot-agent)
#   GATES         the structural checks after the rebase (default: the repo's fast ones)
#   DRY=1         print the commands instead of running them (the tests drive this)
set -uo pipefail

PR="${PR:?PR is required}"
HEAD_BRANCH="${HEAD_BRANCH:?HEAD_BRANCH is required}"
HEAD_REPO="${HEAD_REPO:-}"
REPO="${REPO:?REPO is required}"
OWNER="${REPO%%/*}"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The base remote is RESOLVED, not assumed (issue #925): this bot rebases onto `${ORIGIN}/main`, and in a clone
# whose `origin` is the owner's FORK that replays every PR onto different history. `base_ref.py` names the remote
# whose URL is the repository the PRs target. `ORIGIN` still overrides.
resolve_origin() {
  local ref
  ref="$(python3 "${SELF_DIR}/base_ref.py" --quiet 2>/dev/null || true)"
  printf '%s' "${ref%%/*}"
}

ORIGIN="${ORIGIN:-$(resolve_origin)}"
if [ -z "${ORIGIN}" ]; then
  ORIGIN="origin"
  printf '[rebase-bot] WARNING: no base remote could be resolved; falling back to `origin` (issue #925)\n' >&2
fi
FORK_REMOTE="${FORK_REMOTE:-fork}"
# `make` must PARSE the Makefile before it can run any target — and the conflict may BE in
# `Makefile` ("Makefile:628: *** missing separator", run 39566967551 on PR #446). So the agent leg
# is reached through a snapshot taken BEFORE the checkout: same target, from a file that still
# parses while the tree is mid-rebase (issue #460).
MK_SNAPSHOT="$(mktemp)"
cp Makefile "$MK_SNAPSHOT"
AGENT_CMD="${AGENT_CMD:-make -f $MK_SNAPSHOT rebase-bot-agent}"
# `&&`, not `;`: a `;` list reports only the LAST command's status, so a failing `make lint`
# was swallowed while `make check-wiring` passed and the branch was pushed anyway (issue #455).
GATES="${GATES:-make -n ci-unit && make lint && make check-wiring}"
MARKER="${MARKER:-rebase-bot}"
TODAY="${TODAY:-$(date -u +%Y-%m-%d)}"
DRY="${DRY:-}"
PROMPT="$(mktemp)"
LOG="$(mktemp)"

# --- the remote that hosts the PR's head: pushing a fork PR's branch to origin leaves a stray
# --- branch on the wrong remote, so this follows headRepositoryOwner, not the name "origin".
if [ -n "$HEAD_REPO" ] && [ "$(printf '%s' "$HEAD_REPO" | tr 'A-Z' 'a-z')" != "$(printf '%s' "$OWNER" | tr 'A-Z' 'a-z')" ]; then
  REMOTE="$FORK_REMOTE"
else
  REMOTE="$ORIGIN"
fi

run() {
  if [ -n "$DRY" ]; then echo "[rebase-bot] DRY: $*"; else echo "[rebase-bot] $*"; "$@"; fi
}

# Leave NO stopped rebase behind on a failure path: the caller's next `make` must be able to parse
# Makefile, and a conflict there can be in the Makefile itself (issues #460/#462). `git rebase
# --abort` is a no-op when nothing is in progress.
abort_rebase() {
  if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
    echo "[rebase-bot] aborting the stopped rebase so the tree is clean" >&2
    git rebase --abort >/dev/null 2>&1 || true
  fi
}

comment() {
  # $2 is the `bot-done` KIND: `rebased` only when this run really pushed, `gave-up` on every
  # failure path. The sweep counts a PR as "already rebased today" from that marker alone
  # (issues #453/#457), so recording a failure as `rebased` blocks the retry for the rest of the day.
  local kind="${2:-gave-up}"
  if [ -n "$DRY" ]; then
    echo "[rebase-bot] DRY: gh pr comment $PR --body <the outcome; kind=$kind>"
  else
    # Every comment this bot posts ALSO releases its claim (scripts/bot_claims.py, issues #279/#285).
    # The reader ages a claim by its own TTL (4h for a repair), so a run that ended has to say so -
    # on every path, which is why the release lives in this one helper rather than at the exits.
    local done_marker
    done_marker=$(PYTHONPATH="$(dirname "$0")" KIND="$kind" python3 -c \
      'import datetime as dt, os, bot_claims; print(bot_claims.done_comment(bot_claims.REBASER, dt.datetime.now(dt.timezone.utc), os.environ["KIND"]))' 2>/dev/null)
    gh pr comment "$PR" --repo "$REPO" --body "$1
${done_marker}" >/dev/null || echo "[rebase-bot] could not comment" >&2
  fi
}

echo "[rebase-bot] PR #$PR: $HEAD_REPO:$HEAD_BRANCH -> main (remote $REMOTE)"
run git fetch "$ORIGIN" main --quiet
run git fetch "$REMOTE" "$HEAD_BRANCH" --quiet
run git checkout -B "$HEAD_BRANCH" "$REMOTE/$HEAD_BRANCH"

# rerere replays its RECORDED resolution, which may be wrong or stale: resolve by hand instead.
if run git -c rerere.enabled=false rebase "$ORIGIN/main"; then
  OUTCOME="rebased cleanly onto \`main\`"
else
  echo "[rebase-bot] conflict: asking the agent to resolve it"
  git diff --name-only --diff-filter=U >"$LOG" 2>/dev/null || true
  # The rules are the preloaded `rebase-conflict` skill (issue #577); this prompt carries only the
  # facts of THIS conflict.
  {
    echo "Follow the preloaded skills rebase-conflict and bot-unattended. Resolve the conflict below."
    echo
    echo "Conflicted files:"; cat "$LOG"
    echo
    echo "The branch is rebasing onto ${ORIGIN}/main; HEAD is \`main\`, the replayed commit is the PR's own work."
  } >"$PROMPT"
  if [ -n "$DRY" ]; then
    echo "[rebase-bot] DRY: <agent> <$(wc -l <"$PROMPT")-line conflict prompt"
  elif ! bash -o pipefail -c "$AGENT_CMD" <"$PROMPT"; then
    comment "The rebase bot could not get the agent to resolve the conflict with \`main\`; leaving it for a human. <!-- $MARKER: $TODAY -->"
    echo "[rebase-bot] agent failed" >&2; abort_rebase; exit 1
  fi
  if ! run env GIT_EDITOR=true git -c rerere.enabled=false rebase --continue; then
    comment "The rebase bot's conflict resolution did not complete; leaving it for a human. <!-- $MARKER: $TODAY -->"
    echo "[rebase-bot] rebase --continue failed" >&2; abort_rebase; exit 1
  fi
  if grep -rIl '^<<<<<<< \|^>>>>>>> ' --exclude-dir=.git . >/dev/null 2>&1; then
    comment "The rebase bot stopped: conflict markers remain. Not pushed. <!-- $MARKER: $TODAY -->"
    echo "[rebase-bot] conflict markers remain" >&2; abort_rebase; exit 1
  fi
  OUTCOME="rebased onto \`main\` with \`$(wc -l <"$LOG")\` conflicted file(s) resolved by the agent"
fi

# The rebase moved code onto a new base: check the structure before publishing it. The full suite
# belongs to CI, which runs the moment the push lands; these are the checks a broken resolution
# fails (a recipe's TAB, a dead document, a stale rename).
echo "[rebase-bot] structural gates: $GATES"
if [ -n "$DRY" ]; then
  echo "[rebase-bot] DRY: $GATES"
elif ! bash -o pipefail -c "$GATES"; then
  comment "The rebase bot rebased this branch onto \`main\` but the structural checks failed, so nothing was pushed. <!-- $MARKER: $TODAY -->"
  echo "[rebase-bot] gates failed" >&2; exit 1
fi

run git push --force-with-lease "$REMOTE" "HEAD:$HEAD_BRANCH"
comment "$OUTCOME. The structural checks (\`make -n ci-unit\`, \`make lint\`, \`make check-wiring\`) pass on the result; CI runs the full suite on this push. Nothing was merged. <!-- $MARKER: $TODAY -->" rebased
echo "[rebase-bot] pushed $HEAD_BRANCH to $REMOTE"
