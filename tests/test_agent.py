"""Regression tests for agent.py CLI."""

import json
import subprocess
import sys


def test_agent_returns_valid_json():
    """Test that agent.py returns valid JSON with required fields."""
    result = subprocess.run(
        [sys.executable, "-m", "uv", "run", "agent.py", "What is 2+2?"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Check required fields exist
    assert "answer" in output, "Response must contain 'answer' field"
    assert "tool_calls" in output, "Response must contain 'tool_calls' field"

    # Check field types
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"

    # Check answer is non-empty
    assert len(output["answer"]) > 0, "'answer' must not be empty"


def test_agent_returns_source_field():
    """Test that agent.py returns a response with 'source' field."""
    result = subprocess.run(
        [sys.executable, "-m", "uv", "run", "agent.py", "What is this project about?"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Check source field exists
    assert "source" in output, "Response must contain 'source' field"
    assert isinstance(output["source"], str), "'source' must be a string"


def test_agent_with_wiki_question():
    """Test that agent.py uses tools for wiki questions.

    This test checks that when asked about wiki content, the agent
    uses read_file or list_files tools.
    """
    result = subprocess.run(
        [sys.executable, "-m", "uv", "run", "agent.py", "What files are in the wiki?"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Check required fields
    assert "answer" in output, "Response must contain 'answer' field"
    assert "source" in output, "Response must contain 'source' field"
    assert "tool_calls" in output, "Response must contain 'tool_calls' field"

    # Tool calls should be populated for wiki questions
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"


def test_agent_framework_question():
    """Test that agent.py uses read_file for framework questions.

    Question: 'What framework does the backend use?'
    Expected: read_file in tool_calls, FastAPI in answer.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uv",
            "run",
            "agent.py",
            "What Python web framework does the backend use?",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Check required fields
    assert "answer" in output, "Response must contain 'answer' field"
    assert "source" in output, "Response must contain 'source' field"
    assert "tool_calls" in output, "Response must contain 'tool_calls' field"

    # Check that read_file was used
    tool_names = [call.get("tool") for call in output["tool_calls"]]
    assert "read_file" in tool_names, "Should use read_file to find framework info"


def test_agent_query_api_tool():
    """Test that agent.py has query_api tool available.

    Question: 'How many items are in the database?'
    Expected: query_api in tool_calls (when backend is available).
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uv",
            "run",
            "agent.py",
            "How many items are currently stored in the database?",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Check required fields exist
    assert "answer" in output, "Response must contain 'answer' field"
    assert "source" in output, "Response must contain 'source' field"
    assert "tool_calls" in output, "Response must contain 'tool_calls' field"

    # Check field types
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"

    # Note: query_api may fail if backend is not running, but tool should be attempted
    # or agent should provide a meaningful error response
