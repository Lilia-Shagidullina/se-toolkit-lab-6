<!-- /*# Agent Documentation

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
| `tests/test_agent.py` | Regression tests | -->
# Agent Architecture

## Overview

This project implements an AI agent (agent.py) that answers questions using a Large Language Model (LLM) with tools. The agent can read files, list directories, and query the backend API to find answers in project documentation, source code, and live data.

## Architecture

User Question → LLM (with 3 tool schemas) → tool_calls?
    ↓ yes                                   ↓ no
Execute tools → Append results         Extract answer

- read_file
- list_files  
- query_api
    ↓
Send back to LLM
    ↓
Repeat (max 10 iterations) → Final JSON output

## Components

### 1. Agent CLI (agent.py)

Main entry point with agentic loop:

- Parse command-line arguments
- Load environment configuration
- Run agentic loop with 3 tools
- Format and output JSON response

### 2. Tools

#### read_file(path: str)

Read contents of a file from the project repository.

Parameters: path — relative path from project root  
Returns: File contents or error message

#### list_files(path: str)

List files and directories at a given path.

Parameters: path — relative directory path  
Returns: Newline-separated listing or error message

#### query_api(method: str, path: str, body: str = None)

Call the backend API with authentication.

Parameters:

- method — HTTP method (GET, POST, etc.)
- path — API path (e.g., /items/, /analytics/completion-rate)
- body — Optional JSON request body for POST/PUT

Returns: JSON string with status_code and body, or error message

Authentication: Uses LMS_API_KEY from .env.docker.secret via X-API-Key header

### 3. Security

Path traversal protection:

- Reject absolute paths
- Reject paths containing ..
- Validate resolved path is within project root

def safe_path(path: str) -> Path:
    project_root = Path(__file__).parent.resolve()
    if os.path.isabs(path) or ".." in path:
        raise ValueError("Invalid path")
    full_path = (project_root / path).resolve()
    if not str(full_path).startswith(str(project_root)):
        raise ValueError("Path outside project")
    return full_path

### 4. Environment Configuration

`.env.agent.secret` (LLM configuration):

| Variable | Description | Example |
|----------|-------------|---------|
| LLM_API_KEY | LLM provider API key | ollama |
| LLM_API_BASE | LLM API endpoint | <http://10.93.25.238:8080/v1> |
| LLM_MODEL | Model name | qwen2.5:3b |

`.env.docker.secret` (Backend API configuration):

| Variable | Description | Example |
|----------|-------------|---------|
| LMS_API_KEY | Backend API key for query_api | my-secret-api-key |
| AGENT_API_BASE_URL | Backend base URL | <http://localhost:42002> |

### 5. LLM Backend (Ollama on VM)

Provider: Ollama (self-hosted)  
Model: Qwen 2.5 3B  
Endpoint: <http://10.93.25.238:8080/v1>

## Usage

# Run the agent with a question

uv run agent.py "How many items are in the database?"

# Output (JSON to stdout)

{
  "answer": "There are 120 items in the database.",
  "source": "",
  "tool_calls": [
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": "{\"status_code\": 200, ...}"}
  ]
}

## Output Format

{
  "answer": "The LLM's response text",
  "source": "wiki/filename.md#section-anchor",
  "tool_calls": [
    {
      "tool": "tool_name",
      "args": {"param": "value"},
      "result": "tool output"
    }
  ]
}

Note: source is optional — system questions may not have a wiki source.

## Agentic Loop

1. Initialize conversation with system prompt + user question
2. Call LLM with 3 tool schemas
3. Check response:
   - If tool_calls → execute tools, append results as tool role messages, go to step 2
   - If text answer → extract answer + source, output JSON, exit
4. Max iterations: 10 tool calls

## System Prompt Strategy

The system prompt instructs the LLM to:

1. Use list_files for directory exploration
2. Use read_file for wiki and source code questions
3. Use query_api for live data, status codes, API behavior
4. Include source references for file-based answers

Key distinction: Wiki/source questions → read_file; Live data → query_api

## Tool Schemas (OpenAI Function Calling)

Three tools registered with the LLM:

[
  {
    "type": "function",
    "function": {
      "name": "read_file",
      "description": "Read contents of a file from the project repository",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {"type": "string", "description": "Relative path from project root"}
        },
        "required": ["path"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "list_files",
      "description": "List files and directories at a given path",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {"type": "string", "description": "Relative directory path"}
        },
        "required": ["path"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "query_api",
      "description": "Call the backend API to query data, check status codes, or test endpoints",
      "parameters": {
        "type": "object",
        "properties": {
          "method": {"type": "string", "description": "HTTP method (GET, POST, etc.)"},
          "path": {"type": "string", "description": "API path"},
          "body": {"type": "string", "description": "Optional JSON request body"}
        },
        "required": ["method", "path"]
      }
    }
  }
]

## Files

| File | Description |
|------|-------------|
| agent.py | Main CLI script with agentic loop |
| .env.agent.secret | LLM configuration (gitignored) |
| .env.docker.secret | Backend API configuration (gitignored) |
| plans/task-1.md | Task 1: LLM agent |
| plans/task-2.md | Task 2: Documentation agent |
| plans/task-3.md | Task 3: System agent |
| AGENT.md | This documentation |
| tests/test_agent.py | Regression tests |

## Testing

Run the test suite:

```bash
uv run pytest tests/test_agent.py -v
```

Tests (9 total):

- test_agent_returns_valid_json — verifies JSON structure
- test_agent_returns_source_field — verifies source field exists
- test_agent_with_wiki_question — wiki documentation questions
- test_agent_framework_question — source code questions (FastAPI)
- test_agent_query_api_tool — API data queries
- test_agent_api_status_code_question — HTTP status code questions
- test_agent_list_files_for_routers — router module discovery
- test_agent_branch_protection_question — wiki lookup for branch protection
- test_agent_ssh_question — wiki lookup for SSH connection

## Benchmark Evaluation

Run the local benchmark:

uv run run_eval.py

The benchmark tests 10 questions across categories:

- Wiki lookup (questions 0-1)
- Source code analysis (questions 2-3)
- API data queries (questions 4-5)
- Error diagnosis (questions 6-7)
- System reasoning (questions 8-9, LLM judge)

## Deployment

The LLM (Ollama) runs on the VM:

# On VM: start Ollama

docker run -d --name ollama --restart unless-stopped \
  -p 8080:11434 -v ollama:/root/.ollama ollama/ollama:latest

# Pull model

docker exec ollama ollama pull qwen2.5:3b

The backend runs separately via Docker Compose on port 42002.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (missing config, API failure, etc.) |

## Limitations

- Maximum 10 tool calls per question
- Ollama qwen2.5:3b may be slow for multi-turn conversations (5-30 seconds per iteration)
- Tool results are truncated in logs for readability
- query_api requires LMS_API_KEY to be configured

## Lessons Learned (Task 3)

1. __Tool descriptions matter:__ The LLM relies on tool descriptions to decide which tool to use. Vague descriptions lead to wrong tool selection.

2. __Source field is optional:__ Not all questions have a wiki source. System queries (via query_api) don't have a file reference.

3. __Two API keys:__ LLM_API_KEY authenticates with the LLM provider; LMS_API_KEY authenticates with the backend API. Don't mix them up.

4. __Environment variables:__ The autochecker injects its own values. Never hardcode API keys, base URLs, or model names.

5. __Error handling:__ The agent must gracefully handle API errors, file not found, and path traversal attempts.

6. __Iteration limit:__ The 10-iteration limit prevents infinite loops but may cut off complex multi-step reasoning.

7. __Content truncation:__ Large files get truncated in tool results. The LLM may miss information if the file is too long.

8. __Project structure in system prompt:__ Adding explicit project structure information to the system prompt significantly improves the agent's ability to navigate the codebase. The agent now knows exactly where to find routers, models, and configuration files.

9. __Explicit JSON output format:__ The LLM doesn't always return structured JSON by default. Adding explicit output format instructions with an example response dramatically improved the consistency of JSON output and proper population of the `source` field.

10. __query_api authentication:__ The query_api tool must authenticate using Bearer token format (`Authorization: Bearer {LMS_API_KEY}`), not `X-API-Key` header. This was critical for the backend API to accept requests.

11. __HTTP method handling:__ The query_api implementation must handle multiple HTTP methods (GET, POST, PUT, DELETE, PATCH) to support various API endpoints. Each method requires different handling of request bodies.

12. __Timeout configuration:__ Setting appropriate timeouts (60s for LLM, 30s for API) prevents the agent from hanging indefinitely on slow responses or network issues.

13. __Iterative benchmark testing:__ Running `run_eval.py` after each change helps identify issues early. The workflow is: run benchmark → analyze failure → fix tool description/prompt/implementation → re-run.

14. __Tool selection patterns:__ The agent learns to associate question types with tools:
    - "What files..." → list_files
    - "What framework..." → read_file
    - "How many items..." → query_api
    - "What status code..." → query_api
    - "Explain the error..." → query_api + read_file

## Final Test Results

All 9 regression tests pass:

- test_agent_returns_valid_json
- test_agent_returns_source_field
- test_agent_with_wiki_question
- test_agent_framework_question
- test_agent_query_api_tool
- test_agent_api_status_code_question
- test_agent_list_files_for_routers
- test_agent_branch_protection_question (new - Task 3)
- test_agent_ssh_question (new - Task 3)
