---
name: agent-soul-versioning
description: "Use when an agent's SOUL/skills change must land as a PR."
version: 1.0.1
author: LLGenie Security Officer
license: MIT
metadata:
  hermes:
    tags: [agents, governance, github, review]
    related_skills: [security-scan-ops, pr-finalization, github-workflow-admission, github]
---

# Land a behaviour change to an agent as a repository artifact

> **Companion, not a duplicate:** the canonical-splice mechanics live in the sibling `security-scan-ops`
> skill's `agent-soul-versioning.md` reference (extracting the bullet from the issuing issue, re-splicing
> `agents/standing-rules.md`, the `fleet-block-drift` gate). This skill carries the *roster and
> declaration* half — exemptions, manifest rules, the lane rule, the tree gate and the protected-file
> consent rule — so read both when versioning a full profile (issue #1060).

## When to Use

An agent's rules, role text or skills must change and the change has to be reviewable: a fleet-wide
standing rule was agreed in an issue, a lane needs its own house rules, a profile's behaviour is
being audited. The behaviour lives in the repo (`agents/<profile>/SOUL.md` plus
`agents/<profile>/skills/`, indexed by `agents/manifest.json`), never only in the machine's private
profile home — an instruction that changes what a credential-holding agent does is the one change
nobody could diff otherwise.

## Procedure

1. **Read the canonical text from its source of truth, mechanically.** The issuing issue (or the
   owner's message) is canonical; a bullet relayed through chat is a paraphrase and will differ in
   wording. Extract the fenced block instead of retyping it:
   ```bash
   gh issue view <N> --repo <o>/<r> --json body --jq .body > /tmp/issue.md
   python3 - <<'PY'
   import re, pathlib
   t = pathlib.Path('/tmp/issue.md').read_text()
   block = [b for b in re.findall(r"```\n(.*?)\n```\n", t, re.S) if b.startswith("## ")][0]
   pathlib.Path('/tmp/canonical.txt').write_text(block)
   print(block)
   PY
   ```
   Re-run this every time the issue changes: the canonical block **grows** (rules get appended), and
   the new bullet is usually longer than the version quoted in chat. The same is true of the **tree's
   own canonical file** when one exists on the consolidation branch: after a rebase onto a moved base,
   re-extract from that file and re-splice the WHOLE block — other lanes add bullets, so a SOUL that was
   byte-identical before the rebase drifts and reds `fleet-block-drift` with just "the section is
   present but differs from the canonical text".
2. **Check whether the tree already exists on the default branch.**
   ```bash
   git fetch origin && git ls-tree -d origin/main | grep -c agents/     # 0 => the tree is unmerged
   ```
   If `agents/` is not on `main` yet, it exists only on an open PR: **stack your branch on that PR's
   head** and say so in the PR body ("stacked on #X; the diff collapses to these files once #X
   lands"). A profile directory added to `main` without a manifest entry is a gate failure — the
   checker reports "a profile directory the manifest does not list — a tree nobody syncs and nobody
   gates" — so the manifest edit must travel in the same PR, not a follow-up.
2b. **Where the tree keeps an exemption roster, keep it honest per profile.** When the canonical block
   grows, every profile that does not yet state it may need an **exemption entry naming that profile's
   OWNING lane** (only a lane may edit its own SOUL, so the gap travels as an owner, never as a patch
   by another lane). When your own lane now states the block, DELETE your own entry — a stale exemption
   ("no longer describes a real gap") is itself a gate failure. Add new-rule exemptions only while the
   gap is real, with a reason that names the rule and the owning lane.
3. **Splice, do not rewrite.** Keep the lane's own rules in the prose above, then the canonical block
   unchanged at the end, under its original heading:
   ```python
   old, new = canonical_old, canonical_new
   s = path.read_text()
   assert old in s, "the previous canonical block is not present verbatim"
   path.write_text(s.replace(old, new))
   assert new in path.read_text()
   ```
   Assert byte-identity (`canon in text`), not "looks right" — that assertion is also the evidence to
   quote in the PR body.
4. **Declare only rules that are true.** The manifest maps a profile to the standing rules its
   `SOUL.md` must keep stating, and the checker only knows a fixed set of keys. Declaring a rule the
   lane does not actually follow (e.g. `never-merge` for a lane whose changes land through the repo's
   own green-PR auto-merge) makes the manifest a lie that the gate happily enforces. Declare the
   subset that holds and state the real mechanic in the prose.
5. **Give the profile at least one rule the shared block cannot express** — that is the whole point
   of a per-lane file: what the fleet rule means *here*, with the failure it prevents.
6. **Run the tree's own gate before pushing**, not the generic suite:
   ```bash
   python3 scripts/check_agent_profiles.py check     # or the repo's `make check-agent-profiles`
   ```
   It checks manifest↔directory agreement, frontmatter names, and **credential shapes in every
   committed file** — these files are read by an agent holding write credentials, so a token in them
   is a leak with a diff. Never paste a real key into a doc to illustrate a rule.
7. **Commit with the allowlisted identity (name AND email), quoted**, then open the PR
   **ready-for-review** naming the issue. Re-read the author of the pushed commits via the API before
   claiming the PR is clean.

## Pitfalls

- **Never open a draft PR.** A draft is invisible to the merge queue, to auto-merge and to reviewers;
  for a lane whose output is a finding, "draft" reads as "blocked on approvals" while the exposure
  stays open. If a PR is somehow a draft, `gh pr ready` it **before** reporting it.
- **A paraphrase is a defect here.** The value of this tree is that a diff across profiles shows the
  same text; a reworded bullet silently forks the fleet rules. Replace the whole block from the
  source, never hand-append the one new line — order and wording drift otherwise.
- **Do not push while a run at the head is in progress.** `cancel-in-progress` makes an authorised
  push destructive: check the PR's in-progress checks first, then push.
- **Editing the private profile instead of the repo** looks like it worked (behaviour changes on this
  machine) and leaves no diff anyone can review — that is the failure the tree exists to prevent.
- **A direct write to a profile's `SOUL.md` can be blocked by a protected-file approval that times out,
  and a timeout is not consent.** Do not route around it (another path, a rename, a copy via the repo)
  and do not retry forever: put the exact replacement sentence in the PR body, open the PR without it,
  and report the consent-block as the one open item. The reviewer/owner applies it; the rule is stated,
  not smuggled.
- **A behaviour change is not a code change**: the PR body should quote the verbatim assertion and
  the gate output, not a narrative of what the rules now "mean".
