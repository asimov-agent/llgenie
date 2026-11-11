# Supply-chain pinning — Actions by SHA, tools by immutable image

Two hardening jobs that come up together: stop third-party GitHub Actions from floating on tags, and
run security tooling from images this repository builds and pins. Both are "rewrite a token across
many files" jobs, so the same pitfalls apply.

## 1. Pin every third-party Action to a full commit SHA

A tag is a moving pointer inside someone else's repository — a force-push or a compromised release
changes what your repo executes with no commit here.

### Resolve tags to commits

```bash
gh api repos/<owner>/<repo>/git/ref/tags/<tag> --jq '.object.sha,.object.type'
# type == "tag" (annotated) -> follow it once more, to the COMMIT:
gh api repos/<owner>/<repo>/git/tags/<sha> --jq '.object.sha'
```

Annotated tags are common (`astral-sh/setup-uv` is one). A resolver that stops at the ref returns the
*tag object's* sha, which is not a commit and will not run.

### Rewrite, keeping the tag readable

`uses: actions/checkout@<40-hex> # v4` — pin the SHA, keep `# <tag>` as a trailing comment. The
comment is what makes a 40-hex line reviewable AND what an `update` command re-resolves later.

One API read per `(repo, tag)` — memoize, or a 56-occurrence tree makes 56 calls.

### Exemptions that are correct

- `./.github/actions/...` and `./.github/workflows/...` — this repo's own content at the commit being
  run; pinning is meaningless.
- `uses:` values with no `/` (a matrix value such as `uses: job`, a variable) — not an action ref.
  A gate that refuses text it cannot classify gets turned off instead of fixed.

### Ship it as check / report / update

- `check` — fail on any non-local ref that is not `^[0-9a-f]{40}$`. Stdlib only, so the host gate and
  CI run identical code.
- `report` — every ref with its pin state, `file:line`, and tag; this is what a reader debugs with.
- `update` — re-resolve each `# tag` comment and rewrite; must be idempotent (a second run is
  byte-identical, or the fix produces an uncommittable diff).

Prove the gate is not vacuous: run `check` on the DEFAULT branch before the rewrite and quote the
non-zero exit naming each floating ref, then show 0 after.

**Fail on floating, never on stale.** A pin several releases behind still runs reviewed code;
freshness is `update`'s reviewed job. Conflating the two makes the gate demand churn.

## 2. Immutable scanner / tool images

A scanner installed at scan time is a mutable tool on a mutable base with network access while it
judges the tree. Build one image per tool and pin it:

- **Base pinned by digest** — `FROM cgr.dev/chainguard/wolfi-base@sha256:<64 hex>`.
- **Tool pinned to an exact version** — `ARG TOOL_VERSION=1.2.3-r0` + `apk add "tool=${TOOL_VERSION}"`.
  A range compiles to a different binary on the next build.
- **Published tag is a content hash** of the Dockerfile — one tag can never mean two builds, and a
  bump cannot reuse a published tag.
- **A generated `digests.json`** carries each tool's version + hash ref; consumers read that file.
  Any Dockerfile edit requires regenerating it, and the gate must fail when it disagrees with the file
  (a stale entry points a scan at a build that no longer matches the tree).
- **Verify by running it**: `docker run <image> version` and assert the pinned version appears.
  "It built" is not "it works".

Wolfi notes that cost a build cycle each: `apk update` is needed before `apk search` answers, many
scanner CLIs are packaged (`trivy`, `grype`, `syft`, `semgrep` are), and **wolfi-base has no
`/usr/local/bin`** — `mkdir -p` it before `curl -o` there, or the download dies with
`curl: (23) client returned ERROR on write`. For a tool Wolfi does not package, fetch the
version-named release asset and verify it against the release's published sha256 in the Dockerfile.

Keep the publish policy (push vs pull-request run, fork behaviour) in the script, not in a
scenario-scoped workflow `if:` — a YAML condition is how a publish silently stops happening.

## Pitfalls

- **Grep the test tree for the literal before a mass rewrite.** A test asserting
  `"uses: docker/setup-buildx-action@v3" in file` turns red the moment you pin it. Search
  `tests/` and `scripts/` for the exact string, then relax the assertion to a pattern
  (`@[0-9a-f]{40}(\s+#\s*v\d+)?`).
- **A new CI gate must be classified by the repo's own gate roster.** Many repos carry a script that
  fails when a target newly added to the unit gate is neither a fast re-check nor a documented
  deferral. Add the DEFERRED entry with a reason; do not widen a pinned "fast gates" list — such a
  list is a contract to an earlier decision and a test usually asserts its exact membership.
- **A gate's own regex can match the good form.** A floating-`FROM` detector
  `\S+:(\w[\w.-]*)` also matches `image@sha256:<hex>`, because `\S+` swallows the `@sha256` part.
  Anchor the rule (`^FROM\s+(?!\S*@sha256:)(\S+?):(\w[\w.-]*)\s*$`) and prove each rule with a
  fixture tree, not by eye.
- **Regenerate the digests after ANY Dockerfile edit** — including a fix made while debugging a
  build. The content hash changes, and an image whose recorded ref no longer matches the file is
  exactly the staleness the gate exists to catch.
- **A containerized test run leaves root-owned caches in the worktree.** pytest inside the test
  image writes `__pycache__` as root; the next `write_file` in that tree fails on permissions.
  `sudo rm -rf tests/__pycache__ scripts/__pycache__` (or `sudo chown -R $(id -u):$(id -g) .`)
  before staging, so the commit contains only the change.

## When to use

Trigger this reference when a task says: pin Actions, stop floating tags, harden the CI supply
chain, build a scanner/tool image, make a scan reproducible, or "immutable image for <tool>".
