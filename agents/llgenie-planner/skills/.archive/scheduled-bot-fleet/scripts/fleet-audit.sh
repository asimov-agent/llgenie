#!/usr/bin/env bash
# Audit a GitHub bot fleet — read-only: no merge, no dispatch, no comment.
#
# For every workflow: the last N runs with their conclusion + event, then the DECISION LINES of each
# workflow's newest run. The decision line is the only evidence that a bot acted; a green scheduled run
# that printed nothing is a no-op, not a success.
#
#   REPO=owner/repo [LIMIT=5] scripts/fleet-audit.sh
#
# Needs an authenticated `gh` with repo read. Run it before diagnosing a single bot, so the one that is
# actually red (or silently idle) is chosen deliberately rather than by whichever run looked newest.
set -euo pipefail

REPO="${REPO:?set REPO=owner/repo}"
LIMIT="${LIMIT:-5}"
DECISION='\[sweep\]|\[rebase|\[issue-|\[auto-merge|\[verify-closure|action=|verdict=|rebased=|picked |nothing to (fix|do)|no (open )?PR'

mapfile -t WF < <(gh workflow list --repo "$REPO" --all --json path --jq '.[].path' | xargs -r -n1 basename)

printf '== workflows (%s) ==\n' "${#WF[@]}"
gh workflow list --repo "$REPO" --all --json state,path --jq '.[] | "\(.state)\t\(.path)"'

echo
printf '== last %s runs per workflow ==\n' "$LIMIT"
for f in "${WF[@]}"; do
  printf '%-30s' "$f"
  gh run list --repo "$REPO" --workflow "$f" --limit "$LIMIT" \
      --json conclusion,status,createdAt,event \
      --jq '[.[] | "\(.conclusion // .status)@\(.createdAt[0:16])/\(.event)"] | join("  ")' \
    || echo '(no runs)'
done

echo
printf '== decision lines of each workflow newest run ==\n'
for f in "${WF[@]}"; do
  run=$(gh run list --repo "$REPO" --workflow "$f" --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null || true)
  [ -n "${run:-}" ] || continue
  echo "--- $f (run $run)"
  gh run view "$run" --repo "$REPO" --json jobs --jq '.jobs[]?.databaseId' 2>/dev/null \
    | while read -r job; do
        [ -n "$job" ] || continue
        gh api "repos/$REPO/actions/jobs/$job/logs" --allow-escape-sequences 2>/dev/null \
          | sed 's/\x1b\[[0-9;]*m//g' \
          | grep -E "$DECISION" \
          | tail -6
      done
  echo
done
