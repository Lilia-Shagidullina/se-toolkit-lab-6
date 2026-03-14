# Task 2 Plan: The Documentation Agent

## Overview

Extend the agent from Task 1 with two tools (`read_file`, `list_files`) and an agentic loop. The agent can now navigate the project wiki to find answers and cite sources.

## Architecture

```
Question → LLM → tool call? → execute tool → back to LLM
                    │
                    no
                    │
                    ▼
            JSON output (answer + source + tool_calls)
```

## Tool Definitions

### 1. `read_file`

**Purpose:** Read a file from the project repository.

**Parameters:**
- `path` (string): Relative path from project root

**Returns:** File contents as string, or error message if file doesn't exist.

**Security:** Block `../` path traversal attempts.

### 2. `list_files`

**Purpose:** List files and directories at a given path.

**Parameters:**
- `path` (string): Relative directory path from project root

**Returns:** Newline-separated listing of entries.

**Security:** Block `../` path traversal attempts.

## Tool Schema (OpenAI Function Calling)

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository",
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
    }
]
```

## Agentic Loop

1. Send user question + tool definitions to LLM
2. Parse response:
   - If `tool_calls` present → execute each tool, append results as `tool` role messages, repeat step 1
   - If text response → extract answer and source, output JSON, exit
3. Maximum 10 tool calls per question (safety limit)
4. Track all tool calls for output

## System Prompt Strategy

```
You are a documentation agent. Use tools to find answers in the project wiki.

Tools available:
- list_files(path): List files in a directory
- read_file(path): Read file contents

Process:
1. Use list_files to discover wiki files
2. Use read_file to find relevant information
3. Include source reference (file path + section anchor) in your answer
4. Only answer when you have found the information

Always include the source field with format: wiki/filename.md#section-anchor
```

## Output Format

```json
{
  "answer": "Answer text here",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

## Security

- Validate paths: reject `../` or absolute paths
- Only allow paths within project root
- Use `os.path.realpath()` to resolve and verify paths

## File Structure

```
se-toolkit-lab-6/
├── agent.py              # Updated with tools + agentic loop
├── AGENT.md              # Updated documentation
├── plans/
│   └── task-2.md         # This plan
└── tests/
    └── test_agent.py     # Add 2 more tests
```

## Testing Strategy

Add 2 regression tests:

1. **Merge conflict question:**
   - Question: `"How do you resolve a merge conflict?"`
   - Expect: `read_file` in tool_calls, `wiki/git-workflow.md` in source

2. **Wiki listing question:**
   - Question: `"What files are in the wiki?"`
   - Expect: `list_files` in tool_calls

## Acceptance Criteria Checklist

- [ ] `plans/task-2.md` exists (committed before code)
- [ ] `agent.py` defines `read_file` and `list_files` as tool schemas
- [ ] Agentic loop executes tool calls and feeds results back
- [ ] `tool_calls` populated when tools are used
- [ ] `source` field correctly identifies wiki section
- [ ] Tools block path traversal attacks
- [ ] `AGENT.md` documents tools and agentic loop
- [ ] 2 tool-calling regression tests exist and pass
