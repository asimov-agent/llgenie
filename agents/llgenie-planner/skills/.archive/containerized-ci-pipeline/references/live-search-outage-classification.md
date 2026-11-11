# Live-search fetch outcomes: refusal vs outage vs quiet (classify, don't collapse)

A scheduled data pipeline's live gate must be held red by neither an INFRA outage nor a
broken credential, and must not pass a real data gap. Each fetch class demands an OPPOSITE
response, and collapsing two classes into one is what turns a 6-minute mirror outage into
every-PR-red for hours. Classify the outcome in the gather step and let the verdict follow.

## The trap: an upstream error page IS "success"

A fetching proxy (Firecrawl or any web-scrape API) answers HTTP 200 and `success: true` even
when the TARGET returned an error. The target's real status rides in the page's own metadata
(`data.metadata.statusCode`), NOT in the proxy's HTTP status. So a Cloudflare 502 mirror comes
back as a "successful scrape", every query "succeeds" with zero model hits, and the check
prints `0 model hits` and blames the query set. Signature of this trap: the live check
finishes in a few seconds (cached error pages) and prints no `[warn]` at all.

## The four classes (decision table)

| class | detection | meaning | gate verdict |
|---|---|---|---|
| refusal | proxy answers HTTP 4xx (401/402/403), `success:false`, non-JSON, no page, target 4xx | OUR credential / quota / target config | RED (block, fix config) |
| upstream outage | proxy OK but the page is the TARGET's error: `metadata.statusCode >= 500`, Cloudflare `Error code 5NN` / `5xx-error-landing` | the source is down, nothing of ours is wrong | GREEN (exit 0), loud `[outage]`, so it cannot block every open PR |
| quiet search | a usable page came back with zero model hits | a real data problem / query-set gap | RED (block) |
| unreachable / transport | never got a page AND it is not our credential (ECONNREFUSED, DNS, timeout, the proxy's own 5xx) | infrastructure, nothing proved | RED (fail loud), UNLESS every other query proved an outage |

## The quorum rule (a single transport hiccup must not flip a proven outage)

Count outage + unreachable as ONE "infra where nothing of ours is wrong" bucket. Verdict on a
zero-hit run:

- any refusal present -> REFUSED (block)
- infra == total queries AND outage >= 1 -> OUTAGE (non-blocking, exit 0): POSITIVE proof the
  source answered with an error
- infra == total queries AND outage == 0 -> UNREACHABLE (block, loud): nothing was proved, and
  a check that proves nothing must fail closed, not pass quietly
- otherwise -> QUIET (block)

One transport failure among 23 proven 502s is part of the outage, never evidence of a healthy
search — measured: it flipped green to red and printed a message contradicting its own
evidence. But an all-transport run proves nothing and must stay red.

## Keep the two HTTP statuses distinct

`status` = the proxy's own HTTP status, `upstream` = the target's status from page metadata.
An OUTAGE verdict is never retried (retrying a 502 storm just hammers the mirror); a transient
transport miss may get one retry. Report both so the log cannot be misread.

## Test it the way CI sees it

- Unit tests drive the REAL fetch/gather code against a real local stand-in HTTP server that
  scripts status + body per request (no mock of the business logic). Assert: the OUTAGE label
  is never retried (one request served), a bot-wall 403 is FAIL, not excused as an outage, and
  a healthy page with no upstream metadata error stays OK.
- An end-to-end test runs the EXACT command the live job runs (e.g. `make validate-fetch`) and
  asserts its exit code across each scenario. Prove RED on the pre-fix branch and GREEN after,
  and re-run the new guard against the OLD code to confirm it actually catches the regression;
  a new guard that passes on both old and new code locks nothing.
- Do NOT treat "an outage makes the gate red" as an accepted price — that is precisely the
  defect this classification removes.
