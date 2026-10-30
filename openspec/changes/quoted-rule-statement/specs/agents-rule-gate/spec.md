# agents-rule-gate

## ADDED Requirements

### Requirement: a standing rule is stated, not merely quoted

A `SOUL.md` satisfies a standing rule its manifest entry declares only when the rule appears in the
file's **own voice**. A rule that appears only inside a quotation — a fenced code block, a
blockquote line, or a `"…"` span — MUST be a finding that names the file and says the occurrence is
a quotation. An instruction an agent is not under must never satisfy the gate for the rule it quotes.

WHEN a profile's SOUL quotes a declared standing rule but no longer states it
THEN `make check-agent-profiles` fails with `standing-rule-quoted`, naming the SOUL.

#### Scenario: a SOUL that only quotes a declared rule fails, naming the file

- **Given** a manifest declaring `never-merge` for a profile whose `SOUL.md` carries that rule only inside a `"…"` span
- **When** the gate reads the tree
- **Then** it reports `standing-rule-quoted` for `agents/<profile>/SOUL.md` and exits non-zero
- **Test:** `tests/test_agent_profiles.py::test_a_soul_that_only_quotes_never_merge_is_rejected`

#### Scenario: a fenced block or a blockquote is a quotation too

- **Given** a `SOUL.md` that states the rule nowhere and mentions it only inside a fenced code block, and a second whose only mention is a blockquote line
- **When** the gate reads each tree
- **Then** both are `standing-rule-quoted` findings, because neither shape is an instruction the agent runs under
- **Test:** `tests/test_agent_profiles.py::test_a_rule_inside_a_fence_or_a_blockquote_is_also_only_quoted`

#### Scenario: stating the rule passes, and stating it while quoting the owner still passes

- **Given** a `SOUL.md` that states the rule, and a second that states it and *also* quotes the owner's instruction it overrides
- **When** the gate reads each tree
- **Then** neither is a finding — the quoted span is removed before matching, and the statement survives its removal
- **Test:** `tests/test_agent_profiles.py::test_a_stated_rule_passes_even_when_the_soul_also_quotes_it`

### Requirement: an entry that declares no rule is reported unprotected

A manifest entry with `rules: []` gates nothing. The gate MUST report it as `UNPROTECTED`, in both
`check` and `report`, rather than accepting it as a pass — "no rule to check" and "the rule held"
must not read the same. It is a report, not a failure: a profile may legitimately declare no rule.
It MUST NOT be folded into the findings that fail the gate, because five of the seven committed
profiles declare none and a permanently red gate is a filtered gate.

WHEN a profile's manifest entry declares no standing rule
THEN the gate's output names that profile as `UNPROTECTED`, and the exit code stays 0.

#### Scenario: an empty rule list is reported, not silently green

- **Given** a manifest whose profile declares `rules: []`
- **When** the gate renders its report
- **Then** the profile is named `UNPROTECTED` in the output
- **And** the finding list carries no `standing-rule` entry for it — the manifest, not the SOUL, is what is silent
- **Test:** `tests/test_agent_profiles.py::test_a_profile_with_no_declared_rules_is_reported_unprotected`
