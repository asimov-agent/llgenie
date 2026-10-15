# code-review-truthfulness

## ADDED Requirements

### Requirement: a secret named only in a comment is never a finding

`check_secrets_not_defined` SHALL match `secrets.X` against the workflows with full-line comments
removed, so a documentation example is not reported as a secret the repo fails to define.

#### Scenario: a commented `secrets.X` is not a finding

- **GIVEN** a workflow whose only `secrets.X` appears in a `#` comment,
- **WHEN** the secrets check runs,
- **THEN** it reports no finding for that name.

- **Test:** `tests/test_code_review.py::test_a_secret_named_only_in_a_comment_is_not_a_finding`

#### Scenario: a real `secrets.X` on an env line is still a finding

- **GIVEN** a workflow step that reads `${{ secrets.X }}` in its `env:`,
- **WHEN** the secrets check runs and `X` is not defined,
- **THEN** it reports the `secrets-not-defined/X` finding.

- **Test:** `tests/test_code_review.py::test_a_secret_a_workflow_reads_but_the_repo_does_not_define_is_a_finding`

### Requirement: the scan step runs the same checks as the filer

The code-review workflow's scan step SHALL carry the same `GH_TOKEN` as its filer step, so
`make code-review-scan` and `make code-review-file` report the same findings on the same tree.

#### Scenario: the scan step reads the API-backed checks

- **GIVEN** `code-review-bot.yml`,
- **WHEN** the `Scan the tree and the pipelines` step's env is read,
- **THEN** it carries `GH_TOKEN`, exactly like the `File one issue per new finding` step, and the two
  steps call `make code-review-scan` / `make code-review-file` (one make target per step).

- **Test:** `tests/test_code_review.py::test_the_scan_step_carries_the_same_token_as_the_filer`
