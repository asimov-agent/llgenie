# llgenie repo work: finding, proving and landing a fix

Recipes for the parts of an llgenie change that are not the engine-image pipeline: where to look
before writing code, how to run one test fast, how to prove a fix is real, and how to verify a
`workflow_dispatch`-only job without merging.

## 1. Before writing a line: look for a fix that already exists

llgenie's branches outlive their PRs. A commit pushed to a branch **after** that branch's PR merged
never reaches a PR — it sits on the branch, unreviewed, while `main` keeps failing for the reason it
fixes. Two cheap checks before implementing anything:

```bash
git log --oneline -S"<the symbol or string you are about to add>" origin/main   # has it landed?
gh pr list --repo asimov-agent/llgenie --head <branch> --state all \
  --json number,state,closedAt                                                 # merged? when?
git merge-base --is-ancestor <candidate-sha> origin/main || echo "NOT IN MAIN"
```

If a candidate commit exists but is not in `main`, cherry-pick it onto a fresh branch off
`origin/main` (`git cherry-pick -n <sha>`) instead of rewriting it, then re-run the gates against
current `main`. Check the commit's own doc edits: an old fix may append its work record to a
*different* change's `agent-wiki/` entry — move that section into a new dated entry for your change
(`git checkout HEAD -- <that file>` first) so the record lands with the right issue.

## 2. OpenSpec CLI creates the change directory as root

`make openspec-new NAME=<name>` runs the `openspec/` container with `-u root`, so the new change
directory is root-owned and `write_file` returns `Permission denied` on `proposal.md` (the editor's
temp file in that directory is refused first). Fix it before writing:

```bash
make openspec-new NAME=<kebab-name>
sudo chown -R $(id -u):$(id -g) openspec/changes/<kebab-name>
```

Then write `proposal.md`, `specs/<capability>/spec.md`, `tasks.md` by hand and validate:
`make openspec-validate NAME=<kebab-name>`.

## 3. OpenSpec spec shape that validates

- Every `### Requirement:` needs a top-level `WHEN … / THEN …` block **and at least one
  `#### Scenario:`** — a requirement without a scenario is the validator's `must include at least one
  scenario` error even when the prose is perfect.
- Each scenario needs separate `- **Given**` / `- **When**` / `- **Then**` lines plus a `- **Test:**`
  line naming `tests/<file>.py::<test_case>` exactly.
- Tick `tasks.md` as each step is verified; the last task is a verification you can actually run
  (`make test-unit`, the check-* gates, `openspec-validate`), never the loop command itself.

## 4. Running one test file fast (without waiting for the whole suite)

The gate is `make test-unit` (discovered, ~15 min), but iteration is a single file inside the same
test image, with the same mounts `make -n test-unit` prints:

```bash
docker run --rm -u root -v "$PWD":/repo:rw -w /repo -e HOME=/root \
  llgenie/test:latest python -m pytest tests/test_<x>.py -q -p no:cacheprovider -k "<expr>"
```

If the file's test imports `scripts.llgenie_serve` on the **host** python, drop it: import-time
engine/install work can pull an image and start a server. Import it inside the test image only.

## 5. Prove the test is real: stash the source, watch it fail

llgenie reviews a test by whether it fails on the unfixed code. Do that explicitly and record the
output:

```bash
git stash push -q -m falsify scripts/<the file you changed>
<run the new test>            # must fail, ideally with the CI's own symptom
<run the new test>            # after: must pass
git stash pop -q
```

A test that only ever passed is not evidence. Note that a selective `git stash push <path>` keeps
the test in the tree while the fix leaves it — that is the shape you want.

## 6. Tell a network flake from a regression

`make test-unit` reaches live services (Hugging Face API/link probes). Before treating a red as
yours:

1. `gh run list --workflow CI --branch main --limit 8` — was the job green on the previous commits?
2. Re-run **only** the failing node ids in isolation (recipe 4). A pass there = transient; say so and
   do not fix it in your PR.
3. Name the flake's existing issue in the PR body instead of filing a duplicate; the run-failure
   reactor files its own `ci: <job> failed` issues, so search open issues by the job name first.

## 7. Verify a `workflow_dispatch`-only workflow before merge

A `workflow_dispatch` run must name a ref that exists **in the upstream repo**, so a branch that
lives only on the fork cannot be dispatched. In this checkout the remotes are inverted from the usual
convention: `origin` = `asimov-agent/llgenie` (upstream), `fork` = `andyholst/llgenie`. Pushing the
feature branch to `origin` as well makes it dispatchable, which turns an argument about a credential
into a green run:

```bash
gh workflow run <workflow>.yml --repo asimov-agent/llgenie --ref feat/<branch>
gh run view <run-id> --log | grep -E "push-check|202|accepted|no-op"
```

Then keep both refs at the same sha (`git push --force-with-lease fork …` and `origin …`) so the PR
head and the dispatched ref do not diverge. Say plainly in the PR body what the dispatch proved and
what it did not.

## 8. Hub transport failures: the exception classes matter

A **read-phase** socket timeout is the builtin `TimeoutError` (raised inside `http.client`/`ssl`
after the connection is established) and is **not** a `urllib.error.URLError` subclass; only a
connect-phase failure is wrapped in `URLError`. A retry loop that catches `URLError` alone therefore
lets one slow read escape as a traceback (`ssl.py ... TimeoutError: The read operation timed out`)
and exits 1. llgenie's two Hub GET seams (`scripts/hf_auth.py::hub_open` and
`scripts/llgenie_serve.py::_hf_get`) must both name `(urllib.error.URLError, TimeoutError)`. When
testing this, do not monkeypatch `urlopen`: serve from a real local `ThreadingHTTPServer` that accepts
the connection and answers nothing, so the client's own socket timeout raises.
