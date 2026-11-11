# Object identity and live state: PR vs issue, duplicate vehicles, stale cursors

Before reasoning about a number on the llgenie board, establish WHAT it is and WHAT state it holds RIGHT NOW. A claim built on a misidentified object type or a stale open/closed read is wrong before you write a word on-wire.

## Identify the object before you reason about it

- **`/issues/{n}` returns pull requests too.** A number read through the issues endpoint can be a PR; calling it an "issue" and reasoning about it as tracking/board state then misleads the whole dispatch. Before labelling a number, `GET /pulls/{n}` — a 200 with `head`/`base`/`diff_url` keys means it is a PR — or check the `pull_request` key on the issue object. Confirm the type first, then route.
- **Two PRs touching the same files are one vehicle, not two independent fixes.** Compare `/pulls/{a}/files` to `/pulls/{b}/files` and the `base.sha` of each: identical file sets (same `docs/changes.d/<same-file>.md`, same `agent-wiki/<same-file>.md`) mean a duplicate vehicle — the collision that piles branches on one issue. Pick one on measured merit (base freshness, CI state), close the other with a comparison table, and state explicitly that the diagnosis was not rejected.

## Read live state at the instant you post

- **Read `state`/`closed_at` live at the moment you post.** A PR you believe is "open" — or "the single open vehicle" — can have closed seconds before; a list fetched from a stale cursor still shows it `open`. Direct-GET the PR (`state`, `merged`, `closed_at`) at post time before asserting it is the live vehicle. A stale open-state read produces a reconciliation built on a premise that is already false.
- **A comments list can return a stale slice.** `/issues/{n}/comments?sort=created&direction=desc` may not include your newest post (its max id can predate comments you just created). Do not conclude your write failed — verify with a direct-ID GET `/issues/comments/{id}`; the direct GET is the evidence, the list is not.

## Correct your own record when the wire disproves it

- **Correct your own on-wire post when the wire invalidates its premise.** If an earlier comment you posted rested on a now-disproven assumption (stale state, misidentified object type), post an explicit correction naming the wrong premise and the live fact that replaces it. A silent move-on leaves a false statement as the durable record the next reader trusts; the correction is the record they need.
