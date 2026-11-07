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
# Fetching the PR's head is a WRITE into this checkout's object store, exactly where a runner can
# transiently fault ("insufficient permission for adding an object to repository database
# .git/objects", run 42354009408 on #1926). The fetch has no `set -e` behind it, so a bare failure
# used to slip past: the `git checkout -B` that follows then failed on a ref that never arrived and
# the actor cascade-failed onto a rebase of WHATEVER branch was last checked out (main) — a wrong-
# vehicle push that the squash-close re-check then caught only by accident. So a fetch fault is a
# LASTING stop, not a silent pass: retry once (a transient object-write clears), then refuse.
fetch_head() {
  local attempt out
  for attempt in 1 2 3; do
    out="$(git fetch "$REMOTE" "$HEAD_BRANCH" --quiet 2>&1)" && \
      git rev-parse --verify -q "refs/remotes/$REMOTE/$HEAD_BRANCH" >/dev/null 2>&1 && return 0
    echo "[rebase-bot] fetch of $REMOTE/$HEAD_BRANCH failed (attempt $attempt/3): $out" >&2
    sleep "${RETRY_SLEEP:-2}"
  done
  return 1
}
if [ -n "$DRY" ]; then
  echo "[rebase-bot] DRY: git fetch $REMOTE $HEAD_BRANCH --quiet (+ ref-verify)"
else
  if ! fetch_head; then
    # classify+skip with a NAMED error: the outer sweep counts this PR as failed and continues,
    # and the tree stays exactly where it started — never a bare fatal that aborts the sweep.
    comment "The rebase bot could not fetch \`$REMOTE/$HEAD_BRANCH\` into the runner's object store after 3 attempts (a git object-write/fetch failure). Nothing was pushed; the branch was left untouched and the sweep continued. <!-- $MARKER: $TODAY -->"
    echo "[rebase-bot] could not fetch $REMOTE/$HEAD_BRANCH after 3 attempts; giving up on this PR (issue #1952)" >&2
    exit 1
  fi
fi
run git checkout -B "$HEAD_BRANCH" "$REMOTE/$HEAD_BRANCH"
# The checkout is the point of no return: the rebase below operates on the CURRENT branch, so a
# checkout that did not land (the same silent-slip class as the fetch) must stop before any code
# moves on the wrong base. Verify the ref and the branch both exist, then leave HEAD on it.
if [ -n "$DRY" ]; then
  echo "[rebase-bot] DRY: git rev-parse --verify HEAD == $HEAD_BRANCH"
elif ! { git rev-parse --verify -q "refs/heads/$HEAD_BRANCH" >/dev/null 2>&1 \
  && [ "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" = "$HEAD_BRANCH" ]; }; then
  echo "[rebase-bot] checkout of $HEAD_BRANCH did not land; refusing to rebase a different branch" >&2
  abort_rebase
  exit 1
fi

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

# A rebase RE-AUTHORS the HEAD commit message (it replays each commit). `git rebase` can silently
# drop a claimed `closes #N` from the re-written message even when the diff is intact — and
# check-pr-closing reads the SQUASH TEXT (this repo merges with COMMIT_MESSAGES), so a drop turns
# the freshly-rebased PR RED at its new head with no file-level indication (the 4-PR close-drop,
# issue #1716: #1697/#1707/#1702 all reddened post-rebase while "patch-intact"). The structural
# gates above only compare CONTENT, they cannot see a message-level close dropping. So before the
# push, prove the rebased HEAD still carries the same adjacent close set as the LIVE body (fetched
# now, never assumed): a drop is a reportable red naming the #N, never a silent pass.
CLOSE_BODY="$(mktemp)"
if [ -n "$DRY" ]; then
  echo "[rebase-bot] DRY: gh api repos/$REPO/pulls/$PR --jq .body > CLOSE_BODY"
else
  gh api "repos/$REPO/pulls/$PR" --jq '.body // ""' >"$CLOSE_BODY" 2>/dev/null || {
    echo "[rebase-bot] could not read the live body for the close re-check" >&2; rm -f "$CLOSE_BODY"; exit 1
  }
fi
echo "[rebase-bot] squash-close re-check: base ${ORIGIN}/main rev HEAD body $HEAD_BRANCH (issue #1716)"
if [ -n "$DRY" ]; then
  echo "[rebase-bot] DRY: python3 scripts/check_pr_closing.py check --base \"${ORIGIN}/main\" --head \"$HEAD_BRANCH\" --body-file CLOSE_BODY --rev HEAD --cwd ."
elif ! CLOSE_OUT="$(python3 "${SELF_DIR}/check_pr_closing.py" check --base "${ORIGIN}/main" --head "$HEAD_BRANCH" --body-file "$CLOSE_BODY" --rev HEAD --cwd . 2>&1)"; then
  echo "$CLOSE_OUT" >&2
  # The check's own evidence names the exact #N that would be dropped; carry it to the PR so the
  # lane (and a reader) sees the close that vanished, not a mute gate failure (issue #1716).
  CLOSE_EV=$(printf '%s\n' "$CLOSE_OUT" | awk '/ci:/{print}' | tr '\n' ' ' | cut -c1-600)
  comment "The rebase would drop a squash-close: the re-authored HEAD's adjacent-close set no longer matches the live body, so this PR would redden on \`check-pr-closing\` at its new head. ${CLOSE_EV:+${CLOSE_EV} }Nothing was pushed; fix the commit message to keep the plain \`closes #N\`. <!-- $MARKER: $TODAY -->"
  echo "[rebase-bot] squash-close re-check failed" >&2; rm -f "$CLOSE_BODY"; exit 1
fi
rm -f "$CLOSE_BODY"

# A PR can MERGE between the sweep's `--state open` decision and this push (issue #1733). The
# force-with-lease guards a moved branch TIP, not a closed/merged PR: a push onto a MERGED PR's
# branch is an incident-class action on a dead vehicle — no rebase-able branch exists, the push
# is discarded, and the merge state reads as a null-state trap. Re-read the LIVE API at the only
# moment that matters (right before the push) and hard-stop with a `gave-up` marker, branch
# untouched, if the PR is no longer open or is merged. The same close/merge re-read that the
# sweep did at decision time is NOT enough: the gap between decide and push is exactly the window
# a human merge fills.
if [ -n "$DRY" ]; then
  echo "[rebase-bot] DRY: gh pr view $PR --repo $REPO --json state,merged --jq '.state + \"/\" + (.merged|tostring)'"
else
  # The dead-vehicle re-read is authoritative at push time, but a TRANSIENT read fault (rc=1 / an
  # empty answer from a gh relay drop) is not evidence the PR merged — reddening the whole sweep on
  # one API hiccup teaches operators to ignore the red (the #1602/#1603 discipline). Bounded-retry
  # the read so a single glitch does not abort the run; a persistent unreadable state still fails
  # closed exactly as before.
  PR_LIVE=""
  PR_GH_RC=1
  for _attempt in 1 2 3; do
    PR_LIVE="$(gh pr view "$PR" --repo "$REPO" --json state,merged --jq '.state + "/" + (.merged|tostring)' 2>/dev/null)"; PR_GH_RC=$?
    if [ "$PR_GH_RC" = "0" ] && [ -n "$PR_LIVE" ]; then break; fi
    echo "[rebase-bot] live re-read of PR #$PR failed (attempt $_attempt/3 rc=$PR_GH_RC); retrying" >&2
    sleep "${RETRY_SLEEP:-2}"
  done
  PR_STATE="${PR_LIVE%/*}"; PR_MERGED="${PR_LIVE#*/}"
  if [ "$PR_GH_RC" != "0" ] || [ -z "$PR_LIVE" ]; then
    # A PR whose state cannot be read is NOT a go signal: refuse like every other fail-closed
    # re-read in this script (the sweep, the body, the gates). A push that cannot prove the
    # vehicle is open is a push on faith.
    comment "The rebase started but the PR's state could not be re-read on the live API before the force-push (gh pr view rc=$PR_GH_RC after 3 attempts). Nothing was pushed; the vehicle may have merged while this run worked — refuse the dead-vehicle push. <!-- $MARKER: $TODAY -->"
    echo "[rebase-bot] could not re-read PR #$PR state at push time (rc=$PR_GH_RC after 3 attempts); refusing the force-push (issue #1733)" >&2; exit 1
  fi
  if [ "$PR_STATE" != "open" ] || [ "$PR_MERGED" = "true" ]; then
    comment "The rebase started but PR #$PR is no longer open at push time (state=$PR_STATE merged=$PR_MERGED) — it may have merged while this run worked, and a force-push onto a merged PR's branch is a dead-vehicle push. Nothing was pushed; the branch is untouched. <!-- $MARKER: $TODAY -->"
    echo "[rebase-bot] PR #$PR is not open at push time (state=$PR_STATE merged=$PR_MERGED); refusing the force-push onto a dead vehicle (issue #1733)" >&2; exit 1
  fi
  echo "[rebase-bot] dead-vehicle re-check OK: PR #$PR open and unmerged at push time"
fi

run git push --force-with-lease "$REMOTE" "HEAD:$HEAD_BRANCH"
comment "$OUTCOME. The structural checks (\`make -n ci-unit\`, \`make lint\`, \`make check-wiring\`) and the squash-close re-check (check-pr-closing against ${ORIGIN}/main and the live body) pass on the result; CI runs the full suite on this push. Nothing was merged. <!-- $MARKER: $TODAY -->" rebased
echo "[rebase-bot] pushed $HEAD_BRANCH to $REMOTE"
