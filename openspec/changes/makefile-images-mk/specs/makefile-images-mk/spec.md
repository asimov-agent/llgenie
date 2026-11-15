# makefile-images-mk — Spec Delta

## ADDED Requirements

### Requirement: The image build/publish surface lives in mk/images.mk

The repository SHALL keep the image build/publish surface in `mk/images.mk`, included from the
top Makefile, with every target name, `##` help line, and recipe byte-identical to the
pre-split top Makefile. The file SHALL contain exactly these 9 targets: `test-image`,
`test-image-pull`, `test-variant-image`, `publish-ci-images`, `publish-agent-image`,
`agent-image-push-check`, `agent-image`, `agent-image-pull`, `agent-image-ref`. Membership is
decided by recipe shape, not name: `agent-image-ref` runs a `scripts/ci_images.py` call and
therefore belongs to the images domain, not the agents domain. `ci-image-refs` belongs to
`mk/ci.mk` (ci domain) and SHALL NOT be re-moved.

#### Scenario: the include block lists the images file

- **Given** the repository at a commit after this change
- **When** the top Makefile is parsed by `make -qp`
- **Then** `mk/images.mk` appears among the included makefiles and all 9 targets listed above
  are defined exactly once across the whole include set

#### Scenario: moved recipes are byte-identical

- **Given** the pre-split top Makefile at the change's base commit
- **When** each of the 9 target blocks (header line through its final recipe line) is compared
  to the same block in `mk/images.mk`
- **Then** the comparison is byte-identical for every block

### Requirement: The split changes no observable make behavior

The split SHALL preserve `make help` byte-for-byte and SHALL NOT change any target's behavior;
variables (`VARIANT_IMG`, `VARIANT_RUN`), banners, `.PHONY` declarations, `help`, and
`DEFAULT_GOAL` remain in the top Makefile, as in `mk/engines.mk`, `mk/ci.mk`, `mk/gates.mk`,
`mk/install.mk`, `mk/security.mk` and `mk/bots.mk` (all of which declare zero variables).

#### Scenario: help output identity

- **Given** the same repository before and after the split at the same base content
- **When** `make help` runs on both trees
- **Then** the outputs are byte-identical

#### Scenario: no target declared in two makefiles

- **Given** the include set of the top Makefile after the split
- **When** the declared target names across all `mk/*.mk` files and the top Makefile are
  compared pairwise
- **Then** no target name among the 9 images targets appears in more than one file


