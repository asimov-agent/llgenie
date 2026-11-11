# TypeSafe Jev in Hermes Plugins

## Hermes Hook Constraints

| Hook | Can Do | Cannot Do |
|------|--------|-----------|
| `pre_llm_call` | Inject `{"context": "..."}` | Skip LLM, change model, return results |
| `pre_tool_call` | Block/approve calls | Execute tools, return synthetic results |
| `post_tool_call` | Return dict to caller | Modify history, inject context |

**Hermes issue #56655**: No per-turn model routing — closed as "Not planned".

## Plugin Architecture

```
hermes-typesafe-jev/
├── jev_middleware/
│   ├── plugin.yaml          # Manifest with hooks + config
│   ├── register.py          # Hook handlers + register(ctx)
│   ├── call_validator.py    # Pre-tool validation
│   ├── result_verifier.py   # Post-tool verification
│   ├── context_compactor.py # Conversation compaction
│   └── __init__.py
├── typesafe_jev_server.py   # MCP server bridge
├── scripts/install.sh       # Multi-profile installer
├── tests/                   # Real API tests, no mocks
└── .github/workflows/ci.yml # 5 jobs
```

## CallValidator Pattern

```python

# call_validator.py
SAFE_TOOLS = {"read_file", "search_files", "web_search", ...}
MUTATION_TOOLS = {"write_file", "patch", "terminal", "execute_code"}

class CallValidator:
    async def validate(self, tool_name, args, task_context):
        if tool_name in SAFE_TOOLS:
            return {"action": "approve", "message": "Safe tool"}
        
        response = await self.client.system_one(
            state=f"Task: {task_context}\nTool: {tool_name}\nArgs: {args}",
            questions={
                "tool_appropriate": choice(yes/uncertain/no),
                "args_complete": noul(0-1),
                "risk_level": score(0-4),
            }
        )
        
        if response.choice == "no" and probs["no"] > 0.7:
            return {"action": "block", "message": "Hallucinated"}
        if risk_score >= 3.0:
            return {"action": "block", "message": "Too risky"}
        return {"action": "approve", "message": "Validated"}
```

## ContextCompactor Pattern

```python

# context_compactor.py
COMPACT_TURN_THRESHOLD = 8
COMPACT_RESULT_THRESHOLD = 15
IRRELEVANCE_THRESHOLD = 0.30

class ContextCompactor:
    def __init__(self, client):
        self.client = client
        self.turn_count = 0
        self.tool_results = []  # Relevance tracking
        self.last_compaction = 0
    
    async def analyze_result(self, tool_name, args, tool_result, task_context):
        if len(tool_result) < 100:
            return {"relevant": True, "summarizable": False, "relevance_score": 1.0}
        
        response = await self.client.system_one(
            state=f"Task: {task_context}\nTool returned:\n{tool_result[:800]}",
            questions={
                "result_relevant": noul,
                "can_summarize": noul,
            }
        )
        return {"relevant": ..., "summarizable": ..., "relevance_score": ...}
    
    def should_compact(self):
        return (self.turn_count >= 8 and 
                len(self.tool_results) >= 15 and 
                time.time() - self.last_compaction >= 60)
    
    def get_compaction_context(self):
        if not self.should_compact():
            return ""
        return f"📊 Context: {self.turn_count} turns, {len(self.tool_results)} results..."
```

## Testing Policy

- **No mocks, no fallbacks, no skips** — all tests use real TypeSafe API
- Tests fail explicitly if `TYPESAFE_API_KEY` not set: `pytest.fail(...)`
- Unit tests cover pure logic only (no API calls)
- Edge cases test boundary values, empty inputs, large payloads
- Permutation tests cover all input combinations

## CI Configuration

```yaml

# secrets.TYPESAFE_API_KEY required

# Model: meituan/longcat-2.0:free
jobs:
  lint: { runs-on: [ubuntu-latest, macos-latest] }
  install: { needs: lint }
  test: { needs: [lint, install], if: secrets.TYPESAFE_API_KEY != '' }
  compaction: { needs: [lint, test] }
  summary: { needs: [lint, install, test, compaction] }
```

## Installer Script Pattern

```bash
#!/bin/bash

# Install MCP server
cp typesafe_jev_server.py ~/.hermes/mcp/

# Install plugin to root
cp -r jev_middleware ~/.hermes/plugins/

# Install plugin to ALL profiles
for profile_dir in ~/.hermes/profiles/*/; do
  mkdir -p "$profile_dir/plugins"
  cp -r jev_middleware "$profile_dir/plugins/"
  echo "mcp_servers:
  typesafe_jev_server:
    command: python3
    args: [typesafe_jev_server.py]" >> "$profile_dir/config.yaml"
done
```

## Common Pitfalls

- **pre_llm_call overhead**: ~400ms per turn from Jev API call. Don't inject context on every turn — only when compaction needed.
- **Jev approval varies**: `rm -rf` may be approved in some contexts. Don't hardcode expected block/approve values.
- **Small results skip analysis**: <100 chars skip Jev to reduce overhead.
- **Safe tools skip validation**: memory, session_search, todo_list, skill_view always approved.
- **Compaction cooldown**: 60s between suggestions to avoid spamming context.
- **Terminal kept for investigation**: Don't deny-list globally; call_validator blocks dangerous commands instead.
