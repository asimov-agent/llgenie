# An allowlisted email under an alias display name is the same person (issue #971)

## Why

`scripts/check_pr_authors.py` keys its allowlist **name → email** (`ALLOWED: dict[str, str]`) and its
docstring defended that: *"the name must match exactly AND the email must be the one that belongs to
that name."* The intent — a reader of `git log` must be able to tell who wrote a line — is right. The
consequence is not: a commit authored `Andy <andy.holst@protonmail.com>` is the owner by every other
reading (`git shortlog`, `git blame`, mail all resolve to one address) and is rejected anyway.

Measured on PR #919's range (`python3 scripts/check_pr_authors.py check --base 5338bc6d --head
4fb3bf3a`, head `4fb3bf3a`, run `40846990086` job `guard`): **7 violation(s)**, of which **6** are
`Andy <andy.holst@protonmail.com>` — the owner's own allowlisted address under a shorter name — and
**1** is `fd31640d Andy Holst <andy.holtd@protonmail.com>`, a genuine typo that must keep failing.

The alias spelling is not something the committer always chooses: GitHub writes a squash commit's
author from the account's **profile display name**, and a producer that sets only the email inherits
whatever name the host has. Measured on this tree (`git log --all --format='%an <%ae>' | sort | uniq -c
| sort -rn`):

```
    764 Andy Holst <andy.holst@protonmail.com>
    549 Asimov Agent <support@docondee.com>
    234 Andy <andy.holst@protonmail.com>
     98 Mr. Asimov <support@docondee.com>
     48 andyholst <andy.holst@protonmail.com>
     34 github-actions[bot] <andy.holst@protonmail.com>
      3 Andy Holst <andy.holtd@protonmail.com>
```

Every one of the top five is one of the two allowlisted people. The gate cannot tell *"someone else
wrote this"* from *"the same person, shorter display name, same address"*, and each false red costs a
full `linux / unit` matrix.

## What Changes

- **`scripts/check_pr_authors.py`** — one explicit alias map keyed by the allowlisted **email**:

  ```python
  ALIASES: dict[str, frozenset[str]] = {
      "andy.holst@protonmail.com": frozenset({"Andy Holst", "Andy", "andyholst"}),
      "support@docondee.com": frozenset({"Asimov Agent", "Mr. Asimov"}),
  }
  ALLOWED: dict[str, str] = {name: email for email, names in ALIASES.items() for name in names}
  ```

  The **email is the identity**; a display name is only allowed when the alias list of the address it
  carries names it. `ALLOWED` stays derived — so `git_identity.py`'s `ALLOWED["Asimov Agent"]`, the
  producer scan and the seam's `pins_identity` keep working unchanged — and the name → email intent
  still holds for every pair the map does not name: `Andy <andy.holtd@protonmail.com>`,
  `Andy <someone@else.example>` and `github-actions[bot] <andy.holst@protonmail.com>` all fail.
  A finding's evidence names the **email** as the identity that was matched, not only the name.
- **`AGENTS.md` / `docs/BOTS.md`** — state the rule as it now is: the email is the identity and each
  allowlisted address has a named alias list; the alias list is a NAME list, never an email list.
- **`tests/test_pr_authors.py`** — alias-name pass, typo-email fail, unknown-author negative control,
  and the existing vocabulary tests updated to the new policy.
- **`agent-wiki/` + `CHANGES.md`** — the dated work record and its index row.

## Not covered

- The commits on #919 themselves. `fd31640d`'s typo is a real violation and it is the owner's commit to
  re-author; the alias commits need no rewrite once this lands. #919's content is out of scope.
- Widening the email allowlist. A new address is a policy decision, not an alias: the map is a set of
  display names per allowlisted address.
