# cleanup-ownership-rule

## Why

Issue #2478 (carrier for #1624's cross-lane `/tmp` deletion guarantee) requires a fleet rule that no cleanup command may wildcard shared `/tmp`: every lane shares `/tmp` for container builds and ephemeral probes, so an `rm -rf /tmp/<glob>`-shaped cleanup in any prompt, script, or make target can destroy another tenant's state. The placement rule (worktrees never under `/tmp`, reclaim only via `make reclaim-tmp-worktrees`) exists in `agents/standing-rules.md`, but the *cleanup-side* rule — name your own lane's paths, never a shared `/tmp` wildcard — is not stated anywhere.

## What Changes

- `agents/standing-rules.md`: add an explicit cleanup-ownership line in the placement section: a cleanup command names its OWN lane's path prefix (a named file it created, or its own `llgenie-wt/<lane>` tree), never a shared `/tmp` wildcard; system and other-tenant occupants are never fleet cleanup targets.
- New spec capability `cleanup-ownership-rule` with the requirement and its scenarios.

## Impact

- Affected spec: new capability `cleanup-ownership-rule`.
- Affected file: `agents/standing-rules.md` (rule text only; no scripts, no make targets change).
- Carries the third remaining criterion of issue #1624 to completion.
