#!/usr/bin/env python3
"""Agent CLI - Call an LLM with tools and return a structured JSON answer.

Usage:
    uv run agent.py "How do you resolve a merge conflict?"

Output:
    {
      "answer": "Answer text",
      "source": "wiki/git-workflow.md#resolving-merge-conflicts",
      "tool_calls": [...]
    }
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load environment variables from .env.agent.secret
load_dotenv(".env.agent.secret")

# LLM configuration from environment
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_API_BASE = os.getenv("LLM_API_BASE")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3-coder-plus")

# Project root for file operations
PROJECT_ROOT = Path(__file__).parent.resolve()

# Maximum tool calls per question
MAX_TOOL_CALLS = 10

# System prompt for the documentation agent
SYSTEM_PROMPT = """You are a documentation agent with access to tools for reading files.

Your goal is to find answers in the project wiki and documentation files.

Tools available:
- list_files(path): List files and directories at a given path
- read_file(path): Read the contents of a file

Process:
1. Use list_files to discover what files exist in relevant directories (e.g., "wiki", "lab")
2. Use read_file to read specific files and find the answer
3. When you find the answer, provide it along with the source reference

Source reference format: path/to/file.md#section-anchor
- Use the file path relative to project root
- Add a section anchor based on the heading where you found the answer (lowercase, hyphens instead of spaces)

Important:
- Only use the tools provided
- Always include the source field with your answer
- If you cannot find the answer after exploring, say so honestly
- Maximum 10 tool calls allowed"""


# Tool definitions for OpenAI-compatible function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository. Returns the file contents as a string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path. Returns a newline-separated listing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki')",
                    }
                },
                "required": ["path"],
            },
        },
    },
]


def validate_path(path: str) -> Path:
    """Validate and resolve a path, ensuring it's within the project root.

    Args:
        path: Relative path from project root

    Returns:
        Resolved absolute Path

    Raises:
        ValueError: If path is outside project root or uses path traversal
    """
    # Reject path traversal attempts
    if ".." in path or path.startswith("/"):
        raise ValueError(f"Invalid path: {path}")

    # Resolve the full path
    full_path = (PROJECT_ROOT / path).resolve()

    # Ensure the path is within project root
    try:
        full_path.relative_to(PROJECT_ROOT)
    except ValueError:
        raise ValueError(f"Path traversal not allowed: {path}")

    return full_path


def read_file(path: str) -> str:
    """Read a file from the project repository.

    Args:
        path: Relative path from project root

    Returns:
        File contents as string, or error message
    """
    try:
        full_path = validate_path(path)
        if not full_path.exists():
            return f"Error: File not found: {path}"
        if not full_path.is_file():
            return f"Error: Not a file: {path}"
        return full_path.read_text()
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """List files and directories at a given path.

    Args:
        path: Relative directory path from project root

    Returns:
        Newline-separated listing of entries, or error message
    """
    try:
        full_path = validate_path(path)
        if not full_path.exists():
            return f"Error: Path not found: {path}"
        if not full_path.is_dir():
            return f"Error: Not a directory: {path}"

        entries = []
        for entry in sorted(full_path.iterdir()):
            suffix = "/" if entry.is_dir() else ""
            entries.append(f"{entry.name}{suffix}")
        return "\n".join(entries)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error listing files: {e}"


# Map of tool names to functions
TOOLS_MAP = {
    "read_file": read_file,
    "list_files": list_files,
}


def execute_tool(tool_name: str, args: dict) -> str:
    """Execute a tool and return the result.

    Args:
        tool_name: Name of the tool to execute
        args: Tool arguments

    Returns:
        Tool result as string
    """
    if tool_name not in TOOLS_MAP:
        return f"Error: Unknown tool: {tool_name}"

    tool_func = TOOLS_MAP[tool_name]
    try:
        return tool_func(**args)
    except TypeError as e:
        return f"Error: Invalid arguments for {tool_name}: {e}"
    except Exception as e:
        return f"Error executing {tool_name}: {e}"


def call_llm(messages: list[dict], timeout: int = 60) -> dict:
    """Call the LLM API and return the parsed response.

    Args:
        messages: List of message dicts for the chat API
        timeout: Request timeout in seconds

    Returns:
        Parsed response data
    """
    if not LLM_API_KEY or not LLM_API_BASE:
        raise ValueError(
            "LLM_API_KEY and LLM_API_BASE must be set in .env.agent.secret"
        )

    url = f"{LLM_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 0.7,
    }

    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    return data


def run_agentic_loop(question: str) -> dict:
    """Run the agentic loop to answer a question using tools.

    Args:
        question: The user's question

    Returns:
        Result dict with answer, source, and tool_calls
    """
    # Initialize conversation with system prompt and user question
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    # Track all tool calls for output
    tool_calls_log = []
    tool_call_count = 0

    while tool_call_count < MAX_TOOL_CALLS:
        # Call the LLM
        response = call_llm(messages)
        choice = response["choices"][0]
        message = choice["message"]

        # Check for tool calls
        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            # No tool calls - LLM provided a final answer
            content = message.get("content", "")

            # Try to parse the content as JSON
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # If not JSON, create a structured response
                result = {
                    "answer": content,
                    "source": "unknown",
                }

            # Ensure required fields
            if "answer" not in result:
                result["answer"] = content or "No answer provided."
            if "source" not in result:
                result["source"] = "unknown"
            if "tool_calls" not in result:
                result["tool_calls"] = tool_calls_log

            return result

        # Execute tool calls
        for tool_call in tool_calls:
            tool_call_count += 1
            if tool_call_count > MAX_TOOL_CALLS:
                break

            function = tool_call["function"]
            tool_name = function["name"]
            tool_args = json.loads(function["arguments"])

            # Execute the tool
            result = execute_tool(tool_name, tool_args)

            # Log the tool call
            tool_calls_log.append(
                {
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result,
                }
            )

            # Add the tool response to messages
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tool_call],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result,
                }
            )

    # Max tool calls reached - provide best available answer
    return {
        "answer": "Reached maximum tool calls limit. Based on gathered information, I couldn't find a complete answer.",
        "source": "unknown",
        "tool_calls": tool_calls_log,
    }


def main():
    """Main entry point for the agent CLI."""
    if len(sys.argv) < 2:
        print('Usage: uv run agent.py "<question>"', file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    try:
        result = run_agentic_loop(question)

        # Ensure required fields are present
        if "answer" not in result:
            result["answer"] = "No answer provided."
        if "source" not in result:
            result["source"] = "unknown"
        if "tool_calls" not in result:
            result["tool_calls"] = []

        # Output only valid JSON to stdout
        print(json.dumps(result))
        sys.exit(0)

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        # Return a fallback response on error
        fallback = {
            "answer": f"Error processing question: {exc}",
            "source": "unknown",
            "tool_calls": [],
        }
        print(json.dumps(fallback))
        sys.exit(0)


if __name__ == "__main__":
    main()
