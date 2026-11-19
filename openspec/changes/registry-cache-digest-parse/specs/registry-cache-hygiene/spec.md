# registry-cache-hygiene (MODIFIED)

## MODIFIED Requirements

### Requirement: digest_of resolves the digest from the real imagetools inspect output

`_extract_digest(ref, text)` and `digest_of(ref)` MUST resolve the full content digest from the
imagetools inspect output whether it aligns as `Digest:    sha256:...` (colon, then padding spaces —
the format Go's text/tabwriter emits and what GHCR publishes) or as the legacy single-space
`digest: sha256:...`. A no-digest output MUST raise `SystemExit` naming the ref, keeping the exact
current wording so the gc failure output keeps its shape.

#### Scenario: the captured padded imagetools format resolves

- **Given** the three-line inspect header captured verbatim from GHCR
  (`Name:`, `MediaType:`, `Digest:    sha256:c5299a41...`) as the sole `run_ok` output
- **When** `digest_of` parses that output
- **Then** it returns the full content digest `sha256:c5299a4136c4473606ff8eeedefd28ace2c783c05ee1f7e974b88de08bd36650`
- **Test:** `tests/test_registry_cache_orphans.py::test_digest_of_reads_the_captured_padded_imagetools_format`

#### Scenario: the legacy single-space form still resolves

- **Given** the old `digest: sha256:...` line with exactly one space after the colon
- **When** `digest_of` parses it
- **Then** it returns the same full content digest
- **Test:** `tests/test_registry_cache_orphans.py::test_digest_of_still_reads_the_legacy_single_space_form`

#### Scenario: a no-digest output is refused with the canonical wording

- **Given** an inspect output whose header carries no digest line
- **When** `digest_of` cannot find a digest
- **Then** it raises `SystemExit` whose message contains `no digest for` and the ref
- **Test:** `tests/test_registry_cache_orphans.py::test_digest_of_refuses_a_no_digest_output`

### Requirement: the deleted-injection gates stay green and unbroadened

The existing `run_gc` injected-seam tests (which pass `digest_resolver=`) MUST continue to pass
unmodified, and `digest_of` MUST do its own parsing without a `digest_resolver` seam — the real parser
is now covered by the three scenarios above.

#### Scenario: injected-resolver gc tests remain unchanged

- **Given** the pre-existing `run_gc` gates that inject `digest_resolver`
- **When** `make test-unit` runs the module's tests
- **Then** those tests still pass without modification
- **Test:** `tests/test_registry_cache_orphans.py` gc seam tests (`test_gc_without_yes_deletes_nothing`,
  `test_gc_deletes_exactly_the_orphans_and_verifies_zero`, `test_gc_reports_failure_when_a_delete_leaves_an_orphan`)
