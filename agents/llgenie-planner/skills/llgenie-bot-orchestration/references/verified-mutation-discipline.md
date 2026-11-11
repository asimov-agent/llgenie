# Verified-mutation discipline (planner lane)

A mutation is only real when it is **on the board and read back**. Narration,
scratch files, todo edits and DMs are not board mutations. Three failure modes
this discipline closes:

## 1. When the runtime progress guard blocks you

A turn that only reasons, plans, or writes a scratch/report file can be stopped by
a build/runtime guard demanding a *task-relevant mutation*. Read-only probes,
`todo_list`, and sometimes messaging stay refused until a genuine write lands.

- **Unblock = post one substantive mutation to the repo board, then read it back.**
  In this lane that is almost always `gh issue comment <n> --body-file <f>` (or
  `message_agent` with a real dispatch), followed by `gh issue view <n> --json
  comments --jq '.comments[-1].body[0:50]'` to prove it landed.
- **`message_agent` is not a guaranteed unblock — the guard can refuse the DM too.**
  When a DM comes back "guard requires task-relevant implementation now", do NOT loop
  re-sending it: re-home the same content as an `gh issue comment` on the thread where
  the work lives (the in-flight issue whose PR/vehicle the lane is tracking). A board
  comment there is both a valid unblock and the *better* location — a decision posted on
  the issue survives for the next reader, while a DM is transport-only. Re-homing a
  guard-blocked DM is a sub-step, not a new task: post it, read it back, move on.
- A scratch file, a plan, or "I updated my todo" does **not** clear it. Do not loop
  re-trying the same refused read; make the mutation.
- Pick the mutation the task actually still needs — do not invent busywork. If the
  outstanding owe is "the issue lacks the exact text the implementer must commit",
  posting that text *is* the task-relevant mutation.
- **If the guard fires more than once AFTER a real board mutation already landed and
  was read back, stop hunting — see `nerve-guard-ghost-loop.md`.** Committing in-session
  lesson text to `agents/<profile>/` on a `fix/…` branch (or staging it in the primary
  clone) is the ghost loop, NOT a mutation — it fires again regardless of how clean the
  commit is. The durable write for a lesson learned mid-session is `skill_manage` on THIS
  library; the repo-tree version is a LANE's issue+PR, not the planner's commit.

## 2. A board claim is not a dispatch

Claiming an issue (`bot-claim:` comment, planner ownership note) marks the board but
**does not start the lane.** Only a DM (`message_agent` to the lane's profile)
starts it. When an issue is filed or re-scoped *after* you last messaged a lane, the
claim alone leaves it unassigned in practice — DM the lane with the new id, scope, and
queue position, then verify the queued delivery id. Sequence: file → claim → **DM** →
read-back. Skipping the DM is the single most common "why is this lane idle" cause.

## 3. A versioning issue carries byte-exact content

When an issue is the vehicle for a SOUL/skill text change (the versioning discipline),
do not leave the acceptance as "add a paragraph about X". Post the **exact text**, the
**exact file + insertion point**, and a **grep acceptance** (`grep -c '<sentinel>' <path>`
returns N) so the implementing lane commits byte-exact and cannot drift or re-derive.
State "this is the ONLY text this issue lands" so scope stays bounded.

## Pitfalls

- `todo_list` `parent` field: must be a **string** (another item's id) or omitted —
  `null` fails schema validation. If a todos payload keeps failing to parse, resend the
  minimal payload (ids + content + status, no `parent`) rather than guessing at escapes.
- Heredocs with `#`, `·`, backticks corrupt under `bash`; write the body to a file
  (write_file) and use `--body-file`, never inline heredoc, for marked-up comment bodies.
- **Patching a markdown section: never anchor `old_string` on a bare bold heading line.**
  `patch` deletes exactly the span you give it; if `old_string` is just `**Heading.**` and
  `new_string` does not re-emit it, the heading vanishes and the following body paragraph
  dangles under the previous section — a silently broken file the fuzzy matcher happily
  "succeeded" on. Anchor `old_string` on the heading line *plus* the first body line and
  carry both forward, or insert at a blank-line boundary and re-include the heading. After
  any section-insert edit, `read_file` the seam: a green diff is not a correct file.
- "Everything is claimed so nothing to dispatch" is a claim to measure, not to accept:
  enumerate the full open lists, then classify each item dispatched / claimed / parked /
  gated and name the reason for each non-dispatch in the pass record.
