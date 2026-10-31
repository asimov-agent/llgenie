# 2026-10-31 — The engine lane's skill is versioned; and what "measured_on" cannot tell you

## What landed

`agents/llgenie-engine-improver/skills/llgenie-engine-improver/SKILL.md` and its four
`references/*.md` now live in the tree, byte-identical to the live profile copy (#1115). Before this,
the lane's operating loop existed only on one host: a sync would have left the profile with rules
that pointed at files it did not have, and no reviewer could read what the lane was told to do.

The skill carries the loop itself (sync the trending list → each engine's arch types → verify each
`(engine, arch)` builds a Linux image → offer only hardware-correct pairs), the pipeline duty, and
six lessons learned while doing it.

## The distinction worth keeping: `measured_on` is not `server`

While checking the classifier in #1099, the fixture turned out to be **mixed**:

```
tests/fixtures/trend-list-matrix.json at origin/main (adf2c4e1), Bonsai 2 4B rows:
  162 total · 48 route to 'llama.cpp (PrismML fork)' @ 128   ← correct
               33 record   plain 'llama.cpp' @ 6.0           ← the ternary defect, on main today
               81 unserved
```

`Bonsai 2 4B` is ternary (`GGML_TYPE_PQ2_0` = 142), so **plain `llama.cpp` cannot load the file at
all**. Those 33 rows name an engine that cannot execute the model — and 17 of them are `arch='cuda'`,
which is verbatim #1073's close condition.

**Regenerating the fixture does not fix this.** With the classifier applied the render changes
`server` and `tps` on 8 models, and on `Bonsai 2 4B` it flips 16 currently-correct
`PrismML fork @128` rows to plain `llama.cpp @6.0`. So the regen is **possible and it would be
wrong** — the fixture stays 0 diff vs main and the matrix test stays held until the routing lands.

## Why regenerating does not fix it — the selection divergence (#1124)

```
mp.rank_engines(bonsai-2-4b, "cpu")[0]  → llama.cpp        6.0    same_hw=True
mp.rank_engines(bonsai-2-4b, "cuda")[0] → llama.cpp-prism  128.0  same_hw=True
tlm.trend_rows(registry, 8, 8, "cuda")  → llama.cpp        6.0    ← the phone's run
```

Two selection paths disagree for the same model and host, and the golden is generated from
`trend_rows`. Making `trend_rows` follow `rank_engines` was tried and **reverted** — on a cpu host the
ranking *also* prefers the phone's plain `llama.cpp`, because `same_hw=True` is all it knows and the
tensor type is missing from the registry. **The divergence is a symptom; both paths are wrong in the
same direction.** The fix needs the per-file GGUF tensor type, which `registry-sync` does not record.

## Two harness lessons, both found the hard way

- **The frontmatter boundary is a markdown section boundary.** `# H1` directly after the closing
  `---` reds `make lint`; a blank line separates them.
- **`linux/unit` did not run for #1099 at `faf5943a`** (only `scope`/`holds`/`guard` did), so a
  "held red by design" claim was a local measurement reported as though a gate shared it. A check
  that never runs cannot pass, fail, or hold — filed as #1137.

## Related

#1115 (this), #1099 (the classifier + held-red fixture), #1073 (ternary routing), #1124 (the
selection divergence), #1137 (the absent unit gate), #1109 (the hermetic snapshot that made the
offline measurement possible).
