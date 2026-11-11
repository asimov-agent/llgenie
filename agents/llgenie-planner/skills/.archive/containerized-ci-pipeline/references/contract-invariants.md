# Contract invariants: enforce where the value is WRITTEN

For a pipeline whose store is governed by JSON-Schema contracts (required keys, enums, a
regex on the id) and whose values are produced by an LLM step, then merged by code.

## The gate belongs at the funnel, not at validation

A schema violation that reaches validation has already cost a CI cycle and a hand-repair.
Every value the contract constrains has at least two funnels; fix BOTH:

| funnel | what it is | why it alone is not enough |
|---|---|---|
| the write path | the one function every producer writes through (`--write-raw`-style) | stops the bad value entering the artifact… |
| ingest | the merge/normalise step | …but a hand-written or older artifact still bypasses the writer |
| validation | the schema check | it can only REJECT — that is a red PR, not a repair |

So: normalise at the writer AND at ingest, and keep validation as the backstop. A value
that already satisfies the contract must pass through **byte-identical**, so a stored key
is never renamed by a normaliser.

## A prompt that names the bad value does not hold

Telling the model "`FP4-Local` and `NVFP4` must never be written as the engine" — in so
many words, interpolated into every prompt — was followed by exactly that value on the
next run, and again two shapes later by a different invention. Prompt instructions are
necessary and **not sufficient**. Put the refusal in code, where the value becomes data,
and make the log line name the offending value, the record and the source:

```
[ingest] REFUSED fabricated engine 'FP4-Local' on <model>: the name carries the
quantization token 'FP4'; post <url> — a t/s with no engine is not a valid entry
```

## Refuse only the PROVABLE shape

A guard that guesses produces false positives that are worse than the disease: a
"name is a substring of the model id" rule refused `WebLLM`, a real engine that
legitimately appears inside `Llama-3.1-8B (WebLLM)`, and broke an unrelated module's
fixture. Refuse only what cannot be legitimate — a quantization token inside an engine
name, a hardware product token inside an engine name — and let anything merely
implausible through, where validation still fails loudly for a human.

Corollary: an "unknown but plausible" value MUST keep failing validation. The guard
suppresses FALSE data, not real-but-new data.

## Keep an issue-triggering signature COARSE

A daily analysis that files an issue when its "gap set" changed must fingerprint the
DIMENSION, not the per-item list. A per-model signature
(`missing:<key>:<model-id>`) grows every time the store grows, so a dataset that gains
models re-files the identical gap forever — a measured case produced a dozen issues for
one dimension, with the item count climbing while nothing was fixed.

- fingerprint: `missing:<key>`, `unstructured:<key>`, `contract:<key>`;
- keep the per-item detail in the report/issue BODY so a human still sees which items
  and how many;
- make a genuinely NEW dimension still change the signature (test it), and keep the
  open-issue dedup marker as the second gate.

## Test the refusal, not just the happy path

Every contract guard needs three fixtures, driven through the real function (no stand-in
for the logic): the exact measured bad value; a value that LOOKS bad but is legitimate
(the false-positive case); and a value that is merely unknown (must pass through and
still fail validation). Assert the log/refusal names what it refused — a silent drop is
indistinguishable from data loss.
