# Vision

llgenie exists so a person can load a trending local model on the trending inference server they choose, on the machine they have, and get the highest tokens per second that machine can honestly deliver.

## The experience

1. They pick a model from the [trending-local-llms](https://github.com/andyholst/trending-local-llms) list.
2. They pick an inference server the registry knows. The README names llama.cpp, Prism, vLLM, Ollama, SGLang, MLX, and TensorFold.
3. The choice fits this card. Card RAM selects the llama.cpp tree: Prism at 24 GB and below, upstream above that. The backend is Metal, CUDA, or CPU. Both decisions live in `scripts/detect_server.py`.
4. Among the servers that fit, the one that serves is the one with the highest measured tokens per second. A number that was not measured on this card is not a claim.
5. The result is the OpenAI-compatible local endpoint the README already describes, `http://127.0.0.1:11434/v1`.

## What later work is for

A change earns its place when it removes friction on that path: the model or the server is hard to choose, the server does not fit the card, or a faster server that does fit was not the one that served. This file does not change the ranker. Measuring tokens per second in the picker is a later change.

## What this file is not

It is not a changelog and it is not a design of the ranker. The user guide stays in the README. The layout of the code stays in `docs/ARCHITECTURE.md`.
