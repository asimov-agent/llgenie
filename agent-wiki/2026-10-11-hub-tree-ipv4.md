# 2026-10-11 Hub tree listing over IPv4

Issue #161. `macos / unit` on the #154 main push failed
`test_download_mlx_repo_snapshot_for_real` because the tree GET timed out and
`_tree` cached that as no files. Hub GETs now use a new request each attempt
and connect over IPv4. A transport failure is not cached. The five trend-pick
tests, including the real tiny safetensors snapshot, passed in the test image.
