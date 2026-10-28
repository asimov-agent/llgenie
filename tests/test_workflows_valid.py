"""The workflow gate (issues #330, #329): every YAML file is validated before it can merge.

GitHub refuses a whole workflow file whose `${{ ... }}` it cannot parse, and the refusal is silent — a
0-job run whose `name` is the file path, with no log. `.github/workflows/engine-bump-rebase.yml` shipped
exactly that: a `#` line inside a `run: |` block is script text, not a YAML comment, so a literal
`${{ ... }}` in it was parsed as an expression and the file was refused on every workflow-touching push.

Every rule is tested on a fixture tree first, then the gate is run over THIS repository, because a
convention the repo itself violates is not a convention. The strict YAML parse (no duplicate keys) is
here rather than in the make target on purpose: it needs a YAML library, and the make gate is stdlib-only
so `ci-unit` can run it on the host on Linux and macOS alike.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import check_workflows as cw  # noqa: E402

#: The exact text that shipped in engine-bump-rebase.yml and made GitHub refuse the file.
PRE_FIX_COMMENT = ("          # folded into one `${{ ... }}` so the mode this run took is readable "
                   "in the log.\n")

#: A workflow that passes every rule, so a fixture breaks exactly one thing.
WORKFLOW_OK = (
    "name: a-bot — does one thing\n"
    "on:\n"
    "  workflow_dispatch:\n"
    "\n"
    "jobs:\n"
    "  go:\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - run: echo \"${{ github.repository }}\"\n"
)


class _StrictLoader(yaml.SafeLoader):
    """`yaml.SafeLoader` that refuses a duplicate key, which GitHub also refuses."""


def _no_duplicate_keys(loader: _StrictLoader, node, deep=False):
    mapping: dict = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r} (GitHub refuses the file)", key_node.start_mark)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys)


def _tree(tmp_path: Path, **files: str) -> Path:
    """A fixture root with the given relative paths written verbatim.

    A keyword cannot carry a path, so the keys are the file names under `.github/workflows/` and the
    extra `yaml_text` key writes a top-level `a.yml`. No `.git` is created, so the gate walks the tree.
    """
    root = tmp_path / "repo"
    (root / cw.WORKFLOWS).mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        path = root / "a.yml" if name == "yaml_text" else root / cw.WORKFLOWS / f"{name}.yml"
        path.write_text(text)
    return root


def _keys(root: Path) -> list[str]:
    return [f["key"].split("/")[0] for f in cw.findings(root)]


def _exempt(root: Path, *names: str) -> Path:
    """Record a dated exemption for each workflow name, the way the repository does (#349)."""
    path = root / cw.EXEMPTIONS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "note": "fixture exemptions",
        "decided_utc": "2026-10-28",
        "workflows": {n: {"reason": "exempted by this fixture"} for n in names}}, indent=2) + "\n")
    return path


def _reactor_workflow(*names: str) -> str:
    """A consumer whose `workflow_run.workflows:` block lists `names`, one per line."""
    block = "".join(f"      - {n}\n" for n in names)
    return (
        "name: a-bot \u2014 reacts to a run\n"
        "on:\n"
        "  workflow_run:\n"
        "    workflows:\n" + block +
        "    types: [completed]\n"
        "\n"
        "jobs:\n"
        "  go:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: echo hi\n")


def test_a_malformed_expression_is_a_violation(tmp_path: Path):
    """The class GitHub refuses the whole file for: an expression that cannot be parsed."""

    # Given a workflow whose run block carries an unparseable expression
    root = _tree(tmp_path, a_bot=WORKFLOW_OK + "")

    # When  the same file carries `${{ ... }}`
    (root / cw.WORKFLOWS / "bad.yml").write_text(
        "name: bad — refuses to be parsed\non:\n  workflow_dispatch:\n\njobs:\n  go:\n"
        "    runs-on: ubuntu-latest\n    steps:\n      - run: echo \"${{ ... }}\"\n")

    # Then  the expression violation is reported for that file
    keys = _keys(root)
    assert "workflow-expression" in keys
    assert any("bad.yml" in f["where"] for f in cw.findings(root))


def test_a_valid_expression_is_accepted(tmp_path: Path):
    """The shapes this repo actually uses must not be false positives."""

    # Given the baseline workflow, whose only expression is `${{ github.repository }}`
    root = _tree(tmp_path, a_bot=WORKFLOW_OK)

    # When  the gate reads it
    keys = _keys(root)

    # Then  nothing is reported
    assert keys == []


def test_common_github_expression_shapes_all_parse():
    """Every expression form used in this repository parses — the parser has no false positives."""

    # Given the distinct expression forms this repo's workflows use
    forms = [
        " github.repository ", " matrix.engine != 'none' ", " steps.apply.outputs.rc == '0' && 'yes' "
        "|| 'no (see the step log)' ", " fromJSON(needs.engine-matrix.outputs.matrix) ",
        " !cancelled() && github.event_name == 'push' && needs.engine-image.result == 'success' ",
        " secrets.BUMP_TOKEN || github.token ", " inputs.check || 'make ci-unit' ",
        " github.event.issue.number || inputs.issue_number || '' ", " 3 * 2 + 1 ", " job.steps[0].name ",
        " runner.os == 'Linux' ", " null ", " -matrix.engine ",
        # issue #859: the row-selection axis of the top-tier stage
        " fromJSON(inputs.top_tier_rows) ", " matrix.row != 'none' && runner.os == 'Linux' ",
        " matrix.row != 'none' && always() ", " toJSON(github.event.pull_request.labels.*.name) ",
    ]

    # When  each is parsed
    failures = []
    for form in forms:
        try:
            cw.parse_expression(form)
        except cw.ExpressionError as exc:  # noqa: PERF203 - collect every failure
            failures.append((form, str(exc)))

    # Then  none of them fails
    assert failures == []


def test_the_pre_fix_comment_is_a_violation(tmp_path: Path):
    """The exact line that shipped on main is caught — this is the regression, pinned."""

    # Given a workflow carrying the comment that made GitHub refuse engine-bump-rebase.yml
    root = _tree(tmp_path, a_bot=WORKFLOW_OK + "\n# " + PRE_FIX_COMMENT.strip() + "\n")

    # When  the gate reads it
    keys = _keys(root)

    # Then  it is reported as an unparseable expression, with the offending token named
    assert "workflow-expression" in keys
    evidence = " ".join(f["evidence"] for f in cw.findings(root))
    assert "unexpected token '.'" in evidence


def test_a_missing_trailing_newline_is_a_violation(tmp_path: Path):
    """The repo's linefeed lint spec applies to the YAML files too."""

    # Given a YAML file whose last byte is not a newline
    root = _tree(tmp_path, a_bot=WORKFLOW_OK)
    (root / "a.yml").write_bytes(b"name: no-newline\non: workflow_dispatch")

    # When  the gate reads it
    keys = _keys(root)

    # Then  the missing newline is reported, and the file is otherwise clean
    assert "workflow-newline" in keys
    assert "workflow-expression" not in keys


def test_a_missing_workflow_name_is_a_violation(tmp_path: Path):
    """A workflow with no `name:` is what makes a 0-job run present itself as a path."""

    # Given a workflow with no top-level name
    root = _tree(tmp_path, a_bot="on:\n  workflow_dispatch:\n\njobs:\n  go:\n"
                                 "    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n")

    # When  the gate reads it
    keys = _keys(root)

    # Then  the missing name is reported
    assert "workflow-name" in keys


def test_a_workflow_run_without_a_workflows_list_is_a_violation(tmp_path: Path):
    """GitHub refuses a `workflow_run` trigger that names no workflows — the file is never read."""

    # Given a workflow whose workflow_run lists nothing to react to
    root = _tree(tmp_path, a_bot=(
        "name: a-bot — reacts to a run\n"
        "on:\n"
        "  workflow_run:\n"
        "    types: [completed]\n"
        "\n"
        "jobs:\n"
        "  go:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: echo hi\n"))

    # When  the gate reads it
    keys = _keys(root)

    # Then  the missing workflows list is reported
    assert "workflow-run-refs" in keys


def test_a_workflow_run_that_names_existing_workflows_is_accepted(tmp_path: Path):
    """The shape this repository ships must not be a false positive."""

    # Given a workflow_run that names workflows that exist, and a consumer nothing watches
    root = _tree(tmp_path, a_bot=(
        "name: a-bot — reacts to a run\n"
        "on:\n"
        "  workflow_run:\n"
        "    workflows: [CI, pipeline]\n"
        "    types: [completed]\n"
        "\n"
        "jobs:\n"
        "  go:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: echo hi\n"),
        ci_job=WORKFLOW_OK.replace("a-bot — does one thing", "CI"),
        pipe=WORKFLOW_OK.replace("a-bot — does one thing", "pipeline"))
    _exempt(root, "a-bot — reacts to a run")

    # When  the gate reads it
    keys = _keys(root)

    # Then  nothing is reported: every name exists and the consumer is an exempted decision
    assert keys == []


def test_a_roster_naming_a_workflow_that_does_not_exist_is_a_violation(tmp_path: Path):
    """The silent break #349 predicts: a workflow is renamed and its roster entry stops matching."""

    # Given a roster that still carries the OLD name of a workflow that has since been renamed
    root = _tree(tmp_path, a_bot=_reactor_workflow("a-bot — the OLD name"),
                 renamed=WORKFLOW_OK.replace("a-bot — does one thing", "a-bot — the NEW name"))
    _exempt(root, "a-bot — the NEW name")

    # When  the gate reads it
    items = cw.findings(root)

    # Then  the stale entry is reported, naming the string that matches nothing
    assert "workflow-run-unknown-name" in _keys(root)
    assert any("the OLD name" in f["title"] for f in items), cw.render(items)


def test_a_workflow_no_roster_names_is_a_violation(tmp_path: Path):
    """A new workflow is a one-file change today; nothing used to notice it was never watched."""

    # Given a consumer that watches one workflow while another exists unwatched
    root = _tree(tmp_path, a_bot=_reactor_workflow("watched — a bot"),
                 watched=WORKFLOW_OK.replace("a-bot — does one thing", "watched — a bot"),
                 orphan=WORKFLOW_OK.replace("a-bot — does one thing", "orphan — a bot"))
    _exempt(root, "a-bot — reacts to a run", "watched — a bot")

    # When  the gate reads it
    items = cw.findings(root)

    # Then  the uncovered workflow is reported by file
    assert "workflow-run-uncovered" in _keys(root)
    assert any("orphan.yml" in f["title"] for f in items), cw.render(items)


def test_a_reasoned_exemption_is_accepted_and_a_reasonless_one_is_not(tmp_path: Path):
    """An omission has to be a dated decision with a reason, not an accident."""

    # Given a coverage gap recorded WITH a reason
    root = _tree(tmp_path, a_bot=_reactor_workflow("watched — a bot"),
                 watched=WORKFLOW_OK.replace("a-bot — does one thing", "watched — a bot"),
                 quiet=WORKFLOW_OK.replace("a-bot — does one thing", "quiet — a bot"))
    _exempt(root, "a-bot — reacts to a run", "watched — a bot", "quiet — a bot")

    # When  the gate reads it, and then the same entry loses its reason
    with_reason = cw.findings(root)
    (root / cw.EXEMPTIONS).write_text(json.dumps({"workflows": {
        "a-bot — reacts to a run": {"reason": "a consumer cannot watch itself"},
        "watched — a bot": {"reason": "covered by this fixture's roster"},
        "quiet — a bot": {}}}))

    # Then  the reasoned exemption is clean and the reasonless one is a violation
    assert with_reason == [], cw.render(with_reason)
    assert "workflow-run-exemption-no-reason" in _keys(root)


def test_a_stale_exemption_is_a_violation(tmp_path: Path):
    """The exemption file rots the same way the roster does, so it is checked the same way."""

    # Given an exemption naming a workflow that no longer exists
    root = _tree(tmp_path, a_bot=_reactor_workflow("watched — a bot"),
                 watched=WORKFLOW_OK.replace("a-bot — does one thing", "watched — a bot"))
    _exempt(root, "a-bot — reacts to a run", "watched — a bot", "gone — a bot that was renamed")

    # When  the gate reads it
    keys = _keys(root)

    # Then  the stale entry is reported
    assert "workflow-run-exemption-stale" in keys


def test_a_workflow_may_not_watch_its_own_completion(tmp_path: Path):
    """A self-reference re-fires on its own completion — a loop, not a route."""

    # Given a workflow that lists itself
    root = _tree(tmp_path, a_bot=_reactor_workflow("a-bot — reacts to a run"))

    # When  the gate reads it
    keys = _keys(root)

    # Then  the self-reference is reported
    assert "workflow-run-self" in keys


def test_the_repository_roster_matches_the_workflows_on_disk():
    """The repo passes its own gate: each workflow is watched by name or exempted with a reason."""

    # Given this repository
    names = cw.workflow_names(REPO)
    exempt = cw._exemptions(REPO)
    covered = {n for path in cw.workflow_files(REPO)
               for _, listed in cw.workflow_run_lists(path) for n in listed}

    # When  every workflow is looked for in the roster
    unwatched = sorted(n for n in names if n not in covered and n not in exempt)

    # Then  none is left unwatched, and the roster is not empty
    assert covered, "no workflow_run roster was found — the reader is broken, not the repo"
    assert unwatched == []


def test_the_gate_reads_every_yaml_file_not_only_the_workflows(tmp_path: Path):
    """A top-level YAML file is read too — the rule is about every YAML file, not just `.github`."""

    # Given a non-workflow YAML file with an unparseable expression
    root = _tree(tmp_path, a_bot=WORKFLOW_OK, yaml_text="key: \"${{ ... }}\"\n")

    # When  the gate reads the tree
    seen = {str(p.relative_to(root)) for p in cw.yaml_files(root)}

    # Then  the top-level file is in scope and its expression is reported
    assert "a.yml" in seen
    assert "workflow-expression" in _keys(root)


def test_a_duplicate_key_is_refused_by_the_strict_loader():
    """GitHub refuses a file with duplicate keys; PyYAML's default loader hides it (last wins)."""

    # Given a workflow with a key declared twice
    text = "name: dup\nname: again\non:\n  workflow_dispatch:\n"

    # When  it is parsed strictly and loosely
    strict_failed = False
    try:
        yaml.load(text, Loader=_StrictLoader)
    except yaml.constructor.ConstructorError:
        strict_failed = True

    # Then  the strict loader refuses it while the default one silently accepts it
    assert strict_failed, "the strict loader must refuse a duplicate key"
    assert yaml.safe_load(text)["name"] == "again"


def test_every_yaml_file_in_this_repository_parses_with_no_duplicate_keys():
    """The whole point: every YAML file in the repo is parseable and has no duplicate key."""

    # Given this repository
    files = cw.yaml_files(REPO)

    # When  each YAML file is parsed strictly
    problems = []
    for path in files:
        try:
            yaml.load(path.read_text(), Loader=_StrictLoader)
        except yaml.YAMLError as exc:  # noqa: PERF203 - collect every failure
            problems.append((str(path.relative_to(REPO)), str(exc).splitlines()[0]))

    # Then  none of them fails, and the set is not empty
    assert files, "the gate found no YAML file at all — the listing is broken, not the repo"
    assert problems == []


def test_this_repository_passes_its_own_gate():
    """A convention the repo itself violates is not a convention."""

    # Given this repository
    # When  the gate reads it
    items = cw.findings(REPO)

    # Then  it reports no violation
    assert items == [], cw.render(items)


def test_check_exits_non_zero_on_a_violation_and_zero_on_this_repo(tmp_path: Path):
    """`main(["check"])` is what `ci-unit` gates on."""

    # Given a fixture tree with an unparseable expression
    root = _tree(tmp_path, a_bot="name: bad — refuses\non:\n  workflow_dispatch:\n\njobs:\n  go:\n"
                                 "    runs-on: ubuntu-latest\n    steps:\n      - run: echo \"${{ ... }}\"\n")

    # When  the gate checks the fixture and this repository
    bad = cw.main(["check", "--root", str(root)])
    good = cw.main(["check", "--root", str(REPO)])

    # Then  the violation is non-zero and this tree is zero
    assert bad == 1
    assert good == 0


# ---------------------------------------------------------------------------------------------------
# issue #882: a `uses:` job with a job-level key makes GitHub reject the FILE, and the run then has no
# jobs at all - which every rollup reads as "nothing failed".
def _wf(tmp_path, name: str, body: str):
    d = tmp_path / ".github" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")
    return tmp_path


def test_a_uses_job_with_a_timeout_is_reported(tmp_path):
    """The measured #882 shape: `uses:` + `timeout-minutes` → the workflow never produces a job."""
    root = _wf(tmp_path, "ci.yml", """
name: ci
on: push
jobs:
  linux:
    timeout-minutes: 150
    uses: ./.github/workflows/pipeline.yml
""")

    items = cw.check_uses_job_keys(root)

    assert [i["key"].split("/")[0] for i in items] == ["uses-job-key"], items
    assert "linux" in items[0]["title"], items[0]
    assert "0 jobs" in items[0]["evidence"], items[0]["evidence"]


def test_a_uses_job_with_only_inputs_is_accepted(tmp_path):
    """The legal shape: `uses:` plus `with:`/`permissions`/`secrets`, and nothing else."""
    root = _wf(tmp_path, "ci.yml", """
name: ci
on: push
jobs:
  linux:
    uses: ./.github/workflows/pipeline.yml
    permissions:
      contents: read
    secrets: inherit
    with:
      runner: ubuntu-latest
""")

    assert cw.check_uses_job_keys(root) == []


def test_a_workflow_with_no_jobs_is_reported(tmp_path):
    """A file that parses to no job can never run — the same invisible failure, one step earlier."""
    root = _wf(tmp_path, "empty.yml", "name: empty\non: push\njobs: {}\n")

    items = cw.check_uses_job_keys(root)

    assert [i["key"].split("/")[0] for i in items] == ["workflow-jobs"], items


def test_every_committed_workflow_has_a_runnable_shape():
    """The tree itself: every workflow parses into at least one job, and no `uses:` job carries a key
    GitHub rejects at load time (the defect that made #882 unapprovable and invisible)."""
    assert cw.check_uses_job_keys(REPO) == []
