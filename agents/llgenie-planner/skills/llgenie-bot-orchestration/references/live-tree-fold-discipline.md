# live→tree fold discipline (#1273)

A lane's *live* agent-profile (what the credential actually runs) drifts ahead of the reviewed *tree* (`agents/<lane>/…`). Folding it back is versioning hygiene (#791: behaviour is versioned in the repo), NOT a CI-red repair — the two are filed and routed separately.

## Rules

- **Byte-identical fold.** Copy the CURRENT live file verbatim into the tree. Verify with a blob/sha comparison (`git rev-parse origin/main:<path>` vs live file sha256) — not "looks right".
- **Bind to the sha measured at branch time.** If live grows DURING the run, that delta is a NEW residual for the NEXT vehicle, not scope-creep on this one. Do not chase a moving live file; re-measure and re-file.
- **Size-limit content goes in `references/`, not the SKILL body.** When `SKILL.md` is near the ~100k limit, the new rule text lives in a `references/<topic>.md` the SKILL points at — folding the rule into the body risks overflowing. The reference must exist in the tree for the SKILL's link to resolve (a dangling reference is exactly what reds `test_agent_profiles`).
- **`sync-agent-profile CHECK=1` only** for the verification mode; never write-mode while a live file is ahead (it truncates silently).
- **Fold lane never merges/arms** (#1088): report the real completed `linux/unit` verdict + run id + headSha, never the merge event.
- **Preflight a fresh `origin/main` sha** and write it into the start comment; bookend with a finish comment (head sha + proving run id).

## Distinguishing fold vs gate-red

A fold is *needed* when `sync-agent-profile CHECK=1` shows live≠tree and nothing in CI is red from it. A fold is *forced* (and tracked as a CI-red issue) when a dangling reference / stale render makes a real gate (e.g. `test_agent_profiles`, `test_engine_skill_gap`) fail in `ci-unit`. File the CI-red to the owning lane; file the fold as its own hygiene vehicle so the lane stays productive between reds.
