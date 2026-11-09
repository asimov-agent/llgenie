# CI gate: openspec change-dir authoring + an unchecked task box can be the intended hold

## Delta-spec authoring format — get the shape right before validating

A behavioural script/workflow change owes an openspec change dir. The validator
(`docker run --rm -v $PWD:/repo -w /repo llgenie/openspec:latest openspec validate <change> --type change`)
is picky about structure; these are the exact requirements, each of which cost an
iteration when wrong:

- The delta spec lives at `openspec/changes/<change>/specs/<capability>/spec.md` — a capability
  subdirectory, NOT `specs/spec.md` at the change root.
- Top section is `## ADDED Requirements` (a plain `# <change>` title line above it is fine).
- Each requirement is `### Requirement: <name>` and MUST be followed by a prose paragraph that states
  the WHEN … THEN semantics BEFORE any `#### Scenario:` block. A requirement whose first child is a
  `#### Scenario:` header fails with **"missing requirement text"** even though it has scenario text.
- A requirement may carry MULTIPLE `#### Scenario:` blocks — but only when the prose paragraph is
  present above the first one; that is what distinguishes it from the missing-text case.
- Each scenario carries `- **Given**/**When**/**Then**` bullets and a `- **Test:**` line pointing at the
  hermetic test (and, where useful, the live probe).
- `.openspec.yaml` mirrors an existing change: `schema: spec-driven` + `created: <date>`.
- A `docs/changes.d/<stem>.md` fragment must be EXACTLY one table row in the `| date | what | [note] | #NNN |`
  form, and its `[note]` link must resolve to a real `agent-wiki/<stem>.md`. Re-run `make changes-index`
  after writing it, then `make check-docs`.

Copy the shape from a recently-validated change (e.g. the stall-holder spec) rather than inventing it:
`git show <union-sha>:openspec/changes/<known-good>/specs/<cap>/spec.md`.

## CI gate: an unchecked openspec task box can be the intended hold

When `make ci-openspec` (the `scope` job) fails with
`[openspec-tasks] FAIL <change>: unchecked task checkbox(es) at lines [N]`,
that red is NOT automatically a forgotten task to tick. If the named box is a
proof cell of the form "… is proven on a CI run from this PR", the red is the
gate WORKING: the box stays unticked BY DESIGN until a CI engine-build at the PR
head goes green.

- Do NOT tick it on faith.
- Do NOT "fix the change fragment" to clear the red — the fragment is correct.
- The only correct resolution: proof-green → tick the box → push → confirm a
  completed green `ci-openspec` + CI run at the NEW head.

"Proof-green" here means a completed engine-build run whose `head_sha` EQUALS the
live PR head. Because `engine-build.yml` is `workflow_dispatch`-ONLY and a
cross-repo PR's head lives in a fork, that run is a dispatch you make after
aligning the BASE repo's same-named branch to the fork head — see
`ci-run-watching.md` (dispatch-by-branch, base-repo vs fork head). A green run at
the base repo's stale branch proves the parent, not the head: it is NOT the
trigger to tick.

Ticking the box early to clear the red defeats the gate it exists to enforce.

## Pitfall: head sha vs parent sha — the fix may be the parent, not the head

A proof run whose `head_sha` is the PR head's PARENT still proves the cell when
the head only layers openspec doc/test/task-alignment files on top (no
installer or Dockerfile change). Verify ancestry before concluding a fix
"never landed":

    GET /repos/<owner>/<repo>/compare/<parent>...<head>
    → expect status: "ahead", ahead_by: N, total N commits (= head only)

A head sha that differs from your fix commit does NOT mean the fix is missing —
it may be the head's immediate parent. State head and parent as two separate
facts and never conflate them (a reviewer reading "proof runs at <parent>" as
"head is <parent>" is a common misread).

## Pitfall: request identity is not enablement

`gh pr merge --auto` exit 0, a GraphQL/pushing identity, or
`auto_merge.enabled_by` alone is a REQUEST identity, never enablement.
The PR is armed ONLY when REST `/pulls/<n>` shows a **non-null**
`auto_merge.enabled_at`. `enabled_by` present with NO `enabled_at` key means
NOT armed (#964 / #1247). Report arm time only from a non-null `enabled_at`.
