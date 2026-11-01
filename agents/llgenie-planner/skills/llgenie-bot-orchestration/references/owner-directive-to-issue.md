# Owner message → refined issue → dispatch

An owner message that arrives mid-pass and gives a *design directive* (terse, typo-heavy, or
correcting work that just merged) is not a draft and not a dispatch order to forward verbatim. It is
an instruction to be **grounded, disambiguated, refined into a six-section issue, and dispatched to
the owning lane**. Do not implement it yourself.

## Procedure

1. **Ground the interpretation against the tree first.** Before asking the owner anything, grep the
   machinery the directive touches: `Makefile` targets, the relevant `scripts/*.py`, the target
   lane's `SOUL.md`/`SKILL.md`, and any related open issues. An interpretation the tree does not
   support is a guess, not a reading.
2. **Disambiguate only the genuinely ambiguous parameters, in ONE `clarify` call.** Batch every
   independent question into a single call (up to ~5), recommended option FIRST in each (the UI
   marks it and auto-adds an Other row). Ask only what *changes the implementation shape* — what is
   actually verified, what the new thing replaces — never what the tree already answers, and never
   cosmetics. If the wording is clear enough to act on, act; do not ask for permission to proceed.
3. **Refine into the six-section shape**, folding each answer in:
   Summary / Acceptance criteria / Out of scope / Evidence / Notes for the implementer. The owner's
   own words go in **Evidence**, quoted verbatim — the quote is the clearest statement of intent.
   Keep acceptance criteria concrete and checkable (a real run's output, a green run id at head).
4. **File, label, claim, dispatch.** `gh issue create --body-file`, `--add-label agent:implement`,
   a `bot-claim:` comment naming the owning lane and the branch, then `message_agent` to that lane
   telling it plainly it *is* the bot the directive names. Report the issue number back.

## Pitfalls

- **Typo-heavy phrasing is an interpretation task, not a transcription task.** Parse the intent
  (e.g. "hiost ci est wiring" = "host CI test wiring"), confirm it against the tree, and write the
  refined issue in clean prose — never mirror the typos into the issue or the dispatch.
- **A directive that "corrects the just-merged approach" is a NEW issue with its own branch, not a
  reopen.** The merged PR's diff is now `main`; file a new issue that names what it replaces and
  states the relationship explicitly (e.g. "the command IS the caller; `check-wiring` still fails an
  unwired script"). Never reopen or rebase the merged PR.
- **Ask about the parameters that flip the design, not ones you can decide.** A wrong read of a
  single parameter burns the whole lane's run and produces an unreviewable PR — that is the cost the
  clarify call is buying down. But a clarify that asks three cosmetic questions wastes the owner's
  time; pre-decide the low-stakes ones.
- **Carry the standing constraints into the acceptance criteria even when the owner omits them:**
  subset-not-exact-list (`expected <= set(actual)`) for any manifest/roster, a gate that must still
  RED on a directly-attempted failure rather than be silenced by a roster note, preflight off a fresh
  `origin/main` sha, and never merge/push to `main`.
- **Name the two consumers when a directive says "the lane and also the pipeline's last step".**
  A directive can point at one make command used by both the host lane and a CI workflow's final
  step; spell out both in the issue so the implementer knows the command is shared, not lane-only.
