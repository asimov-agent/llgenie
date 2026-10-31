# Reading a verdict: green, red, and the markers in between

A check result is a claim like any other. These are the shapes that mislead most often, and the field that settles each.

## A red is not always a complaint about the change

Four red tests reported as "symptoms of a defect" included one that was **doing its job** — a duplicate-rule gate
catching the duplicate that a verbatim relocation is exactly the operation likely to create. The lane had the file and
line and still read it only as a symptom.

- Before summarising a red set, read **which assertion fired**, not just which test failed. Ask: does this assertion
exist to protect the tree from this change, or to complain that the change is wrong? A guard that fires is the change's
safety check, and the remedy is a better change, not a waived test.
- A file or line number is not a diagnosis. `test_x.py:69 AssertionError` names where the check lives, never whether the
  expectation or the implementation is the wrong side.

## A marker must be able to fail

An `xfail` (or any skip/marker) that cannot fail the build is an assertion with no verdict, and it outlives the defect it
documents: when the underlying fix lands, the suite stays green and nobody removes the marker.

```python
@pytest.mark.xfail(reason="… tracked as #n; close condition: <observable>", strict=True)  # an xpass REDS
```

- Legitimacy test for the marker itself, all four required: the expectation is unchanged against trunk; the branch
  behaves like trunk except for the intended change; the residue is a known defect with a tracked close condition; and
  the close condition is **observable** (a shape a test can assert, not "when someone gets to it").
- `strict=True` ties removal to the fix mechanically: the PR that fixes the defect makes the test xpass, which reds, which
  forces the marker's deletion in that same PR. `strict=False` is the vacuous pass in the marker direction.
- The same principle governs guards: a gate that can pass on an empty population proves nothing. Require a
  non-vacuity assertion (`assert checked > 0`) on every enumeration gate — the Dockerfile/manifest-shaped check that
  asserts how many items it inspected, not only that each inspected item was fine.

## Green is per-head and per-object; derived flags lag the object they describe

After any state change, re-read the object, never the derived flags on it:

```bash
gh pr view <n> --repo <o>/<r> --json state,mergedAt,mergeCommit        # the object
gh pr view <n> --repo <o>/<r> --json mergeable,mergeStateStatus       # computed, lags, may read UNKNOWN
```

- `mergeStateStatus: UNKNOWN` immediately after a squash-merge is a **recompute, not a state**; once closed, `mergeable`
  and `mergeStateStatus` describe nothing. The deciding fields are `state`, `mergedAt`, `mergeCommit.oid`.
- Same family: a merge/`mergeable` read that answers "would this diff apply" rather than "did it pass"; a CLI that
  resembles the gate (`check` vs `ratchet`, a docs CLI vs the test that asserts equality); a frozen `updated_at` read as
  "hung". In each case the cheap field answers a neighbouring question, in the reassuring direction.
- Quote a **completed** run at the head: `gh run view <id> --json status,conclusion,headSha`. `cancelled` is not a
  verdict and `fail` columns that report `cancelled` as failure mislead both ways.

## Two lanes agreeing on the same evidence is one source

Independent agreement is not corroboration when both parties read the same wrong field: two lanes both citing one
`check_docs rc=0` is one measurement counted twice, and a planner claim a second lane echoes is a claim about to be
acted on rather than a claim under review.

- Before treating a second concurring report as confirmation, ask **what command produced it**. Same command ⇒ same
  source ⇒ no additional evidence; only an execution that could have failed differently counts.
- The repair is to re-run the underlying measurement yourself, not to weigh two statements against each other.

## Board lines carry an expiry

Every row should be falsifiable when read:

- Quote the **head sha and the minute together**. A row with a head but no minute is a photograph of an unknown moment;
  a row with a minute but no head cannot be re-derived.
- Where the head could not be re-read in the turn that composes the line, write `pending at <hh:mmZ>` — **a fact with an
  expiry rather than a state word**. "Waiting"/"blocked"/"in flight" decay silently; `pending at 21:44Z` does not.
- Composing from a cached snapshot is normal; reporting without the snapshot's timestamp is what makes it read as
  current.
