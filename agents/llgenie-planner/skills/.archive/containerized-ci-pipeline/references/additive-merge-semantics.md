# Additive merge semantics (a measured value may only be RAISED)

A pipeline that merges a fresh capture into a store usually carries a rule like *"additive only — an
existing value may be raised, never shrunk"*. That rule is easy to implement as something stricter
and wrong: **fill only when empty**. The two are not the same, and the second fails in both
directions.

## The rule, precisely

When two measurements of the SAME run both state a dimension (`weight_gb`, `context_tokens`,
`system_ram_min`, a per-run footprint), the merged row keeps the **larger** figure.

Why fill-only is wrong, both ways:

- **It forbids raising.** The first figure that ever lands is pinned for ever, so a later, more
  accurate capture of the same source can never correct it. The store then publishes a number that
  contradicts the source it cites — and every other gate stays green because they read the store, not
  the source.
- **It does not even prevent shrinking.** The merged representative row is picked by engagement or
  date, not by which member stated the figure. If the representative is the member carrying the
  SMALLER value, the row is already set from it and the fill-only loop never corrects it — so the
  merge silently shrinks a stored value, the exact opposite of the rule it claims to enforce.

## Implementation shape

```python
def raised(stored, incoming):
    if empty(incoming):            # an unstated dimension never removes a stated one
        return stored
    if empty(stored):
        return coerce(incoming)    # the fill half is still correct
    a, b = magnitude(stored), magnitude(incoming)   # parse a leading number + unit: GB / MB
    if a is not None and b is not None:
        return coerce(incoming) if b > a else stored
    return stored                  # text dimension: never replace a spelling

# ... then, per dimension:
kept = raised(row.get(k), member.get(k))
if kept is not None:               # absent, not null: never store None/""
    row[k] = kept
```

Decision table:

| stored | incoming | kept |
|---|---|---|
| `5.93GB` | `5.95GB` | `5.95GB` |
| `5.95GB` | `5.13GB` | `5.95GB` |
| absent | `5.95GB` | `5.95GB` |
| `5.95GB` | absent | `5.95GB` |
| `26.10.1` (text) | `26.9.6` (text) | `26.10.1` — a version is not a magnitude |

Normalise units before comparing (`950MB` < `1.2GB`), and compare the NUMBERS, not the strings:
`"5.13"` sorts above `"5.9"` as text.

## Test shape that actually holds

Test the merge function directly, with four checks and BOTH orderings:

1. a larger incoming **raises** a stored value;
2. the same answer when the capture arrives first (order independence);
3. a smaller incoming **never wins**;
4. an empty row still **adopts** a stated value, and an unstated one is **never invented**.

A single-ordering test passes against the broken implementation, because the merge's representative
choice can happen to carry the right member. Prove the guard bites: copy the base version in
(`git show origin/<base>:scripts/<generator>.py > scripts/<generator>.py`), run the focused module,
confirm the specific check FAILS, then restore. A new guard that passes on the old code is asserting
the wrong ordering.

## The neighbouring gap worth reporting

Nothing in such a pipeline re-reads a measurement's `source_post` / raw capture, so a stored value can
contradict the source it cites indefinitely and no schema, link or table check will see it. When you
are in this area, note it as its own issue: a report-only check that re-derives stated values from the
captured text and flags a stored value present in neither. Report-only first, so one parser miss
cannot red a refresh.
