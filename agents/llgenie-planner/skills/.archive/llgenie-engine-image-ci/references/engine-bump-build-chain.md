# How a bumped engine actually gets built (and who does which part)

Answering "does the bot build the engine with the right parameters?" needs the CHAIN, not one file.
Three different actors, and confusing them is how a wrong answer gets shipped.

## The chain

| Step | Actor | Command / artifact |
|---|---|---|
| 1. bump | deterministic Python, **no LLM** | `make engine-bump ENGINE=<id>` → `scripts/engine_bump.py`: `plan` (git ls-remote) → `pin` (frontmatter) → `derive` (`scripts/engine_params_derive.py`) → `apply` → `make generate-engine-params` |
| 2. doc review | **Hermes agent leg** | `make engine-params-review-brief` → `make engine-params-review` (`hermes -z … -s engine-params-review,bot-unattended`) → `make engine-params-review-apply`; the PR body gets `params-review-section.md` |
| 3. build | **CI matrix, no LLM** | PR's `ci.yml`: `engine-matrix` (`make -s list-engine-images CI=1 JSON=1 CHANGED=<base>`) → `engine-image` job → `make build-engine ENGINE=… ARCH=<variant>` |
| 4. test | CI, per row | `make test-engine-stage ENGINE=… ARCH=… TEST=serve|detect` |
| 5. publish | CI, after tests | `make push-engine ENGINE=… ARCH=…` |
| — rebase | deterministic | `engine-bump-rebase.yml` daily: forward-merges latest `main` into open `chore/engine-bump-*` PRs. Builds nothing. |

So: **the agent reviews/proposes parameters; CI builds them.** Never say "the bot builds the engine".

## Verify it on the live tree, in this order

```bash
make -s list-engine-images CI=1 JSON=1 | python3 -c 'import json,sys;d=json.load(sys.stdin);print(len(d["include"]),"rows");[print(r) for r in d["include"][:5]]'
#   → engine × backend rows, each with the test mode (cpu=serve, GPU=detect)

python3 -c 'import json;d=json.load(open("containers/engines/params/llama.cpp.json"));print(d["pinned"][:12]);[print(k, v.get("arch"), list(v.get("build_args",{}))) for k,v in d["variants"].items()]'
#   → per-variant GPU arch lists (e.g. cuda '75;80;86;89;90;120') + build args

git show <bump-merge-sha> --stat      # pin + params JSON + Dockerfile must move TOGETHER
```

`scripts/engine_image.py::build` is the proof the params are what gets compiled: it reads
`containers/engines/params/<id>.json`, selects `variants[<variant>]`, writes that object as
`params.json` into the build context, and uses
`containers/engines/dockerfiles/<id>/Dockerfile.<variant>`.

## Facts that get stated wrongly

- **"One image per arch" is false.** The matrix is per engine × **backend** (cpu/cuda/rocm/vulkan).
  GPU coverage is a FAT build: one CUDA image covering SM 75–120, one ROCm image covering
  gfx1030–gfx1201. The `arch` list in the params selects inside that build, it does not pick an image.
- **`engine-bump-rebase` has nothing to do with trending data.** It only rebases bump PRs onto `main`.
  Trending updates arrive through `registry-sync` (vendors `data/models.json` from the sibling
  registry) and become *new-engine* issues via `engine-skill-gap`, not engine rebuilds.
- **The documentation-review leg is advisory.** `continue-on-error: true`: a failed or empty review
  still opens the PR (the body says so). It is not a gate; do not describe it as one.
- **The review leg may propose, never invent.** `scripts/engine_params_review.py` accepts a proposal
  only when the flag AND its quoted evidence appear verbatim in the named upstream file; everything
  else is dropped and listed. The deterministic derive stays the only writer of the skill.
- **A derive hard-fail is not a failed run.** The pin still moves, the PR still opens, the body
  carries "Manual review required", and the PR's build is red on purpose until a human fixes the skill.

## When the question is "is this already implemented in the repo?"

`git fetch origin main` first and read `git show origin/main:<path>` / `git grep <symbol> origin/main`.
A local checkout is routinely many merged PRs behind (auto-merge lands PRs continuously), so a
missing directory in the working tree proves nothing — in one session `.hermes/skills/` was absent
locally while `origin/main` already carried nine skills and the review leg. Answer from the fetched
main, and say which sha you read.
