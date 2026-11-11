# Change finalization: analysis findings ship as linked issues, not prose

For every feature/bug PR in this repo, the "analysis ships issues" rule from
AGENTS.md is a concrete finalization step, not a sentiment:

- **File each real gap as its OWN issue while the verification numbers are in
  hand.** Pair the measurement with the filing: a PR body that names a live
  issue and quotes a concrete figure (a tok/s delta between two run paths, the
  bytes re-fetched by a redundant download, a tag/flag that silently picks the
  wrong variant) reads as verified; the same claim left as prose in the PR body
  is the defect the rule forbids.
- **Each filed issue states which PR it came from, and the PR's `Not covered`
  section names every one** (both directions). Never leave a finding as an
  un-filed paragraph in the PR body — a reviewer cannot track it.
- **A finding is only an issue if demonstrable** (a code path, a byte count, a
  measured rate). A vague concern is not an issue.

Concrete reusable examples from the llgenie repo this generalizes:

- The installed engine shim on a CUDA host is a `-cpu`-tagged image with no
  `--device nvidia.com/gpu=all`, so the launcher the user runs is CPU. The
  finding's evidence is a measured eval tok/s delta (40 vs 394 on a 0.5B model),
  not a complaint. Verify the host-GPU path detail in
  `references/gpu-verification-host.md`.
- A make target that writes a model into a `--rm` container's throwaway `HOME`
  means `make loop` re-fetches it — evidence is the file path + the second
  fetch in the same run, quantified in bytes.
