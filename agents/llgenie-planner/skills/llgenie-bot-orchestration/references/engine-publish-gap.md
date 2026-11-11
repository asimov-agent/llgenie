# Engine publish gap: a green merge whose image tag was never pushed

## The failure shape

An engine bump merges to `main`; its post-merge `engine-build` publish run is cancelled or superseded.
Nothing is red on `main` itself, so `main` looks green — but the committed pin points at a GHCR tag that
does not exist. Every open PR whose `linux/unit` suite polls for those tags
(`test_every_image_install_pulls_is_published`) then fails after a ~120 s timeout, with the poll log naming
the 404 tag.

Signature: several unrelated PRs go red on the SAME single test at once, and the poll log shows
`ghcr.io/<repo>/<image>:<sha>-<arch>` 404 for a sha already in `main`.

## Diagnose before attributing

1. Read the failing test's log, not its name: extract the exact image:tag strings it polled.
2. Verify each tag live, never from a lane's report. Only two probes are ground truth:
   - `docker manifest inspect ghcr.io/<o>/<r>/<image>:<sha>-<arch>` → `manifest unknown` = never published.
   - Without docker, the registry's own TAG LIST settles it: fetch an anonymous pull token
     (`curl -s "https://ghcr.io/token?scope=repository:<o>/<r>/<image>:pull"`), then
     `curl -s -H "Authorization: Bearer $TOK" "https://ghcr.io/v2/<o>/<r>/<image>/tags/list?n=200"`.
     Assert the pin-prefixed tag across the WHOLE list (e.g. 33 tags, every one an older sha, zero pin
     prefix = the pin was never published), which is stronger than one 404 probe.
   - Do NOT judge existence from an authenticated manifest HEAD: `.../manifests/<tag>` with
     `Authorization: Bearer $(gh auth token)` returns **403** for tags that exist AND tags that do not
     (auth-scoped, no verdict), and `gh api repos/<o>/<r>/packages/container/<image>` can 404 while the
     package plainly exists. A 403/404 from those two is "not measured", never "missing" or "present".
3. Confirm the pin is committed on `main` (`git show origin/main:<manifest>`). A 404 with a committed pin
   is a publish gap, not a content defect — do not let a lane "fix" the PR's content for it.

## Why the publish run vanished

`engine-build` push runs share one concurrency group (`engine-build-push`) with `cancel-in-progress: false`:
a newcomer QUEUES behind the live run rather than cancelling it, but a burst of dispatches builds a stack.
`cancelled` conclusions you see come from runs superseded while queued.

Dispatch discipline when tags are missing:

- Dispatch `push=true` ONE at a time: confirm via `gh api repos/<r>/actions/runs/<id>/jobs` that the run
  carries the engine you want, wait for it to conclude, then dispatch the next.
- Never dispatch twice to "cover both engines" — the second joins the same group and delays the first.
- Before dispatching, check for an already-queued run at the current head and skip if one exists.
- After each run concludes, re-verify the tag exists before moving on.

## One owner for the unblock

Only the engine lane dispatches engine-build publishes. If the planner unblocks, it dispatches ONE run and
says so on the issue — planner tick and engine lane both dispatching is what turns one gap into a stack of
cancelled runs. When a lane claims "other lanes are dispatching", measure: `gh api .../workflows/<id>/runs`
ordered by `created_at` shows whether anything new landed, and `actor` shows the token, not the lane — the
planner must own up to its own tick's dispatches instead of endorsing a phantom rogue lane.
