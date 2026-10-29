# Auditing and routing tests that hit the real network out of a hermetic gate

A `linux / unit`-style gate has a time budget and a flake budget. A large share of both comes from
one class of test: one that opens a real hub URL for a model/dataset/registry. This is the recipe for
finding those tests and routing each to a pattern that is fast and hermetic.

## 1. Static scan: build the candidate list, know it is only a candidate list

A reference to an endpoint is NOT proof the test opens it — many are mock URLs in fixtures, a local
in-process server, or a probe helper. Grep the unit test directory for a coincident open-call and an
endpoint reference on the same line, per file:

```
OPEN = re.compile(r"(requests\.(get|head|post)|urlopen|urlretrieve|hf_hub_download|snapshot_download|huggingface_hub|from_pretrained)")
HF   = re.compile(r"huggingface\.co|hf\.co|HUGGINGFACE_HUB|HF_|hub\.hf|huggingface_hub")
for each test_*.py: count lines matching OPEN AND HF; note whether the file marks `@pytest.mark.network`
                   or its tests appear in the unit suite's deselection roster
```

The count is the candidate list. Report it as such — "N reference lines, none marked, none
quarantined" is the finding a reviewer reads; do not dress the grep count up as a network-opens count.

## 2. Ground truth is execution: `--durations=N` over the suspects

A grep tells you what LOOKS network-bound. `pytest --durations=25 <suspect files>` on the exact files
tells you what IS. Run it over the named files, not the whole suite — the local unauthenticated full
suite can be an order of magnitude slower than CI because the Hub-touching tests crawl, and a whole
suite run is a multi-hour wait for the same signal the named-files pulse gives in minutes.

Attach the durations output (slowest table) to the issue **before** editing any test: it is the
baseline the refactor is judged against, and the ceiling a later PR's timing is held to.

## 3. Route each real-call test into exactly one pattern

| pattern | what it is | when to use it |
|---|---|---|
| loopback | real function against a real in-process server (a `test_hub_*` transient-budget style test reusing a local responsive server) | the function's logic is what matters; no external state is needed |
| liveness | HEAD/curl through ONE probe helper that proves the link returns and fails with a legible string naming the dead URL and the caller | the test needs to know the upstream file still exists; link rot must be a named message, not a raw 404 |
| `@pytest.mark.network` | a real call that cannot be loopback or liveness, quarantined from the default gate | everything else — never a silent real call in the default path |

Pick ONE liveness helper as the authority (a `hub_probe` module). Do not let two files spell the
proof two ways: pin the unit gate so a second authority fails a scan.

## 4. The marker mechanism so a refactor has a target

- add the marker to the pytest config: `network: a test that calls the real hub; excluded from the
  hermetic gate`;
- the suite selection gets `-m "not network"` (or an equivalent explicit deselect) so any
  `@pytest.mark.network` test is out of `ci-unit` by construction;
- a pinning test that scans the unit suite for an **unmarked** real endpoint open (a real call with no
  `network` mark and no loopback/liveness provenance) and fails on the first — the gate's own proof
  that nothing slipped back in. A widened gate passes its own gate trivially; only the pin reports it.

### 4a. A substring census is the wrong detector — model-id downloads slip through, loopback does not

A grep for a network primitive COINCIDENT with a `huggingface.co` string misses the repo's OWN
network entry: `mp.download(model_dict, …)` reaches the Hub with the host encoded as a model *id* in
a data dict, and no line shows a URL literal — so a host-string census reports "0 open primitives"
for a file that really downloads. Build the pin from what actually REACHES the Hub, as a set of
OR-rules that must not cross-fire:

- URL-host reach: a network primitive whose URL literal (or a var assigned a URL literal earlier in
  scope) carries the hub host;
- model-id reach: the repo's own download/meta entries (`mp.download`/`mp.gguf_files`/`mp.hf_size`)
  whose first argument is a model dict (module- or test-scope) with a live `hf` id, in a scope with
  no loopback server;
- must NOT fire on: `def urlopen(...)` redefinitions (a monkeypatch STUB, not a call — drop `def`
  lines before scanning), planning-only entry points (`plan_download`), local-resolve entry points
  (`resolve_local`), or loopback probes — the loopback indicator often lives in a helper
  contextmanager/fixture, NOT in each test body, so per-test loopback detection is unreliable; a test
  that BINDS a server is offline by construction.

Do not treat a "4 real opens" count from a substring census as ground truth: re-run the hardened pin
over the whole selection and report what it actually flags — the true unmarked-real-call count is
commonly LARGER than the census said, and that larger count is the acceptance finding.

### 4b. Assert at the collection/execution boundary, and pin the wiring chain

The stronger shape of the acceptance is "the default unit path must execute zero network-marked
tests" — a grep that the marker exists is not that. Run the gate's OWN command to the boundary that
determines execution and assert no network-marked node is collected:

```
pytest --collect-only -q -m "not network" <the suite selection>   # assert no @pytest.mark.network node present
```

And wherever a gate seam is added, add a test that pins the whole wiring chain so the seam cannot
hover in one script while the workflow/make target silently stops reaching it: assert
`ci.yml → (reused pipeline job) → make ci-unit → test-unit → scripts/unit_tests.py run` (whose
default carries the `-m` expression), and that the network twin (`test-unit-network`) runs `--marker
network` on the SAME expression.

## 5. Coordinate before editing

When a model/registry/data-path lane owns the files that are slow, hand the audit + durations to it
and take the gate side (marker, pin, ledger) yourself. Agree the liveness-helper name up front so the
split does not produce two spellings of the same proof.
