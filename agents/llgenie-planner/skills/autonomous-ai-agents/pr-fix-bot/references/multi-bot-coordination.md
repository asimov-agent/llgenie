# Several bots on one repo: coordination, claims, rebase verification

A repo can end up with a repair bot, a rebase bot, an implementation bot and a refiner all touching
PRs and issues. These are the rules that keep them from harming each other, and the tree checks that
prove a rebase did not quietly break something.

## Collision safety between bots on one PR

- **Make a collision LOUD, never lossy.** A bot that *rewrites* history (a rebase) must push
  `--force-with-lease`; a bot that only *adds* commits pushes a plain fast-forward. Then if two
  overlap, the second push is REJECTED in either direction — nothing is clobbered, and the losing run
  fails visibly. Verify this from the argv, not by hope: assert `--force-with-lease` is present and a
  bare `--force ` is absent.
- **Refuse to act while a run is in flight.** Read the PR's checks (`gh pr checks <n> --json state`)
  and skip when any state is `PENDING/IN_PROGRESS/QUEUED/WAITING`: rebasing a PR whose CI is running
  cancels the very run that is deciding it, and that is the one genuinely wasteful interference (it
  also removes most of the window in which two bots could collide at all).
- **Split the work explicitly.** A PR that is only *behind* and *red* belongs to the repair bot — a
  rebase fixes staleness, not a failing test. A *conflicted* PR belongs to the rebase bot even when it
  is red, because the rebase is the precondition for anything else on it to be fixable. Write that
  split into both bots' sweep rules and test both branches of it.
- **An implementation bot cannot be raced by a rebase bot**: it pushes a NEW branch and only then
  opens the PR, so a PR it created is fresh (never `BEHIND`/`DIRTY`) by construction. Do not add a
  "skip the bot's own PRs" rule for that — the freshness does it.
- **Bound every run**: one PR per run, a daily cap, and a once-a-day record per PR. A marker comment
  (`<!-- <bot>: <date> -->`) is the record — it needs no label, and it is what stops a rebase bot
  from rebasing the same PR twice in a day.
- Keep each bot's `concurrency` group separate from the others' (per-PR for a repair bot, global for
  a sweep), and never let any of them merge.

## The claim protocol: a comment is the lock

When bots pick work from a shared backlog (issues or PRs), a machine-readable claim comment is the
lock that stops two bots starting the same item:

- **Claim before you start, read every claim before you pick.** A bot that intends to work an item
  posts a marker comment first (`<!-- bot-claim: <bot> <ISO-timestamp> <work> -->`); a bot choosing
  work skips any item whose LATEST comment is a recent claim that has NOT been concluded by a `done`
  comment, and moves to the NEXT item rather than stopping.
- **`done` has two meanings and both release the lock**: the item was closed because it was
  implemented and merged, OR a PR is open but not yet approved. Treat either as "not occupied".
- **The claim must be machine-readable, not free text** — the other bot parses the marker. Keep the
  marker grammar in ONE shared helper (`bot_claims.py`) every bot imports, so the format cannot
  drift between bots.
- **The `work` field must accept a repair** (`fix`/`rebase`) as well as `refine`/`implement`,
  because a bot works on a PR, not only an issue.
- **A `--dry` run must not claim anything** — deciding and printing is not starting.
- **A label is a queue, occupancy is a claim.** A bot that stands down whenever ANY item carries the
  queue label never works again once the labelled backlog outlives it: yield only to a LIVE claim
  (a run id in the marker, a fresh timestamp), and skip past a label-only queue to the next
  candidate, naming that it did.

## Rebasing a PR onto latest main: verify the TREE, not git

- **A list-conflict resolver only handles LIST conflicts.** On a non-list conflict (a cron line, a
  Makefile recipe, a test expectation) it silently CONCATENATES both sides into broken YAML or leaves
  raw `<<<<<<<` markers. After any rebase, verify the TREE, not git: no conflict markers anywhere
  (`grep -rl '<<<<<<<\|>>>>>>>'`), every workflow YAML parses, `make -n <target>` parses, and the
  guard tests still exist — a rebase can silently DROP a test file.
- **`MERGEABLE` from git means only that git has no conflict** — it says nothing about whether the
  working tree is sound. A branch is shippable only when its own suite is green AND the tree parses.
- **A repo's own guard may assert globally-unique cron minutes** ("no workflow shares a minute").
  Reusing a minute across different hours still fails it — give every scheduled workflow a DISTINCT
  minute, and align your own schedule test to that rule rather than a fixed grid.
- **A recipe/block conflict resolved by a token-union can silently DROP env lines that live only on
  the branch.** When a Makefile `target:` recipe conflicts, the union keeps one side's set of recipe
  lines — main's version can win and the branch's added `-e TYPESAFE_API_KEY -e NERVE_REQUIRE ...`
  lines vanish, while 0 conflict markers, `make -n <target>` parsing and `make lint` ALL still pass.
  The git-level checks prove the tree parses, not that the recipe is correct. In a repo that passes
  env to a container, after ANY recipe/Makefile conflict resolution run the test that ASSERTS the
  env reaches the container (e.g. `"TYPESAFE_API_KEY" in recipe`, "the key must reach the container
  at run time") — that test is the only thing that catches the semantic break; the "clean" checks
  will not. (Same reason a rebase can look shippable yet be red: 0-markers + parse + lint is NOT the
  green bar — run the affected suite.)

## A base that moved while the bot worked

A bot that spends 20-30 minutes implementing races every merge. Assert the base ONCE where the work
STARTS, never again where it is committed: cut or attach the branch from the CURRENT HEAD, commit,
`git rebase` onto the freshly fetched tip, and on conflict ABORT the rebase (every commit intact),
push anyway, and let the PR's fix loop repair it. A second `HEAD == fetched tip` assertion at commit
time refuses a finished implementation and throws away the whole run.
