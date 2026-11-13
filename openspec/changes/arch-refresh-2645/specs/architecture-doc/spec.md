# architecture-doc — delta for arch-refresh-2645

## ADDED Requirements

### Requirement: The publish leg's issue-body update uses gh's flag-form verb

The architecture bot SHALL update the filed issue's body with
`gh api --method PATCH <endpoint> -F body=@-`, never with a positional method
(`gh api PATCH <endpoint> …`). A gh release that stops accepting the positional form
(measured: gh 2.103.3 fails it with `accepts 1 arg(s), received 2`) must not be able to
silently break publishing: the test suite SHALL lock the flag-form call shape and SHALL fail
if any `gh api` call in the publish path carries a positional HTTP verb.

#### Scenario: publish ticks the issue through the flag form

- **WHEN** the publish leg files a refresh and ticks its acceptance mirrors
- **THEN** the issue-body update call is `api --method PATCH <endpoint> -F body=@-`
- **AND** the call still lands AFTER the commit and BEFORE the PR opens

#### Scenario: a positional verb in the publish path is a test failure

- **WHEN** any `gh api` invocation in `scripts/architecture_bot.py` names its verb
  positionally (`api PATCH …`, `api POST …`, `api PUT …`)
- **THEN** the architecture-bot test fails with the offending call named
