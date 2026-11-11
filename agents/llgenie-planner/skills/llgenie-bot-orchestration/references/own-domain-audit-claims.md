# Verifying a lane's "own-domain audit finished" report

A continuous-improvement audit is the easiest place for a lane to produce a plausible summary with nothing
behind it: the work is read-only, so no CI run contradicts it, and the deliverable is prose. Verify the
landings, not the narrative.

## The times inside a report body are decoration

A bookend reading `since 11:25Z` on a comment the API created at `11:11:56Z` is not clock skew to explain
away — lanes template their fixed state line and can emit planned, copied, or future timestamps. Take both
ends of any claimed duration from the API:

```bash
gh api repos/<owner>/<repo>/issues/<n>/comments --jq '.[]|.created_at+": "+(.body[0:120]|gsub("[\r\n]";" "))'
```

Judge implausibility (a multi-issue, multi-PR audit finished in three minutes) only against `created_at`,
and never repeat the body's times to the owner as measured facts.

## Count the landings per target thread

The bookend says "annotated N issues"; the check is one count per named issue, scoped to the audit window:

```bash
for iss in 1811 1843 1849 1745 1558 1815 1845; do
  c=$(gh api repos/<owner>/<repo>/issues/$iss/comments \
      --jq '[.[]|select(.created_at>"<audit-start-iso>" and (.body|test("tester|annotat|verification path|AC-")))]|length')
  echo "#$iss post-start annotations=$c"
done
```

A target at `0` means the annotation was never posted, was posted before the audit started (i.e. copied from
somewhere else), or landed on a different issue — all three are the same defect for the board. Probe every
named issue, not a sample: the claim is a list, and one missing element falsifies it.

## Verify the filed finding

`findings: 1 (filed #<n>)` is a claim about an object. Fetch it and assert the shape the queue requires:

```bash
gh api repos/<owner>/<repo>/issues/<new> --jq '{state,labels:[.labels[].name],title}'
gh api repos/<owner>/<repo>/issues/<new> --jq '.body' | grep -cE '^## (Problem|Why it matters|How we fix it|Benefit|Technical|Acceptance criteria)'
```

Expect `state=open`, the queue labels (`agent:refined`, `agent:implement`), and six section headings. A
finding that exists but carries five sections is a `refine`, not a dispatchable issue.

An audit that filed nothing and declares itself clean must carry the exact line
`re-audited at <sha>, no findings` — accept it only with the sha, and only if the audit window shows the
measurement work (counts, queries) on the tracker thread.

## "audit swept, no PR owed" with no finish record is an unfinished audit

A start comment is a claim, a finish comment is the artifact. When a lane posts a start line ("audit swept, no PR
owed · blocked on none") and then nothing — no `re-audited at <sha>` line, no findings issue, no further post an hour
later — the audit did not finish; the start comment is a plan wearing the shape of a result. Re-dispatch it with a
bounded round-two scope rather than accepting the start line as the deliverable, and say which artifact you are
measuring (the missing finish comment) so the lane cannot answer with a restatement of the start.

## Then close the dispatch, with evidence

Post a closure comment on the tracker that restates each acceptance criterion with what verified it (counts,
object state, six-section check), names the main sha the audit ran against, and states `no merge/arm/tick`.
Read the comment back by direct id before reporting it to the owner. Queue the filed finding through the
normal implementer lane — an audit never implements its own finding.
