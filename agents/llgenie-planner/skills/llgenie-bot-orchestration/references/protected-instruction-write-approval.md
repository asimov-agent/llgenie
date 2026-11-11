# Protected agent-instruction writes: the approval gate no dispatch can satisfy

Applies when a lane (docs / any implementer) reports it cannot land an edit to a protected
file — `SOUL.md`, an agent-instruction file under `agents/<profile>/`, or `<repo>/.hermes/config.yaml`.

## What the gate actually is (verified in Hermes source)

`tools/file_tools_write_guards.py` → `_check_protected_instruction_write` /
`_request_protected_instruction_approval`:

- Matches by basename (`SOUL.md`, agent-instruction basenames, glob patterns) and by an
  `<x>/.hermes/` immediate parent. Any write tool call hitting those files routes here.
- Its own docstring: *"Deliberately NOT routed through `_run_approval_gate` (honors --yolo and
  allowlists): this gate is one-operation approval EVERY time, no persisted scope, fail-closed
  without a human channel."*

Consequences — do not spend time fighting them:

- **No config escape hatch exists.** No config key, no `approvals.command_allowlist`, no
  `--yolo`, no auto-approve, no session/permanent scope. Searching config or docs for an allowlist
  is wasted motion.
- **The refusal message is binding:** `"The user has NOT consented. Do NOT retry it or attempt
  the same edit via another path (terminal, execute_code, etc.)."` Routing the edit through a
  shell or `execute_code` is both forbidden by the gate and pointless.
- **A planner-relayed consent does NOT satisfy it.** The gate is a read-time approval tied to the
  session performing the write; the owner saying "yes, grant the write" in the planner's chat is
  not the same event as the human answering the lane's own prompt. Silence/timeout = not consented.

## The gate exempts the ACTIVE profile's own home — and only that

`_hermes_exempt_homes()` exempts the active profile's home directory (the agent's own store,
which has its own guards) so the gate does not fire on it. Everything else is gated, including
**the repo tree copy of the same file**. The practical split, measured:

| Path | Gate fires? |
|---|---|
| `<root>/profiles/<lane>/SOUL.md` (live, active profile) | **No — writable by that profile's session** |
| `<repo>/agents/<lane>/SOUL.md` (versioned tree copy) | **Yes — per-write human approval** |

So "the same gate applies to the planner too" is FALSE for the planner's own live profile: a
planner session can edit its live `SOUL.md`/skills directly. It still may not edit another
profile's home (different active scope), and it still may not edit the repo tree copy.

**Do not read that exemption as a licence to self-edit behaviour.** A live-only rule edit creates
two copies that disagree — live has the rule, the tree does not — which is precisely the drift
class the sync/size gates exist to catch, and it is invisible to reviewers. When the owner
instructs a behaviour change, the correct sequence is: issue + repo-tree PR for the versioned
copy (the gated write, needs a human), and say plainly on the issue that until it lands the rule
is **live-only**. Report the divergence rather than quietly normalising it.

A useful diagnostic when a lane reports a protected-write block but the planner's own write to a
similarly-named file succeeded: they are different paths with different gate status, not a lane
bug and not a working bypass. Check which of the two rows above the path is before drawing any
conclusion.

## Landing the versioned copy: never copy live → tree

The live profile and the repo tree are **not** a newer/older pair — each can carry lines the other
lacks. A live copy is routinely *smaller* than the tree copy while the tree holds unique rules, so
"sync live into the tree" silently deletes them. Prove the direction before copying anything:

```bash
# distinct-line subset check — the only safe basis for a copy or a move
python3 -c "
import subprocess
orig = subprocess.run(['git','show','origin/main:<tree path>'],capture_output=True,text=True).stdout
new  = open('<new body>').read() + open('<extracted reference>').read()
t = {l.strip() for l in orig.splitlines() if l.strip()}
n = {l.strip() for l in new.splitlines() if l.strip()}
print('LOST:', len(t - n))"
```

A non-zero `LOST` means stop — the edit is destructive, not a sync. (Measured: a live body 81
distinct lines shorter than its tree counterpart; a straight copy would have deleted the
merge-over-red verification rule, the ci-verdict re-judge/expiry rule and a push discipline.)

Base every such edit on the **tree** copy and move sections outward, never inward:

1. `git show origin/main:<tree path> > /tmp/tree_copy.md` — the base.
2. Move an oversized section verbatim into `references/<topic>.md`; leave a summary plus a pointer
   in the body. This is the standard remedy when the body hits the writer's character cap.
3. Add each new reference and link it from the pointer block, then re-run the subset check
   including the new reference file. Zero `LOST` is the gate.

**The skill-writer cap is a silent failure mode worth pre-empting.** `skill_manage` refuses any
`SKILL.md` over 100,000 characters and rolls back the *whole* batch, so a body that grew past the
cap cannot be patched at all — the failure reads as "could not find a match" or a bare abort, not
as "over the limit". Measure `wc -c SKILL.md` before planning an edit; when headroom is thin
(hundreds of bytes), write the lesson into a `references/` file and spend the only budget you have
on a short pointer. A gate that fails on any `agents/*/skills/*/SKILL.md` over the cap, naming the
file and the overflow, is the durable fix — the refusal message should name its own remedy
(move sections into `references/`), not just the character count.

## Where the prompt surfaces

`_request_protected_instruction_approval` resolves a gateway notify callback for the *writing
session's* key (`get_current_session_key()`), else a per-thread CLI callback. So the approval
button appears in the **lane's own session/chat window**, never the planner's. A timeout means
nobody was watching that window — not that the lane misbehaved. With no interactive user and no
gateway callback it returns `"requires approval but no interactive user or gateway is present"` —
genuinely impossible until a human is attached.

## Correct orchestration

1. Treat the lane's block as **correct behaviour**, not a stall. Confirm from the source (above)
   rather than assuming a bypass exists. Do not ask the lane to retry "via another path".
2. Do **not** take the repo-tree write yourself — the planner never implements, and that path is
   gated for the planner too (only the active profile's own home is exempt; see the table above).
3. Confirm the owner is actually present at the desktop *now*.
4. Dispatch exactly **one** retry to the lane and, in the same breath, tell the owner to switch to
   that lane's session and click **approve** when the prompt appears. Quote the prompt text
   (`"Write to protected agent-instruction file(s): agents/<lane>/SOUL.md"`) so they recognise it.
5. Cap retries: a second timeout is a human-presence problem, not a lane loop. Stop, report the two
   timeout ids, and leave the branch/worktree ready for when a human is watching. Never hammer a
   fail-closed gate.

## Reporting line

When handing back, state: the gate's block observation id, that the gate is per-write human
approval by construction (cite the guard function), the branch sha prepared, and the unblock
condition "owner answers the approval prompt in the lane's session". That tells the next reader why
the lane stood down without implying it abandoned the issue.
