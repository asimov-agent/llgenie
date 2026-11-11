#!/usr/bin/env python3
"""Restate a non-canonical GitHub issue body into the repo's canonical six-section
shape, by MAKING A DRAFT ONLY (never posts). One invocation per issue.

Why a generator instead of hand-authored markdown: a ticket FAMILY (dozens of
sibling issues sharing one skeleton, e.g. per-pipeline verification tickets) uses
non-canonical headings -- `## Problem` / `## Proposal ...` / `## Acceptance ...` /
`## Ownership` / `## Related` -- with the ONLY per-ticket difference being a single
naming token and one criterion line. Hand-editing N of those is where content
gets lost; a generator that reads the original body extracts the per-ticket
specifics and emits the canonical skeleton around them, so the unique details are
derived, not retyped.

Usage:
    python3 restate_issue_canonical.py <issue-number> <body-file> <scripts-dir> [out.md]

Gate the draft with the repo's OWN parser before posting (never eyeball headings):
    python3 restate_issue_canonical.py 123 /tmp/b123.md scripts /tmp/123-canonical.md
Then post, then RE-GATE the LIVE fetched body -- missing() on the draft only
proves you authored a good string, not that GitHub stored it.
"""
import os
import re
import sys

# Canonical headings, in gate order. `## Technical` MUST be last.
CANON = ["## Problem", "## Why it matters", "## How we fix it",
         "## Benefit", "## Acceptance criteria", "## Technical"]

TPL = """<!-- refiner: rule-37 restate of #{n} into canonical six-section body; per-ticket specifics extracted from the source body. Acceptance criteria un-ticked by design (verification evidence lands on a `verify` comment, then ticks). -->

## Problem

{problem}

## Why it matters

`{subject}` is one tracked unit whose health is invisible as a whole: no ticket
proves it works end-to-end, so a regression goes unmeasured indefinitely.

## How we fix it

{how}

## Benefit

One per-unit deliverable in the tracked family, so a completed run (or a *named*
deliberate skip, or a recorded blocked state) ticks this ticket and moves the
umbrella one row closer to fully verified instead of leaving it silently unverified.

## Acceptance criteria

- [ ] {c1}
- [ ] {c2}
- [ ] {c3}

## Technical

- **Ownership / board state:** {ownership}
- **Evidence:** post the run id + conclusion as a `verify` comment; ticks in the
  umbrella ledger only after a `verify` comment cites a completed run id.
- **Related:** {related}
"""


def load_missing(scripts_dir):
    sys.path.insert(0, scripts_dir)
    import issue_body  # the repo's own parser -- never restate its rules
    return issue_body.missing


def section(body, name):
    m = re.search(rf'## {re.escape(name)}[^\n]*\n(.*?)(?=\n## |\Z)', body, re.S)
    return m.group(1).strip() if m else ''


def numbered(block):
    """Split a numbered-criteria block into individual criterion texts."""
    out = []
    for line in block.splitlines():
        line = line.strip()
        m = re.match(r'^(\d+)\.\s*(.+)$', line)
        if m:
            out.append(m.group(2).strip())
    return out


def main():
    n = int(sys.argv[1])
    src = open(sys.argv[2]).read()
    missing = load_missing(sys.argv[3])

    if not missing(src):
        print(f'#{n} already canonical -- nothing to do')
        sys.exit(0)

    # Subject: the single naming token unique to this ticket (backticked name,
    # branch slug, workflow name). Prefer an explicit `verify \`X\`` / `for \`X\``
    # mention, else the first inline code span.
    m = (re.search(r'verify `([A-Za-z0-9_.-]+)`', src)
         or re.search(r'`([A-Za-z0-9_.-]+)`', src))
    subject = m.group(1) if m else f'unit-{n}'

    crit = numbered(section(src, 'Acceptance'))
    c1 = crit[0] if crit else 'a current-main run reaches a completing state (success or a deliberate, named skip; queued/stuck/cancelled-without-superseding is a finding).'
    # c2 is the ONLY per-ticket line -- derive it, never share a cousin's text.
    c2 = crit[1] if len(crit) > 1 else 'the run performs its intended effect (measured, not asserted).'
    c3 = crit[2] if len(crit) > 2 else 'a blocked/disabled state is recorded with run id + date; any defect found becomes a NEW issue for the owning lane.'

    problem = ' '.join(section(src, 'Problem').split()) or f'No ticket proves #{n} ({subject}) works end-to-end.'
    how = ' '.join(section(src, 'Proposal').split()) or ' '.join(section(src, 'How we fix it').split()) \
        or f'Exercise `{subject}` and record the measured result. Out of scope: altering the workflow, weakening a gate, fixing a defect found (that becomes a NEW issue).'
    ownership = ' '.join(section(src, 'Ownership').split())
    related = ' '.join(section(src, 'Related').split())

    out = TPL.format(n=n, subject=subject, problem=problem, how=how, c1=c1, c2=c2,
                     c3=c3, ownership=ownership, related=related)

    outpath = sys.argv[4] if len(sys.argv) > 4 else f'/tmp/{n}-canonical.md'
    os.makedirs(os.path.dirname(outpath) or '.', exist_ok=True)
    open(outpath, 'w').write(out)

    miss = missing(out)
    heads = [l for l in out.splitlines() if l.startswith('## ')]
    ac = len(re.findall(r'^- \[ \]', out, re.M))
    print(f'#{n} draft -> {outpath}')
    print(f'  missing(): {miss if miss else "NONE - gate-clean"}')
    print(f'  last heading: {heads[-1] if heads else "(none)"}  ac-rows: {ac}')
    print(f'  per-ticket criterion 2 (verify it is THIS ticket, not a cousin): {c2[:90]}')


if __name__ == '__main__':
    main()
