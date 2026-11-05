#!/usr/bin/env bash
# ghcr_publish_probe.sh <image-leaf> <tag> [owner]
#   image-leaf: the DASHED image name, e.g. llama-cpp (never llama.cpp, never the repo path)
#   tag:        the bare tag, e.g. 1b6935b2-5b7be358-cpu
#   owner:      default asimov-agent
#
# Exit 0 = PUBLISHED (HTTP 200), 1 = ABSENT (genuine 404), 2 = UNKNOWN (auth/other - retry, never
# read as absent). The URL shape is the whole trick: the image leaf goes in the PATH and the bare tag
# is the manifest reference, and one bearer token is fetched PER image repo (comma-joining two scopes
# returns 403).
set -uo pipefail

image="${1:?usage: ghcr_publish_probe.sh <image-leaf> <tag> [owner]}"
tag="${2:?usage: ghcr_publish_probe.sh <image-leaf> <tag> [owner]}"
owner="${3:-asimov-agent}"
repo="llgenie/${image}"

tok=$(curl -fsS "https://ghcr.io/token?scope=repository:${owner}/${repo}:pull" 2>/dev/null | jq -r .token 2>/dev/null)
if [ -z "${tok}" ] || [ "${tok}" = "null" ]; then
  echo "UNKNOWN token fetch failed for ${owner}/${repo} (auth hiccup - retry, do NOT read as absent)"
  exit 2
fi

code=$(curl -s -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer ${tok}" \
  -H 'Accept: application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json' \
  "https://ghcr.io/v2/${owner}/${repo}/manifests/${tag}")

case "${code}" in
  200) echo "PUBLISHED ${image}:${tag}"; exit 0 ;;
  404) echo "ABSENT ${image}:${tag} (genuine 404 - a push=true dispatch is legitimate)"; exit 1 ;;
  *)   echo "UNKNOWN HTTP ${code} ${image}:${tag} (auth/token hiccup - retry, do NOT read as absent)"; exit 2 ;;
esac
