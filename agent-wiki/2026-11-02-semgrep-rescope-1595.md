# 2026-11-02 — run-shell-injection false-positive class knocked out at 8 sites (issue #1595)

Issue: [#1595](https://github.com/asimov-agent/llgenie/issues/1595). The daily security-scan
(run 41458285599) red at `scan` on `yaml.github-actions.security.run-shell-injection` at eight
workflow sites. The triage split them into the GH013-family false-positive class (issue #1595) —
every flagged value is a trusted, quoted constant or authorized dispatch input routed through a
`make` step on a workflow_dispatch-only or pull_request trigger, never `pull_request_target`.

## What changed

At each of the eight sites an inline suppression was added — a `# nosemgrep:
yaml.github-actions.security.run-shell-injection.run-shell-injection` comment on the line
immediately above the flagged `run:`. The rule is therefore NOT disabled: the suppression is
scoped to exactly these eight `file:line` sites, and the same rule keeps firing everywhere else.

Sites (all read at `origin/main 75b3d1b`):

| site | interpolated value | trigger | trusted? |
|---|---|---|---|
| engine-build.yml:211 | `${{ matrix.engine }} ${{ matrix.variant }}` | dispatch | matrix constants |
| pipeline.yml:220 | `${{ matrix.row }} ${{ inputs.runner }}` | pull/write call | repo-declared |
| publish-agent-image.yml:133 | `${{ github.actor }}` | dispatch | authorized actor |
| queued-alarm.yml:102 | `${{ github.repository }}` | schedule+dispatch | constant |
| scope.yml:98 | `${{ github.base_ref }}` | PR+dispatch | base branch name |
| security-bot.yml:107 | `${{ github.repository }}` | schedule+dispatch | constant |
| security-scan.yml:126 | `${{ github.event.inputs.tools }}` | dispatch | authorized input |
| security-scan.yml:144 | `${{ github.event.inputs.enforce }}` | dispatch | authorized input |

## Key decisions

- **The fix is semgrep-native inline suppression, not a config/policy edit.** `data/security-policy.json`
  gates only by severity (`fail_on`/`require_fix`/`issue_severities`) and is untouched; no allowlist or
  severity set is widened; `make check-security-scan` triggers (schedule+workflow_dispatch only) are
  unchanged. The GH013 carve family (#1282/#1284) is precedent — an over-broad rule that reds a clean
  daily scan buries real findings in noise.
- **The above-line comment placement is exactly the matched line.** Each semgrep finding reported at the
  `run:` key line itself, so the immediately-above comment is the correct suppression placement.

## Verification (measured with the real scanner)

- Real `semgrep --config=p/default` (the pinned immutable image, `containers/scanners/digests.json`)
  over the FIXED tree: **0** run-shell-injection findings.
- The same pack over a planted genuine fixture (unquoted `${{ github.event.inputs.command }}` /
  `${{ github.event.pull_request.body }}` in a `pull_request_target` `run:` step): **2** run-shell-injection
  findings — the rule still fires, acceptance criterion #2 intact.
- All 7 edited workflows still parse as valid YAML; diff is exactly 8 comment insertions (+8/−0);
  `make check-security-scan` contract untouched.

The PR closing #1595 carries: 8 inline suppressions, this note, a `docs/changes.d/` row, regenerated
`CHANGES.md`. No `fail_on`/severity/policy change, no trigger change, no test weakened.
