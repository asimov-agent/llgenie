# quoted-rule-statement — proposal

Issue: [#922](https://github.com/asimov-agent/llgenie/issues/922)

## Why

`scripts/check_agent_profiles.py` proves a declared standing rule is **present in the file** by
matching a regex — `never\s+merge` — *anywhere* in the text. A SOUL that **quotes** the rule
therefore satisfies it without stating it:

```
this lane, verbatim:
  the owner's instruction to this profile is "Never merge PRs (no squash/auto-merge/push to main)…"
→ re.compile(r"never\s+merge", re.I).search(text) is True → gate GREEN
```

Measured on the tree that carries this gate: deleting the statement from a SOUL whose lane section
quotes the owner's instruction left the gate printing `OK` and exiting **0**. Only deleting both
occurrences — the statement *and* the quotation — reddened it. So "the rule is present" currently
means "the words appear", not "the agent is instructed to follow them", and that is the worst
possible false negative in the one file whose whole purpose is to make deleting a rule loud.

## What Changes

- **`scripts/check_agent_profiles.py`** reads a SOUL for what it *instructs*, not for every string
  it contains. `stated_text()` removes the three shapes a quotation takes in this tree — a fenced
  code block, a blockquote line, and a `"…"` span — and the standing-rule check matches only what
  remains. A rule found in the raw text but not in the stated text is a **new, separately named
  finding** (`standing-rule-quoted`), so the failure says which defect it is instead of reporting
  the same message for a deleted rule and a quoted one.
- **Single quotes are deliberately NOT a quotation marker**, and that is a measured decision, not an
  omission: `owner's` opens a span that would swallow the rest of the sentence, and a stripper that
  deletes a legitimately stated rule is worse than the bug it fixes.
- **A profile whose manifest entry declares `rules: []` is reported `UNPROTECTED`**, in `check` and
  in `report`. It is not a failure — five of the seven committed profiles legitimately declare no
  rule yet — but it is no longer a silent green: an entry that gates nothing must never read as an
  entry that passed.
- **`tests/test_agent_profiles.py`** gains one case per shape: quoting-only fails (fenced,
  blockquote and `"…"`), stating-only passes, **stating *and* quoting passes** (the live shape of
  the architect SOUL in #921 — a naive "fail anything inside quotes" would red a correct file), and
  `rules: []` is reported unprotected.
- `make check-agent-profiles`'s help line and `docs/BOTS.md`'s list of what the gate fails on now
  describe the statement/quotation distinction, so the claim and the measurement agree.

## Not covered

- The canonical fleet block's content — #873 owns it; this change touches only how a *declared*
  standing rule is matched.
- The `live-longer` / shrink comparison — a different axis (#791, #928).

## Why this mechanism and not the others

Three candidates were measured against all seven committed SOULs **before** one was chosen:

| candidate | verdict |
|---|---|
| **strip quoted spans, then match** (chosen) | no committed SOUL loses a statement; the architect SOUL's statement *and* quote survive correctly (3 raw matches → 2 stated) |
| require an imperative form | rejected: the two gated SOULs state the rule as `**Never merge, …**` and `**You never merge, …**` — an imperative-only rule reds a correct file |
| require an exact section heading | rejected for this change: it needs a heading added to seven SOULs and collides with #921, which is editing the same files; the strip is the smallest mechanism that distinguishes instruction from occurrence |
