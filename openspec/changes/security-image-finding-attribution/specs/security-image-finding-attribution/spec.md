# security-image-finding-attribution

## ADDED Requirements

### Requirement: the image record is written before the scanners run

`scan_image` MUST write `image-<slug>.meta.json` — naming the exact digest-pinned `ref` it is about to
scan — **before** the first scanner container starts, so that a scanner stage which dies mid-scan still
leaves the attribution the rest of the pipeline reads. The record MUST be written once, before the
trivy/Syft/Grype chain, never after it.

WHEN a published-image scan fails in one of its scanner stages
THEN the reports directory still holds the image record naming the ref that was being scanned.

#### Scenario: a mid-scan failure keeps the attribution

- **Given** a stubbed scanner runner that succeeds for trivy and raises for Syft
- **When** `scan_image` is called with a digest-pinned ref
- **Then** `image-<slug>.meta.json` exists, names that ref, and was written before the Syft call
- **Test:** `tests/test_security_scan.py::test_image_meta_survives_a_mid_scan_failure`

### Requirement: an image report without its record fails the run

`findings` MUST NOT emit a finding read from `image-*.trivy.json` or `image-*.grype.json` when the
matching `image-<slug>.meta.json` is absent or names no ref. It MUST fail the step and name the report,
because an untagged image finding is indistinguishable from a checkout finding and would be labelled as
one.

WHEN the reports directory holds an image report with no image record
THEN the step exits non-zero naming that report instead of returning its findings untagged.

#### Scenario: an orphan image report is refused

- **Given** a reports dir holding `image-agent.trivy.json` and no `image-agent.meta.json`
- **When** `findings` is called on that dir
- **Then** it raises naming `image-agent.trivy.json` and emits no untagged finding from it
- **Test:** `tests/test_security_scan.py::test_an_image_report_without_its_meta_fails_the_run`

### Requirement: a scanned ref resolves to its allow-list owner

`image_owner` MUST map a scanned ref back to the `containers/scanned-images.json` entry that named it —
directly for a `ref` entry, and through the same engine resolution the scan used for an
`engine`+`variant` entry — and return that entry's `owner` (the Dockerfile or params file that publishes
it). The mapping MUST ignore the `@sha256:` digest when matching, since the manifest names refs and the
scan addresses them by digest.

WHEN a finding carries an image ref from an allow-list scan
THEN the allow-list entry that produced that ref, and its `owner`, can be named for a reader.

#### Scenario: the agent ref names its Dockerfile

- **Given** `ghcr.io/asimov-agent/llgenie/agent:latest@sha256:<64 hex>`
- **When** `image_owner` is called with it
- **Then** the returned entry names the `agent` allow-list entry and its `containers/agent/Dockerfile` owner
- **Test:** `tests/test_security_scan.py::test_image_owner_names_the_allow_list_entry_and_its_owner`

### Requirement: an image finding's issue body names the image, not a dependency pin

`body_for` MUST render, for a finding that carries an image ref, remediation that names the ref and the
allow-list owner responsible for that image (or states plainly that the allow-list names no owner for
it). It MUST NOT tell the reader to move the package through the generated `tools/requirements*.in` →
`requirements*.txt` path, and its acceptance criteria MUST be satisfiable by the owner it names.

WHEN a container finding found inside a published image becomes an issue
THEN its body names the `ref@digest` and the owner file that can change that image, and never names the
requirements-pin path.

#### Scenario: the container body names the owner

- **Given** a HIGH trivy finding carrying an image ref whose allow-list entry has an `owner`
- **When** `body_for` renders it
- **Then** the body names the ref, the owner, and `component:container`, and contains no
  `requirements*` wording
- **Test:** `tests/test_security_issues.py::test_an_image_finding_names_the_image_owner_not_the_pin_path`

### Requirement: the component label is reconciled, not only added

`set_labels` MUST, after the label POST and its read-back, remove any `component:*` label the finding no
longer earns from the issue it is labelling, and MUST fail the step if the removal did not stick. The
marker, severity and `auto-fixable` labels are never removed by this rule.

WHEN a finding is re-filed with a different component than the open issue already carries
THEN the issue ends with exactly the component label the current finding computed.

#### Scenario: a re-labelled finding loses its stale component

- **Given** an open issue carrying `component:python` and a finding whose labels say `component:container`
- **When** `apply` updates that issue
- **Then** the tracker stub records a delete for `component:python` and the issue keeps `component:container`
- **Test:** `tests/test_security_issues.py::test_a_relabelled_finding_loses_its_stale_component_label`
