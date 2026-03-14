# Task 1 Plan: Call an LLM from Code

## Overview

Build a Python CLI (`agent.py`) that takes a question as a command-line argument, sends it to an LLM API, and returns a structured JSON response with `answer` and `tool_calls` fields.

## LLM Provider and Model

**Provider:** Qwen Code API (deployed on VM)
- **API Base:** `http://10.93.25.232:42005/v1` (OpenAI-compatible endpoint)
- **Model:** `qwen3-coder-plus`
- **API Key:** Stored in `.env.agent.secret` (not hardcoded)

**Rationale:**
- Qwen Code provides 1000 free requests per day
- Works from Russia without restrictions
- No credit card required
- Strong tool-calling capabilities for future tasks

## Architecture

```
CLI Input → agent.py → Qwen Code API → JSON Output
(question)   (parse,     (LLM response)  (stdout)
             call LLM)
```

## Implementation Details

### 1. Environment Configuration

Read LLM settings from `.env.agent.secret`:
- `LLM_API_KEY` - API authentication
- `LLM_API_BASE` - API endpoint URL
- `LLM_MODEL` - Model name

### 2. CLI Interface

- Accept question as first command-line argument: `uv run agent.py "Question?"`
- Use `sys.argv` for argument parsing

### 3. LLM API Call

- Use `httpx` for HTTP requests
- OpenAI-compatible chat completions API format

### 4. Response Format

Output a single JSON line to stdout:
```json
{"answer": "Response text.", "tool_calls": []}
```

### 5. Error Handling

- All debug/logging output goes to stderr
- Only valid JSON goes to stdout
- Exit code 0 on success
- 60-second timeout for LLM response

## File Structure

```
se-toolkit-lab-6/
├── agent.py              # Main CLI script
├── .env.agent.secret     # LLM configuration
├── AGENT.md              # Documentation
├── plans/
│   └── task-1.md         # This plan
└── backend/tests/unit/
    └── test_agent.py     # Regression test
```

## Testing Strategy

Create `backend/tests/unit/test_agent.py`:
1. Run `agent.py` as subprocess with a test question
2. Parse stdout as JSON
3. Assert `answer` field exists and is non-empty string
4. Assert `tool_calls` field exists and is a list
