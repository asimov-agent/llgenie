# Spec delta: engine-bump-commit-restamp (issue #3076)

## ADDED Requirements

### Requirement: the bump producer MUST restamp its commit text before push

`scripts/engine_bump_restamp.py` MUST expose a commit-text mode that reads a commit message file,
finds its `## Acceptance:` block and replaces that block with the acceptance clauses rendered by
the SAME composer that renders the PR body (`engine_bump_pr_body.acceptance_items`). The replace
MUST be scoped to that block: the subject line and every paragraph outside it MUST be preserved
byte-for-byte.

The replacement clauses MUST be measured proof: a replayable `make` command, `rc=0` and the
workflow run id. They MUST NOT name a head sha — a self-amending commit cannot name its own final
sha, and a pre-amend sha would be stale at the live head (issue #2288). The PR body carries the
head-stamped clauses instead.

The mode MUST refuse to write when a draft stub token (`PLACEHOLDER`, `HEADSHA`, `MAINSHA`) survives
anywhere in the resulting message.

#### Scenario: a stub-carrying acceptance block is restamped before push

- **Given** a bump lane's commit message whose `## Acceptance:` block carries a `PLACEHOLDER`
  proof clause
- **When** the lane runs `make engine-bump-commit-restamp ENGINE=<id> RUN=<run id>
  COMMIT_FILE=<path> COMMIT_OUT=<path>` before `git push`
- **Then** the output file has the composer's three measured `- [x]` clauses with `rc=0 run=<id>`,
  no draft stub token anywhere, and the subject and non-acceptance paragraphs unchanged

#### Scenario: a stub survives outside the acceptance block

- **Given** a commit message with a `PLACEHOLDER` in a paragraph outside `## Acceptance:`
- **When** the restamp mode runs
- **Then** it exits non-zero and writes no output file

### Requirement: the engine-bump workflow MUST call the restamp before pushing

`.github/workflows/engine-bump.yml` MUST call the commit-text restamp after `git commit` and before
`git push`, amending the commit in place only when the restamped message differs from the original.

#### Scenario: the composer already emitted clean proof

- **Given** a bump commit whose acceptance block already matches the measured proof
- **When** the lane restamps it
- **Then** the message is unchanged and no amend is issued
