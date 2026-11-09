# Reviewing an engine source-build conversion (`prebuilt: true → false`)

A conversion PR flips one or more engine cells from "start FROM the upstream image" to "build the
engine from its pinned source, then COPY the artifacts onto a slim runtime base". The review is a
supply-chain question first and a build question second: **does the pinned commit actually resolve to
what the PR claims it is, and does each variant carry the runners it says it does?** Everything below
is measured, not read off the PR body.

## 1. The params schema — read `variants`, not `cells`

`containers/engines/params/<engine>.json` is **not** a flat list of cells. Its shape:

```json
{
  "_generated_by": "…", "engine": "Ollama", "id": "ollama",
  "repo": "…", "ref": "v0.40.12", "pinned": "f067033f9126993b6172bdfffa71a74ad693fda4",
  "native": …, 
  "variants": { "cuda": {…}, "rocm": {…}, "vulkan": {…}, "cpu": {…} }
}
```

`variants` is a **dict keyed by backend**, and the tag and the sha are **top-level** (`ref` / `pinned`).
Parsing with `d['cells']` raises `KeyError`; iterating `d['variants']` and calling `.get()` on each
entry raises `AttributeError` once you index it as a dict-of-strings — it is dict-of-dicts. Print the
keys first (`print(json.dumps(d, indent=1)[:600])`) before writing a loop, so the shape is measured.

Per-variant keys that matter for the review: `prebuilt` (must be `false` after the conversion), `base`
(the devel image that has the toolchain), `runtime_base` (the slim image shipped), `runtime_copy`
(the artifact paths copied from build → runtime), `apt` (build deps like `golang-go`), `install`
(the build script lines).

## 2. Prove the pin IS the tag, via the API — and that a moved tag cannot change the build

A pinned sha is a supply-chain claim: "this commit is what builds, regardless of the tag". Verify both
halves — that the sha matches the tag *today*, and that the build fetches the sha (not just the tag), so
a future tag move does not silently change the artifact:

```bash
gh api repos/asimov-agent/llgenie/git/ref/tags/<tag> --jq .object.sha   # must equal the pinned field
# and in the variant's install lines: git clone -b <tag> … then git fetch origin <sha> + checkout --detach
```

`git clone -b <tag>` alone proves only "the tag at clone time"; the `git fetch origin <sha> && git
checkout --detach <sha>` (or equivalent) is what makes the pin immovable. If the build clones the tag
and never checks out the pinned sha, say so — a moved tag then rebuilds different code and the pin is
decorative.

## 3. Each variant must install the CPU runner PLUS its own backend runner

An ollama-style cell vendors llama.cpp runners per backend. The claim (and the README's) is usually
"the CPU runner in every image, the backend runner per backend". Verify per variant by extracting the
`llama-server-<x>` names from the `install` list, not by trusting the count:

```python
for b, c in d['variants'].items():
    runners = {m.split('_v')[0] for line in c['install'] for m in re.findall(r'llama-server-([a-z0-9_]+)', line)}
    print(b, sorted(runners))
# cuda→['cpu','cuda']  rocm→['cpu','rocm']  vulkan→['cpu','vulkan']  cpu→['cpu']
```

The asymmetry is the finding: a cuda image missing the CPU runner fails every CPU-only model the same
image is supposed to serve; a cpu image building a cuda runner is wasted build time. Name the exact
variant and runner that is wrong, not "the install list looks off".

## 4. Dockerfile: multi-stage, and the runtime base carries the runtime deps

Each `containers/engines/dockerfiles/<engine>/Dockerfile.<arch>` after conversion follows one shape:

```
FROM <devel base>:<pin> AS build
  apt install <toolchain> (e.g. golang-go)
  WORKDIR /opt/llgenie/app ; COPY engine_runner.py entrypoint.sh params.json .
  RUN python3 engine_runner.py install params.json     # the build itself
FROM <runtime base>                                     # slim: -runtime / ubuntu:24.04
  apt install ca-certificates curl python3 libgomp1     # runtime-only libs
  COPY --from=build <runtime_copy paths>
  COPY --from=build /opt/llgenie/app
```

Check the `runtime_base` actually carries what the built binary links against at *run* time (a CPU
build needing `libgomp1`, a CUDA build needing the `-runtime` driver image, not `-devel`). The
`engine_runner.py` mechanism is pre-existing — a conversion is normally **config-only** (params JSON +
generated Dockerfiles), so a diff that rewrites `engine_runner.py` itself is out of scope and worth a
question, while a diff that touches only params + Dockerfiles is the expected shape and mirrors every
prior conversion (llama.cpp, sglang, vllm).

## 5. The census/guard test and the docs must move with it

The source guard (`scripts/engine_source_guard.py` / `tests/test_engine_source_guard.py` family) asserts
the exact **source-vs-prebuilt count** and any recorded exception (e.g. `litert/cpu`, whose pip package is
a Bazel wheel over a Git-LFS `prebuilt/*.so`, so building it would still ship a foreign binary). Run it
and quote the count line — a conversion that flips a cell without updating the count reds this gate.
The docs are a second census: `README.md` and `docs/ENGINES.md` carry the same "still prebuilt today"
list and the per-engine conversion sentence, and `check-docs` reads them. When the conversion changes
which cells are prebuilt, every one of those sentences is a claim to re-derive, not just the headline.

## 6. Why the cells were prebuilt, and the tracking issue

Cells ship `prebuilt: true` because their **build cost is unmeasured** — that is the stated reason each
one carries its own linked issue. A conversion PR should cite that issue (and the build time it
measured); a conversion with no cost measurement behind it is converting a deliberate deferral into an
unmeasured build without the evidence the deferral asked for. Read the PR body for the cost figure and
say whether it clears the bar the issue set.

## 7. The verdict while `linux / unit` is still running

All the content above is verifiable offline (pin API, params parse, runner lists, guard census, docs),
and it can be fully green while the deciding `linux / unit` job is still `make ci-unit`. That is **not**
a verdict — report the content findings as ready, arm a completion watcher on the run, and hold the
verdict for the completed run at the head. Post the start comment (bookend) with the content evidence
so the claim is on record, then the verdict when the run concludes.
