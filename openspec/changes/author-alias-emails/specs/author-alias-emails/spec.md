# author-alias-emails

## ADDED Requirements

### Requirement: An allowlisted email is the identity, and its alias names are the spellings it may carry

`make check-pr-authors` SHALL accept a commit whose author **email** is one of the allowlisted
addresses and whose display name appears in that address's explicit alias list, regardless of which
alias spelling was used. It SHALL reject a commit whose email is not allowlisted, even when its display
name is an allowed alias, and it SHALL reject a commit whose allowlisted display name carries an address
that is not the one the map assigns to it. The finding SHALL name the email as the identity that was
read.

WHEN a commit's author email is allowlisted and its display name is in that email's alias list
THEN the guard SHALL report no violation; and WHEN the email is a lookalike of an allowlisted address
(`andy.holtd@protonmail.com`) or the author is unknown, THEN the guard SHALL exit non-zero naming the
email.

#### Scenario: an allowlisted email under an alias display name

Given a real git repository whose branch adds a commit authored `Andy <andy.holst@protonmail.com>`
When  `check_pr_authors.py check --base main --head HEAD` runs
Then  it exits 0 and reports no violation

- **Test:** `tests/test_pr_authors.py::test_an_allowlisted_email_under_an_alias_name_passes`

#### Scenario: an allowlisted alias carrying a typo address

Given a real git repository whose branch adds a commit authored `Andy Holst <andy.holtd@protonmail.com>`
When  the guard reads the range
Then  it exits non-zero and the finding names `andy.holtd@protonmail.com`

- **Test:** `tests/test_pr_authors.py::test_an_alias_name_with_a_typo_email_still_fails`

#### Scenario: an unknown author is a negative control

Given a real git repository whose branch adds a commit authored `Hermes Agent <agent@asimov.local>`
When  the guard reads the range
Then  it exits non-zero, so the widened allowlist has not become a pass-through

- **Test:** `tests/test_pr_authors.py::test_an_unknown_author_still_reds_the_gate`

#### Scenario: every alias maps to exactly one allowlisted address

Given the alias map in `scripts/check_pr_authors.py`
When  it is read
Then  every key is an allowlisted email and no display name belongs to two addresses

- **Test:** `tests/test_pr_authors.py::test_the_alias_map_is_one_address_per_name`

### Requirement: The existing author rule keeps its scope and its producers

The commit scan SHALL keep reading only the commits a PR ADDS (`git rev-list --no-merges
<base>..<head>`, merges and base-reachable commits out of scope), SHALL keep checking every
`Co-authored-by:` trailer, and the producer half SHALL keep accepting exactly the allowlisted names and
addresses — now the expanded alias sets, read from the same one map.

WHEN an allowed author carries a `Co-authored-by:` trailer
THEN an alias of an allowlisted address SHALL be accepted and a foreign address SHALL still be reported.

#### Scenario: a co-author alias is accepted and a foreign address is not

Given a commit authored by an allowed identity whose trailer reads
      `Co-authored-by: Mr. Asimov <support@docondee.com>`
When  the guard reads the range
Then  nothing is reported; and the trailer `Co-authored-by: Andy Holst <not.andy@example.com>` is still
      reported

- **Test:** `tests/test_pr_authors.py::test_an_allowed_co_author_is_accepted`
