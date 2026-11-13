# Agent image base has no `:latest` default (issue #2617)

Date: 2026-11-13 · Branch: `feat/agent-image-base-pinned` · OpenSpec: `agent-image-base-pinned` · Issue: #2617 · PR: #PRNUM

## What was verified against the spec

Measured on `main` `da2fc5adb` with `make security-scan TOOL=trivy` (rc=0): the tree holds
exactly ONE dockerfile misconfig row — `containers/agent/Dockerfile` `':latest' tag used` — every
engine/test Dockerfile is clean after the DS-0002 sweep closed. The finding is the
`ARG TEST_IMAGE=llgenie/test:latest` default behind `FROM ${TEST_IMAGE}`. Every wired build
path already passes the exact hashed ref (`ci_images.py::build_args` →
`--build-arg TEST_IMAGE=<ghcr test hash tag>`, locked by
`test_publish_agent_pins_the_test_image_it_builds_from`), so the default is reachable only from
an ad-hoc `docker build`, where it would silently base the every-bot-lane image on a moving tag.

The landed change: the Dockerfile declares `ARG TEST_IMAGE` with NO default — a bare
`docker build -f containers/agent/Dockerfile` fails loudly (empty base name) instead of
resolving the mutable alias. No wired path or workflow changed. New lock
`test_agent_dockerfile_has_no_latest_base_default` pins the no-default line and the absence of
any pre-`FROM` `:latest` reference; trivy on the branch reports zero misconfig rows across all
Dockerfiles.

## Current status

Daily security lane: with the DS-0002 family cleared (reconcile posted clearing evidence to 39
issues) and this last misconfig fixed, the scan verdict on `main` has no dockerfile findings.
