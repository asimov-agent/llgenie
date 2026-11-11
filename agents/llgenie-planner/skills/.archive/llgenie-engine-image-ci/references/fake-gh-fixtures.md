# A fake `gh` that can carry a multi-step bot flow

The llgenie bots shell out to `gh`, so the no-mock way to test them is a fake `gh` script written to a temp
dir, put on `PATH`, that records its argv and answers the exact queries the product builds
(`scripts/issue_implementer.py`, `scripts/auto_merge.py`, `scripts/verify_closure.py` are all tested this
way). The base shape is in `SKILL.md` ("Testing a bot that shells out to `gh`"); this file is the depth
that costs a debugging round when the flow is longer than one call.

## Embedding the fixture: exactly ONE `json.dumps`

```python
# right — the child gets `PR = json.loads('{"state": …}')` and holds a dict
f"PR = json.loads({json.dumps(pr)!r})"
# wrong — double-encodes: the child holds the JSON TEXT as a str
f"PR = json.loads({json.dumps(json.dumps(pr))!r})"
```

The wrong form makes the fake print a JSON *string*, the product's `json.loads` returns a `str`, and the
first `view.get(...)` dies with `'str' object has no attribute 'get'` — which reads as a product bug.

Same class: never put `json.dumps(x)` straight into the f-string body (`{'a': 1}` becomes a Python SET
literal, prints single quotes, and the caller's `json.loads` fails on `Expecting property name enclosed in
double quotes`), and never reference a name defined only inside the generated script from the template.

## Model the post-write state, not one frozen answer

A flow the product reads twice cannot be tested against one fixture: `decide → merge → verify` reads the
PR again after the merge, so a fake whose `pr view` always answers `state: OPEN` makes the follow-up
verification exit 2 (`not MERGED`) even though the merge argv was right.

Give the fake a marker file:

```python
if os.path.exists(log + ".merged"):
    PR = dict(PR, state="MERGED")
if args[:2] == ["pr", "view"]:
    print(json.dumps(PR)); sys.exit(0)
if args[:2] == ["pr", "merge"]:
    open(log + ".merged", "w").write("1"); print("merged"); sys.exit(0)
```

## Assert the token, not just the argv, when the token is the change

A monkeypatched `_gh` proves the argv and nothing about credentials. When the point of the change is
*which* token each write receives, record the child's environment per call and assert it:

```python
fh.write(json.dumps({"argv": args, "token": os.environ.get("GH_TOKEN")}) + "\n")
```

Then assert the ORDER too (the comment/marker run before the side effect), and add a `deny=` list to the
fake so a refused write (`addComment` → rc 1) can be simulated: the test then asserts the PR was never
created, which is the property the ordering exists for.

## What to assert on the recorded calls

- The exact argv (`--squash`, `--delete-branch`, `--match-head-commit <sha>`, the `--repo` slug).
- The absence of a call (`pr merge` must not appear on a deferred/blocked path).
- The count (a second run must not double-claim or double-comment).
- The exit code of the CLI, separately from the argv: "deferred to a human" exits 0 with a reason, it
does not fail.
