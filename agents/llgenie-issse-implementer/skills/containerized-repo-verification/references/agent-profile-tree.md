# Keeping a host agent's SOUL and skills in the repo

Depth for the `agents/<profile>/` tree: what belongs in it, and the two ways a re-seed goes wrong.

## A re-seed must name the files it copies, never walk a profile home

A profile home (`~/.hermes/profiles/<p>/`) is a **runtime directory that happens to contain a rulebook** —
`SOUL.md` and `skills/`, but also `state.db` (tens of MB), `cache/`, `plugins/` with a nested `.git`, and the
entire installed skill library. `rglob("*")` over it copied **15,963 files** into `agents/<profile>/` in one
run; only the command's own output revealed it, and it was cleaned before committing.

- Copy an explicit allowlist (`SOUL.md`, `skills/<the profile's OWN skill>/…`) and print each file with its
  size, so a 73 MB `state.db` is obvious in the output rather than in the PR diff.
- Verify after: `git ls-tree -r <head> agents/<profile>` should be a handful of files, and
  `git ls-tree -r <head> | grep -cE 'state\.db|\.curator_backups|plugins/|cache/'` must be `0`.
- `git clean -fd <dir>` does **not** remove a directory holding a nested `.git`; clean with an explicit
  keep-list (`SOUL.md`, `skills`) and remove the rest by name.

## A replacement that is LARGER while dropping lines defeats every size guard

Comparing a lane's PR copy of a SOUL with its live profile by size passes the dangerous case: measured on
four lanes, the PR versions were 4,936 / 6,346 / 6,046 / 5,714 b against live 431 / 722 / 4,936 / 2,811 b —
**all larger, and all dropping live lines** (4 / 4 / 32 / 30 respectively). Size is the signal an operator
and a gate both read first, so a "bigger means newer" heuristic replaces a rulebook with different text and
reports success.

- The test is **set-of-lines**: every non-blank line the tree carries must appear in the live file, and the
  live file must not carry lines the tree lacks. Subset means prefix means truncation.
- Choose the **live** text for the tree, and let each lane land its rewrite as its own one-file PR where its
owner can defend the deletions.
- `manifest.json` is a **shared** file: N lanes each adding "one line" is N PRs editing the same JSON, and
  that is where a merge resolution drops a profile entry silently. Land the tree once with every entry, then
  a lane's follow-up touches only its own `SOUL.md` and, at most, its own entry's `rules` array.

## The write path needs an AGE guard, and the source time is a COMMIT, not an mtime

A live-vs-tree comparison is a read; `sync` is the write, and no read-time caveat can see a write it
already allowed. The live profile is a **moving reference** — its owner edits it while a PR is under
review — so a sync into a file edited after the source commit is a silent merge in the wrong direction.

- **Refuse when `mtime(live) > source_time(tree)` unless `--force`.** Name **both times**, both sizes and
the line count the overwrite would cost, say **would overwrite**, never say "verified", and write nothing.
- **The source time is `git log -1 --format=%ct -- <path>`, never the tree file's mtime.** A fresh clone
  sets every mtime to checkout time, so an mtime comparison says the tree is newer than any live file and
  the guard **silently disarms on exactly the checkout that runs the sync**. Fall back to mtime only for an
  untracked fixture, and pin it with a test that `utime`s a committed file into the future and asserts the
  source time does not move.
- **Negative control is mandatory**: a live file OLDER than the source commit must not be refused, or the
  guard is just a red gate. And the refusal must leave the file byte-unchanged — assert that too.
- `--force` must then say what it did: `overwrote a live file NEWER than the source commit by --force
  (live <t> vs source <t>)`, with `identical` absent from both paths.
- **Refuse the HARM, not the timestamp.** The mtime is a proxy for "someone else wrote this"; the harm is
  losing a line they wrote. Two cases must PASS, or the guard fires on its own previous write and the
  operator learns to pass `--force` — and then the one case that matters gets forced too: the bytes are
  already identical (the sync writes nothing), and every live line also appears in the tree (the write
  cannot drop one — the same set-of-lines test `shrinks()` uses, in the other direction). Measured:
  a refresh two minutes after the previous sync was refused for five files, three byte-identical and two
  where the live lines were a strict subset of the tree's.
- **Order the refusal by what the gate actually checked, and never name whose work it is.** First the mtime
  fact (`the live file was edited AFTER the tree copy was committed — live <t>, source commit <t>`), then —
  only when the content differs — the line count (`and the content differs: N live line(s) the tree lacks`),
  byte sizes, and the remediation. The tree has no ownership information, so a hard-pinned `of another
  lane's work` is a guess the harness has no right to make — it fires on a lane's own files when only the
  mtime moved, and redirects blame at the wrong owner. Assert the phrases in a test and negative-control it
  (restore the blame phrase → fail).
- **When you EDIT a tree copy of a live file, edit as an additive superset, never a replace.** The set-of-lines
  gate reads a replace of a live paragraph as *dropping* those lines — even when the tree copy is your own,
  the edit is deliberate, and the new text is better (measured: a two-line correction to an in-tree skill
  redded its own gate with `live-lines-missing`, 3 lines). Keep the live paragraph verbatim and append the
  corrected/re-measured text as its own additive paragraph, then confirm `live lines the tree lacks == 0`
  before the sync. A corrective replace is indistinguishable from a truncation to the gate.

**And compute "what changed" from a snapshot taken BEFORE the write.** Asking after the copy answers
"all of them" on every run — `replaced an existing file` computed post-copy is a property the instrument
never checked, inside the very file whose job is to refuse exactly that.

**Re-take the tree after EVERY live edit.** The live-longer finding only fires where live profiles exist,
so a tree that has not been re-seeded since the last edit to the live file is a prefix, and a reviewer who
merges it ships the truncation the guard refuses. `CHECK=1` must say `N file(s) … match byte for byte`
before the push, and the count is expected to grow as references are added.

## A copy cannot watch itself: the missing piece is a CALLER

Hand re-seeding holds for one push and then fails again within the hour, because the direction of staleness
is structural — the tree is a copy and the live file is what gets edited. Measured: a tree that went
byte-exact at three files was three files behind again after the next round of edits (`SKILL.md`
22,296 → 23,349 b, one reference 3,398 → 5,882 b, another 6,721 → 10,634 b). **The gate was right both
times; what was missing was a caller that runs where the live rulebooks exist**, since a runner has none.

So a live-comparison check is not finished until it has three parts:

- **A reading fix**: print the number of live comparisons (`live comparisons: N`), so a runner's green says
  "0 compared" instead of reading like "compared and clean".
- **A calling fix**: a named target a host can run on a timer (e.g. `make profile-drift`, plus `--only <key>`
  filtering **after** the findings are computed so a filter can narrow output but never hide a class).
- **A threshold that can be satisfied**: plain difference is *normal lag* — the live file is edited while a
  PR is open, so a target that reds on any difference is always red and teaches nothing. The defect is a
  tree that **lacks** live lines (subset/prefix, the shrink rule); report that as the failure and the rest
  as information.

**What the timer must NOT do is copy.** An automated re-seed is a `cp` in the destructive direction with no
reader: it overwrites a deliberate tree-side edit and reports success. Opening one deduped issue naming the
files is the whole job — the copy is a judgement the lane owns.

**While a copy is under review, freeze the source.** Editing the live file and re-seeding in the same window
recreates the drift before the next gate runs — two re-takes inside one hour went stale the same way, the
second after the branch was already armed. Either stop editing the live profile until the PR merges, or
accept that every push needs a re-take; say which in the commit so the reviewer does not have to discover it.

**Four states, not two, and only three are defects.** Truncated (the tree misses live lines → a sync DELETES
live behaviour), **diverged** (each side owns lines the other lacks → a sync destroys work on *both* sides),
missing (structural), and tree-ahead (the tree carries lines live lacks and misses none → a sync only ADDS,
so it is lag). A size comparison or a two-state "differs" test reports **diverged as nothing at all**, which
makes the most destructive state the invisible one — classify by subset relation in BOTH directions.

## Versioning a fleet rule into one lane: SOUL states it, skill uses it

A repo that keeps a canonical rule block (`agents/standing-rules.md`) and N lanes' `SOUL.md` copies will
re-issue that block with new numbered rules. Adding rule N to a lane is a repeatable procedure, and every
step below was a defect the first time it was skipped:

1. **Copy the rule from the FILE at commit time, not from the message that announced it.** The block is the
   authority; a chat summary drifts from it within the hour. Cite the rule and issue in the same line the
   block uses (`… (rule N of the fleet block, <issue>)`) so the next reader can diff the two.
2. **First person passes; paraphrase does not.** Rewriting `you` → `I` is expected in a SOUL. Dropping or
   softening a commitment is not: keep each clause the block asserts (file the issue, name the removal
   condition, remove the tag yourself, record the conclusion in the issue).
3. **The skill carries the procedure, the SOUL carries the constraint.** A skill loads only when its
   trigger matches, and a rule about holds or lanes is needed *before* the situation names itself — so the
   SOUL states the rule whole and the skill that governs the action lists the steps in order.
4. **Pin both with a test, and run a negative control.** Assert the rule text and each clause in the SOUL,
   and each step in the skill; then delete the paragraph and confirm the test FAILS (restore, confirm it
   passes). A test that only ever ran green does not pin anything.
5. **Normalise whitespace in prose assertions.** A rule wrapped across a line still states the rule, so a
   raw-substring assertion fails on a reformat and passes on a genuine edit. Split-join both sides before
   asserting. And assert each phrase against the file it actually lives in: a clause quoted from the SOUL
   will not be found in the skill, and vice versa.
6. **Sync tree → live, then `CHECK=1` must say byte-identical**, before the push.
7. **A protected instruction file needs the owner's approval.** Writing a lane's `SOUL.md` may be refused
   as a protected agent-instruction file; that refusal is not something to route around with a shell write.
   Ask, state which rule is missing, and land it in the same commit as its tests once approved.
8. **One canonical bullet, one place — a duplicate is a second source of truth that drifts first.** Measured
   on #972: the SOUL "had 16 bullets" yet paraphrased rule 13, because the block sat beside a stray copy of
   the same title in the lane-rules section. The second copy goes stale while the block stays canonical, so
   *count occurrences, not a bullet total*. A lane-specific line that merely mentions a rule is fine; a full
   restatement of a canonical bullet is a drift waiting to happen. The deletion itself may be a protected
   write (item 7) — pin the occurrence count as a red test first, so no editor ships another duplicate.
   - **Mirror the bolded-rule form, never the raw text and never the bullet count.** The viper is the
     delimiter: counting the whole-file text over-claims a *prose* mention as a duplicate (a bold rule
     inside a sentence is a restatement, a bare text reference is not); counting only `- **` bullet lines
     under-claims a bold paragraph outside a fence that restates the rule (implementer's rules 13/14 sat in
     bold paragraphs, not bullets). The title inside emphasis, punctuation-trimmed on both ends
     (`**Title**` / `**Title.**`) counts real statements and excludes prose. Pin the durable SUBSET — the
     lanes that still carry debt, and the lane THIS vehicle cleared — not a magic row count: a count reds the
     moment the dedupe lands (measured: a test pinned `len==11` from a measured table, and it passed as soon
     as this lane cleared its own two duplicates, 11→9, for a change the planner ordered). Assert
     `still-debt-lanes <= set(named)` and `cleared-lane not in named`; a wrong discriminator still shifts
     which lanes appear without making a count brittle.
   - **A dedupe leaves stale pins behind: an assertion phrase that lived ONLY in the removed copy reds the
     suite.** If the duplicate restated a canonical rule in a personal voice ("remove the tag myself") that
     the surviving fleet block never used ("remove the tag yourself"), the pin fails the moment the duplicate
     goes. Re-point the assertion at the SURVIVING canonical wording — never resurrect the duplicate to
     satisfy an old phrase, which re-creates the very second source of truth the dedupe removed.
   - **`check` output is where a reviewer sees it; a silent green is the amnesty.** A gate that computes this
     debt but prints it only in `report` leaves CI and reviewers hearing nothing on a green tree. Print one
     informational note per duplicate to **stderr while EXIT stays 0** — the deletion is a protected write the
     owner routes (item 7), so a hard failure is a red no editor can clear, and silence teaches the next
     editor to ship another copy. Now it is visible and unblocking.
   - **A negative control must actually remove the code.** A plant whose `replace()` string does not match the
     file leaves the feature intact, and the test stays green for the wrong reason — an invalid control that
     looks like a pass. Confirm the mutation landed (grep for a sentinel, or assert the replacement returned)
     before trusting the red.
9. **A lane-offered re-take must pass the gate's own comparison BEFORE you take it.** When another lane says
   "I deduplicated the live file, take it into the tree", run `_stated_block(live) == fleet_block()` first —
   a file whose bullet-counts are right but whose TEXT paraphrases the fence (the "one full stop" drift) can
   claim `block in soul == True` while failing the byte comparison, and taking it replaces a gate-green tree
   with a gate-red one (measured: a 13,394 b doc-SOUL re-take offered as verbatim redd `fleet-block-drift` on
   the first of four paraphrased rules). Refuse the take, show the unified diff (N removed-from-canonical, N
   added), and tell the lane to copy `agents/standing-rules.md`'s block byte-for-byte rather than re-type it —
   then re-run the comparison and take it only when it holds. A refusal that keeps the tree green is a result;
   a take that turns the gate red is not.
10. **A COUNT-clean dedupe can still fail the fence — dedupe is not immunity.** The doc lane's offer looked
   right by count (`1 occurrence per rule`, retired bullet gone) yet `block_in_soul` was STILL False: its
   surviving block had reworded rule 16 to *"Arm when done, and only on a base of `main`"* against the
   canonical *"Arm auto-merge when the work is done, not when it is approved"* — a paraphrase of exactly the
   rule a dedupe preserves. So the check is the fence comparison, not the occurrence count AND not the
   bullet total; a take accepted on `count==1 per rule` alone imports a gate-red fence. Run
   `_stated_block(live) == fleet_block()` even on a dedupe the lane certifies as count-clean, and refuse
   when the retained text differs. (Measured against #919's doc-SOUL at 11dd97d3.)

**It lands on the branch that carries `agents/`, which may not be `main`.** Check first:
`git ls-tree -r --name-only origin/main agents/ | wc -l`. If that is `0`, a branch cut from `main` cannot
modify the file at all, and a stacked PR cannot be armed — so the rule goes as a commit on the tree's
existing vehicle, with `Refs <issue>` in the message. That is also the only ordering that keeps the
live-comparison green: tree and live profile change together.

## Composing a lane's SOUL when its tree copy is the broken side

A tree-wide gate can be red on files you do not own, and the vehicle cannot merge on a red gate. Copying
the live file blindly is wrong when the live file is the *stale* side; editing the lane's text is worse.
The composition that loses nothing:

- Read both sides and classify: identical · tree-short (a sync deletes live behaviour) · **tree-long but
  missing live lines** (a rewrite that dropped them) · tree-ahead (lag, not a defect).
- When the tree dropped live lines, rebuild it as **live verbatim, then the canonical fleet block, then
  that lane's own rules**, and assert programmatically that every non-blank live line survives. Report the
  composed size and the surviving-line check, not the intent.
- **Tell the lane, with the id and the sha** — a cross-lane change announced only in a commit message is
  the silence the announce rule exists to end. Invite the other direction: if their live profile is the
  one that is behind, they say so and the re-take reverses.

## A skip must be audible, and a home must HOLD a profile

A runner has no `~/.hermes/profiles/`, so a live-vs-tree comparison cannot run there: fail it and every CI
run is red for a condition the runner cannot fix; stay silent and a reader concludes it compared.

- Print the skip, **and put the caveat on the success line too** — `EXIT=0` is what a `&&` chain reads:
  `OK: N profile(s) … — tree checks only, LIVE RULEBOOKS NOT COMPARED`.
- `exists()` is not the test for a profiles home. `Path(env).parent` always exists (a typo, a bare filename,
  `/nonexistent-home` all have a parent), so require **at least one `<base>/<name>/SOUL.md`** before treating
  it as a home; otherwise take the skip path with the caveat.
- Two env vars can mean different things: one names a single profile's home, the other the directory holding
  them all. Accepting the singular name without deriving its parent sends the gate looking for
  `<a profile>/<lane>/SOUL.md`, finding nothing, and reporting a green with the comparison skipped.
- **"Holds at least one profile" is still too weak.** Any directory of probe folders with a `SOUL.md` each
  passes it, so a junk path reports a comparison it did not make. The durable test is a **manifest match**:
  `<base>/<name>/SOUL.md` for at least one name in `manifest.json`. An existence test and a count are both
  satisfiable by accident; a name is not.
- **The retired arming bullet is gate-named debt, never a silent pass and never a red.** The retired
  `Arm auto-merge at PR creation` is neither a canonical title nor (appearing once) a duplicate, so the old
  gate saw NOTHING while documentation-maintainer and pr-reviever ran under a contradiction of rule 16
  (arm when done / main-base only, #873, #950). `_retired_rule_debts` names every such SOUL in `report()`
  and as a `check` `note:` — the same visible-not-silent contract as the duplicate-rule debt. Do not remove
  the bullet from another lane's SOUL to clear the note: that is a protected SOUL write the owner routes,
  and the gate fuses nothing on it. Removing the note wiring while keeping `report()` makes the debt silent
  again in the exact place a reviewer runs — the pin test keeps that wiring on green.
- **The fleet block has ONE canonical — `agents/standing-rules.md`, never the issue fence.** The gate reads
  `fleet_block()` from `agents/standing-rules.md` (rule 16 = "Arm **auto-merge** when the work is done, not
  when it is approved"). Issue #873's body fence states rule 16 as "Arm **when done, and only on a base of
  main**" — the SAME intent, DIFFERENT wording, and `_stated_block()` compares byte-for-byte against
  `standing-rules.md` only. Measured (head 28ce443f): `agents/llgenie-documentation-maintainer/SOUL.md:112`
  and this reference's earlier rule-16 quote carried the #873 wording, so taking the doc lane's live 13,394
  (which matched #873) re-introduced `block-in-soul` FAIL — the planner's "take 13,394, block True" was
  measured against the wrong canonical and was withdrawn (tracked on issue #1005, the single surviving
  vehicle; #1009 closed as a duplicate). Two authorities for one fleet rule is
  how a lane ships an instruction measured against the wrong source. When in doubt, compare against
  `fleet_block()`, never a sampled fence.
