# The `agents/` profile tree: foundation PRs, canonical copies, and owned debts

Depth for `SKILL.md` §"A PR that carries another PR's file" — read this before adding a file under
`agents/`, before touching a checker that several PRs carry, or when a fleet-wide rule needs one text.

## Four PRs each carrying the same foundation

Two lanes building the same foundation (`agents/manifest.json`, a `scripts/check_*.py`, a `make` target)
each open a PR containing it, and the merge order then decides whether the newer PR's additions survive:
had the sibling landed second, the merge would have reverted the checker to the version that compares
nothing, with **no red check and three profiles silently ungated**.

- Write the loss down as a test: `assert callable(getattr(guard, "<the_leg>", None))` **plus**
  `assert "items.extend(<the_leg>(" in source`. Planting the removal must red it.
- When four PRs each carry the same skeleton (`gh pr view <n> --json changedFiles,files` shows it),
  adding a fifth copy is the wrong move. Split instead: the lane's **content** goes into the widest PR
  (the one the dispatcher widens to carry every lane), and the lane's **code** — the gate leg, the single
  canonical file, the exemptions, the tests — becomes its own one-commit delta prepared on the sibling's
  head and HELD unpushed until it merges.
- Prove the held delta is scope-clean before holding it: `git diff --stat <base>..HEAD` must name only
  your files, and any test in it that depends on a file the base does not have is either rewritten
  against a fixture or it is out.

## One canonical copy, compared by a gate

Behaviour files that must agree across many directories (thirteen `agents/*/SOUL.md`, a fleet block, a
policy table) drift the moment two authors copy from memory: a second profile shipped **10 of 12
bullets** and every gate stayed green, because the checker only tested the rules a *manifest declared*.

The shape that works, in four parts:

1. one canonical file (`agents/standing-rules.md`);
2. the gate extracts it and compares each copy, failing with **the item name and the first missing
   line**, not just "mismatch";
3. deleting the canonical file is a **finding** rather than a skip while any copy still claims it —
   otherwise the check passes by not looking;
4. gaps that are genuinely unowned go into an exemptions file with a mandatory `reason` **and**
   `owner`, are printed by the gate's `report` (green, but named), and are reported **STALE** the moment
   the copy becomes verbatim.

Clause 4 is what keeps an allowlist from becoming permanent: the guard audits its own list, and an entry
with no written reason — or naming a profile the tree does not list — is itself a finding.

## A rule must be STATED, not quoted

The rule check asked "do the words appear anywhere in the file?", so a lane section citing the owner's
instruction satisfied the rule with the statement itself deleted — found by sabotage, where removing the
statement PASSED. Strip the three shapes a quotation takes in these files (fenced code blocks, blockquote
lines, `"…"` spans) before matching, and keep a distinct finding key for "present in the raw text but
absent from the stated text", so a deletion and a quotation do not print the same message. A correctly
stated rule must still pass — over-correcting into a gate that reds a properly stated rule is the same
cost one step later.

## Report-only findings live OUTSIDE `findings()`

An "unprotected profile" item (`rules: []` — the gate protects nothing there) was appended to the findings
list, and that broke a clean-tree test asserting `findings() == []`: one function then answered two
different questions ("is the tree clean" and "is anything worth naming"). Keep the report-only class in
its own function, print it BEFORE the clean/dirty branch so it appears on a dirty tree too, and let it be
loud without being fatal — several lanes legitimately ship an empty rule list, and a gate that reds every
PR on a pre-existing manifest gap is a gate that gets switched off.

## The sync seam writes into a RUNNING agent

`make sync-agent-profile` copies the tree into a profile's Hermes home, so a truncated in-tree copy would
replace live behaviour: measured, an in-tree seed was 20,297 b against a live 100,031 b, and 5,149 b
against 7,509 b. Two rules: the write path REFUSES to shrink the live file unless explicitly forced
(printing both sizes and the file), and a read-only comparison names the direction
(`TRUNCATED?`), because the neutral wording "differs, run the sync" is the instruction that destroys it.
The escape hatch has to be reachable through the documented interface (`make … FORCE=1`), verified end to
end against a temporary destination — refusal leaves the live file byte-identical, the forced run writes
and reads back.

## Covering the half of the comparison that cannot run in CI

The live-vs-tree comparison needs `~/.hermes/profiles/`, which a CI runner does not have, so its strongest
finding skips in every automated context. Three parts make it a control instead of a reminder:

1. **The skip is a COUNT, not a sentence.** Print `live comparisons: N`, with `0 (… NOT compared)` when
there is no profiles directory, and write the same number into `$GITHUB_STEP_SUMMARY`. "Compared and
found nothing" and "compared nothing" otherwise read identically as a green line.
2. **A caller that runs where the profiles exist.** A make target plus a host cron script, exit codes
`0` clean / `3` defect / `2` could-not-compare (never report `0` from a host with no profiles). Script-only
cron jobs deliver stdout verbatim and send nothing on empty stdout, so a clean run must print nothing.
3. **One issue, refreshed — never a second one.** File `profile drift: <categories>`, and on the next run
comment on the open issue. Dedupe by LISTING and matching the title locally: a title SEARCH is eventually
consistent and filed two issues a minute apart for one condition.

**Classify by which side owns the extra lines; a size test calls the worst case nothing at all.**

| category | lines | what a sync does | reported? |
|---|---|---|---|
| `truncated` | tree ⊂ live | deletes live behaviour | yes |
| `diverged` | both sides own lines the other lacks | destroys work on **both** sides | yes |
| `missing` | no counterpart | creates or drops a file | yes |
| `tree-ahead` | tree ⊃ live | only adds | counted, never filed |

A tree copy LARGER than live (10,634 b vs 9,876 b, 15 tree-only lines) is invisible to `live > tree`,
which is exactly the destructive case. Without the `tree-ahead`/`diverged` split the target is red almost
continuously — a lane editing its own live skills generates drift by acting normally — and a permanently
red alarm is a filtered alarm.

**Scope: enumerate the TREE only, on an allowlist.** Walking the live side reported 52,165 "missing" state
files (`.curator_backups/blobs/`, `.backup.lock`), then 3,184 installed skills. A live profile holds state
and every installed skill; the tree is a curated subset, so "live has a file the tree does not" is the
design. Allowlist `SOUL.md` + `skills/**`, skip any dot-segment, and never enumerate live→tree.

**A tree copy MIRRORS behaviour; it does not rewrite it.** A tree SOUL that was the tidier rewritten
version while live still ran the older text is `diverged` (5,714 b vs 2,811 b, 45 tree-only and 30
live-only lines) — the detector's own first catch was its author's file. Rebuild such a copy as the LIVE
file verbatim plus the canonical block it is missing, and fix wording in the live file deliberately, not
by letting the repository diverge from what the agent actually runs under.
