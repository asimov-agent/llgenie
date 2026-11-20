# Proposal: openspec-seam-uid-map

## Why

`#433` filed the rule that container runs mounting the repo must write as the
invoking user, not root. The plain test stages got that mapping via `TEST_OPTS`
(issue #2563), but the OpenSpec CLI seam kept `OS_OPTS := --rm -u root ...` —
so `make openspec-new`, the mandated first step of every lane, still creates
root-owned `openspec/changes/<name>/` trees in the user's checkout (re-measured
2026-11-20 on a fresh worktree: the change dir needed a root `chown`). The
ownership trap #433 was filed to close re-appears at the very first command of
every work item.

## What Changes

- `Makefile` `OS_OPTS`: replace `-u root` with the invoking user's mapping
  `-u "$(shell id -u):$(shell id -g)"` and give the CLI a writable home with
  `-e HOME=/tmp` (the openspec image's `USER 65532` has no writable home for a
  mapped uid). The engine stages that must reach the root-only `docker.sock`
  (`ENGINE_TEST_ARGS`) and the root-tree cleaner (`CI_HOME_CLEAN`) keep `-u
  root` on purpose — #2563's carve-outs.
- `tests/test_openspec_gate.py` pins the seam: `OS_OPTS` names the `id -u` /
  `id -g` mapping and carries no `-u root`; exactly the two carve-out stages may
  run as root, each named.

## Out of Scope

- The pre-existing root-owned residue dirs under `../llgenie-wt` from earlier
  waves — the #2477 CONFIRM-gated prune's job.
