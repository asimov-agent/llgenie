# A standing rule is stated, not quoted (issue #922)

**Issue:** [#922](https://github.com/asimov-agent/llgenie/issues/922) · **PR:**
[#944](https://github.com/asimov-agent/llgenie/pull/944), stacked on
[#919](https://github.com/asimov-agent/llgenie/pull/919) (`feat/agent-profile-implementer-skill`)
because the gate and the `agents/` tree do not exist on `main` yet.

## The defect, reproduced before it was fixed

`scripts/check_agent_profiles.py` proved a declared standing rule with
`re.compile(r"never\s+merge", re.I).search(text)` — anywhere in the file. A SOUL that **quotes** the
owner's instruction therefore satisfied the gate for the rule it quoted. Measured on a real tree
(planner SOUL + the architect lane's quotation, statement deleted):

```
[old gate] exit=0   <-- the words appear, so it passes
[new gate] exit=1
[check-agent-profiles] FAIL standing-rule-quoted: agents/llgenie-planner/SOUL.md: mentions
`never-merge` only inside a quotation … (issue #922)
```

Restoring the statement returns both gates to exit 0. So the guard was seen to catch the bug and to
release the fixed tree — a guard only ever run on the fixed tree has demonstrated nothing.

## Decisions

- **Strip quoted spans, then match.** `stated_text()` removes the three shapes a quotation takes in
  this tree — a fenced block, a blockquote line, a `"…"` span — and the rule is matched against what
  remains. A rule present in the raw text but absent from the stated text is its own finding,
  `standing-rule-quoted`, so a deleted statement and a quoted one do not print the same message.
- **Measured against every real SOUL before it was chosen.** All seven committed SOULs keep every
  rule they state after the strip; the one file that states *and* quotes (#921's architect SOUL,
  3 raw matches) keeps its statement and loses its quotation (2 matches). No legitimate statement
  lives in a fence, a blockquote line or a `"…"` span.
- **Single quotes are not a quotation marker.** `owner's` opens a span that would swallow the rest of
  the sentence; a stripper that deletes a legitimately stated rule is worse than the bug.
- **Rejected:** requiring an imperative form (the two gated SOULs state the rule as `**Never merge, …**`
  and `**You never merge, …**` — an imperative-only rule reds a correct file); requiring an exact
  section heading (needs a heading added to seven SOULs and collides with #921, which edits the same
  files — the wrong shape for a three-line defect).
- **`rules: []` is now reported `UNPROTECTED`**, in `check` and `report`, and is deliberately not a
  failure: five of the seven committed profiles declare no rule, and a permanently red gate is a
  filtered gate. What it may not do is read as a pass.

## Status

`make check-agent-profiles` exits 0 on the unmodified tree (naming the five unprotected profiles);
`tests/test_agent_profiles.py` carries one rejection per shape — quoting-only in a span, a fence and a
blockquote; stating-only; stating-and-quoting; and `rules: []` reported. The gate lives only on #919's
open tree, so this change is stacked on that branch, not on `main`.
