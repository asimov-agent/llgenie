# 2026-09-26 model context window

`llgenie` sets `llama-server` `-c` from the selected GGUF's `context_length`,
lowered only when the q4_0 KV cache does not fit card RAM. Hybrid models use
`full_attention_interval`, key/value length, and the MTP block. Ternary Bonsai
2 (262144) on a 16 GB card stays at 262144; the same shape on 8 GB is 30720.

Verified: `make test-unit` 192 passed, `make openspec-validate
NAME=feat-server-clone-build` valid. Issue #84 acceptance updated. Hermes
`local-llm` nerve threshold is 0.60 of the live `/props` n_ctx (profile config,
not this repo).
