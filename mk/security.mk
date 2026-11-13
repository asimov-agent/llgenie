# mk/security.mk — the security domain of the top Makefile (issue #800 → #2459).
#
# Moved BYTE-IDENTICAL from the top Makefile (issue #800 decomposition): `include mk/security.mk`
# in the top Makefile brings them back. No recipe changed; only the file that declares each
# target moved. Each block spans from its target line through the first blank line OR the next
# target header (ifeq depth tracked), so neighbours with no blank line between them never bleed in.
#
# Ownership seams: `ci-scanner-images` is the CI job surface target for the scanner-images job and
# lives in `mk/ci.mk` (ci split #2458), NOT here; the `engine-pins` prerequisite named by `sbom`
# and `security-scan-all` resolves through `mk/engines.mk` (engines split, PR #2635).
# Section banner comments stay in the top Makefile at their original positions (#2456/#2458 precedent).

check-secret-output: ## CI: fail when any file prints a secret's VALUE, passes it on a command line, xtraces it, dumps the environment around it, or commits a credential-shaped literal
	python3 scripts/check_secret_output.py check

secret-output-report: ## Show which files name a secret-shaped variable, and whether any prints it
	python3 scripts/check_secret_output.py report

_secret-scan: # (internal) the working-tree scan over the committable set; `secret-scan` wraps it with the remediation text
	python3 scripts/secret_scan.py --runtime $(RUNTIME)

secret-scan: ## CI: fail when a credential VALUE is committed in the working tree (gitleaks, its own pinned image; a finding means remove it and rotate the key — never allowlist it)
	@python3 scripts/secret_scan.py --runtime $(RUNTIME); rc=$$?; \
	if [ $$rc -eq 1 ]; then \
		echo "SECRET SCAN FAILED: a credential shape is present in the working tree."; \
		echo "Remove the value, rotate the key in the provider AND in the GitHub secret, and only"; \
		echo "then push. Never add it to .gitleaks.toml to make the scan pass — an allowlist is"; \
		echo "for a documented PLACEHOLDER, never for a real value."; \
		exit 1; \
	elif [ $$rc -ne 0 ]; then \
		echo "SECRET SCAN COULD NOT RUN (exit $$rc): the scanner produced NO verdict. This is not a"; \
		echo "clean tree and not a finding — read the message above and fix the scan itself. Never"; \
		echo "report a scan that could not run as clean (issue #382)."; \
		exit $$rc; \
	fi

_secret-scan-history: # (internal) the history scan; refuses a worktree, where .git is a file
	@if [ -f .git ]; then \
		echo "SECRET SCAN (history) needs a real clone: this checkout is a git worktree (.git is a file)."; \
		echo "Run it in the primary checkout or in CI."; \
		exit 1; \
	fi
	$(GITLEAKS_RUN) git /repo --config /repo/.gitleaks.toml --redact --no-banner --exit-code 1

secret-scan-history: ## Fail when a credential VALUE is anywhere in the git history — host-only by design: it refuses a worktree and CI clones shallowly, so run it in a real clone before a release
	@$(MAKE) --no-print-directory _secret-scan-history

secret-scan-self-test: ## CI: prove the scanner is not a false green — a planted fake credential MUST be caught, and the same tree is clean once it is removed
	python3 scripts/secret_scan_self_test.py

sbom: engine-pins ## Generate the CycloneDX SBOM with the pinned Syft image into security-reports/sbom.cdx.json (issue #715); the engine install-string pins are inventoried into security-reports/engine-pins/ first so the SBOM covers the engine runtime deps (issue #1282)
	python3 scripts/security_scan.py sbom

security-scan: ## Run ONE scanner from its immutable image (TOOL=syft|trivy|grype|semgrep); grype needs the Syft SBOM first (issue #715)
	python3 scripts/security_scan.py scan "$(TOOL)"

security-scan-all: engine-pins ## Run every scanner from its pinned image in dependency order (Syft SBOM, then Trivy, Grype, Semgrep); the engine pins are inventoried before Syft so the SBOM covers them (issue #1282)
	python3 scripts/security_scan.py all

security-verdict: ## Apply data/security-policy.json to the reports (EVENT=<github event> decides whether that event may gate; ENFORCE=pr forces report-only; issue #715, #738)
	python3 scripts/security_scan.py verdict --event "$(EVENT)" $(if $(ENFORCE),--mode "$(ENFORCE)",)

check-security-scan: ## CI: fail when the scan policy is empty/unknown, a scanner ref is missing from digests.json, the semgrep rule pack lacks a content pin or lags the declared baseline, the engine install-string pins are not inventoried / absent from the SBOM, or the gitleaks admission scanner is addressed by a mutable tag (issues #715, #1282, #1284, #2235)
	$(MAKE) check-gitleaks-pin
	python3 scripts/security_scan.py check
	python3 scripts/engine_pins.py check

check-gitleaks-pin: ## CI: fail when the secret-scan admission gate addresses gitleaks by a mutable tag or by a digest that diverges from the reviewed pin (issue #2235) — the #1252/#1262 silently-unsatisfiable-pin guard
	python3 scripts/check_gitleaks_pin.py check

security-issues-plan: ## Print the tagged issues the current reports would create/update/clear and mutate nothing (issue #716)
	python3 scripts/security_issues.py plan

security-issues: ## File or update the tagged vulnerability issues for the current reports (SLUG=owner/name, RUN_URL=<run link>, issue #716)
	python3 scripts/security_issues.py apply --repo "$(if $(SLUG),$(SLUG),asimov-agent/llgenie)" --run-url "$(RUN_URL)"

security-issues-reconcile: ## Reconcile closed scan-evidence issues a merged PR's `closes #N` closed: reopen a still-reported one, post the run id + sha clearing comment on a genuinely-gone one (SLUG=owner/name, RUN_URL=<run link>, SHA=<head sha>, DRY=1 previews; issue #1693)
	python3 scripts/security_issues.py reconcile --repo "$(if $(SLUG),$(SLUG),asimov-agent/llgenie)" --run-url "$(RUN_URL)" --sha "$(SHA)" $(if $(DRY),--dry,)

check-security-issues: ## CI: fail when the issue policy/label roster/marker disagree (issue_severities not a subset of fail_on, a missing label, a marker that does not round-trip) (issue #716)
	python3 scripts/security_issues.py check

security-bot-pick: ## Print the ONE auto-fixable issue the remediation bot would take, and what it would edit (issue #717)
	python3 scripts/security_bot.py select --repo "$(if $(SLUG),$(SLUG),asimov-agent/llgenie)"

security-bot: ## Apply the advisory's pin, run the fast gates, and open ONE PR that closes the issue (DRY=1 prints the edit and pushes nothing; issue #717)
	python3 scripts/security_bot.py apply --repo "$(if $(SLUG),$(SLUG),asimov-agent/llgenie)" $(if $(DRY),--dry,)

check-security-bot: ## CI: fail when the bot's select labels/pin sources disagree with the issue roster or a compiled requirements file became an edit target (issue #717)
	python3 scripts/security_bot.py check

security-bumps-plan: ## Print the minimum version the scan's findings demand per package, the pins it would move, and the issues the bump PR would close (issue #738)
	python3 scripts/security_bumps.py plan

security-bumps: ## Write tools/security-floors.in, regenerate the compiled pins through the one generator, and open ONE PR that closes the issues it fixes (DRY=1 prints and pushes nothing; issue #738)
	python3 scripts/security_bumps.py apply --repo "$(if $(SLUG),$(SLUG),asimov-agent/llgenie)" $(if $(DRY),--dry,)

check-security-bumps: ## CI: fail when a floor line states no advisory, a compiled pin is below its floor, or the `-c security-floors.in` include is gone (issue #738)
	python3 scripts/security_bumps.py check

scanner-image: ## Build one scanner image from containers/scanners/<SCANNER>/Dockerfile (SCANNER=trivy|grype|semgrep, issue #714)
	python3 scripts/scanner_image.py build "$(SCANNER)"

test-scanner-image: ## Build a scanner image and prove it prints the version its Dockerfile pins (SCANNER=<id>)
	python3 scripts/scanner_image.py test "$(SCANNER)"

scanner-digests: ## Rewrite containers/scanners/digests.json from the Dockerfiles (the immutable tag + pinned version per scanner)
	python3 scripts/scanner_image.py write

pin-scanner-image-digests: ## Record each scanner image's published manifest digest into digests.json as `image_digest` (issue #2609; run after publish-scanner-images, re-run on every republish; SCANNER=<id> pins one, default all)
	python3 scripts/scanner_image.py pin "$${SCANNER:-all}"

scanner-ref: ## Print the published immutable ref of a scanner image (SCANNER=<id>)
	python3 scripts/scanner_image.py ref "$(SCANNER)"

semgrep-rules-refresh: ## Re-resolve the semgrep rules pack from upstream p/default through the pinned scanner image and rewrite default.yml + digests.json (rules_sha/rules_captured_at/rules_count) — the refresh half of the rule-freshness floor (issue #2283 criterion 2)
	python3 scripts/semgrep_rules.py refresh

publish-scanner-images: ## Build linux/amd64+arm64 and push one scanner image's content-hash tag to GHCR (SCANNER=<id>; the scanner-images job publishes through make ci-scanner-images)
	python3 scripts/scanner_image.py publish "$(SCANNER)"

check-scanner-images: ## CI: fail when a scanner Dockerfile floats (tag base, version range) or digests.json is stale (issue #714)
	python3 scripts/scanner_image.py check all

check-actions: ## CI: fail when a GitHub Action in any workflow or composite action is not pinned to a full commit SHA (issue #719)
	python3 scripts/pin_actions.py check

actions-report: ## Show every `uses:` ref the action-pin gate reads, its pin state and its tag
	python3 scripts/pin_actions.py report

update-actions: ## Re-resolve every pinned action's tag to its current commit SHA and rewrite the workflows (needs gh + network)
	python3 scripts/pin_actions.py update

check-renovate: ## CI: fail when renovate.json automerges more than low-risk updates, opens a second merge path, or may edit a generated/vendored file (issue #718)
	python3 scripts/check_renovate.py check

renovate-report: ## Show every Renovate package rule, its managers, its automerge state and the ignored paths
	python3 scripts/check_renovate.py report
