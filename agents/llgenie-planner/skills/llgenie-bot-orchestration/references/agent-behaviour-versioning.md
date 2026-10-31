# Versioning a lane's own behaviour, and who can approve it

An instruction a credential-holding agent runs under must be reviewable in the repository, not lived
only in a home directory. Doing that safely has a direction, an author, and an approver.

## Direction matters more than the diff

- The tree copy under `agents/<profile>/` is a **seed**; the live profile is where the agent actually
  learns. When the live file is **longer** than the tree copy, the tree is a *prefix* of the rulebook
  and a write-mode sync **truncates the live rules** — silently, with no gate noticing.
- Always measure both sides first and establish the direction. Live richer ⇒ copy **live → tree**.
- After copying, run the sync in **compare-only** mode (`CHECK=1`) and put the byte sizes on both
  sides into the PR body, so the direction is evidenced rather than asserted.
- Say explicitly in the PR body: *do not run the sync in write mode for this profile*. The tool treats
  the seed as authoritative and cannot distinguish "drift" from "the live agent learned something";
  the warning is what stops the next maintainer from deleting a night of lessons.
- **A byte count is a measurement at one time.** Syncing a size remembered from earlier in the session
  reverts every lesson recorded since; re-measure immediately before the copy, and prefer the live
  content over any number quoted in chat.

## Who writes the PR

- **Versioning your own lane's skill text is in-role, not an implementation.** A lane whose standing rule is
  "never implement / never author an implementation PR" *can and must* author the PR that commits its own
  `agents/<profile>/` skill/reference text — that is versioning behaviour, not shipping code, and delegating it
  to another lane is how the instruction drifts from the agent that runs it. The no-implementation rule bars
  code/branch work on issues; it does not bar mirroring your own rulebook into the tree.
- Delegate only when the work is genuinely outside the lane's remit (a code change, or profile/agent files the
  lane does not own), and then **attribute the delegation in the PR body** — "<owner lane>'s versioning delegated
  to <lane> at that lane's dispatch" — or a later reader concludes the delegate owns those files.
- A behaviour that contradicts a fleet rule is fixed by **amending the versioned instruction** (issue + PR under
  `agents/<profile>/`), never by a private edit and never by a standing one-off override.
- **When a completion check demands a "task-relevant mutation" and the lane has no legitimate code work, the
  honest change is your own lane's versioning sync** — mirroring the live skill/reference into `agents/<profile>/`
  is a real, reviewable mutation inside your remit. Make that change and verify it. Do not clear the counter by
  editing a peer lane's files (boundary violation) or by committing a throwaway edit (theater); both are the
  failure the counter is meant to catch, not a way past it.
- **A completion counter that fires again after a verified, pushed mutation is not evidence you failed to
  mutate.** The instrument measures a working-tree window it controls; work already committed and pushed to a
  PR is invisible to it, so it can read zero while the mutation is real. When it fires after you have proven
  the push landed (PR head sha == local == `git ls-remote`), restate that evidence and keep refusing — do not
  invent a throwaway commit to turn a structurally-unsatisfiable counter green. The API is the verdict; the
  counter is a proxy that can be blind to the exact thing it asks for.

## Mirroring a live reference into the tree: prove byte-identical and additive

The versioned `agents/<profile>/` copy routinely drifts **behind** the live profile (the agent keeps learning
locally). Before committing a sync PR, prove two things and put both in the PR body:

- **byte-identical**: `sha256sum` the live file and the copied tree file; they must match — a diff of zero
  bytes is the whole claim. State the sha in the PR body.
- **purely additive**: `diff <tree-at-origin/main> <live>` and confirm **no `<` (deletion) lines** — only `>`
  additions. A `<` line means the tree had content the live file lost, which is a truncation, not a sync; stop
  and inspect before committing.

Base the branch off a freshly-fetched `origin/main`, keep it to the one file, and return the checkout to `main`
clean afterwards. `wc -c` on both sides is a fast first check that the tree is the shorter (stale) side.

### The tree copy can be AHEAD of live — and over-cap is the tell

The "purely additive, tree is the shorter stale side" pattern is the common case, not the only one. The tree
copy can drift **ahead**: it carries content the live profile has since pruned, so `diff` shows `<` (deletions)
on both sides and the tree is *larger* than live. Do not reflexively abort on the `<` lines when this happens —
decide authority, then reconcile:

- **The cap decides who is authoritative.** If the tree copy exceeds the SKILL.md cap (100 KB) while the live
  file is under it, the tree copy is the invalid side and live is authoritative — a committed mirror that busts
  the cap could never have passed the skill-cap gate, so the tree was never the good state. Sync **live → tree**
  even though that shrinks the tree and deletes lines from it.
- **Two-way drift is a reconciliation, not a truncation.** When live both added content (a new block, a pin) and
  dropped content, `cmp` will differ at many bytes and the diff is `<`/`>` interleaved — that is expected here, and
  is not the truncation the additive rule warns against. Confirm the *result* is byte-identical
  (`cmp live tree && echo IDENTICAL`) and that the synced size is under the cap (`wc -c`), and state both in the PR.
- The additive rule still governs the common stale side: when the tree has **no** content live lacks and live is
  longer, only `>` lines is the proof of a clean sync. Reach for the over-cap test first — it tells you which of
  the two regimes you are in before you read a single diff line.

## Knowing whether an approver exists

- Before reporting "only the owner can approve", check who actually approved past PRs:
  `gh api repos/<owner>/<repo>/pulls/<n>/reviews --jq '.[]|"\(.user.login) \(.state)"'`.
  The **authoring identity and the approving identity are often different accounts**, so an
  independent reviewer can exist even when every PR shows the same author.
- Read the merged counter-examples before proposing a ruleset change: if two comparable PRs merged with
  `review=APPROVED` and a third sits at `REVIEW_REQUIRED`, the variable is *who signed*, not *which
  paths the change touches*. That distinction changes the remedy from "edit branch protection" to
  "route it to the approving identity".
- Lanes must not self-approve, and must not tick another lane's task boxes. Both refusals are correct
  behaviour; the parked board that results is a throughput bound to state plainly, not a lane defect.

## The propagated-rules tool that falls back to a stale source

A rules-/fleet-*propagating* tool (one that copies a canonical block into each lane's SOUL/skill) is safe only as
long as its **source resolution is pinned to a versioned file in the tree**. The failure class: the loader resolves
`$ENV`, else the versioned reference *beside the SKILL*, else a **historical scratch path** (`/tmp/873.md`). When a
middle path does not exist on a given host, it silently falls through to the scratch file — dated two generations
stale — and *rewrites four standing rules to older wording while printing "block in soul: True"*. Every check that
reads the resulting file for *presence of a block* passes; nothing reads it for *the exact current wording*, so a
keys-only verification cannot see the degradation (same blind spot as mode-100644 scripts and a `make` that refuses
to parse).

- **Pin the source to a versioned file, never a scratch path.** A rules source must resolve to a path committed in
  the tree (`agents/<lane>/skills/…/references/…`), updated *in the tree* when a rule changes — never `/tmp`.
- **A fallback to a host-local scratch file is a defect, not a nicety.** The default should fail loudly, not
  degrade silently to whatever `/tmp` holds.
- **Verify the output differs the way you expect, then verify they are identical.** For a splice: run it on the
  *correct current* SOUL, confirm `git diff` shows **no** rule line changed (idempotent, 4/4 kept), and confirm the
  file is byte-unchanged. A tool that prints success while degrading is the tell.
- **Add a no-regression guard**: if the source would *drop* a rule the target already carries, refuse and write
  nothing (compare on a signature ignoring emphasis and trailing punctuation, so a legitimately versionless rule
  like #16 doesn't read as "changed").
- **Audit the lanes' current wording after such a finding, not before.** Even when your own lane is clean (grep
  for the *stale* wording, not the canonical — the absence of "Arm when done, and only on a base of main" is the
  cleanliness proof), say which lanes *could* have run the tool, and list the safe override invocation + the
  `git diff`-before-commit rule in the relay.
