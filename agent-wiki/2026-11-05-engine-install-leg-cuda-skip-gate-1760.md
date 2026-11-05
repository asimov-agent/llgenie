# the cuda install-leg #1240 skip is a real gate, not a printed line

## Background (measured 2026-11-05)

The `#1753` acceptance engine-build matrix (run **41978470867** @ merged main
`2795354c6`) fails 5 cuda cells (freetoken, llama.cpp, ollama, strata, mlx) at
the install-leg with:

```
[install-leg] SKIP cuda install-leg: ... (issue #1240)   <- printed BEFORE the make that follows
make engine-launchers ENGINES="mlx" ARCH="cuda"          <- STILL RUNS
[install] FAIL cuda host without the NVIDIA CDI spec: ... <- and fails
make[1]: *** [Makefile:281: engine-launchers] Error 1
```

Real mlx-cuda cell log (job 127082875386): line 704 prints the SKIP reason,
line 705 runs `make engine-launchers`, line 708 fails, line 710 errors. The
`#1240` skip was a *printed reason*, never a gate.

## Root cause (structural)

`Makefile` `test-engine-install` put the skip query and its conditional on ONE
recipe line:

```
@reason="$$(python3 scripts/install_engine_launchers.py --install-leg-skip-reason --arch "$(ARCH)")"; \
if [ -n "$$reason" ]; then echo "$$reason"; exit 0; fi
make engine-launchers ENGINES="$(ENGINE)" ARCH="$(ARCH)"   <- SEPARATE recipe line
```

but `make engine-launchers` on the NEXT line. `make` runs each recipe line in
its **own shell**, so the `exit 0` on the skip branch ends only the first shell
(returning success), and `make` proceeds to the unconditional `make
engine-launchers` on the next line. The skip could never gate launchers.

## The answer

Fold launchers/verify/uninstall under the `else` of the skip branch inside ONE
recipe line, so a non-empty skip reason truly prevents them from running:

```
@reason="$$(python3 scripts/install_engine_launchers.py --install-leg-skip-reason --arch "$(ARCH)")"; \
if [ -n "$$reason" ]; then echo "$$reason"; \
else \
  make engine-launchers ENGINES="$(ENGINE)" ARCH="$(ARCH)" && \
  make test-built-engine && \
  make ci-install-uninstall; \
fi
```

Now a cuda-without-CDI cell is an evidence-backed SKIP (the documented #1240
reason) instead of a red FAIL that buries real findings; a genuinely GPU+CDI
host still exercises `install()`. Proven locally with the exact recipe logic:
non-empty reason → SKIP branch (launchers blocked); empty reason → else branch
(launchers run). Only the `test-engine-install` recipe changed; no workflow, no
product code. Closes #1760 via PR #1761.
