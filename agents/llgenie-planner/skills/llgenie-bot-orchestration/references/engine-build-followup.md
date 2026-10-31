# Engine build changes need a delegated build+test follow-up

**Rule (owner directive, issue #1085):** an engine build change is not reviewable when no build
and no test has been executed. Open the follow-up issue **with** the PR, delegated to
`llgenie-engine-improver`, so verification never depends on the author's own report.

## Why

A cached build reports `available -> no rebuild`, which *looks* like evidence and is not. #1075
(ollama cells) reached "reviewable" with three of six criteria open: AC3/AC4 author-reported only,
AC6 unmeasured because the build hit the cache. The PR that changes how four cells are built had
never been built cold and never been served.

## The four things the follow-up must do

1. **Run the pipeline** — dispatch the engine build workflow and quote **the run id you dispatched**,
   never a previous run.
2. **Build locally** — build the changed cells on the host. A lane rule that says "CI is the sole
   builder" must not become the reason a change ships unbuilt; if the local image is not the shipped
   one, state how it differs. Reconcile the rule in the lane's versioned SOUL rather than overriding
   it silently (the #1076 pattern).
3. **Test locally** — serve at least one cell to `READY` and record the stage `detect` output.
4. **Record the numbers** — wall-clock and per-cell image size in the change note, **each beside the
   run id or command that produced it**. A wall-clock without a run id is a claim about time.

## Failure modes to refuse

- Substituting the author's cached `no rebuild` for a measurement. **An honest `NOT MET` is
  actionable; a cached number is worse than no number** because it cannot be told apart from
  evidence.
- Measuring on a different artifact: a locally-built image is not the image CI ships, so a local
  wall-clock measures the wrong thing unless the difference is stated.
- Treating `prebuilt: false` in the registry as proof of a successful build — it is a declaration.

## Related

- #1085 — the rule itself, first instance #1075/#936 (ollama cells).
- #1076 — the pattern for amending a lane rule in the repository instead of overriding it.
- #1092 — the engine verification loop this rule feeds.
