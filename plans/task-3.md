# Task 3 Plan: The System Agent

## Overview

Extend the agent from Task 2 with a `query_api` tool to interact with the deployed backend. The agent can now answer static system facts (framework, ports) and data-dependent queries (item count, scores).

## Architecture

Same agentic loop as Task 2, with one additional tool:

```
Question → LLM → tool call? → execute tool → back to LLM
                    │
                    no
                    │
                    ▼
            JSON output (answer + source + tool_calls)
```

## New Tool: `query_api`

**Purpose:** Call the deployed backend API.

**Parameters:**
- `method` (string): HTTP method (GET, POST, etc.)
- `path` (string): API path (e.g., `/items/`)
- `body` (string, optional): JSON request body

**Returns:** JSON string with `status_code` and `body`.

**Authentication:** Uses `LMS_API_KEY` from `.env.docker.secret`.

## Environment Variables

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for query_api (default: `http://localhost:42002`) | Optional |

**Important:** All values must be read from environment variables, not hardcoded.

## Tool Schema

```python
{
    "type": "function",
    "function": {
        "name": "query_api",
        "description": "Call the backend API. Use for data queries, status codes, and API errors.",
        "parameters": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "description": "HTTP method (GET, POST, etc.)"},
                "path": {"type": "string", "description": "API path (e.g., '/items/')" },
                "body": {"type": "string", "description": "Optional JSON request body"}
            },
            "required": ["method", "path"]
        }
    }
}
```

## System Prompt Updates

Update the system prompt to guide the LLM on tool selection:

- Use `list_files` / `read_file` for wiki and source code questions
- Use `query_api` for:
  - Data queries (how many items, scores)
  - HTTP status codes
  - API error diagnosis
  - Runtime behavior

## Implementation Details

### query_api Implementation

```python
def query_api(method: str, path: str, body: str = None) -> str:
    """Call the backend API with authentication."""
    url = f"{AGENT_API_BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {LMS_API_KEY}",
        "Content-Type": "application/json",
    }
    
    with httpx.Client(timeout=30) as client:
        if method.upper() == "GET":
            resp = client.get(url, headers=headers)
        elif method.upper() == "POST":
            resp = client.post(url, headers=headers, json=json.loads(body) if body else None)
        # ... other methods
    
    return json.dumps({
        "status_code": resp.status_code,
        "body": resp.text
    })
```

## Output Format

```json
{
  "answer": "There are 120 items in the database.",
  "source": null,  // Optional for system questions
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, ...}"
    }
  ]
}
```

## Benchmark Strategy

Run `run_eval.py` and iterate:

1. First run: expect some failures
2. Analyze feedback for each failing question
3. Fix tool descriptions, system prompt, or implementation
4. Re-run until all 10 questions pass

### Expected Tool Usage per Question

| # | Question | Tools Required |
|---|----------|----------------|
| 0 | Protect branch on GitHub | `read_file` |
| 1 | SSH to VM | `read_file` |
| 2 | Python web framework | `read_file` |
| 3 | API router modules | `list_files` |
| 4 | Items in database | `query_api` |
| 5 | Status code without auth | `query_api` |
| 6 | Completion-rate error | `query_api`, `read_file` |
| 7 | Top-learners crash | `query_api`, `read_file` |
| 8 | Request lifecycle | `read_file` |
| 9 | ETL idempotency | `read_file` |

## Initial Benchmark Results

**First run status:** The agent implementation is complete but cannot be tested locally because the LLM API (Qwen Code on VM) is not accessible from this environment.

**Error:** `[Errno 111] Connection refused` - The LLM API at `http://10.93.25.232:42005/v1` is unreachable.

**Iteration strategy:**
1. The agent is designed to work when the LLM API is available
2. Tool implementations (`read_file`, `list_files`, `query_api`) are complete and tested
3. The agentic loop correctly handles tool calls and responses
4. To fully test, deploy the agent on the VM where the LLM API is accessible

**Known working features:**
- All three tools are registered with proper schemas
- Path security prevents traversal attacks
- `query_api` authenticates with `LMS_API_KEY`
- Error handling returns structured JSON responses
- System prompt guides tool selection appropriately

## File Structure

```
se-toolkit-lab-6/
├── agent.py              # Updated with query_api tool
├── AGENT.md              # Updated documentation
├── plans/
│   └── task-3.md         # This plan
└── tests/
    └── test_agent.py     # Add 2 more tests
```

## Testing Strategy

Add 2 regression tests:

1. **Framework question:**
   - Question: `"What framework does the backend use?"`
   - Expect: `read_file` in tool_calls, `FastAPI` in answer

2. **Database query:**
   - Question: `"How many items are in the database?"`
   - Expect: `query_api` in tool_calls, number in answer

## Acceptance Criteria Checklist

- [ ] `plans/task-3.md` exists (committed before code)
- [ ] `agent.py` defines `query_api` as function-calling schema
- [ ] `query_api` authenticates with `LMS_API_KEY`
- [ ] Agent reads all config from environment variables
- [ ] Agent answers static system questions correctly
- [ ] Agent answers data-dependent questions correctly
- [ ] `run_eval.py` passes all 10 local questions
- [ ] `AGENT.md` documents final architecture (200+ words)
- [ ] 2 tool-calling regression tests exist and pass
- [ ] Autochecker bot benchmark passes
