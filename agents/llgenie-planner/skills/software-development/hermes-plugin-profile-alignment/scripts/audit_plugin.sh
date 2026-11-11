#!/usr/bin/env bash
# Audit a Hermes plugin across the default home and every named profile.
# Usage: audit_plugin.sh <plugin-id>
#
# Reports, per home: plugin dir name, install-metadata key, enabled list,
# doctor result, git revision. Exits 1 if any home FAILs the consistency check.
set -uo pipefail

PLUGIN="${1:?usage: audit_plugin.sh <plugin-id>}"
HERMES_ROOT="$HOME/.hermes"
FAILED=0

row() { # label home flag
  local label="$1" home="$2" flag="$3"
  local dir meta enabled doc rev status

  dir=$(find "$home/plugins" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null | head -1)
  meta=$(python3 -c "import json;print(','.join(json.load(open('$home/plugins/.install-metadata.json')).keys()))" 2>/dev/null || echo ERR)
  enabled=$(hermes $flag config get plugins.enabled 2>/dev/null \
            | grep -oE '\b[a-z0-9_-]+\b' | grep -v 'plugins\|enabled' | tr '\n' ',' | sed 's/,$//')
  rev=$(git -C "$home/plugins/$PLUGIN" rev-parse --short=12 HEAD 2>/dev/null || echo NO-GIT)
  doc=$(env -u HERMES_KANBAN_TASK -u HERMES_KANBAN_TASK_ID -u HERMES_KANBAN_BOARD \
        -u HERMES_CRON_SESSION -u HERMES_GATEWAY_SESSION \
        HERMES_HOME="$home" timeout 90 hermes plugins doctor "$PLUGIN" --ci 2>&1 \
        | grep -oE '[0-9]+ tool\(s\), [0-9]+ hook\(s\)' | head -1 | tr -d '\n')
  [ -n "$doc" ] || doc=DOCTOR-FAIL

  status=PASS
  [ "$dir" = "$PLUGIN" ] || status=FAIL
  [ "$meta" = "$PLUGIN" ] || status=FAIL
  case ",$enabled," in *",$PLUGIN,"*) ;; *) status=FAIL ;; esac
  [ "$doc" = "DOCTOR-FAIL" ] && status=FAIL
  [ "$status" = FAIL ] && FAILED=1

  printf '%-18s %-8s %-8s %-10s %-9s %-24s %s\n' \
    "$label" "$dir" "$meta" "$enabled" "$status" "$doc" "$rev"
}

printf '%-18s %-8s %-8s %-10s %-9s %-24s %s\n' \
  HOME DIR META ENABLED STATUS DOCTOR REV
row default "$HERMES_ROOT" ""
for p in "$HERMES_ROOT"/profiles/*/; do
  [ -d "$p" ] || continue
  n=$(basename "$p")
  row "$n" "$p" "-p $n"
done

exit $FAILED
