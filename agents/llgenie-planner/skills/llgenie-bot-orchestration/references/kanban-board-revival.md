# Kanban board revival: stale blocked cards park the whole fleet

**A board reading "N lanes idle, N cards blocked" is not idle capacity — it is capacity parked
behind gates that no longer exist.** A card blocked weeks ago can point at an issue that has since
been MERGED or CLOSED; the lane stays blocked forever because nothing re-checks the gate it waits on.
Revive before you report a single lane as idle.

## The check (every pass where blocked cards exist)

1. List cards with true status from JSON, never a text grep:
   `hermes kanban list --json` → count the `status` field (`running`/`ready`/`blocked`/`todo`).
   Grepping the text output for `ready` or `blocked` hits card TITLES (many contain
   "ready-for-review") and yields false counts — the JSON `status` is the only honest read.
2. For each `blocked` card, resolve its target issue on the wire:
   `gh issue view <n> --repo asimov-agent/llgenie --json state --jq .state`.
3. `MERGED` or `CLOSED` → the underlying work already landed. Complete the card with the merge as
   the result, freeing the lane:
   `hermes kanban complete <task> --result "issue MERGED/CLOSED on main; card stale against the
   landed merge — lane freed" --metadata '{"reason":"issue_merged_on_main"}'`.
4. Still `OPEN` → a real gate; leave it. Ready/blocked counts converge to honest ones.

## CLI quirks that cost a whole extra round-trip

- `hermes kanban complete` uses **`--result`**, not `--message` (the `--message` flag does not exist).
- `--summary` / `--metadata` are **per-task** and are REJECTED when passed with multiple ids
  ("would apply the same handoff to every task"). Complete one at a time to attach a result, or
  bulk-complete with ids only and no flags.
- `--force` exists and bypasses the normal completion guard; do not reach for it to "clear" a card
  whose gate you have not verified — verify the issue state first.

## Dispatch is the act; the dispatch return is not the fact

- `hermes kanban dispatch --dry-run` previews what WOULD spawn (`Spawned: N (dry)`).
- The real `hermes kanban dispatch` can report **`Spawned: 0` while the ready cards are already
  `running`** — workers claimed them in the interval between the dry-run and the execute.
  `Spawned: 0` is therefore NOT proof nothing happened. Confirm by re-reading
  `hermes kanban list --json` and watching `ready` → `running`; report the status transition, not
  the dispatch return.
- Global worker cap (5 observed): a ready card that stays `ready` after dispatch is a capacity
  answer — it spawns when a running card finishes. Report the unblock condition; do not re-dispatch.

## Why it matters

Idleness is the defect you are accountable for. Five stale cards on merged issues made ten lanes
read as "quiet" when the cron tick was running fine and the board was full of resolved work. The
fix is a board-state repair (complete the stale cards, then dispatch), never a claim that the fleet
is lazy or that the owner must intervene.
