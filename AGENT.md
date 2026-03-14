# Agent Documentation

## Overview

This agent is a Python CLI that connects to an LLM (Large Language Model) and answers questions. It serves as the foundation for more advanced agent features (tools, agentic loop) in subsequent tasks.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  CLI Input  │ ──> │   agent.py   │ ──> │  Qwen Code API  │
│  (question) │     │  (parse,     │     │  (LLM response) │
│             │     │   call LLM)  │     │                 │
└─────────────┘     └──────────────┘     └─────────────────┘
                           │
                           v
                    ┌──────────────┐
                    │  JSON Output │
                    │  (stdout)    │
                    └──────────────┘
```

## LLM Provider

**Provider:** Qwen Code API
- **API Base:** `http://10.93.25.232:42005/v1`
- **Model:** `qwen3-coder-plus`
- **Authentication:** Bearer token via `LLM_API_KEY`

## Configuration

The agent reads configuration from `.env.agent.secret`:

```bash
# LLM API key
LLM_API_KEY=your-api-key-here

# API base URL (OpenAI-compatible endpoint)
LLM_API_BASE=http://10.93.25.232:42005/v1

# Model name
LLM_MODEL=qwen3-coder-plus
```

## Usage

### Basic Usage

```bash
uv run agent.py "What does REST stand for?"
```

### Output Format

The agent outputs a single JSON line to stdout:

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

**Fields:**
- `answer` (string): The LLM's answer to the question
- `tool_calls` (array): Empty for Task 1 (will be populated in Task 2)

### Error Handling

- All debug/error output goes to stderr
- Only valid JSON goes to stdout
- Exit code 0 on success
- 60-second timeout for LLM responses

## Implementation Details

### Dependencies

- `httpx` - HTTP client for API calls
- `python-dotenv` - Environment variable loading

### API Call Format

The agent uses the OpenAI-compatible chat completions API:

```python
POST /chat/completions
{
    "model": "qwen3-coder-plus",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant..."},
        {"role": "user", "content": "<question>"}
    ],
    "response_format": {"type": "json_object"}
}
```

## Testing

Run the unit test:

```bash
uv run poe test-unit
```

## Files

| File | Description |
|------|-------------|
| `agent.py` | Main CLI script |
| `.env.agent.secret` | LLM configuration (not committed) |
| `AGENT.md` | This documentation |
| `plans/task-1.md` | Implementation plan |
| `backend/tests/unit/test_agent.py` | Regression test |
