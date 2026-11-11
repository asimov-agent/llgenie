# Durable rule capture: turn a merged fix into a class-level rule issue

A fix that merges proves an incident was handled; it does not, by itself, teach the
fleet's future gates. When a merged change encodes a **generalizable invariant** (not a
point patch), the durable deliverable is a NEW class-level issue that states the rule,
keyed to the merge commit — so the next gate/script refactors to the rule instead of
re-deriving the same incident. This is the concrete form of "a change to how the fleet
behaves arrives as an llgenie issue plus a PR": the ISSUE is the deliverable, the PR is
the vehicle.

## When a fix IS a rule (mint the issue)

Mint when the merged change's acceptance reduces to a rule that applies beyond the one
script — a property of gates/verifiers/assemblies, not a typo. Canonical shape: a
verdict/gate that reads a set and ALSO writes an artifact into that set must exclude its
own artifact from the set it judges (a self-referential judge that reds a green run). The
rule generalizes to any read-then-write-the-same-set gate; the point fix is one instance.

Do NOT mint for: a lint newline, a one-file constant bump, a missing `AGENTS:` body line —
those are correctly just fixed and merged. The test is "would another gate hit this same
shape?" — if yes, the rule is the artifact; if no, the merge is the artifact.

## Shape of the rule issue (six sections, AC grounded on the merged tip)

- **Problem** — the defect shape in mechanism terms, with the measured evidence (the run /
  job / head that proved it). This becomes the rule's negative example.
- **Why it matters** — the *class*: which other gates share the shape, what re-breaks it.
- **How we fix it** — state the RULE imperatively ("a gating judge must never count its own
  posted artifact back into the set it judges"), then the concrete mechanism the fix used.
- **Acceptance criteria** — three grounded boxes, not prose:
  1. the rule is PROVABLE on the merged tip — read it at the merge sha (`git show <sha>:<path>`),
     never the working tree, which lags `origin/main`;
  2. a CONTROL test proving the rule's converse still holds — the guard survives (a genuinely
     unknown failing row still reds; the fix excluded only its own artifact), so the rule is
     not "green by weakening the gate";
  3. the change→note / openspec cross-ref so the rule is discoverable (agent-wiki note +
     `docs/changes.d` row, via `references/change-note-gate.md`).
- **Technical** — name the **merge commit sha** so the rule traces to the proof, plus the
  files the fix touched and the reviewer/run ids that validated it.

## Keyed to the merge commit, never a reopen

- Name the merge sha in Technical; the rule's provenance is the commit that proved it.
- Do NOT reopen the merged PR (its diff is now `main`) and do NOT reopen the completed
  issue it closed. The rule issue is NEW, class-level titled ("<area>: durable rule — …"),
  and separate from the incident tracker.
- Verify the merged fix is actually green at the tip BEFORE minting: a rule captured over a
  red or unproven merge enshrines a defect as doctrine. Read the merge-tip check-set
  (`merged-over-red-gate.md`) first; AC1 above is that same proof, restated as the criterion.

## Route and boundaries

- The planner WRITES the rule issue; it never edits the rule text or `docs/VISION.md`
  itself — the doc/openspec capture ships in the owning lane's PR. Route the doc work to the
  documentation lane and state scope: capture the rule, do not re-implement the merged fix,
  do not rebase the merged branch.
- One issue per rule. If an existing class-level tracker already states the invariant, this
  is evidence accretion on it, not a fresh issue — dedupe first.

## An owner "capture this behavior" directive is this same pattern

When the owner says "save the skill/soul behavior to a new issue for this commit," they are
asking for exactly this: the merge commit's lesson restated as a class-level rule issue, not
a narrative of the incident. Lead with the RULE, ground the ACs on the merged tip, name the
sha, and route the doc capture. Do not summarize the session — extract the invariant.
