#!/usr/bin/env bash
# rerun-flaky-gate.sh <branch> [check-name] [max-attempts]
# Re-run a PR branch's failed CI jobs (same run id, --failed) in a bounded loop until the
# named check goes GREEN or the budget is exhausted. Reports every attempt:
# run id, per-job conclusion, and the failed step name(s) in the target check.
#
# Created for the live-smoke-gate case: deterministic checks green every attempt while an
# external network check (Firecrawl->lightbrd reachability / --require-hits) flakes on infra.
# Per-project rule: for that case KEEP RE-RUNNING in this loop (user's standing choice) rather
# than asking for a manual override or skipping ahead. Stop after the budget; do not spin on a
# sustained outage.
#
# Example: scripts/rerun-flaky-gate.sh qa-validate-guard live-smoke 4
set -uo pipefail
REPO=${REPO:-andyholst/trending-local-llms}
BRANCH=${1:?usage: $0 <branch> [check-name] [max-attempts]}
CHECK=${2:-live-smoke}
MAX=${3:-4}

latest_run() { gh run list --branch "$BRANCH" --limit 1 --json databaseId --jq '.[0].databaseId'; }

for a in $(seq 1 "$MAX"); do
  ID=$(latest_run)
  echo "=== attempt $a  run=$ID  ($(date -u +%H:%M:%SZ))"
  gh run rerun "$ID" --failed --repo "$REPO" >/dev/null 2>&1 || echo "  (rerun request non-zero; poll anyway)"
  S=""
  for i in $(seq 1 48); do
    S=$(gh run view "$ID" --repo "$REPO" --json status,conclusion --jq '"\(.status) \(.conclusion)"')
    case "$S" in completed*) break;; esac
    sleep 15
  done
  echo "  state: $S"
  gh run view "$ID" --repo "$REPO" --json jobs --jq '.jobs[] | "  \(.name): \(.conclusion)"'
  C=$(gh run view "$ID" --repo "$REPO" --json jobs --jq \
      --arg c "$CHECK" '.jobs[] | select(.name==$c) | .conclusion')
  if [ "$C" = success ]; then echo "  >>> $CHECK GREEN on attempt $a"; break; fi
  echo "  --- failed step(s) in $CHECK:"
  gh run view "$ID" --repo "$REPO" --json jobs --jq \
      --arg c "$CHECK" '.jobs[] | select(.name==$c) | .steps[] | select(.conclusion=="failure") | "      \(.number) \(.name)"'
done
echo "=== PR status:"
git_safe=$(gh pr view --repo "$REPO" --json state,isDraft,mergeStateStatus,mergedAt \
  --jq '"state=\(.state) draft=\(.isDraft) merge=\(.mergeStateStatus) mergedAt=\(.mergedAt)"')
echo "  $git_safe"
