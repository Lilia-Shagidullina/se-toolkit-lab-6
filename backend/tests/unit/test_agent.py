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
