# Spec Delta: auto-merge-record-token (issue #2953)

Capability: `sweep-record`
Issue: [#2953](https://github.com/asimov-agent/llgenie/issues/2953) (closed by this change)
Side issue: [#2954](https://github.com/asimov-agent/llgenie/issues/2954) (owner PAT-scope decision)

## ADDED Requirements

### Requirement: the sweep record comment is posted with a token allowed to comment on issues

The record comment a sweep posts on a tracker ISSUE SHALL run with a token whose
account is allowed to create issue comments. `scripts/auto_merge.py recheck` SHALL read
a `RECORD_TOKEN` environment variable: when it is non-empty, the `gh issue comment`
call for the record SHALL run with `GH_TOKEN` set to that value — through the
environment only, never on the command line (the credential rule) — and every other
gh call of the sweep SHALL keep the ambient token. When `RECORD_TOKEN` is unset, the
record call SHALL behave exactly as before (ambient `GH_TOKEN`).

The `auto-merge.yml` recheck sweep step SHALL set `RECORD_TOKEN` to the workflow job
token (`github.token`), whose workflow `permissions:` carry `issues: write`; the merge,
approve, deferral and announcement calls SHALL stay on the owner PAT (`BUMP_TOKEN`).

#### Scenario: RECORD_TOKEN reaches exactly the record call

- **Given** the stub gh store and a `RECORD_TOKEN` in the environment
- **When** `recheck(..., record=2652)` finishes a non-dry sweep
- **Then** the captured `issue comment` call ran with `GH_TOKEN` equal to the
  `RECORD_TOKEN` value, and no other captured call used that token
- **Test:** `tests/test_auto_merge.py::test_record_comment_uses_record_token`

#### Scenario: without RECORD_TOKEN the record keeps the ambient token

- **Given** the same stub store and no `RECORD_TOKEN` in the environment
- **When** `recheck(..., record=2652)` finishes a non-dry sweep
- **Then** the captured `issue comment` call ran with the harness default token
- **Test:** `tests/test_auto_merge.py::test_record_comment_without_record_token_uses_ambient`
