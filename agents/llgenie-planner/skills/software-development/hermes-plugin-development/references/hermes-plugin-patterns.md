# Hermes Plugin Patterns

## Hook Return Values

### pre_llm_call

Returns context injection or empty dict:

```python
def pre_llm_call_handler(task_context, **kwargs):
    return {"context": "Task is investigation. Prefer read-only tools."}
    # or return {} for nothing
```

### pre_tool_call

Returns approve/block action:

```python
def pre_tool_call_handler(tool_name, args, task_id, **kwargs):
    if tool_name in SAFE_TOOLS:
        return {"action": "approve", "message": "Safe tool"}
    # ... validate ...
    return {"action": "block", "message": "Hallucinated tool"}
```

### post_tool_call

Returns dict (informational only):

```python
def post_tool_call_handler(tool_name, args, result, task_id, **kwargs):
    return {"coherent": True, "continue": True, "compaction": {...}}
```

## State Persistence Across Hooks

Use module-level singletons for state that must persist:

```python
_compactor = None
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = AsyncTypeSafeClient(api_key=_get_api_key())
    return _client

def _get_compactor():
    global _compactor
    if _compactor is None:
        _compactor = ContextCompactor(_get_client())
    return _compactor
```

## Config Schema Pattern

```yaml
config:
  jev_model:
    type: string
    default: "jev-latest"
    description: "TypeSafe Jev model ID"
  risk_block_threshold:
    type: float
    default: 3.0
    description: "Risk score above which calls are blocked"
  compact_turn_threshold:
    type: integer
    default: 8
    description: "Turns before compaction suggestion"
  fail_open_on_error:
    type: boolean
    default: true
    description: "Approve on Jev API failure"
```

## Profile Config Registration

Register MCP servers in each profile's `config.yaml`:

```yaml
mcp_servers:
  typesafe_jev_server:
    command: python3
    args:
      - typesafe_jev_server.py
```

## Testing Matrix

| Test Type | Needs API Key | What It Tests |
|-----------|--------------|---------------|
| Unit | No | Plugin loading, YAML validity, handler signatures |
| Integration | Yes | Real API calls, filtering, validation |
| Edge | Yes/No | Boundary values, empty inputs, large payloads |
| Permutation | Yes | All combinations of inputs |
| Enabled | No | Plugin registered in Hermes context |
| Profile | Yes | Installation across profiles |

## Makefile Template

```makefile
.PHONY: all lint test unit integration compaction install ci clean

PYTHON := python3

all: lint test

dev-deps:
	$(PYTHON) -m pip install pytest pytest-asyncio typesafe-sdk pyyaml

lint:
	$(PYTHON) -m py_compile plugin_dir/*.py
	-shellcheck scripts/install.sh

unit: dev-deps
	$(PYTHON) -m pytest tests/test_unit.py -v --tb=short

integration: dev-deps
	@if [ -z "$$TYPESAFE_API_KEY" ]; then echo "ERROR: TYPESAFE_API_KEY not set"; exit 1; fi
	$(PYTHON) -m pytest tests/test_real_api.py -v --tb=short

compaction: dev-deps
	@if [ -z "$$TYPESAFE_API_KEY" ]; then echo "ERROR: TYPESAFE_API_KEY not set"; exit 1; fi
	$(PYTHON) -m pytest tests/test_context_compactor.py -v --tb=short

test: dev-deps
	@if [ -z "$$TYPESAFE_API_KEY" ]; then echo "ERROR: TYPESAFE_API_KEY not set"; exit 1; fi
	$(PYTHON) -m pytest tests/ -v --tb=short

install:
	bash scripts/install.sh

ci: lint test
```

## CI Pipeline Structure

```yaml
jobs:
  lint:
    runs-on: ${{ matrix.os }}
    matrix:
      os: [ubuntu-latest, macos-latest]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: make lint

  install:
    needs: lint
    # ... install + verify plugin loads

  test:
    needs: [lint, install]
    if: secrets.TYPESAFE_API_KEY != ''
    steps:
      - run: make integration
        env:
          TYPESAFE_API_KEY: ${{ secrets.TYPESAFE_API_KEY }}
```

### CRITICAL: Check CI after every push

After EVERY commit and push, you MUST check the CI pipeline:

```bash
sleep 30-60
gh run list --limit 1

# If failed:
gh run view <run-id> --log-failed
```

Fix, push, and repeat. **Do not move on to another task while CI is red.**

### GitHub Actions + Python pitfalls
- `ubuntu-latest` may have Python 3.14 — pin with `actions/setup-python@v5`
- `pip` may not be on PATH — use `python -m pip install` or `pip install` after setup-python
- Test jobs fail silently if TYPESAFE_API_KEY is not set — set it explicitly in env
- Use `gh secret set <name> --body "<value>"` to configure API tokens
- Reference secrets via `${{ secrets.<NAME> }}` in workflow YAML
