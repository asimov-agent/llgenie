"""The semgrep rules-pack refresh path (issue #2283 criterion 2).

A committed rules pack with a recency floor is only half a control: there must be a path that
re-resolves upstream `p/default`, rewrites `default.yml`, and re-stamps `digests.json` so the
floor's `rules_captured_at`/`rules_count`/`rules_sha` follow the new capture. These tests lock the
two properties an implementation must not break:

- `write()` records `rules_sha == sha256(rewritten default.yml)` and `rules_captured_at == the
  refresh date` (the re-pin PR's proof, criterion 5);
- `neutralise()` re-applies the credential-shape escapes the committed pack carries (`\x59`,
  `\x2e`/`\x2f`) so a raw fetch does not become a gitleaks / push-protection finding, and it
  REFUSES (SystemExit) a no-op when an upstream spelling it must escape has drifted — so a refresh
  never silently commits a credential-shaped pack.

Hermetic by design: no network and no container — the fetch and the pinned-image `resolve` are the
workflow's live path (`make semgrep-rules-refresh`), proven end-to-end against the pinned image in
CI (an e2e proof quoted in the PR body). Here the *write discipline* and the *neutralization* are
proven on a fixture tree, which is where a regression would actually show up.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from scripts import scanner_image as si
from scripts import semgrep_rules as sr

BASE_DIGEST = "sha256:" + "a" * 64
SEMGREP_DOCKERFILE = (
    "# syntax=docker/dockerfile:1\n"
    f"FROM cgr.dev/chainguard/wolfi-base@{BASE_DIGEST}\n"
    "ARG SEMGREP_VERSION=1.165.0-r0\n"
    'RUN apk add --no-cache "semgrep=${SEMGREP_VERSION}"\n'
    'ENTRYPOINT ["semgrep"]\n'
    'CMD ["--version"]\n'
)


def _tree(tmp_path: Path, pack_text: str) -> Path:
    """A repo-shaped fixture: semgrep Dockerfile + the rules pack, REPO pointed at it."""
    d = tmp_path / "containers" / "scanners" / "semgrep"
    d.mkdir(parents=True)
    (d / "Dockerfile").write_text(SEMGREP_DOCKERFILE, encoding="utf-8")
    (d / "rules").mkdir()
    (d / "rules" / "default.yml").write_text(pack_text, encoding="utf-8")
    return tmp_path


def test_refresh_write_records_sha_and_capture_date(tmp_path, monkeypatch):
    """The re-pin proof: after a refresh, digests.json records rules_sha == sha256(the file just
    written) and rules_captured_at == the refresh date (criterion 2's half of criterion 5)."""

    # Given  a fixture tree with a prior pack and only the semgrep scanner
    old = "rules:\n- id: a.b.c.old\n  pattern: old\n"
    root = _tree(tmp_path, old)
    monkeypatch.setattr(si, "SCANNERS", {"semgrep": si.SCANNERS["semgrep"]})
    monkeypatch.setattr(si, "REPO", root)

    # When  the refresh rewrites the pack (a new upstream capture with one more rule)
    new = "rules:\n- id: a.b.c.new\n  pattern: new\n"
    pack, sha, captured, count = sr.write(new, repo=root)

    # Then  rules_sha equals sha256 of the file just written, captured_at is today, count matches
    assert hashlib.sha256(pack.read_bytes()).hexdigest() == sha
    assert pack.read_text(encoding="utf-8") == new

    digests = json.loads((root / "containers" / "scanners" / "digests.json").read_text())
    assert digests["semgrep"]["rules_sha"] == sha
    assert digests["semgrep"]["rules_captured_at"] == captured
    assert captured == date.today().isoformat()
    assert digests["semgrep"]["rules_count"] == "1"  # one `- id:` line
    assert count == 1


def test_refresh_write_preserves_the_content_pin(tmp_path, monkeypatch):
    """The byte/sha discipline is atomic: a file on disk always matches the recorded sha, never a
    stale one (the #1284 reproducibility promise must survive a rewrite)."""

    # Given  a fixture tree with the semgrep scanner
    old = "rules:\n- id: a.b.c.old\n  pattern: old\n"
    root = _tree(tmp_path, old)
    monkeypatch.setattr(si, "SCANNERS", {"semgrep": si.SCANNERS["semgrep"]})
    monkeypatch.setattr(si, "REPO", root)

    # When  a refresh writes a changed pack
    new = "rules:\n- id: a.b.c.new\n  pattern: new\nand more\n"
    sr.write(new, repo=root)

    # Then  the committed file's bytes hash to the recorded sha (`check-scanner-images` agrees)
    digests = json.loads((root / "containers" / "scanners" / "digests.json").read_text())
    on_disk = (root / "containers" / "scanners" / "semgrep" / "rules" / "default.yml").read_bytes()
    assert hashlib.sha256(on_disk).hexdigest() == digests["semgrep"]["rules_sha"]


# --- neutralisation -----------------------------------------------------------------------

PEM_PGP = "  pattern-regex: '-----BEGIN PGP PRIVATE KE\x59 BLOCK-----'\n"
PEM_PRIV1 = "      - pattern: '-----BEGIN $TYPE PRIVATE KEY----- $KEY'\n"
PEM_PRIV2 = ("      - pattern: |\n          -----BEGIN PRIVATE KE\x59-----\n          $KEY\n")
WEBHOOK_REGEX = "  - pattern-regex: https://hooks\\.slack\\.com/services/"
WEBHOOK_PATTERN_NOT = (
    "  - pattern-not: https://hooks\x2eslack\x2ecom\x2fservices\x2fT00000000\x2fB00000000\x2fXXXXXXXXXXXXXXXXXXXXXXXX")


def test_neutralise_removes_the_credential_shapes():
    """A raw upstream pack carries its own detector-pattern bytes (PEM headers, the Slack webhook
    URL); the neutralizer must escape them so `make secret-scan` stays green on the committed pack."""

    # Given  a pack that contains every live credential spelling (as upstream emits it)
    raw = (PEM_PGP + PEM_PRIV1 + PEM_PRIV2 + WEBHOOK_REGEX + WEBHOOK_PATTERN_NOT)

    # When  the neutralizer rewrites it
    out = sr.neutralise(raw)

    # Then  no PEM private-key header and no plain webhook host survive in the bytes
    assert "-----BEGIN PGP PRIVATE KEY" not in out
    assert "-----BEGIN PRIVATE KEY-----" not in out
    assert "hooks.slack.com/services" not in out and "hooks\\.slack\\.com/services" not in out
    # And   the escapes are present (KE\x59, \x2e/\x2f) so the resolved form still matches
    assert "KE\\x59" in out
    assert "hooks\\x2eslack\\x2ecom\\x2fservices\\x2f" in out
    # And   the private-key `pattern: |` block became a single escaped double-quoted scalar
    assert "\\n$KEY\\n" in out


def test_neutralise_refuses_a_noop_on_a_drifted_spelling():
    """The refresh must never silently write a credential-shaped pack: if an upstream spelling is
    gone (an upstream rule-body edit), the neutralizer FAILS instead of nopping (fail-closed)."""

    # Given  a pack missing one of the live spellings (upstream renamed the PEM header rule)
    drifted = (PEM_PRIV1 + PEM_PRIV2 + WEBHOOK_REGEX + WEBHOOK_PATTERN_NOT)
    assert "PGP PRIVATE KEY" not in drifted

    # When  the neutralizer runs on it
    try:
        sr.neutralise(drifted)
    except SystemExit as exc:
        # Then  it refuses the no-op, naming the missing spelling
        assert "refusing a no-op" in str(exc) and "PGP PRIVATE KEY" in str(exc)
        return
    raise AssertionError("a drifted upstream spelling was silently accepted")
