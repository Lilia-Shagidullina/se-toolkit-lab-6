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
# Also load .env.docker.secret for LMS_API_KEY
load_dotenv(".env.docker.secret", override=False)

# LLM configuration from environment
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_API_BASE = os.getenv("LLM_API_BASE")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3-coder-plus")

# Backend API configuration from environment
LMS_API_KEY = os.getenv("LMS_API_KEY")
AGENT_API_BASE_URL = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")

# Project root for file operations
PROJECT_ROOT = Path(__file__).parent.resolve()

# Maximum tool calls per question
MAX_TOOL_CALLS = 10

# System prompt for the system agent
SYSTEM_PROMPT = """You are a system agent with access to multiple tools.

Your goal is to find accurate answers using the available tools.

Tools available:
- list_files(path): List files and directories at a given path
- read_file(path): Read the contents of a file
- query_api(method, path, body): Call the backend API

Project structure:
- wiki/ — project documentation
- backend/app/routers/ — API router modules (items.py, analytics.py, interactions.py, pipeline.py, learners.py)
- backend/app/main.py — main FastAPI application
- backend/app/models/ — SQLAlchemy database models
- backend/app/etl.py — ETL pipeline code
- docker-compose.yml — Docker configuration
- Dockerfile — backend Dockerfile

Tool selection guide:
- Use list_files/read_file for wiki documentation and source code questions
- Use query_api for:
  - Data queries (how many items, scores, statistics)
  - HTTP status codes
  - API error diagnosis
  - Runtime behavior and responses

Process:
1. Choose the right tool based on the question type
2. For wiki/source questions: use list_files to discover, read_file to find answers
3. For data/API questions: use query_api with appropriate method and path
4. For error diagnosis: use query_api to reproduce the error, then read_file to find the bug
5. When you find the answer, provide it with a source reference if applicable

Code analysis guide (when asked about bugs or risky operations):
- Look for division operations (/) that could cause ZeroDivisionError
- Look for sorting operations with None values that could cause TypeError
- Look for database queries that might return None or empty results
- Check if error handling exists for edge cases
- When analyzing analytics.py, pay special attention to:
  - Division operations (completion rate calculations)
  - Sorting operations (top learners ranking)
  - None handling in aggregations

Output format:
You must respond with a JSON object containing:
- "answer": Your answer to the question (string)
- "source": A reference to where you found the information (string)
  - For files: use path/to/file.md#section-anchor format
  - For API queries: use the endpoint (e.g., "GET /items/")
  - If no source was used, use "unknown"

Example response:
{
  "answer": "The backend uses FastAPI framework.",
  "source": "backend/app/main.py"
}

Source reference format: path/to/file.md#section-anchor
- Use the file path relative to project root
- Add a section anchor based on the heading (lowercase, hyphens instead of spaces)
- For API queries, source can be the API endpoint (e.g., "GET /items/")

Important:
- Only use the tools provided
- Include the source field when you found information in files
- Source is optional for pure API data queries
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
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the backend API. Use for data queries, HTTP status codes, and API error diagnosis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE, etc.)",
                    },
                    "path": {
                        "type": "string",
                        "description": "API path (e.g., '/items/', '/analytics/completion-rate')",
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST/PUT requests",
                    },
                },
                "required": ["method", "path"],
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


def query_api(method: str, path: str, body: str = None) -> str:
    """Call the backend API with authentication.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: API path (e.g., '/items/')
        body: Optional JSON request body for POST/PUT requests

    Returns:
        JSON string with status_code and body, or error message
    """
    if not LMS_API_KEY:
        return json.dumps(
            {"status_code": 0, "body": "Error: LMS_API_KEY not configured"}
        )

    url = f"{AGENT_API_BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {LMS_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=30) as client:
            method_upper = method.upper()
            if method_upper == "GET":
                resp = client.get(url, headers=headers)
            elif method_upper == "POST":
                req_body = json.loads(body) if body else None
                resp = client.post(url, headers=headers, json=req_body)
            elif method_upper == "PUT":
                req_body = json.loads(body) if body else None
                resp = client.put(url, headers=headers, json=req_body)
            elif method_upper == "DELETE":
                resp = client.delete(url, headers=headers)
            elif method_upper == "PATCH":
                req_body = json.loads(body) if body else None
                resp = client.patch(url, headers=headers, json=req_body)
            else:
                return json.dumps(
                    {"status_code": 0, "body": f"Error: Unsupported method: {method}"}
                )

        return json.dumps({"status_code": resp.status_code, "body": resp.text})
    except httpx.ConnectError as e:
        return json.dumps(
            {"status_code": 0, "body": f"Error: Could not connect to API at {url}: {e}"}
        )
    except json.JSONDecodeError as e:
        return json.dumps({"status_code": 0, "body": f"Error: Invalid JSON body: {e}"})
    except Exception as e:
        return json.dumps({"status_code": 0, "body": f"Error: {e}"})


# Map of tool names to functions
TOOLS_MAP = {
    "read_file": read_file,
    "list_files": list_files,
    "query_api": query_api,
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
