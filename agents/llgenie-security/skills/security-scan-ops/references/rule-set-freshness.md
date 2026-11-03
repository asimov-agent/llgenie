# Rule-set freshness: is the scanner's rule set actually pinned?

A scanner image addressed by digest pins the *binary*, not the *rules*. Semgrep's `--config p/default`
is a **registry alias that re-resolves on every run**, so the rule set drifts silently between two runs of
the same pinned image. That is the "rule-set freshness" gap: the scan reports what a database snapshot
said, not what this tree triggers under a fixed rule set.

## What was measured (semgrep 1.165.0, in the pinned scanner image)

- `semgrep --validate --config p/default` resolves **1,074 rules** from the live registry on each run.
- There is **no subcommand that dumps the resolved pack to a file.** After a full scan the tool's cache
  under `$HOME/.semgrep/` holds only `settings.yml` and `semgrep.log` — **no rule files**. The resolved rules
  are held in memory, not written anywhere a build could copy out.
- Consequence: a **build-time "bake-at-build" re-pin cannot be byte-exact.** Re-resolving `p/default` at
  build time reproduces the same drift the gap exists to close; and swapping to a deterministic source
  (`semgrep/semgrep-rules@<commit>`) **changes which rules run** — a scan-coverage change, not a pin.

## The decision, and why it is not the unblock

Making the rule set reproducible is a **scan-coverage policy decision the owner makes**, not something to
slip into a "just fix the pin" change: either you keep p/default semantics (and accept drift), or you switch
source and accept different findings. When asked for a gate-free slice, present both options measured and file
the chosen redesign as its own scoped, tracked issue rather than smuggling a parity change into an "unblock."

## If you do try to pin it

- **Committing the resolved pack trips `GH013` push-protection** — a snapshot of `p/default` is tens of
  thousands of lines and includes detection patterns (a slack-webhook URL regex, etc.) that are
  **secret-scanner false positives**, so any push of the literal commit is rejected. The block has **no local-git
  bypass**: a `PUSH_PROTECTION_BYPASS` HTTP header, waiting for rule propagation, and plain retries all return the
  same rejection until the repo-side state changes. Clear it only by (a) a **push-protection secret-scanning
  allowlist entry scoped to that file path** (`containers/scanners/semgrep/rules/default.yml` — the file, not just
  a secret type; a durable carve can take minutes to propagate, and it is **not readable through the public REST
  API** — `…/secret-scanning`, `…/security-scanning/push-protection-allowlist` all 404 — so the **push itself is
  the only ground truth**), or (b) the owner opening the `…/unblock-secret/<token>` URL in the UI as a repo admin.
  **Do not encode/base64/omit the pack to dodge the scan** — that is a deliberate weakening. When the owner
  chooses to commit the pin, parity is still proven by the manifest gate (`rules_sha` = sha256 of the committed
  file byte-for-byte); otherwise digest/build it and do not track it.
- The honest deterministic option is a **content-addressed ref** (`semgrep-rules@<40-hex-commit>`), which is
  reproducible; state plainly that it changes rule parity versus `p/default`, so the owner sees the coverage
  trade before approving.
- Prove the current state before proposing: run the image's `--validate --config p/default`, record the rule
  count and the sha it was measured at, and show the cache holds no dumpable pack.
