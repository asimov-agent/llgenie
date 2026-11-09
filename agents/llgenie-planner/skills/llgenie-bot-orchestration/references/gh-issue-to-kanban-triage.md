# Triaging existing GitHub issues into the kanban

Route open GitHub issues to their owning lanes as kanban cards — both un-PR'd issues
and each open PR's closing issue (read-only mirror), so the board mirrors every open
issue. The fleet's board is the planner's real dispatch surface; an issue that only
sits in GitHub is invisible to the host lanes and never gets worked.

## When

Owner asks to "load N issues into triage" or a lane is idle with no card. First
**measure the pull candidates**, then create cards, then **verify one card per issue**.

## 0. Cover BOTH directions — no-PR issues AND open PRs' linked issues

A triage pass is not complete when only un-PR'd issues are carded. The board must
mirror every open issue that is the subject of an open PR too, so the
PR→issue→board trail is complete and can't be lost when the PR lands.

1. No-PR issues → create a card routed to the issue's owning lane (the body of this
   reference after this section).
2. **Open PRs → their closing issue:** for every open PR, read `closes #n` from the
   body; if that issue has no live card, create one that is a **read-only mirror**
   (body: "issue N open, linked from PR #M which is on the board; do NOT duplicate
   the PR branch work — coordinate/progress the issue"). One vehicle per issue
   (#824) still holds — the PR stays the single vehicle; the issue card exists so
   the issue is tracked and routed to its owning lane.

```bash
# 2a. all open PRs
gh pr list --repo "$S" --state open --limit 200 --json number --jq '.[].number' > /tmp/openprs.txt
# 2b. each PR's closes target, card count for that issue
for n in $(cat /tmp/openprs.txt); do
  closes=$(gh pr view $n --repo "$S" --json body --jq .body |
    grep -oE 'closes? #?[0-9]+' | grep -oE '[0-9]+' | head -1)
  cc=$($HB kanban list --json 2>/dev/null | python3 -c \
    "import sys,json;d=json.load(sys.stdin);ts=d if isinstance(d,list) else d.get('tasks',[]);\
print(sum(1 for t in ts if '#$closes' in (t.get('title') or '') and t.get('status')!='done'))")
  [ "$cc" -ge 1 ] || echo "MISSING card for issue #$closes (PR #$n)"
done
```

Do this in the SAME pass as the no-PR routing; the owner's "make sure existing PRs
and issues are linked to the board too" is the literal ask that catches a pass that
carded only one half.

## 1. Measure candidates (no open PR, no card, agent:implement)

```bash
S=asimov-agent/llgenie
# issues labeled agent:implement with no linked open PR
gh issue list --repo "$S" --state open --label "agent:implement" \
  --limit 250 --json number,title --jq '.[].number' > /tmp/impnums.txt
# per issue: card count on the kanban + open-PR count (search 'closes #n')
HB=$HOME/.hermes/hermes-agent/.hermes/bin/hermes
for n in $(cat /tmp/impnums.txt); do
  c=$($HB kanban list --json 2>/dev/null | python3 -c \
    "import sys,json;d=json.load(sys.stdin);ts=d if isinstance(d,list) else d.get('tasks',[]);\
print(sum(1 for t in ts if '#$n' in (t.get('title') or '')))")
  pr=$(gh pr list --repo "$S" --state open --search "closes #$n" --json number --jq 'length')
  echo "#$n card=$c pr=$pr" >> /tmp/cands.txt
done
# clean candidates = card=0 pr=0
grep ' card=0 pr=0' /tmp/cands.txt
```

## 2. Route each to its owning lane (the #2073/#2270 map)

Not `llgenie-issse-implementer` for everything. Per the ownership map:
docs/agents → `llgenie-documentation-maintainer`; gates/scripts/workflows →
`llgenie-ci-pipelines-maintainer`; security → `llgenie-security`; profile-drift for a
lane → **that lane**; engine → `llgenie-engine-improver`; rebase → `llgenie-pr-merge-conflict`;
verdict/write-back → `llgenie-pr-reviever`; tester → `llgenie-tester`; architect →
`llgenie-architect`; integration/orchestration behaviour → `llgenie-planner`. Add the
lane's label on the GitHub issue too, so the on-repo issue-bot and the host board agree.

## 3. Create the card (CORRECT syntax — pitfalls below)

```bash
# title is POSITIONAL — there is NO --title flag (hermes: error: unrecognized arguments: --title)
# body via --body-file survives newlines/flag-like lines
make_card() {
  local issue=$1 lane=$2
  local title=$(gh issue view $issue --repo "$S" --json title --jq .title)
  printf 'Issue %s (agent:implement, no open PR, no card). Dispatch to %s per the #2073/#2270 ownership map. Fetch origin/main, branch fresh off the current tip, implement, bookend (start+finish comments), never merge/arm (#1088).' "$issue" "$lane" > /tmp/cardbody.txt
  out=$($HB kanban create "llgenie #$issue: $title" \
        --body-file /tmp/cardbody.txt --assignee "$lane" --json)
  # read the new id from the JSON, not `` (empty) stdout
}
```

## Pitfalls (all hit live)

- **`--title` does not exist.** `kanban create` takes the title as a positional
  argument. Invoking `create --title ...` errors on *every* call with
  `unrecognized arguments: --title` — no card is made, and the loop fails silently
  so you think nothing happened (or, run twice, you get duplicates).
- **`--json` is required to read the id back.** Without it `create` prints nothing
  useable; you cannot verify the card landed or remember its id. Always `--json`.
- **Idempotency key / dedupe is essential, or you create copies.** A single
  `create` loop run twice (e.g. a probe call + the real call) yields 2 cards per
  issue, plus any `TEST` card. That is exactly how 16 issues became 34 cards.
- **There is no hard `kanban delete`, only `archive`.** `kanban delete` is not a
  subcommand. To clean a duplicate: `kanban archive <id>` (hides it; the card's
  worktree/timeline is kept). A verification line that greps only non-`done` cards
  still counts archived-are-gone? **No:** archived cards leave the board list, but a
  grep on `(t.get('title'))` matches only titles, so after archive the per-issue count
  drops. Verify with the same grep used to detect duplicates.
- **Dedupe guard first:** count cards per issue (title-contains `#n`) before
  creating; a ready/running card on an issue is one vehicle — do not add another
  (#824 one-vehicle-per-issue).

## 4. Verify on-wire (always)

```
kanban list --json | python3 -c "count cards per '#n' (status != done)"
```
Expect exactly **one** live card per issue, assigned to the owning lane, status
`ready` (or `running` if a worker claimed it). Report the id + lane + status, not
just "created N cards".
