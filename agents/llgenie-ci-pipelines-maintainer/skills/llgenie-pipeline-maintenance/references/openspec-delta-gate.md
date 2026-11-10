# The openspec `ci-openspec` gate: the delta contract and how to guard-prove a fix

Use when `make ci-openspec` / `openspec validate --changes` reds a change with
`No delta sections found` / `Change must have at least one delta` — a change doc written as
prose (`## Behaviour`, free notes) instead of an openspec delta.

## What the gate demands

A change under `openspec/changes/<name>/specs/<capability>/spec.md` must contain delta
headers, each requirement with at least one scenario:

```
## ADDED Requirements            (or MODIFIED / REMOVED / RENAMED)

### Requirement: <statement>
<prose>

#### Scenario: <name>
Given ...
When ...
Then ...
And ...
```

Non-delta prose (a `# Spec:` H1 title is fine outside `specs/`, or under a header that is not a
delta header) is not counted. The alternative for a change that legitimately touches no spec
(pure refactor, tooling, docs) is `skip_specs: true` in the change's `.openspec.yaml` — only
use it when the change truly modifies no spec, not to silence a structural error.

## The exact commands (host, when Docker is up)

The gate runs in the `llgenie/openspec` image via the Makefile:

```
make openspec-image                 # pull GHCR hash of openspec/Dockerfile else build locally
make openspec-validate-all          # == the `ci-openspec` target: validates every change
make openspec-validate NAME=<change> # validate ONE change by name (fastest for a single fix)
```

`openspec-validate-all` printing `Totals: N passed, 0 failed` and exit 0 is the CI-equivalent
pass. **Capture the exit code unpiped** (`cmd > out.txt 2>&1; echo exit=$?`), not through
`| tail -1` — the pipe reports `tail`'s status, hiding the real rc.

## Guard-prove the fix (RED on the old spec, GREEN on the fixed one)

The file you edited is the artifact the gate reads, so prove the gate actually catches the
defect before trusting the fix:

```
SPEC=openspec/changes/<name>/specs/<cap>/spec.md
cp "$SPEC" /tmp/spec-fixed.md
git show <parent-sha>:"$SPEC" > "$SPEC"        # restore the OLD (prose) spec
make openspec-validate NAME=<name>             # must FAIL: "No delta sections found"
cp /tmp/spec-fixed.md "$SPEC"                  # restore the fixed delta spec
make openspec-validate NAME=<name>             # must PASS: "Change '<name>' is valid"
git status --short                              # confirm the tree is clean again
```

## Prove the fix is on the vehicle, not just in the worktree

After pushing, confirm the committed delta is actually in the PR payload at the head sha:

```
gh api repos/<o>/<r>/pulls/<n>/files --paginate --jq '.[]|select(.filename|test("<name>/specs/.*/spec.md"))|{filename,status,additions,deletions}'
```

A spec that validates in your worktree but is absent from `pulls/<n>/files` means the commit
did not carry it; re-push before reporting.

## Reading which step redded — `skipped` is not `passed`

When the `guard` job reds `check-pr-base` (base-drift), the workflow short-circuits and the
`linux` job that actually runs `make ci-openspec` reports `skipped` — it never ran. Do not read
its absence from the `conclusion==failure` set as a pass; enumerate all steps with their
conclusions (see `references/gate-replay-verification.md`) and prove the openspec target
locally. The remaining `check-pr-base` red is base staleness owned by the rebase lane, not a
content defect in the spec change.
