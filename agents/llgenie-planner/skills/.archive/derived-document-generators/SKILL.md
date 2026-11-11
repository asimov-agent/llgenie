---
name: derived-document-generators
description: "Use when changing a generated README/index or its gate."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [generator, readme, validator, markdown-tables, scope-gates]
    related_skills: [pr-landing-on-moving-master, github]
---

# Changing a generated document (and the validator that gates it)

## When to Use

A repo whose published document (README, index, catalog, dashboard page) is DERIVED
from a data store by a render function, with a validator that re-renders or re-derives
the same thing and fails on drift. The task is: change what a section shows, add a
section, move a generated section into another document, split one bloated document into
an audience-appropriate set, or change the derivation behind it — without breaking the
gate, the sort, or the tests that read the rendered text.

Related: `references/document-splits.md` — splitting one document into a user guide plus
reference pages and a change index, moving every writer with it.
Related: `references/depinning-data-coupled-tests.md` — rewriting a suite that pins the previous
store's rows (triage by cause, the one-invariant-per-shape table: derive a frozen list, call the product's
fit function, accept either STATED figure and prove the field hermetically, monotonicity instead of a
ladder, rewrite the existing fixture that encoded the removed rule, and regenerate committed derived
fixtures from the committed store).

## Procedure

1. **Ask which layer the change belongs to.** Score/selection bug → the derivation
   function (one function both the renderer and the validator call). Presentation only →
   the render section. Never fix a ranking problem by sorting the table in the template.
2. **Make the derivation ONE function** and call it from both the renderer and the
   validator. A second copy of the rule in the validator is how "the table is right but
   the gate says otherwise" happens.
3. **Render, then read the actual output** (`--render-only`/`--dry-run` to stdout or a
   temp file) before touching any test: the row shape you emit is what the validator and
   the existing tests parse.
4. **Regenerate the store-adjacent derived fields** when the derivation changed (a stored
   `speed_bonus` / `trend_score` / cache computed by the same gate). A render-only pass
   leaves the store holding values the new code would never produce, and the ranking
   validator then fails on the very row you fixed. Recompute with the repo's own merge/
   regenerate target rather than editing numbers.
5. **Add the validator check in the same change**, registered under a stage that a make
   target CI runs; then run the fast gates (`lint`, the doc/architecture check, the
   openspec-equivalent) before the full suite.
6. **Prove the gate fails on the old shape**, not just that it passes on the new one:
   run the REAL validator over a temp copy of the document with one row dropped and one
   number edited, and assert both red. Point the validator at the temp file by reassigning
   its module-level path — never by stubbing the logic.

## Pitfalls

- **A second table with the same row shape re-points every existing test.** Tests find a
  row with `next(ln for ln in md.split("\n") if ln.startswith("| [**Name**]"))`; the
  moment you render another table above it that emits the same shape, those lookups return
  YOUR row and assert on the wrong columns (`IndexError: list index out of range` for a
  4-column table, or a "cell is not the best" failure). Fix every such lookup by scoping
  it to the section (`md.split("## <heading>", 1)[-1]`) or to a line index AFTER the
  section heading — and prefer the section heading over a `startswith` search whenever the
  document has more than one table of rows.
- **A scope/taxonomy gate that enumerates SKUs misses a CLASS wording.** A gate listing
  concrete product families (`b300`, `h100`, `mi300`, …) still admits a row whose hardware
  field says `datacenter GPUs, 512 concurrent requests` — no family token to match, and if
  the size field is absent the "unknown ⇒ allow" fallback lets it through. Grep the store
  for how the field is actually phrased and add a class matcher (regex over the wording)
  beside the SKU list; keep the fallback for genuinely unknown values but prove the class
  shape is refused by testing that exact stored string.
- **A fixture that hand-sets derived fields is recomputed away.** If the sort pass rebuilds
  the score from post-level data, a fixture's `buzz_7d: 10` becomes 0 and every expectation
  disagrees with the render. Build expectations from the store AFTER the real sort pass
  (`s["models"] = sort_models(s["models"], as_of)`), and give fixtures real dated source
  rows so the recompute has something to count.
- **A help/usage `@echo "…"` string cannot be continued onto a second recipe line.** Each recipe line is
  its own shell invocation, so splitting one quoted echo to keep the help block readable leaves the first
  line with an unterminated quote (`/bin/bash: -c: line 1: unexpected EOF while looking for matching`, and
  `make help` exits 2 while the target itself still parses). Keep each `@echo "…"` on ONE line (or add a
  separate `@echo` per message with its own quotes), and after editing a help/`.PHONY` block run
  `make help` and check its status before the suite.
- **Aggregate/bulk figures are not comparable to single-user ones.** A throughput figure
  measured as `AGGREGATE … 512 concurrent requests` is a different quantity from a
  single-stream decode, even on identical hardware. Keep it in the raw table (never delete
  data) but exclude it from anything that ranks or recommends, and say which cell a reader
  can actually reproduce.
- **Report-only vs failing checks.** When a dimension is legitimately unmeasurable, add it
  as a printed report line (coverage, gaps, vocabulary) instead of a failing gate — a gate
  that fails for data nobody can collect gets disabled, and then it guards nothing.
- **A gate that re-derives the artifact from a LIVE source cannot byte-compare the artifact.** When the
  generator queries an external service for its rows (a search ranked by a moving metric, a repo listing),
  the same repository input regenerates the same CONTENT in a different ORDER as that metric moves, and a
  newly published upstream row appears as an addition. A byte comparison then reds the gate for every PR on
  the repo — measured: a catalog gate failed on the base branch itself, before the test stage, because one
  cell's 14 plans came back reordered. Split the comparison by who owns the difference: FAIL on a row the
  committed artifact HAS and the generator no longer produces (a row gone, its repo/files/size/link
  changed, an arch list changed, or the artifact was rendered for a different store version), and PRINT a
  `NOTE:` for what the source re-reads (a reorder, a newly published row) with exit 0 — the same
  report-not-fail rule the store's additive-loss guard uses. Keep the failure provable: drop one committed
  row and watch the gate exit non-zero. Publish the rule in the target's help text and the doc page, so the
  next reader knows "differs" no longer means "one byte".

  **Changing a checker's verdict also invalidates the test that asserted the OLD verdict, and that test
  lives somewhere else.** Grep the tree for the gate's target name and for the checker's public function
  (`grep -rn "check-<artifact>\|compare(" tests/`) before you push: measured, an edge-case module for the
  generator carried `test_check_fails_when_generated_differs_from_committed` ("one extra row fails"), which
  red the whole `ci-unit` job on the fix that made additions a NOTE. SPLIT such a test into the two
  directions the rule now has (a lost/changed row still fails; an addition is a NOTE naming the plan) —
  never delete it, because the "a stale artifact is caught" intent must keep a test. Updating it is not
  loosening: the removed assertion pinned behaviour the fix deliberately reversed.

  **Then run the command that PRINTS the decision, not only the gate that computes it.** A list gated on
  the measured minimum kept printing the display label in its own column, so the header read "every model
  whose VRAM fits this card (16 GB)" directly above a row reading `48GB` — the suite pinned the rows and
  never the column, so every test stayed green while the output contradicted itself. After changing the
  field a gate reads, print one screen of the user-facing command and compare each printed figure with the
  header's claim; give the printer a helper that returns the SAME field the gate used (`vram_label(model)`
  beside `fits(model, gb)`), and lock it with a positional test that also asserts the artifact really has
  rows where the two fields differ — otherwise the test passes because they are equal everywhere.
- **A validator whose exit status is discarded can never fail.** A script whose `main()` `return`s
  a status and whose `__main__` block calls `main()` bare always exits 0: the gate prints `FAIL:`
  plus its diff, the make target is green, and a stale artifact ships for weeks behind it. Fix
  `raise SystemExit(main())`, and prove the gate reds by making the artifact stale and reading the
  PROCESS status (`make <gate>; echo $?` — never through `| tail`, which returns the pipe's status),
  not by reading the message. Guard the class with an `ast` walk over `scripts/*.py`: for any
  `__main__` that calls `main()` bare, `main()` must not `return` a value; a `main()` that does the
  work and returns `None` is fine and must stay green. **A check you just made able to fail obliges you
  to repair what it was hiding in the SAME change** — regenerate the stale artifact with the committed
  generator (never hand-edit it) — or the newly-real gate reds `ci-unit` on your PR and blocks the whole
  queue for a defect you discovered rather than introduced.
- **A live liveness check can manufacture the loss it reports.** Attaching the API bearer token to
  the provider's HTML page is what makes the page look dead: measured, the same URL answered `200`
  without the token and `429` with it (“we had to rate limit your IP … pass a token”), so every link
  in the freshly synced table read as a dead link. Ask the provider's identity endpoint
  (`/api/models/<org>/<repo>`) with the token, and route every link through the repo's single retry
  seam so a 429/5xx waits instead of becoming a verdict, while a 401/403/404 stays definitive on the
  first attempt. When a refresh grows the link count (15 → 90), the same check that worked on the old
  table trips the limit on the new one — that is the check's problem, not the data's.

- **Parse an upstream/render markdown table BY COLUMN NAME, never by "the cell that looks like a value".** A published table gets restyled upstream (`16GB` → `**12GB**<br><sub>stated by the source · …</sub>`), and a parser shaped `next(c for c in cells if re.fullmatch(r"\d+GB|\d+|CPU", c))` then dies with `StopIteration` — which reads exactly like a data failure and sends you to the store instead of the parser. Read the header row, index the column by its NAME (`["VRAM", "Status", …].index("VRAM")`), take the cell text before `<br>`, strip `*`/whitespace, then parse. That survives a restyle AND a column reorder, and one case going green while the rest stay red is the signal that only the parser was stale.

- **The change must not carry the store it consumed.** A branch that started life by syncing in a
  worktree sweeps `data/**` and the derived fixtures into the first `git add -A`, so the review diff is
  16k lines of upstream data under a commit whose message is about tests. Recover with
  `git reset --soft origin/main` then `git restore --staged data/ tests/fixtures/<derived>.json`, commit
  only code/tests, and leave the synced files dirty in the working tree — that is what keeps the local
  runs on the NEW store while the branch stays clean. Prove it: `git show --name-only --format="" HEAD |
  grep -c '^data/'` must print 0.

  **Then put the committed store BACK before you believe a green run.** Those dirty files are exactly
  what every later local run reads, and CI reads the COMMITTED one, so "green locally" measures a store
  nobody else has: measured, a suite green on a locally synced 112-row store came back with 129 reds on
  the branch's own committed store, and the PR body's numbers were all from the local one. The sequence
  that costs nothing: copy the synced files aside (`tar czf <scratch>/localdata.tgz data/ <derived fixtures>`),
  `git checkout -- data/`, re-render every committed derived fixture from the committed store
  (`make <render target>`; its `--check` must then pass), run the suite there — and restore the tarball
  only if you still need the new store. Two stores, two runs, and the branch's numbers come from the
  second one.

## A vendored store ships with the contract it is written against

When the document is derived from a store that a scheduled job replaces WHOLESALE from an external
repo, the store's own schema/contract is a second artifact that must be vendored in the same write.
Leaving it behind means a contract edit arrives as a giant data diff instead of a diff of the
contract, and the consumer's hand-kept shape check silently disagrees with what upstream enforces.

- **Vendor the contract byte for byte next to the store** (the machine-readable schema AND its prose
twin, if both exist), written only when it changes, so the sync PR shows the contract change itself.
- **Read the rules FROM the vendored schema; never restate them in Python.** Pull `required` (top
  level, per row, per nested item), `pattern`, `enum` and `minItems` out of the schema at check time.
  A contract edit that adds a required key is then honoured without touching the consumer — the
  property a hardcoded key list can never have. Name the offending row index + id in every refusal.
- **Check first, dependency second.** A full JSON-Schema engine is a new package, and in a repo whose
  CI image is pinned by a Dockerfile+lockfile HASH, adding one changes the image tag: a fork-head
  `pull_request` run cannot publish packages to the registry, so `ci-unit` finds no image to pull and
  the PR reds for a reason that is not the code. Enforce the subset the contract actually uses
  (required/pattern/enum/minItems) data-driven and say plainly in the issue which keyword classes
  remain unenforced. Do not hand-roll a validator that ignores the vendored schema — that is the
  defect you are fixing.
- **Put the contract check where the LANDED artifact is read, not inside the writer.** A `sync()` that
  rejects a contract violation before writing forces every unit-test fixture through the full schema,
  and those fixtures are deliberately minimal. Validate in the gate (`check()`); the writer only
  vendors.
- **A normaliser added later can collide with an additive-loss guard.** If the writer rewrites a field
  to a vocabulary it can act on (dropping display text that was never a format/label/unit), the guard
  that compares old vs new reads every drop as data loss and freezes the sync at its FIRST normalised
  landing. A label outside the actionable vocabulary is not data — the guard must filter both sides by
  that vocabulary, and it must IMPORT the vocabulary from the normaliser so widening one widens the
  other in the same edit. A real vocabulary member that disappears is still a loss.
- **Match a vocabulary member by its letters and digits, never by its punctuation.** Upstream spells one
  format several ways (`LiteRT-LM`, `litertlm`, `MLX-Safetensors`), and exact equality reads the
  hyphenated spelling as display text: the normaliser drops a REAL format and restates the fallback
  (`GGUF`) for a repo that serves none, so the plan points at a file that cannot exist. Build the
  comparison key with `re.sub(r"[^a-z0-9]", "", name.lower())` and keep the vocabulary's own spelling in
  the store; a genuinely non-format value (`LLM (MoE)`) still falls out, because it matches no member.
- **"Does the bot update X?" is answered by the writer, not the workflow file.** Run the sync into a
  throwaway worktree and read `git status --short` — that is the exact set of files it writes. A workflow
  comment or an AGENTS.md paragraph describes intent and drifts; a file the script never `fetch`es is not
  updated by it no matter what the docs list, and telling the user otherwise is the error you get asked
  about next. Quote the file set as a diff stat (`data/models.json | 16011 +++---`, `+contract`) rather
  than a sentence.
- **"Will I get the latest store?" has TWO answers — say both.** The writer produces it, and the scheduled
  job may not publish it: the files exist in the working tree/runner while `main` keeps the old version
  because a later gate reds and the PR step is skipped. Answer in that shape ("run it yourself: yes, these
  three files; the bot: produces and validates them but does not land them, because <gate>"). And when the
  writer normalises (drops display text, restates a vocabulary), the file it writes is NOT byte-identical
  to upstream even though the published document beside it is verbatim — state the transform, or the user
  diffs two files and thinks the sync corrupted the store.
- **Verify the collision on the real store, in the job's order, with an A/B.** Sync, then run the
  guard: report the old finding count and the new one over the SAME file (`10 LOSS, exit 1` vs
  `OK: additive only`). A guard change is only proven against the freshly synced store, never against
  the committed one the repo already passes.

## The upstream document is an ORACLE — a red acceptance test may be telling you the PRODUCT is wrong

When an acceptance test asserts a relation between the rows the code emits and the upstream published
document (`rows == the upstream list's models whose <column> fits, in upstream order`), a failure on a
freshly synced store is not automatically a stale golden. Compare the two sides before touching the test:

```python
# the upstream document's published column vs the store field the code actually gates on
for row in store["models"]:
    print(row["id"], published_column[row["name"]], row["coarse_label"], row["measured_minimum"],
          row["name"] in offered_set)
```

- **A disagreement is the finding, not a fixture to update.** Measured case: the published `VRAM` column
  and the store's coarse `vram_tier` label disagreed on 10 of 112 rows, so the gate emitted both false
  negatives (a model the source says fits, absent) and false positives (a model the source says does not
  fit, present). The measured minimum (`vram_min`) agreed with the published column in every disagreeing
  row — the label was the wrong field.
- **Then STOP and record the measurement on the owning issue** (a comment with the table and the row
  counts) until the field question is decided — the acceptance test stays red rather than being
  re-derived against the field it exists to catch, which makes the gate green while the product still
  answers wrong.
- **Once the field is decided, the change is one commit and the ledger is the report.** Gating on the
  measured minimum with the coarse label as a fallback cleared 33 of the 130 reds in one file, 21 in
  another, 4 in a third and 1 in a fourth — measure `pytest tests/<file>.py -q` before and after and
  quote both counts, because the residue (a golden table of exact filenames, a handful of prompt/`--select`
  cases, one genuine product rule) is what the next change is scoped to.
- **Triage by CAUSE before rewriting a single test**, and the rewrite recipes per test shape live in
  `references/depinning-data-coupled-tests.md` (invariant table, the ±1 GB rounding tolerance, the
  "assert the other field disagrees or the test proves nothing" rule, the harness-vs-CLI argument diff).
- When several parametrized files fail from one such field, report the per-file counts and name the
  shared cause; a re-pin of 100 goldens is the wrong deliverable and a reviewer cannot see which of them
  encoded a rule and which encoded today's data.

## After a wholesale sync, open ONE change issue

A job that replaces the store wholesale usually dies at one of its own gates, and then its PR step is
skipped — so the store never lands and nobody learns what upstream changed. The change list is the input
every follow-up needs (“re-derive the tests against the new store”), and it can be produced for free in
the runner, where old and new data are both on disk.

- **Derive the report deterministically.** Compare the committed copies (`git show HEAD:<path>`) of the
  store, its vendored contract, the upstream document and each derived table with the working tree's:
  version id old → new, row/entity counts, added / removed / renamed ids (cap each list and point at the
  diff), members new to the registry, vocabulary values seen, contract deltas (required keys, enums),
  document rows changed, and the derived-table counts.
- **ONE issue, keyed by a hidden marker holding the version id** (`<!-- sync-changes: <generated_utc> -->`).
  A re-run for the same version must EDIT that issue, never file a second. Give its body a checklist naming
  the owning issue for each class of follow-up (re-derive goldens, decide a new member, teach the contract
  reader, run the job's gates).
- **Idempotency is per VERSION, so a fresh dispatch that files a NEW issue is correct, not a dup.** The
  upstream store re-publishes while you work, so your local run and a later job run legitimately carry
  different version ids and must each get their own issue. Prove dedupe only by running twice over the
  SAME store (`open` twice → `updated #N`); never by comparing two issues filed hours apart and calling
  one a leak.
- **Set the routing label explicitly AFTER create, then verify it — `--label` on create can be dropped
  silently.** Measured: `gh issue create --label agent:implement` on the runner path exited 0, printed the
  issue URL, and produced an issue with ZERO labels (no `labeled`/`unlabeled` timeline event at all), while
  the same call from a host carried the label. The bots that pick work up key on that label, so an
  unlabelled issue is routed to nobody while every step reads green. `POST repos/<repo>/issues/<n>/labels`
  and read the labels back; raise when they are missing — "the issue exists" and "the issue is routed" are
  two facts, and only the second one gets acted on.
- **Run it with `if: always()` on a changed store.** The analysis is most valuable exactly when a gate
  reds — that is when the store cannot land and the next change is written from it.
- **No model in the path.** A summariser over a 20k-line diff cannot be re-run to the same answer; the
  diff is the artefact and the issue is its index, while the judgement stays with whoever picks it up.
- **Test it hermetically and verify it live once.** Build two stores/contracts/documents in a temp dir
  and drive `compare()`/`render()`; replace the `gh` runner function (the external system) with a
  recorder and assert: update-not-duplicate for a repeated marker, exactly one create carrying the label,
  and `--dry` mutating nothing. Then file it for real against the repo, run again, and confirm the SAME
  issue number comes back.

## Report the slice you shipped — and the part you deliberately did NOT

A request that describes a pipeline ("sync the store → open an issue about the change → update the
contract, the tests and the logic") is almost never one change, and the report decides whether the user
trusts it. Blurring the halves is what produces the follow-ups "did you implement it?" and "so it works
now?".

- **Name both halves in the SAME message, one sentence each**: what landed, and what is left to the agent
  or blocked on a decision ("the change-issue step is landed and idempotent; the contract/test/logic
  rewrite is the agent's work on that issue, and it is blocked on the fit-rule decision"). Say it up front,
  not after being asked — a capability announced without its gap reads as an overclaim.
- **Never call a pipeline "working" when only its producer is.** A sync that writes and validates every
  artifact but cannot publish them is "writes correctly, does not land": say that, and name the gate that
  stops it with its measured count ("`test-unit` 130 failed / 14707 passed, PR step skipped"), never
  "CI is red".
- **When the user asks for the PR while a gate is still red, open it with the honest ledger.** Do not wait
  for a green `test-unit` to create the PR and do not dress the residue as finished: push, open the PR with
  the per-file before/after table, name the remaining work as its own linked items, and say in the same
  message which files are still uncommitted or in flight. The PR is a checkpoint a reviewer can read; a
  silent wait is what produces "so does it work now?".
- **Do not automate the judgement step to turn the answer into "yes".** Rewriting ranking tests or the
  contract to match new upstream data is the patch-the-test failure; the deliverable is the issue that
  describes the change plus a reviewed rewrite behind it.
- **A measured number goes into a body, a doc or a wiki note ONLY as a copy of a command's output.**
  Run the check, paste its line, then re-read the sentence against it. Two ways this goes wrong, both
  silent: the number is inherited from the request or the commit log instead of measured (a store's
  `generated_utc` was "obviously" the new one and was the older committed one), and the aggregation
  SHAPE changes when you fix the rendering (92 per-case findings that the first 60 rows showed as one
  model were three).
- **When the figure changes shape, fix EVERY artifact in the same commit.** The same claim lives in the
  issue body, the proposal, the docs page, the wiki note and the `tasks.md` line; correcting one leaves
  four contradictions that the next reader finds and you re-apologise for. Grep the number's neighbours
  (`grep -rn "<count> findings\|generated_utc" openspec/ docs/ agent-wiki/`) after any correction.

## The next leg after the sync: a review bot on the GREEN PR

Once the sync can open its PR, the missing work item is the one a reviewer would write by hand: at each
card size the product sells, does the list list anything, and does each row name the fastest server that
fits? Two rules make that leg sane (the wiring checklist lives in the `hermes-headless-ci` skill,
reference `bot-leg-wiring.md`):

- **The precondition is the PR's own check buckets** — an OPEN sync PR with every bucket `pass`; a
  missing/failed/pending PR is `skip` with the reason and spends nothing. Reviewing a store that cannot
  land is noise.
- **The ranking rule is the product's, not the reviewer's.** Prefer "the named server is not the fastest
  of its own rank class" over a raw maximum, and say which evidence class each figure came from: a
  48 GB-card figure alongside a 16 GB card is the proven-class rule working, not a defect. Findings that
  cannot occur under a correct sort (`slower-than-class`) are still worth emitting — they are the
  regression detector — so give the checker an injectable `ranker` and prove the detector fires by
  handing it an order that is wrong; the real function is never stubbed.

## Verification

- **A "verify this gate passes" request is answered by proving it can FAIL first.** Make the artifact
  stale (drop a row, edit a number), run the gate, and read the PROCESS status (`make <gate>; echo $?`,
  never through a pipe). A gate never seen red is unproven, and one that prints `FAIL:` while exiting 0 is
  the same class as a discarded `main()` status.
- Render the shipped store and diff the document against what the generator produces
  (`make <repo render target>` or the `--render-only` path) — the repo's own gate does this
  and a hand-edited document must not pass it.
- Run the new test module, the validator on the shipped tree, and the fast gates; then the
  full suite.
- **Prove the new gate/fixture red on the BASE, without disturbing your branch:** add a detached
  worktree at the base tip (`git worktree add --detach ../wt-<name> origin/main`), copy in ONLY the
  new/edited test file and any new data fixtures (`tests/test_x.py`, the vendored schema/store it
  reads), and run that file there. Tests that reference the new seam fail with `AttributeError`/
  import errors — that is the proof. `git stash` is repo-wide across worktrees and will grab another
  agent's entry; never use it to falsify a change.
