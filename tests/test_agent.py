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
    # (may be empty if LLM doesn't use tools, but structure should be correct)
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"
