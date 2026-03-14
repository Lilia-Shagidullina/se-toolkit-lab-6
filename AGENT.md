# Agent Documentation

## Overview

This agent is a Python CLI that connects to an LLM (Large Language Model) with tool-calling capabilities. It can navigate the project wiki using `read_file` and `list_files` tools to find answers and cite sources.

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
- `source` (string): Reference to the wiki section (e.g., `wiki/git-workflow.md#section-anchor`)
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

### Security

Both tools implement path security:
- Block `../` path traversal attempts
- Block absolute paths
- Verify resolved paths are within project root using `os.path.realpath()`

## System Prompt

The agent uses a system prompt that instructs the LLM to:
1. Use `list_files` to discover wiki files
2. Use `read_file` to find relevant information
3. Include source references (file path + section anchor) in answers
4. Only answer when information has been found

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
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
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
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        }
    }
]
```

### API Call Format

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

## Error Handling

- All debug/error output goes to stderr
- Only valid JSON goes to stdout
- Exit code 0 on success
- 60-second timeout for LLM responses
- Maximum 10 tool calls per question

## Testing

Run the unit tests:

```bash
uv run pytest tests/test_agent.py -v
```

## Files

| File | Description |
|------|-------------|
| `agent.py` | Main CLI script with agentic loop |
| `.env.agent.secret` | LLM configuration (not committed) |
| `AGENT.md` | This documentation |
| `plans/task-1.md` | Task 1 implementation plan |
| `plans/task-2.md` | Task 2 implementation plan |
| `tests/test_agent.py` | Regression tests |
