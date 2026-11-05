# vllm build + guard lessons

## torchcodec ABI: preinstall from the backend index, same as torchvision/torchaudio

vLLM requires `torchcodec >= 0.14` (both `requirements/cpu.txt` and `requirements/cuda.txt`, the
video-decoding backend). The default-PyPI wheel is built against the stable torch C++ ABI, so at
`vllm --version` import `torchcodec.decoders -> _core -> load_image_library()` calls
`torch.ops.load_library(torchcodec/libtorchcodec_image.so)` and dies with the generic
`OSError: Could not load this library: .../libtorchcodec_image.so` when the pip-installed torch is a
different minor/backend build (measured: torch 2.13.0+cpu vs PyPI torchcodec 0.17.0). Fix: add
`torchcodec` to the SAME backend-index preinstall line as torch/torchvision/torchaudio
(`--index-url https://download.pytorch.org/whl/{torch_backend}`); cpu and cuXXX both publish the
ABI-matched `0.17.0+<backend>` cp312 wheel, and the already-installed wheel satisfies `>= 0.14` so the
`-e .` resolver keeps it. The `.so` bundles its own av/image libs (auditwheel `torchcodec.libs/`), so it
is not a missing-ffmpeg problem.

## A vendored-Rust `TOML parse error at line N, column 1` on `uv pip install -e .` is a NON-fatal warning

`warning: Failed to parse pyproject.toml during settings discovery ... TOML parse error / unknown field
exclude-dependencies` comes from a `[tool.uv]` typo in UPSTREAM's pyproject; the `-e .` build proceeds
(`Built vllm`, packages installed) and only the later DETECT step is what can fail. Don't "fix" upstream's
file to silence it — verify the build actually built before touching anything.

## check-pr-closing reds on stale `github.event.pull_request.base.sha` when main outlived the PR

On a long-lived PR where `main` advanced past the value GitHub snapshots, EVERY guard run passes
`PR_BASE = github.event.pull_request.base.sha` (frozen at an older main sha, e.g. 23f90235) while
`actions/checkout` checks out `refs/pull/N/merge = Merge <head> into <CURRENT main>` (e.g. a5aff03b).
`check_pr_closing` then ranges `--base <stale> .. HEAD(merge)` and sweeps in every main commit merged
between the two, red-ding on issues the PR never touched (e.g. "claim #1467, #1470, #1471, #1506, #1507,
#1511"). Tell it apart from a real body problem: run locally
`make check-pr-closing PR_BASE=origin/main` — if it passes at base=origin/main but CI reds, the event
`base.sha` is stale, not the PR. A `gh pr edit` body touch does NOT dispatch a new `pull_request` run, so
the stale snapshot persists. Durable fix belongs in `check_pr_closing`: range
`git merge-base(base,head)..head` instead of the raw event base; file that as its own issue.

**Unblock without waiting for that fix: push one NEW additive commit with a plain `git push`.** A fresh
commit dispatches a `synchronize` event that carries a NEW `base.sha` (current main), so the guard's range
collapses to the branch's own commits and goes green. Do NOT force-push or rebase to "refresh" the base —
that rewrites a co-owned branch and gains nothing over an additive commit. The additive commit must be
real content (a docs/status line), not an empty commit, and it must leave every tracked text file ending
in a single `\n` (see next section) or the ci-lint scope gate reds.

## "file missing a trailing newline" from a text-mode read is usually a FALSE conclusion

`git show <rev>:<path>`, `git cat-file -p <rev>:<path>` piped through a Python text capture, and any
`subprocess.run(..., capture_output=True, text=True)` all strip or mangle the final newline — reading
`b'...owner wins).'` where the blob really ends `b'...owner wins).\n'`. Never claim a tracked file lacks a
trailing newline (or "fix" it) from a text-mode capture. Read raw bytes: `pathlib.Path(p).read_bytes()`
on the checked-out file, or clone the pushed branch and run the real gate locally
(`python3 scripts/lint_linefeeds.py`; it prints `LINT FAIL — files missing a trailing newline`). The lint
gate checks ALL tracked text files at the head, so a newline edit that lands after your own commit leaves
HEAD's blob without it until you commit the fix — re-read the pushed blob's raw bytes before concluding.
