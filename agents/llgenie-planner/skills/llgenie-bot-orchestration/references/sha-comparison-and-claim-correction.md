# Comparing commit-ish values and correcting your own on-wire claims

Two failure modes that cost the most time in a planner pass: a comparison that is
*structurally* always-true/always-false, and the recovery when such a comparison has already
been posted as a fact.

## 1. Compare sha prefixes at EQUAL length, or use `startswith`

```python
tip[:12] != '781f698a7e'        # WRONG: 12-char slice vs 10-char literal -> ALWAYS True
tip[:10] != '781f698a7e'        # right: both sides 10
not tip.startswith('781f698a7e')  # best: intent reads correctly
```

**Do not hand-write this comparison for a guarded post — run `scripts/guarded_post.py`.**
`guarded_post.py --issue N --body-file F --expect head:<sha> --expect base:<sha>` fetches the
expect values on the same call, compares prefixes at equal length via `startswith`, prints both
values with their lengths whether or not it posts, then read-back verifies the new comment by
direct-ID GET including body identity. Its exit codes distinguish skipped-precondition (3) from
verify-mismatch (4), so a silent no-op can no longer be mistaken for an endpoint failure.

A slice of one length compared to a literal of another length can never be equal, so the branch
takes the "changed" path every single time. The observable is a confident claim — "branch MOVED",
"base NOT current main" — posted on the board against a branch that never moved. It recurs because
checking `head[:12]` in one place and quoting an 10-char sha in another looks harmless.

- When a `.py`-in-heredoc check is writing a decision, print the two values and their lengths next
to the verdict (`print(a, len(a), b, len(b))`) before the branch executes.
- Never derive "did it move" from a `!=` between differently-normalised values: prefixes, uppercase
  vs lowercase, `abc1234` vs full sha. Normalise both first (`x.lower()[:10]`), then compare.
- A false "moved"/"drifted" verdict is not cosmetic: it can dispatch a lane to rebase a branch that
  is already current, or contradict a lane's correct report.
- **A guarded write that silently produces NO output is THIS bug, not an API failure.** When the post
  is wrapped in `if sha == baseline: post(...)` and the call prints nothing, the first hypothesis is a
  mismatched-length comparison — not a dead endpoint, rate limit, or bad token. Print the compared pair
  with both lengths (`print(repr(a), len(a), repr(b), len(b))`) in the SAME call before re-deriving any
  state; re-reading the API to "find out why the post failed" burns the call that would have shown the
  10-vs-8 mismatch. Repeatedly diagnosing the same silent no-op as "the sha-length bug" post-hoc is the
  signal to stop hand-writing slices and start printing the pair.
- **Compare against a value fetched in the SAME call, not a sha literal carried from an earlier turn.**
  An inline literal is a second normalisation surface (someone shortened it, or you pasted a display
  form). Bind the baseline from the wire in the same invocation
  (`base = api(...)['base']['sha']; if head != base: ...`, full-oid) and only fall back to a recorded
  tip when the call itself returned it.

## 2. A wrong claim already on the wire gets a superseding CORRECTION

Do not delete, do not silently edit, do not append an "UPDATE:" to the same comment.

1. Post a new comment naming the superseded comment id, the exact string you asserted, and the
   measured fact — plus the reason (mismatched-length comparison, stamp read from the wrong side).
2. Re-verify the correction itself with a direct-ID GET and quote `id`, issue, `created_at`, body
   `len` in your record.
3. Keep the *original* claim visible. A record that concedes its own overreach is trustworthy; one
   that quietly rewrites history is indistinguishable from a claim that was never measured.

Correcting yourself the same pass is a PASS, not a failure — but the third occurrence of the *same*
mechanical bug in one session is a signal to move the check into a printed comparison (see §1)
rather than to keep hand-writing slices.

## 3. When a verification gate demands "fresh work" and the board has not moved

If a verify step refuses because it wants a task-relative change and you have just measured that
nothing changed (frozen tips, no new comments, no new runs, same conclusion), the answer is a
**genuinely unmeasured fact**, never a fabricated delta and never a duplicate nudge:

- Read a primary source you have only ever seen second-hand: the issue body's own
  `## Acceptance criteria` section, the recipe/gate source at `origin/main` (`git show origin/main:<path>`),
  the run's job-level census, a base sha confirmed on the API.
- Correlating two already-known facts at a new angle counts, provided you re-measure both before
  posting (e.g. a failed witness run's `head_sha` against the head a lane cites as proven —
  "unproven at the very head its sibling ACs bless" is a new finding, not a restatement).
- Quote acceptance criteria **verbatim from the issue body** in the dispatch. A requirement relayed
  through a lane's DM paraphrase loses the exact wording that decides whether a run witnesses it.
- If after measuring there is genuinely nothing new, say so and stop posting. Idle posting on an
  unmoved board is the failure mode; a written reason nothing could move is the correct output.
