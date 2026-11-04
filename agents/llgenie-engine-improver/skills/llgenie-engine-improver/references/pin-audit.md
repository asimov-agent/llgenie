# Pin-validity audit: annotated-tag pins look broken but aren't

When verifying an engine pin is satisfiable during an audit:

- GitHub's `commits/{sha}` API returns **422** on annotated-*tag-object* SHAs
  (the `refs/tags/vX.Y` value), and a direct `git fetch --depth 1 origin <sha>`
  is refused by design (rc 128) when the pin is a tag **object**, not a commit.
  These are NOT missing pins.

Settle with `git ls-remote <repo> 'refs/tags/<ref>' 'refs/tags/<ref>^{}'`:
- first line == `pinned` → the pin IS the tag object, stable and reproducible;
- second `^{}` line → the commit the build actually checkouts.

Before calling a pin force-pushed/moved, replicate the build's own checkout:
`git clone -b <ref> --depth 1` then `git fetch origin tag <ref>` and
`git checkout -q <pinned>` (use the full 40-char sha from `pinned`).
rc 0 and `HEAD == <ref>^{}` means the pin is fine.

Real missing-pin evidence is a commit-sha pin (light/tag peeled) that both the
REST `commits/{sha}` (200-path ≠ pin, or 422 on a commit) and `git ls-remote`
misplace — i.e. the sha does not resolve to any refs/tags or branch.

## Publish-gap ≠ pin-missing
A pin can be fully satisfiable upstream yet UNPUBLISHED in ghcr (issue #1365):
the committed params `pinned` sha hashing to a NEW digest (`5df63a72-0ddd57cc`,
yet only `5df63a72-250e7780` etc. exist) means the committed params were never
rebuilt after the last publish. `docker manifest inspect
gcr.io/<org>/<img>:<pin>-<digest>` rc=1 distinguishes "not published" from
"bad pin". Fix path (a) = republish via engine-build `push=true`
(`gh workflow run -f engine=<id> -f arch=<arch> -f push=true` on the head sha,
never a local build); if a vllm-cuda publish run is ALREADY in flight on the
same ref, do not dispatch a second — watch it (its `Log in to GHCR` step proves
push=true) and verify the tag after.

## "Unsat pin" findings are INDEX-dependent and HEAD-dependent

An issue that records a pin as "unsatisfiable on every reachable index" is a claim about the index
set that was probed and the params that existed then. Before acting, re-check both:

1. **Which index the install actually uses.** A bare `torch==<V>+rocm<V>` preinstall with no
   `--index-url` resolves against default PyPI → unsat. The SAME pin is satisfiable through the ROCm
   wheel index `--extra-index-url https://repo.amd.com/rocm/whl-multi-arch/` (which serves
   `torch-<V>+rocm<V>` wheels), and `download.pytorch.org/whl/rocm*` has 0 of them. An install that
   resolves torch through `requirements/build/rocm.txt` inherits that AMD extra-index from the
   upstream file — so the row builds even though "the pin" looks unsatisfiable in isolation.
2. **Whether the pin still exists on the current head.** The fix that greens the leg often drops the
   explicit pin (shelling to a requirements file instead). Read the variant's `install[]` on the
   branch head before scheduling work against an "unsat pin" ticket; the premise may be already
   displaced.

Probe the index for the actual wheel (a green build leg is the real proof, but this settles it):

```python
import urllib.request, re
def wheels(index, pkg, frag):
    req = urllib.request.Request(f'https://{index}/{pkg}/', headers={'User-Agent': 'x'})
    body = urllib.request.urlopen(req, timeout=30).read().decode()
    return re.findall(rf'{pkg}-{re.escape(frag)}[^"\']*', body)
```

**Pass `headers=` to `urllib.request.Request`, never to `urlopen()`** — `urlopen(url, headers=...)`
raises `unexpected keyword argument 'headers'`; wrap the URL in a Request first.

## Engine-version bump: four independent checks, each can pass alone

Verifying a bump PR (`ref`/`pinned` moves vA -> vB) is FOUR separate checks. A bump that clears one
does not clear the next — report each explicitly instead of one "verified" stamp:

1. **The new pin resolves upstream.** Use the annotated-tag-object settlement above; a 422 on
   `commits/{sha}` is the tag-object case, never "missing pin".
2. **Params text carries no stale OLD version/sha.** Grep the branch head's params row for the old
   ref and old pin in `install[]`, detect and launch text; a bumped `pinned` beside a leftover
   `v<old>` string is a half-done bump.
3. **The container base image tag tracks the bumped version.** A variant's `"base":
   "<org>/<img>:v<old>"` sitting next to `"ref": "v<new>"` compiles the new source INTO the old
   base — real serving drift, and the most commonly missed one because the pin itself is valid.
   Confirm the new tag actually exists in the registry (`docker manifest inspect <base-with-v<new>>`)
   before asserting it, so the finding is "tag exists, params stale" and not a guess.
4. **Build proof, or an explicit "no build result".** When the engine cells are SKIPPED behind a
   shared guard/scope red, there is no build outcome — write "build proof pending, hygiene-blocked"
   and name the blocking batch. Never report a skipped cell as a build failure or as proven.

Drift found on a bump branch goes to the BRANCH OWNER: a verification-only lane reports it in the PR
thread and never edits or force-pushes another lane's bump branch to "just fix" the base tag.

## Serving-drift check

For headless-capable engines confirm the pinned image resolves in ghcr
(`docker manifest inspect ghcr.io/asimov-agent/llgenie/<img>:<pin-params-variant>`
rc 0) and that the on-host `~/bin/llgenie-engine-<id>` launcher's `IMAGE=` refs
the exact committed-params tag (note launcher ids use hyphens: `llama-cpp`,
`llama-cpp-prism`, not underscores). Any mismatch is a `tps`-ranking drift.

Drift is decided by the PINNED upstream CLI, not the default branch: a flag the
current `main` keeps can be absent from the pinned commit (or renamed) and the
params will still pass it, and a flag the pinned commit lacks is the defect.
Read the option table at the pin itself:

```bash
rm -rf /tmp/pc && git init -q /tmp/pc \
  && git -C /tmp/pc remote add origin https://github.com/<org>/<repo> \
  && git -C /tmp/pc fetch --depth 1 origin <pinned-sha> \
  && git -C /tmp/pc checkout -q FETCH_HEAD
cd /tmp/pc && grep -rn 'grep-me-flag' --include='*.py' . | head   # locate the arg table
```

- **Fetch the sha, then `git checkout FETCH_HEAD` — never rely on `FETCH_HEAD`
  after `git clone --branch <tag>`.** A branched clone leaves no `FETCH_HEAD`
  (`unknown revision`) and exits non-zero, which looks like a bad pin; the
  init+`fetch --depth 1 <sha>`+`checkout FETCH_HEAD` shape resolves reproducibly.
  `--filter=blob:none --no-checkout` with an explicit `fetch --depth 1 <sha>`
  also materialises the files (rc 0); a bare `--filter` clone without the sha
  fetch checks out an empty tree and reads as "file missing".
- **A 404 from `raw.githubusercontent.com/<repo>/<sha>/<path>` means that PATH
  does not exist at that ref — not that the flag is gone.** Directory layout
  moves between releases (`vllm/cli/serve.py`, `…/openai/cli_args.py` are 404 on
  later tags while `vllm/engine/arg_utils.py` holds the whole arg table). Grep
the checked-out tree for the flag and take the file that actually defines it;
  probing a remembered path and reporting "flag removed" is a false finding.
  Grep the flag STRINGS (`'--served-model-name',`) rather than prose mentions.
