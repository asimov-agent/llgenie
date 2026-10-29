# Reviewing security issues and the pipeline that produces them

Depth for the "do the security issues still make sense / could a fix cause a bigger bug" pass.

## Roster, then evidence

```bash
cd /home/asimov/repository/git/llgenie && git fetch -q origin && git log --oneline -3 origin/main
# every open issue that is security-adjacent (labels OR title words)
gh issue list --repo asimov-agent/llgenie --state open --limit 100 \
  --json number,title,labels,createdAt \
  --jq '[.[] | select((.title|test("security|vuln|CVE|scan|secret|token|auth|image";"i"))
        or ([.labels[].name]|any(.=="security" or .=="vulnerability")))]
        | .[] | "#\(.number) [\([.labels[].name]|join(","))] \(.title)"'
```

For each candidate, grep the mechanism the body claims. The greps that answered every question in a
full pass:

| claim class | grep / command |
| --- | --- |
| a tool rides another image | `grep -n "entrypoint=\"syft\"\|SBOM_TOOL" scripts/security_scan.py` |
| an image registry is stale | `cat containers/scanners/digests.json` |
| a label-create is dropped | `grep -n "--label" scripts/*.py` |
| a check skips green | `grep -n "return 0\|SKIPPED\|NOTE:" scripts/<bot>.py` |
| a gate is missing entirely | `grep -rn "<tool>" Makefile .github/workflows/*.yml` (hit in `openspec/`/`agent-wiki/` only == no gate) |
| a pin is floating | `grep -n "ARG .*=\"" containers/*/Dockerfile` — an ARG with no version is a floating dep |
| a job holds the wrong permissions | `grep -n "permissions:" -A 8 .github/workflows/<wf>.yml` |

A parent/tracker issue is stale when every child is `CLOSED` **and** the mechanism each child
installed still exists — check both, then close it with the re-verification named.

## Trust-boundary checklist (what runs the scan)

```bash
grep -n '"ref"' containers/scanners/digests.json              # a TAG (mutable) vs @sha256: (pinned)
grep -n 'v.*REPO}:/work' scripts/security_scan.py            # :rw is a write primitive for the tool
grep -n 'BUMP_TOKEN' .github/workflows/security-scan.yml     # same job as the scanners?
grep -n 'permissions:' -A 10 .github/workflows/security-scan.yml
```

Reasoning to reuse: a scanned tree that the scanner can write is also the tree the *next* step
executes (`make security-bumps` reads `Makefile`/`scripts/` from it), and the write PAT sits in that
job's `env:` — so image compromise → credential. Digest pinning, a `:ro` mount with reports written
to `$RUNNER_TEMP`, and a separate `report` job close the chain.

## Constraints to demand of a remediation leg

An issue proposing an agent that repairs what the scanner cannot place is fine; the *remedy* needs
these written into it, or the safety of the pipeline is inverted:

1. **PR only, never auto-merge.** The change is derived from a string produced by a third-party
   binary, so a human reviews it — exempt those PRs from the repo's auto-merge.
2. **Verify the target upstream.** Resolve the name+version on the index and confirm it belongs to a
   dependency the tree already has, before writing it into the floors file. A poisoned advisory
   database otherwise redirects the bump (including to a typosquat that really exists).
3. **Never let the leg re-publish the image that judges it.** Rebuilding/re-tagging scanner images
   belongs in the reviewed publish path, not an agent job.

## Reviewing a permission-surface widening (a gate or allowlist)

A PR that widens a merge-blocking gate (an author allowlist, a severity set, a check roster) is a
permission-surface change and gets reviewed as one:

1. **Aliases of a key are safe; a new key is the actual widening.** Decide whether the change adds
derived aliases OF an already-trusted identity key (e.g. more display names for the same two addresses)
or adds a new key no reviewer intent covers. The former keeps the trust set identical; the latter is
the real expansion and needs its own justification.
2. **Read the accept predicate, not the prose.** The decision function must still require the
conjunction — the key is allowlisted AND the presented value belongs to that key's set. A widening is
safe when it relaxes the value set of an existing key; it is a hole when it accepts a value without the
key, or a key under any value. Grep the literal `if` and confirm the AND is still there, and that the
derived lookup structure cannot drift from the source of truth.
3. **State the failing cases that still fail.** A widening with no enumerated negative class is not
reviewable. List the classes (a lookalike key, an allowed key under a non-listed value, a cross-key
value) and confirm the suite asserts each one — for an author gate these are the commits that must
still red.
4. **Check the canary that restates the policy.** A gate is usually paired with a mandate string
(template, doc heading) the check refuses to delete. If the gate widens past that sentence, the doc
drifts — usually the safe direction, but it invites the wrong next edit (widening the gate to match the
sentence). Track it; the canary should stay at least as strict as the gate a reader is told about.
5. **Run the suite for the negative cases and say which command passed.** "The negative cases still red"
is a claim until a test run proves it; remember the import path when running tests directly
(`PYTHONPATH=/repo/scripts`), and note the invocation in the review so the reviewer can not reproduce
it, not just trust it.

## Comment shape that survives review

State the verdict, the current line number, and the consequence — not a summary of the issue:

- "Still reproduces at `<sha>`: `scripts/x.py:578-586` returns `None` on refusal, `:590` returns 0
  unconditionally, so a skipped check prints *no findings* and exits green."
- "Status: still accurate — `ci.yml:133-150` still builds all three images on every PR."
- "Closed as done: children #A-#G are CLOSED and merged; re-verified `<gate>` and `<gate>` still fire."

## GitHub API quirk that costs a round-trip

`gh api` takes **no** `--repo` — put the repository in the path (`repos/<owner>/<repo>/issues/<n>/labels`)
and run it bare. Endpoints that answer with an array need the array form of `--jq`:
`gh api repos/o/r/issues/1/labels --jq '[.[].name]|join(",")'` — `--jq '.name'` fails with
`expected an object but got: array`, and the POST itself already succeeded, so it reads like the
label write failed when it did not. Verify the label write by reading the issue back
(`gh api repos/o/r/issues/<n> --jq '[.labels[].name]|join(",")'`).
