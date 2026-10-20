# catalog-link-probe

## ADDED Requirements

### Requirement: Only a dead link fails the catalog sync

The quant-catalog link probe SHALL distinguish a readable file (`ok`, HTTP 200/206), a file that exists
but is not readable with the credential in hand (`gated`, HTTP 401/403) and a link that does not resolve
(`dead`, anything else), and the sync SHALL fail only on `dead` — while reporting the gated links so a
credential-gated model stays visible.

WHEN a newly generated catalog link answers 401 or 403
THEN the sync SHALL complete, write the table, and name the URL as gated.

#### Scenario: the statuses are classified apart

Given a probe answer of 200, 401, 403 and 404
When  the classifier is asked about each
Then  it reports ok, gated, gated and dead respectively

- **Test:** `tests/test_quant_generator_edges.py::test_probe_status_classifies_gated_apart_from_dead`

#### Scenario: a gated new link does not red the sync

Given a committed table and a refresh whose new link is gated
When  the sync runs
Then  it exits zero, writes the table, and the output reports the link as gated

- **Test:** `tests/test_quant_generator_edges.py::test_a_gated_new_link_does_not_red_the_sync`

#### Scenario: a dead new link still fails

Given a refresh whose new link answers 404
When  the sync runs
Then  it exits non-zero and does not write the table

- **Test:** `tests/test_quant_generator_edges.py::test_sync_fails_when_a_new_link_is_dead`
