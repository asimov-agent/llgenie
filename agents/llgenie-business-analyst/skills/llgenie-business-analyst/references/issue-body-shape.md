# Issue body shape gate (`scripts/issue_body.py`)

The repo ships a body-shape checker. Refining a draft into an "issue-ready" body means making it pass this gate, not just writing prose in six loose headings.

## Contract

- Required sections, **in this positional order**:
  1. `Problem`
  2. `Why it matters`
  3. `How we fix it`
  4. `Benefit`
  5. `Acceptance criteria`
  6. `Technical`
- One **optional** section: `Not covered`, and only between `Benefit` and `Technical` (misplacement is reported).
- `Technical` must be the **last** section and must not appear twice.
- `Acceptance criteria` must contain at least one `- [ ]` item — a heading with no tickable item "states no done".
- Any other heading is an **unknown section** and fails. There is no free-form heading budget: fold extra content into an existing section rather than inventing `## Who it is for` or similar.
- The order check is positional: sections present but out of order are reported as out-of-order, not as missing.

## Validate before posting

Import the module and run its own checker — do not hand-eyeball the headings:

```python
import sys; sys.path.insert(0, 'scripts')
from issue_body import missing
body = open('body.md').read()
problems = missing(body)          # [] means it conforms
print('OK' if not problems else problems)
```

## Post and verify

- Edit the issue body, never add a restating comment: `gh issue edit <n> --repo asimov-agent/llgenie --body-file <path>`.
- Read the body back and re-run the checks on what the API returned:

```python
v = json.loads(subprocess.run(['gh','issue','view',str(n),'--repo','asimov-agent/llgenie','--json','body'],capture_output=True,text=True).stdout)
b = v['body']
assert not missing(b)
assert '## Acceptance criteria' in b and '- [ ]' in b
```

Report the gate result and an `acceptance_criteria_bool` per issue to the planner so the relay has a machine-checkable fact, not an adjective.
