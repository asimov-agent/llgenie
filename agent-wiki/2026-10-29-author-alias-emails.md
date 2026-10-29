# An allowlisted email is the identity; its alias names are the spellings it may carry (#971)

## What changed

`scripts/check_pr_authors.py` keyed its allowlist **name → email** and required an exact name match, so
a commit authored `Andy <andy.holst@protonmail.com>` — the owner, under a shorter display name — was a
violation. Measured on PR #919's range (`check --base 5338bc6d --head 4fb3bf3a`, head `4fb3bf3a`): 7
violations, 6 of them that alias and 1 the genuine typo `fd31640d Andy Holst
<andy.holtd@protonmail.com>`.

The policy is now one explicit map keyed by the allowlisted **address**, whose value is the display
names that address may be written under:

```python
ALIASES = {
    "andy.holst@protonmail.com": frozenset({"Andy Holst", "Andy", "andyholst"}),
    "support@docondee.com": frozenset({"Asimov Agent", "Mr. Asimov"}),
}
ALLOWED = {name: email for email, names in ALIASES.items() for name in names}
```

`ALLOWED` stays derived, so `scripts/git_identity.py` (`ALLOWED["Asimov Agent"]`), the producer scan
and the seam's `pins_identity` are unchanged. `_identity_finding` matches on the address and its alias
list; the finding's evidence now names the **address** as the identity that was read.

## Decisions

- **The address is the key, not the name.** GitHub writes a squash commit's author name from the
  account's profile display name and a producer that sets only the email inherits the host's name, so
  the committer cannot always control the display name; the address is what identifies the person.
- **`Mr. Asimov` belongs to `support@docondee.com`**, not to the owner's address the issue conjectured:
  history carries it 98 times under that address (`git log --all --format='%an <%ae>'`).
- **The alias list is a NAME list, never an email list.** `andy.holtd@protonmail.com` and
  `someone@else.example` still fail, and `Andy <someone@else.example>` fails even though `Andy` is an
  alias — the pair must be one the map states.

## Verified

- `python3 scripts/check_pr_authors.py check --base 5338bc6d --head 4fb3bf3a` → **1 violation**
  (`fd31640d`, the typo), down from 7; the six alias commits pass. The remaining one is the owner's
  commit to re-author and is explicitly out of this change's scope.
- `tests/test_pr_authors.py` + `tests/test_git_identity.py` → **38 passed** in `llgenie/test:latest`
  (alias pass, typo-email fail, unknown-author negative control, one-address-per-name map test).
- The control: restoring the pre-change `scripts/check_pr_authors.py` reds the alias test (see the PR
  body for the counted output).

## Open

`AGENTS.md`'s bullet still says `Andy`, `andyholst` and `Mr. Asimov` FAIL. That file is protected and
the write needs the owner's consent, which this unattended run could not obtain — the correction is
filed as its own issue so the drift is tracked rather than left in prose.

Closes #971.
