# GGUF model-tooling Makefile.
# Uses nerdctl (rootless) for the pip-compile container; installs deps into a
# python 3.10 venv at ~/llama-gguf-tools/.venv.

SHELL   := /bin/bash
NERDCTL ?= nerdctl
IMG     := gguf-tools/pip-compile:latest
PY310   ?= /opt/homebrew/bin/python3.10
VENV    := $(HOME)/llama-gguf-tools/.venv

REQIN   := requirements.in
REQTXT  := requirements.txt
DEVREQIN  := requirements-dev.in
DEVREQTXT := requirements-dev.txt

.PHONY: all build-image generate-requirements generate-requirements-venv venv create-venv venv-install venv-dev-install generate-requirements-dev clean version

all: generate-requirements venv-install

# ---- flags -----------------------------------------------------------------
NERDCTL_TOOLS := $(shell command -v $(NERDCTL) >/dev/null 2>&1 && echo yes || echo no)

# ---- container ------------------------------------------------------------------
build-image: ## Build the pip-compile container (python 3.10)
	$(NERDCTL) build -t $(IMG) .

# ---- requirements ----------------------------------------------------------------
# Regenerate requirements.txt from requirements.in, so the locked, installable
# dependencies always stay in sync with the single source of truth (.in).
# Uses the pip-compile container when nerdctl is available, otherwise falls
# back to a venv pip-compile (pip-tools installed on demand).
generate-requirements: ## Compile requirements.in -> requirements.txt
	@if [ "$(NERDCTL_TOOLS)" = "yes" ]; then \
		echo "==> pip-compile via $(NERDCTL) container $(IMG)"; \
		$(MAKE) build-image; \
		$(NERDCTL) run --rm \
			-v "$(CURDIR)":/work:rw \
			-w /work \
			$(IMG); \
	else \
		echo "==> nerdctl not found; using venv pip-compile fallback"; \
		$(MAKE) generate-requirements-venv; \
	fi
	@echo "Regenerated $(REQTXT)"
	@echo "--- head of $(REQTXT) ---"
	@head -15 $(REQTXT)

generate-requirements-venv: venv-install ## pip-compile into the 3.10 venv (no container)
	$(VENV)/bin/python -m pip install --quiet pip-tools
	$(VENV)/bin/pip-compile --output-file $(REQTXT) $(REQIN)
	@echo "pip-compiled $(REQTXT) via venv"

generate-requirements-dev: ## Compile requirements-dev.in -> requirements-dev.txt (container or venv)
	@if [ "$(NERDCTL_TOOLS)" = "yes" ]; then \
		echo "==> pip-compile dev via $(NERDCTL) container"; \
		$(NERDCTL) run --rm \
			-v "$(CURDIR)":/work:rw \
			-w /work \
			$(IMG) pip-compile --output-file $(DEVREQTXT) $(DEVREQIN); \
	else \
		echo "==> nerdctl not found; using venv pip-compile for dev deps"; \
		$(MAKE) generate-requirements-dev-venv; \
	fi
	@echo "Regenerated $(DEVREQTXT)"

generate-requirements-dev-venv: venv-install ## pip-compile dev deps into the venv (no container)
	$(VENV)/bin/python -m pip install --quiet pip-tools
	$(VENV)/bin/pip-compile --output-file $(DEVREQTXT) $(DEVREQIN)
	@echo "pip-compiled $(DEVREQTXT) via venv"

# ---- venv ------------------------------------------------------------------------
create-venv: ## Create the gguf venv (idempotent — reuses an existing one when present)
	# Reuse the venv if it already has a working python; only create it (with
	# the best available python, 3.10 preferred) when absent. This is what lets
	# `make install` round-trip (install -> uninstall -> install) without a
	# fresh-host python3.10, since a second install must not clobber a working
	# venv or fail when python3.10 is unavailable.
	@echo "==> venv at $(VENV)"
	@if [ -x "$(VENV)/bin/python" ]; then \
		echo "    already present — reusing"; \
	else \
		echo "    creating with $$(command -v python3.10 >/dev/null 2>&1 && echo python3.10 || command -v python3)"; \
		PY=$$(command -v python3.10 2>/dev/null || command -v python3 2>/dev/null || echo ""); \
		[ -n "$$PY" ] || { echo "ERROR: no python3.10/python3 found to create the venv"; exit 1; }; \
		"$$PY" -m venv $(VENV); \
	fi

venv: create-venv ## alias

venv-install: create-venv $(REQTXT) ## Install generated requirements.txt into the venv
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/pip install -r $(REQTXT)
	@echo "Installed gguf deps into $(VENV)"
	$(VENV)/bin/python -c "import gguf, numpy; print('gguf ok:', gguf.__file__)"

venv-dev-install: venv-install $(DEVREQTXT) ## Install runtime + dev (pytest) deps into the 3.10 venv
	$(VENV)/bin/pip install -r $(DEVREQTXT)
	@echo "Installed dev deps into $(VENV)"
	$(VENV)/bin/python -m pytest --version

clean: ## Remove generated requirements.txt (keep .in as source of truth)
	rm -f $(REQTXT)

version: ## Show versions in the venv
	$(VENV)/bin/python -c "import gguf,numpy; print('numpy',numpy.__version__, 'gguf', gguf.__version__ if hasattr(gguf,'__version__') else 'n/a')"
