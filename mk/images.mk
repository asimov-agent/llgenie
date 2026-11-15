# mk/images.mk — image build/publish targets split out of the top Makefile (issue #2678).
# Target names and recipes are byte-identical; shared variables stay in the top Makefile.

agent-image-ref: ## Print the GHCR :latest ref every agent pull uses (publish points it at the content hash)
	@python3 scripts/ci_images.py latest agent

test-image: ## The test image: pull the published hash of its Dockerfile + lockfiles (GHCR), else build it here (issue #117)
	python3 scripts/ci_images.py ensure test

test-image-pull: ## CI: pull the published test image (hash of its Dockerfile + lockfiles) as $(TEST_IMG); a push run fails if not published and never builds; a pull_request run defers the publish to the landing run and builds it locally (issue #2518)
	python3 scripts/ci_images.py pull test

publish-ci-images: ## CI job ci-images: build + push the test and OpenSpec images ONLY when their hash tag is not on GHCR yet. The AGENT image is NOT here: the default GITHUB_TOKEN is denied "Create organization package" for a brand-new package (the first llgenie/agent publish), so it goes out through publish-agent-image.yml with the owner PAT, deliberately and by hand
	python3 scripts/ci_images.py publish test openspec

publish-agent-image: ## Build + push ONLY the agent (Hermes) image to GHCR (linux/amd64: it builds Hermes at build time, which times out under arm64 emulation) when its hash tag is not there yet, and point :latest at that hash even when the hash is already published. Set FORCE=--force to rebuild + push even when the hash is already there (issue #990). The dedicated job for the Hermes container (issues #222/#238/#248); guarded to owner/collaborators.
	python3 scripts/ci_images.py publish agent $(FORCE)

agent-image-push-check: ## Prove the GHCR credential can PUSH the agent image BEFORE the (up to 60-minute) build: ask the registry for a push-scoped token, then initiate the cheapest real write there is (an empty blob upload, no data). Prints the registry's own refusal and exits non-zero when the credential may not push (issue #335)
	@test -n "$$GHCR_TOKEN" || { echo "ERROR: GHCR_TOKEN is unset - this target asks GHCR to prove a credential can push the llgenie/agent package"; exit 1; }
	python3 scripts/ci_images.py pushcheck agent

agent-image: ## The agent (Hermes) image: pull ghcr.io/<registry>/llgenie/agent:latest, else build it here
	python3 scripts/ci_images.py ensure agent

agent-image-pull: ## CI: pull ghcr.io/<registry>/llgenie/agent:latest as llgenie/agent:latest; fails if that tag is missing, never builds
	python3 scripts/ci_images.py pull agent


test-variant-image: ## Build the CUDA toolkit + python variant-build image locally (the variant-build matrix is no longer a pipeline job; this reproduces it by hand)
	# The lockfiles are build-time inputs copied from tools/ (the ONE generator of a compiled pin),
	# in a TEMP context — never written into the checkout, where a stale copy becomes a finding the
	# scan can never clear (issue #787, the same shape as scripts/ci_images.py::context).
	@ctx=$$(mktemp -d) && trap 'rm -rf "$$ctx"' EXIT && \
		cp containers/ci-variant/Dockerfile "$$ctx/" && \
		cp tools/requirements.txt tools/requirements-dev.txt "$$ctx/" && \
		$(RUNTIME) build -t $(VARIANT_IMG) "$$ctx"
	@echo "Variant image built: $(VARIANT_IMG)"
