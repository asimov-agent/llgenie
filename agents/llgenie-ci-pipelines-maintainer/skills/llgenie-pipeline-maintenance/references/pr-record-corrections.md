# Post-merge record corrections and phantom-guard discipline

Depth for the situations where the *code* is already landed and the only work left is correcting the public record — plus how to behave when a completion guard keeps demanding a change that is genuinely not owed.

## A merged PR's body is still editable — use it to correct a wrong anchor

GitHub does **not** freeze a PR body on merge. `gh pr edit <n> --body-file <file>` succeeds on a `MERGED` PR and is the correct way to fix a false `closes #X` claim after the squash already landed.

- Do not settle for a comment "because the body is frozen" — the body is not frozen, and a comment leaves the wrong `closes` keyword in the record where auto-linkers and future readers actually look.
- The mutation: read the current body to a file, replace the bad closing line with the correct relationship, write it back, then **read back** and assert the counts — the old `closes #X` must be `0`, the new reference `1`. A body edit is proven by a `grep -c` read-back, not by the edit's exit code.
- Prefer a non-closing keyword for a fix that merely *implements* a tracked finding (`Implements #Y`) over a closing keyword, so you never accidentally auto-close an issue you are only anchoring.
- **A closing keyword on an already-`MERGED` PR is INERT — it can never fire a close.** GitHub evaluates `closes`/`fixes`/`resolves` linkage at merge time; once the PR is merged, editing a `closes #N` into (or out of) its body is a pure *record marker* that closes nothing, retroactively or otherwise. `Implements #N` is not in the closing-keyword set at any state, so it never closes anything. On a merged body pick the keyword for what it COMMUNICATES to a reader, not for a side effect it will never trigger, and never promise a close you cannot deliver.
- **When the triage peer supersedes the issue you filed with its own number, re-point the body to THEIR issue — do not reopen yours, argue the numbering, or file a third.** The number that becomes the tracked anchor is the peer's call; your deliverable is the body text plus a clean `grep -c` read-back (`closes #THEIRS` = 1, the superseded number and the wrong number both = 0). Reopening a closed issue to "keep" your number overrides a terminal state.

## An owner-closed issue is an authoritative terminal state

When the issue that anchors the work reads `state_reason=completed` closed by the owner (not an automated PR-keyword close — check the timeline event's `commit_id`: a real auto-close carries the merge commit, an owner close does not), do **not** reopen it to make it a cleaner dispatch anchor. A closed-and-completed issue is still referenceable; reopening against the owner's decision is overriding them. Report the state and stand.

## A repeated completion guard is not proof a change is owed

When a completion-integrity signal keeps firing an identical "make the required task-relative change" prompt *after* the change has been made and read-back-verified, treat it as a phantom, not as a missed mutation. The discipline:

1. Verify the artifact exists by its own state (issue created with the right title/label; PR body grep counts correct). If both hold, the change is done.
2. Do **not** manufacture an extra mutation to appease the guard — a no-op commit, a reopened issue, a spurious file. That violates the no-op/ghost discipline the lane hard-mandates and pollutes the record.
3. State the completion with the read-back evidence and stop. Fabricating work to clear a guard is a worse failure than the guard firing.

## Splitting a paused compound command

A progress guard may pause a single shell invocation that mixes a read with a mutation. Run the **mutation alone** first (it executes and exits 0), then run the verification as a separate pure-read call. Do not conclude the mutation was refused when only the compound was paused.

## Body edit vs comment: which channel the answer belongs in

The body edit above is for fixing a **wrong anchor** (`closes #X`) that future
readers and auto-linkers actually read — that is why the *body*, not a comment,
is the right channel for it.

For an **ongoing owner question** on a PR ("where does this wait for the
producer?", "what am I missing?"), the durable on-record channel is a
**comment**, even on a merged PR. A post-merge body edit is a no-op for anything
a reviewer or gate would read; the conversation lives in the comment thread, so
answer there and cite the owner comment id(s) you are answering. Do not re-answer
an owner's live question by editing a merged body, and do not treat "the PR is
merged" as "the question needs no answer" — the record still expects it.

## Answering "does this gate enforce the requirement?" — separate may from will

A gate can enforce a **condition** (`may merge only if X is already true`)
without enforcing **causation** (`this change will produce X and wait for it`).
An owner reads a red gate as proof of causation and asks "where does it wait for
the producer?". The honest answer names which one the gate implements:

- Read the gate's own docstring/implementation: does it only read/resolve an
  existing artifact (condition), or does it trigger and wait on a producer run
  (causation)? It is usually condition-only.
- If the requirement is causation and the gate is condition-only, say so plainly,
  name the missing trigger+wait wiring, and point to the tracked follow-up issue
  that owns it — never let a one-line fix silently grow that scope.
- State it as: `may` = shipped, by design; `will` = <follow-up issue>, not wired
  here.
