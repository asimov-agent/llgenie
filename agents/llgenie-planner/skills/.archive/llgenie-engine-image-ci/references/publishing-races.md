# Publishing a tag a run is itself building (two traps that red a correct PR)

Both were measured on real llgenie runs; both fixes are on `main` (#675, #674). When a red
PR's log says `denied: … Write organization package` or `was never published`, check these
before suspecting the PR's code.

## A fork PR cannot write GHCR

A `pull_request` run's token is scoped read-only to the BASE repo, so `make push-engine` on a
fork head answers:

```
denied: installation not allowed to Write organization package
[engine-image] FAIL push ghcr.io/asimov-agent/llgenie/sglang:35ce3132-5d1a4f11-cuda
```

That is a permission GitHub never grants a fork PR, not a defect. Do **not** scope it with a
workflow `if:` — `tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` forbids
scenario-scoped step conditions (the decision belongs in a make target or a script). The
policy lives in `scripts/engine_image.py::push`, which sees the registry's own answer: the
denial plus `GITHUB_EVENT_NAME=pull_request` becomes a `::warning` annotation and a
`SKIP publish <ref> … (issue #155)` line with exit 0; a denial on a push run, or any other
push failure, still fails loudly.

## A bump PR's own new tag does not exist yet

`tests/test_ci_publish_order.py` asks the real registry whether every cpu tag `make install`
pulls is published. On a bump PR the new tag is created by the SAME run's parallel
`engine-image-*` job, so requiring it reds the one thing the PR exists to change
(`1 failed, 5195 passed`, twice on linux and macos). Exclude the engines whose
`containers/engines/params/<id>.json` differs from `origin/main` (`git show
origin/main:<path>`), print what was deferred, and leave those tags to
`make ci-wait-engine-images` — the gate that can actually wait (#169).
