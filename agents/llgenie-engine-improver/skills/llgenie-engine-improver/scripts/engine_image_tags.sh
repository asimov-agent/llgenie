#!/usr/bin/env bash
# engine_image_tags.sh <engine-id> [root] [--probe]
#   engine-id: the params id, e.g. llama.cpp (dots allowed; the tag dashes them)
#   root:      repo checkout (defaults to $PWD) - must be the tree whose params you mean
#   --probe:   also probe each tag on GHCR via ghcr_publish_probe.sh (exit 0 only if ALL 200)
#
# Why this exists: the <digest8> in an image tag is VARIANT-SPECIFIC - it hashes that variant's own
# Dockerfile plus entrypoint.sh and engine_runner.py. Never reuse one variant's digest to probe a
# sibling (a real 404 means nothing there) and never quote a tag you did not compute from the tree.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
eng="${1:?usage: engine_image_tags.sh <engine-id> [root] [--probe]}"
root="${2:-$PWD}"
[ "${root}" = "--probe" ] && root="$PWD"
probe=0
for a in "$@"; do [ "$a" = "--probe" ] && probe=1; done

rows=$(python3 - "$eng" "$root" <<'PY'
import importlib, json, os, sys
eng, root = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(root, 'scripts'))
params = json.load(open(os.path.join(root, 'containers/engines/params', eng + '.json')))
mod = None
for name in ('engine_image', 'engine_skills'):
    try:
        mod = importlib.import_module(name); break
    except ImportError:
        continue
if mod is None:
    sys.exit('no engine_image/engine_skills module under ' + root)
variants = list(params.get('variants', {}))
if hasattr(mod, 'image_spec'):
    for v in variants:
        print(mod.image_spec(params, v)['tag'])
else:
    leaf = params['id'].replace('.', '-')
    for v in variants:
        print('llgenie/%s:%s-%s-%s' % (leaf, str(params['pinned'])[:8], mod._image_hash(params, v), v))
PY
) || { echo "could not compute tags for ${eng} under ${root}" >&2; exit 2; }

[ -z "${rows}" ] && { echo "no variants for ${eng}" >&2; exit 2; }
rc=0
while IFS= read -r ref; do
  printf '%s\n' "${ref}"
  if [ "${probe}" -eq 1 ]; then
    leaf="${ref%%:*}"; leaf="${leaf#llgenie/}"; tag="${ref##*:}"
    bash "${here}/ghcr_publish_probe.sh" "${leaf}" "${tag}" || rc=1
  fi
done <<< "${rows}"
exit "${rc}"
