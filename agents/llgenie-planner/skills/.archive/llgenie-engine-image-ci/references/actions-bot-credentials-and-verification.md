# Which credential makes which bot write — and how to prove the bot worked

Two classes of bot failure look identical from a run's conclusion: a credential that
cannot perform the write, and a run that simply had nothing to do. Both need a
specific way to check.

## 1. A step writes with the credential whose scopes can make it

A workflow's `permissions:` block governs `GITHUB_TOKEN` only. Handing a step
`secrets.<OWNER_PAT>` while the job declares the permission grants nothing — the PAT
has its own, usually narrower, scopes.

| the step does | token | why |
|---|---|---|
| comments on / labels an issue | `${{ github.token }}` + `issues: write` | PATs are commonly scoped for repo contents and pull requests, not Issues; the refusal reads `GraphQL: Resource not accessible by personal access token (addComment)` |
| `gh workflow run` (dispatch another workflow) | `${{ github.token }}` + `actions: write` | PAT refusal reads `HTTP 403: Resource not accessible by personal access token (…/dispatches)` |
| pushes a branch / opens a PR | the owner PAT | a `github.token` push does not re-trigger CI, so the PR would sit with no checks |

Rules:

- **Declare the permission and use the matching token.** A job that declares
  `actions: write` and hands the step a PAT is a defect, not a config choice.
- **`git push` does not read `GH_TOKEN`.** It uses the credential `actions/checkout`
  persisted in the repo's remote URL. When you assert "this job pushes with the PAT",
  read the step env, the job env, AND the job's checkout `with.token`.
- **Grep the tests when you move a credential.** Workflow tests pin literal strings
  such as `"${{ secrets.BUMP_TOKEN }}"`; the suite then fails on your own change.
  Update the assertion to the new rule *and its reason* (which permission needs
  which token), never relax it to a truthiness check.
- **`secrets.GITHUB_TOKEN` also works** where a workflow logs in to a package
  registry with `packages: write` — copy the credential the sibling job that
  demonstrably publishes uses, instead of assuming a PAT is required. A job's own
  pre-flight (`make <x>-push-check`, a push-scoped token request) is the fastest
  verdict: `403 DENIED … does not match expected scopes` names the problem in seconds.

## 2. Prove the bot did the thing, not that the run was green

A run's conclusion cannot distinguish "wrote" from "nothing to do". Read what the
bot decided, then check the artifact.

1. Read the run's own decision lines before believing anything:
   `gh run view <id> --repo <r> --log | grep -Ei "action=|skip|nothing to do|no findings|no .* needed"`.
   A sweep that logs `skip #N: a fork (owner)` or `no failing check` is idle by its own
   rules, and a fast `success` is usually exactly that.
2. Reproduce the decision locally in a dry mode (`make <dispatcher> DRY=1`) to see the
   pick, the branch it would create, and the cap numerator.
3. Fix the credential, then **dispatch the workflow on your branch**, not on `main`:
   `gh workflow run <wf>.yml --ref <branch>`. The ref must already exist in the
   *target* repo, so push the feature branch upstream first.
4. Verify the write itself: the comment/post exists, with the bot's authorship and a
   fresh timestamp (`gh issue view <n> --json comments --jq '.comments[-3:]'`). A red
   before and a green after is not proof; the artifact is.
5. Keep a negative control for the credential test: run the new test against the old
   workflow files and show it fails, otherwise you have only shown the new shape passes.

## 3. Gates that read live upstream data

A target that compares committed artifacts against a *live* upstream (a model index, a
registry, a Hub file listing) can red locally while CI passes, because the runner holds
a token or egress the host does not. Before filing a defect: run the same target inside
CI's log (`gh run view <id> --log | grep <target>`) and look for `make: ***`. Same target
red locally, absent from CI's log = environment (token/network), not a code defect. A
gate that reds in CI's log with **no** `make: ***` around it is a test asserting the
message, not the gate failing — check which make level emitted it.

## 4. Classify a link by what the status means

A probe that treats everything but `200/206` as dead will call a **gated** file dead
(`401/403`: exists, this token may not read it) and block the whole sync on a file that
is there. Classify `ok` (200/206), `gated` (401/403), `dead` (rest); fail only on `dead`
and print the gated count so it stays visible. This is the same rule the repo's web
coverage already applies to bot-facing URLs.
