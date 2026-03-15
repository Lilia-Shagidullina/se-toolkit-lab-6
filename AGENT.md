# Agent Documentation

## Overview

This agent is a Python CLI that connects to an LLM (Large Language Model) with tool-calling capabilities. It can navigate the project wiki using `read_file` and `list_files` tools, and query the deployed backend using `query_api` to find answers and cite sources.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  CLI Input  │ ──> │   agent.py   │ ──> │  Qwen Code API  │
│  (question) │     │ (agentic     │     │ (LLM response   │
│             │     │   loop)      │     │  + tool calls)  │
└─────────────┘     └──────────────┘     └─────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  JSON Output │
                    │ (answer +    │
                    │  source +    │
                    │  tool_calls) │
                    └──────────────┘
```

### Agentic Loop

1. Send user question + tool definitions to LLM
2. If LLM responds with `tool_calls`:
   - Execute each tool
   - Append results as `tool` role messages
   - Send back to LLM
3. If LLM responds with text (no tool calls):
   - Extract answer and source
   - Output JSON and exit
4. Maximum 10 tool calls per question (safety limit)

## LLM Provider

**Provider:** Qwen Code API
- **API Base:** Configurable via `LLM_API_BASE` environment variable
- **Model:** Configurable via `LLM_MODEL` environment variable (default: `qwen3-coder-plus`)
- **Authentication:** Bearer token via `LLM_API_KEY`

## Configuration

The agent reads configuration from two environment files:

### `.env.agent.secret` (LLM Configuration)

```bash
# LLM API key
LLM_API_KEY=your-api-key-here

# API base URL (OpenAI-compatible endpoint)
LLM_API_BASE=http://10.93.25.232:42005/v1

# Model name
LLM_MODEL=qwen3-coder-plus
```

### `.env.docker.secret` (Backend API Configuration)

```bash
# Backend API key for query_api authentication
LMS_API_KEY=your-lms-api-key-here
```

### Optional Environment Variables

```bash
# Base URL for query_api (default: http://localhost:42002)
AGENT_API_BASE_URL=http://localhost:42002
```

**Important:** All configuration values are read from environment variables, not hardcoded. This allows the autochecker to inject different values during evaluation.

## Usage

### Basic Usage

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

### Output Format

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

**Fields:**
- `answer` (string): The LLM's answer to the question
- `source` (string, optional): Reference to the wiki section or API endpoint
- `tool_calls` (array): All tool calls made during the agentic loop

## Tools

### `read_file`

Read a file from the project repository.

**Parameters:**
- `path` (string): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as a string, or an error message.

**Example:**
```json
{"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}}
```

### `list_files`

List files and directories at a given path.

**Parameters:**
- `path` (string): Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated listing of entries.

**Example:**
```json
{"tool": "list_files", "args": {"path": "wiki"}}
```

### `query_api`

Call the backend API with authentication.

**Parameters:**
- `method` (string): HTTP method (GET, POST, PUT, DELETE, PATCH)
- `path` (string): API path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional): JSON request body for POST/PUT requests

**Returns:** JSON string with `status_code` and `body`, or an error message.

**Authentication:** Uses `LMS_API_KEY` from environment variables.

**Example:**
```json
{"tool": "query_api", "args": {"method": "GET", "path": "/items/"}}
```

### Security

File tools (`read_file`, `list_files`) implement path security:
- Block `../` path traversal attempts
- Block absolute paths
- Verify resolved paths are within project root using `os.path.realpath()`

## System Prompt

The agent uses a system prompt that guides tool selection:

- **Wiki/source questions:** Use `list_files` to discover, `read_file` to find answers
- **Data/API questions:** Use `query_api` for data queries, status codes, API errors
- **Error diagnosis:** Use `query_api` to reproduce the error, then `read_file` to find the bug

The prompt instructs the LLM to:
1. Choose the right tool based on question type
2. Include source references when found in files
3. Source is optional for pure API data queries
4. Maximum 10 tool calls allowed

## Implementation Details

### Dependencies

- `httpx` - HTTP client for API calls
- `python-dotenv` - Environment variable loading

### Tool Schema (OpenAI Function Calling)

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository",
            "parameters": {...}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path",
            "parameters": {...}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the backend API for data queries and error diagnosis",
            "parameters": {...}
        }
    }
]
```

### API Call Format (LLM)

```python
POST /chat/completions
{
    "model": "qwen3-coder-plus",
    "messages": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "<question>"},
        {"role": "assistant", "tool_calls": [...]},
        {"role": "tool", "tool_call_id": "...", "content": "..."}
    ],
    "tools": [...],
    "tool_choice": "auto"
}
```

### API Call Format (query_api)

```python
GET /items/
Headers:
  Authorization: Bearer <LMS_API_KEY>
  Content-Type: application/json

Response:
{
  "status_code": 200,
  "body": "[...]"
}
```

## Error Handling

- All debug/error output goes to stderr
- Only valid JSON goes to stdout
- Exit code 0 on success
- 60-second timeout for LLM responses
- 30-second timeout for API calls
- Maximum 10 tool calls per question

### Common Errors

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `LMS_API_KEY not configured` | Missing `.env.docker.secret` | Create file with `LMS_API_KEY` |
| `Could not connect to API` | Backend not running | Start backend with `docker-compose up` |
| `401 Unauthorized` | Wrong API key | Check `LMS_API_KEY` matches backend |
| Agent times out | Too many tool calls | Reduce max iterations or use faster model |

## Testing

Run the unit tests:

```bash
uv run pytest tests/test_agent.py -v
```

## Benchmark Evaluation

Run the local benchmark:

```bash
uv run run_eval.py
```

The benchmark tests 10 questions across all categories:
- Wiki lookup (branch protection, SSH)
- Source code (framework, router modules)
- API data queries (item count, status codes)
- Error diagnosis (division by zero, NoneType)
- Reasoning (request lifecycle, ETL idempotency)

## Lessons Learned

1. **Tool descriptions matter:** The LLM relies on tool descriptions to decide which tool to use. Vague descriptions lead to wrong tool selection.

2. **Environment variable separation:** `LLM_API_KEY` and `LMS_API_KEY` serve different purposes. Mixing them causes authentication failures.

3. **Path security is critical:** Without path traversal protection, the agent could read sensitive files outside the project.

4. **Error messages help debugging:** Returning structured error messages from tools helps the LLM understand what went wrong and try alternative approaches.

5. **Source field flexibility:** For API queries, the source can be the endpoint itself (e.g., `GET /items/`). For file-based answers, use `path/to/file.md#section-anchor`.

6. **Bug fixes from benchmark testing:**
   - **Division by zero:** The `/completion-rate` endpoint crashed when no learners existed. Fixed by checking `total_learners == 0` before division.
   - **None-unsafe sort:** The `/top-learners` endpoint crashed when `avg_score` was `None`. Fixed by handling `None` in the sort key and output formatting.

7. **System prompt design:** Clear guidance on when to use each tool type (wiki vs API) significantly improves tool selection accuracy.

8. **Timeout handling:** Setting appropriate timeouts (60s for LLM, 30s for API) prevents the agent from hanging indefinitely.

9. **Iterative development:** Running `run_eval.py` after each change helps identify issues early and track progress.

10. **LLM limitations:** The agent may need multiple tool calls to gather enough context. The 10-call limit provides a safety net while allowing sufficient exploration.

## Files

| File | Description |
|------|-------------|
| `agent.py` | Main CLI script with agentic loop and tools |
| `.env.agent.secret` | LLM configuration (not committed) |
| `.env.docker.secret` | Backend API configuration (not committed) |
| `AGENT.md` | This documentation |
| `plans/task-1.md` | Task 1 implementation plan |
| `plans/task-2.md` | Task 2 implementation plan |
| `plans/task-3.md` | Task 3 implementation plan |
| `tests/test_agent.py` | Regression tests |
