# Refining an issue into the six-section shape (the body gate)

llgenie gates issue bodies on six canonical headings. `scripts/issue_body.py` exposes
`missing(body) -> list` naming exactly which canonical headings are absent. A body that reads
complete can still fail on ALL six — the gate checks the heading set, not the prose.

## Procedure

0. **Filing a NEW refined issue from a private finding** (not editing an existing one) follows the
   same shape end-to-end: write the six-section draft, gate it with `missing()` on the draft, then
   `gh issue create --body-file <draft> --label …` (see create pitfall below), then re-gate the LIVE
   body. Turning a finding you only posted as comments on other tickets into a titled, labelled,
   gate-clean issue of its own is the strongest planner board mutation — it produces a NEW changed
   path instead of comment-churn on a settled thread.
1. Read the live body: `gh api repos/<o>/<r>/issues/<n> --jq .body`.
2. Gate the draft in the repo root (so `scripts` imports):
   `python3 -c 'import sys;sys.path.insert(0,"scripts");import issue_body as ib;print(ib.missing(open("<file>").read()))'`
3. If `missing` is non-empty, rewrite into the exact canonical headings, in order:
   `## Problem`, `## Why it matters`, `## How we fix it`, `## Benefit`, `## Acceptance criteria`, `## Technical`.
   Preserve every measured fact (shas, run ids, evidence strings) — you are reshaping, not summarising.
4. Acceptance criteria must be real tickable checkboxes (`- [ ] …`), not prose paragraphs.
5. PATCH only after the draft gates clean: `gh api -X PATCH repos/<o>/<r>/issues/<n> -F body=@/tmp/draft.md`
   (or the simpler `gh issue edit <n> --body-file <draft>` — same effect, no `-F`/jq escaping to get wrong).
6. **Re-verify LIVE**: re-fetch `.body` and re-run `missing()` on the fetched text. A clean draft
   proves the draft, not the wire — confirm `missing(live)==[]` AND that your preserved evidence
   strings still appear in the live body. Also print the heading list
   `[l for l in body.splitlines() if l.startswith('## ')]` — presence is not enough, `## Technical`
   must be the LAST canonical heading, so an order-break passes `missing()` but still fails the shape.

## Batch refining several gate-failing issues in one pass

When a sweep surfaces more than one unroutable tracker (same class, e.g. several planner-domain
conventions filed as prose), refine them in ONE terminal pass instead of one turn each. Write each
draft to its own `/tmp/refine_<n>.md`, loop gate → PATCH → label, then re-verify all live:

```bash
for n in 101:draft101 102:draft102; do
  N=${n%%:*}; F=/tmp/${n##*:}.md
  python3 -c "import sys;sys.path.insert(0,'scripts');import issue_body as ib;print(ib.missing(open('$F').read()))"
  echo "checkboxes=$(grep -c '^\s*- \[ \]' $F)"          # must be >0 before PATCH
  gh api -X PATCH repos/<o>/<r>/issues/$N -F body=@$F >/dev/null
  gh api -X POST repos/<o>/<r>/issues/$N/labels -f labels[]='agent:implement' -f labels[]='agent:refined' >/dev/null
done
```

- **Gate, patch and label in the same loop only when the gate is already clean** — a label added to a
  body that still fails the gate advertises routability that isn't there. Print `missing()` for every
  issue before any PATCH so one bad draft cannot ride along with the good ones.
- **Run `missing()` BEFORE you treat a label as the guard-clearing mutation — a "reads-complete" body is the
  trap, not the evidence.** When a progress guard pushes you to mutate the board and you find an unlabelled
  issue whose body looks finished, the cheap move (add `agent:refined`+`agent:implement`) is WRONG if the body
  is not in the six canonical headings: a body sectioned `## Summary / ## Why / ## What to add / ## Non-goals /
  ## Acceptance / ## Related` (or `## Background & Goal / ## Current state`) reads complete to a human and fails
  ALL SIX of `missing()` — the label then advertises a routability CI re-reds on the next `check-pr-acceptance`.
  Order is always: gate the LIVE body (`missing()`), and only if `[]` does the label alone count as the mutation;
  if non-empty, reshape the headings THEN label in the same pass (a label without the reshape is not a
  board-fix, it is a false advertisement). The label is a legitimate board mutation ONLY over an already-clean
  body — that is the precise distinction the guard is scoring, and it is easy to skip under guard pressure.
- **Verify the labels separately from the body**: a label POST that half-applied reads as success in the
  loop's exit code; re-read `.labels[].name` for each issue and quote the list.
- **A tracker whose HOME is another lane's audit record can still be planner-refined** — reshaping an
  audit-record issue's headings is issue shaping (planner authority), not an edit to that lane's code or
  branch; note in the summary that only the body/labels changed.

## Pitfalls

- **The fetch output and the draft cannot be the same path.** `gh api … --jq .body > /tmp/x.md` creates a
  file this task never read with `read_file`, so `write_file` then refuses it (`stale_write_blocked`). Write
  the draft to a fresh filename; re-fetching the body purely to licence the overwrite is wasted work, and
  under the nerve guard's read-pause it is impossible.
- **Non-canonical headings fail the gate even when the content is complete.** A body written as
  `## Background & Goal` / `## Current state` / `## Acceptance` returns all six canonical headings
  as missing. The fix is to rename/restructure the headings and keep the prose — do not conclude
  the issue is unrefined, and do not restate it from scratch.
- **Bold-label pseudo-headings are the sneaky variant.** A body sectioned as `**Problem.** …` /
  `**Why it matters.** …` / `**Route.** …` paragraphs (bold spans, not `##` headings) looks fully
  structured to a reader and still returns ALL six as missing — the gate matches `## <heading>` line
  prefixes, not emphasis. Promote each bold label to a real `## ` heading and move any trailing
  `**Measured.**`/`**Route.**` prose under `## Technical` LAST; subsections the author already had
  (e.g. an `## Not covered`) can stay between Acceptance criteria and Technical. The content is
  already good — this is a heading-level reshape, never a rewrite.
- **A body already labelled `agent:refined` can still fail the gate** — the label records a past
  refine, not the current heading set. Sweeping open `agent:implement`/`agent:refined` issues with
  `missing()` is a reliable way to find genuine refine work (and, from the planner seat, a
  legitimate task-relevant mutation that clears the guard without a peer-lane edit).
- **Create the issue with `gh issue create --body-file <draft> --label …`, not a raw `curl -F` multipart.**
  `curl -X POST …/issues -F body=@draft.md -F 'labels[]=…'` can return HTTP 400 `"Problems parsing JSON"`
  (`gh issue create` succeeds first try on the identical draft+labels). The create-issue endpoint expects a
  JSON payload; multipart `-F` fields are not decoded the same way, so the failure reads as a schema error
  in your body when the body is fine. `gh issue create` handles the encoding and prints the new issue URL —
  verify that URL, then re-gate the LIVE body.
- **A per-lane `agent:<lane-name>` label is a phantom — the owning lane is routed via the body's `owns:` line,
  not a label.** Only a small fixed set of routing labels exists (`gh label list --json name` returns e.g.
  `agent:implement`, `agent:refined`, `continuous-improvement`); `agent:ci-pipelines-maintainer`-style strings
  do NOT, and passing one aborts the create. Name the owning lane in `## Technical`'s `owns:` line and label
  with the routing labels you confirmed exist.
- **`gh issue create --label <unknown>` fails ATOMICALLY — no issue is created.** An unknown label
  string aborts the whole create (`could not add label: 'x' not found`) and nothing lands, unlike a
  guard bounce (which leaves the payload intact and is cleared by an identical retry). So after any
  failed `gh issue create`, first check whether the issue actually landed
  (`gh issue list --search '<title fragment>' --json number,state`) before deciding what to do: if it
  landed, only the label failed — add it separately with
  `gh api -X POST repos/<o>/<r>/issues/<n>/labels -f labels[]='agent:implement'`; if it did not, retry
  the create with only labels you have confirmed exist (`gh label list --json name`). Never assume a
  non-zero create means "retry the same call" — a bad label makes that retry fail identically.
- **A `## Acceptance criteria` list of pre-ticked `- [x]` rows fails the gate exactly like a missing section — and
  the tick state is a FACT to read before you reset it.** `issue_body.missing()` reports "carries no `- [ ]` item",
  so the red reads like a pure shape defect while the real question is whether the work is done. On an OPEN issue,
  all-ticked criteria are either (a) genuinely satisfied — then the right action is close-with-evidence or a verdict
  write-back, not a rewrite — or (b) ticks copied in from a template/derived body, which must be reset. Decide by
  reading that issue's own evidence comments first; then reset with a line-anchored pass over criteria rows only
  (`re.sub(r'(?m)^- \[[xX ]\]', '- [ ]', body)`), never a global `[x]`→`[ ]` replace — that un-ticks completed work
  quoted under `## Technical` or inside a preserved excerpt.
- **Malformed checkbox syntax is invisible to both the gate and any count.** A row written `- [x]]` (doubled closing
  bracket) or `* [ ]` matches neither the gate's `- [ ]` prefix nor `grep -c '^- \[ \]'`, so the body reads fully
  ticked to one tool and unticked to another, and the red names the section rather than the offending row. Print
  every row that is not exactly `- [ ] text` (`re.findall(r'(?m)^[-*] \[.*', body)`) before deciding, and normalise
  it in the same edit.
- **`## Not covered` belongs BEFORE `## Technical`, never after it — and appending it last is the natural writing order that fails the gate.** `Technical` must be the final canonical heading; a body whose tail reads `… ## Technical … ## Not covered` returns two violations at once (`## Technical must be the LAST section (it is followed by ## Not covered)` and `## Not covered must sit between ## Benefit and ## Technical`). Write the out-of-scope note immediately after `## Acceptance criteria`, then let `Technical` close the body — or programmatically cut the `## Not covered` block off a finished draft and re-insert it before `## Technical`, then re-gate. Attempting to close scope by appending is what makes this recur.
- **An unlisted seventh heading is a violation only by POSITION, not by existence.** `Not covered` is the one optional section; anything else you add (a `## Rollout`, a `## Related`) is outside `SECTIONS` and will not gate clean. Fold extra sections into `Technical` as prose rather than inventing headings.
- The body gate is separate from the change-note gate: never hand-edit `CHANGES.md` to satisfy
  either; the change-note row lives in `docs/changes.d/` (see `change-note-gate.md`).
