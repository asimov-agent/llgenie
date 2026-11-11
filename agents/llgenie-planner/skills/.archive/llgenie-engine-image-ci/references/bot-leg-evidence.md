# Proving a scheduled bot leg actually did work

`completed/success` is not evidence. A job whose decision returned `action=none`, or whose sweep
skipped every candidate, reports the same green as one that commented, implemented and opened a PR.

## Read the decision line out of the run

```bash
gh run list --repo <repo> --workflow <name>.yml --limit 5 \
  --json databaseId,conclusion,createdAt --jq '.[]|"\(.createdAt) \(.conclusion)"'
gh run view <id> --repo <repo> --log 2>&1 | grep -E "\[sweep\]|action=|no open PR"
gh run view <id> --repo <repo> --log-failed 2>&1 | tail -40
```

What you find means:

- `action=none` / "no issue labelled …" = the picker ran and had nothing. Green, not working.
- `[sweep] skip #N (…): a fork (owner)` on every candidate = the selector can never pick here; a
  structural defect, not a quiet hour.
- The **same** failure line across N consecutive runs = a structural blocker. Report the run ids and
  the line; do not call it flaky.

## Two blockers that look like model problems

- **Token scope.** `GraphQL: Resource not accessible by personal access token (addComment)` on an
  issue, or `could not create workflow dispatch event: HTTP 403: Resource not accessible by personal
  access token`, means the PAT cannot do that write. The leg dies before any model call, which is
  why the log reads like an agent failure. Check which secret the writing step uses, and whether the
  job's own `permissions:` already grants it (`issues: write`) — `github.token` is often enough where
  the owner PAT is not.
- **A cap or selector counting an identity the bot never uses.** Prove it against the API instead of
  reading the constant:

  ```bash
  python3 scripts/<dispatcher>.py count --repo <repo> --today <date>                        # cap numerator
  python3 scripts/<dispatcher>.py count --repo <repo> --today <date> --bot <actual author>  # the truth
  gh search prs --repo <repo> --author '<assumed login>' --limit 5 --json number            # often []
  ```

  A `0` on a day with real bot PRs is the defect: the PRs are authored by whoever's token opened
  them, not by the bot login the code asserts.

## Model and alias checks

- One real call through the alias (`make hermes-smoke`) proves the endpoint, the key and the alias
  resolve. It does **not** prove which model answered, nor tool calling.
- Model id: read the alias config inside the image (`hermes config get model.aliases.<alias>.model`)
  and compare with `GET /v1/models` for the exact id.
- Tool calling: send a prompt that requires one tool with a trivial command and assert the tool's own
  output appears (ask for `printf <marker>`, look for the marker). A text echo passes on a model
  whose tool support is broken.
- **Never assert a versioned id by prefix.** A family id and a dated snapshot id can both answer
  `200` while being different models, and `"<family>" in text` is satisfied by every future
  snapshot — so it cannot detect drift. Pin the exact id; compare exact strings in the gate.

## Reporting progress on these long runs

Jobs here run 15–180 minutes; a status line of "still running" is a non-answer (the output is
buffered, so the user sees nothing).

- Run long gates with `> /tmp/<job>.log 2>&1`, not `| tail -N` — a piped `tail` prints nothing until
  the pipe closes, so polling looks frozen.
- Read real progress: the test container's log (`docker logs --tail 3 <cid>`, the pytest `[ NN%]`
  line), or the build's active step (`sudo ps -eo pid,ppid,etime,cmd --forest` around the build's
  `runc`, then the `RUN` line it is executing).
- Quote that number and what the stage is doing in every status update.
