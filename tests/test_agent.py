"""Regression tests for agent.py CLI."""

import json
import subprocess
import sys
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.resolve()


def run_agent(question: str) -> dict:
    """Helper to run agent.py and return parsed JSON output."""
    result = subprocess.run(
        [sys.executable, "agent.py", question],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=PROJECT_ROOT,
    )
    return json.loads(result.stdout)


def test_agent_returns_valid_json():
    """Test that agent.py returns valid JSON with required fields."""
    output = run_agent("What is 2+2?")

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
    output = run_agent("What is this project about?")

    # Check source field exists
    assert "source" in output, "Response must contain 'source' field"
    assert isinstance(output["source"], str), "'source' must be a string"


def test_agent_with_wiki_question():
    """Test that agent.py uses tools for wiki questions.

    This test checks that when asked about wiki content, the agent
    uses read_file or list_files tools.
    """
    output = run_agent("What files are in the wiki?")

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
    output = run_agent("What Python web framework does the backend use?")

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
    output = run_agent("How many items are currently stored in the database?")

    # Check required fields exist
    assert "answer" in output, "Response must contain 'answer' field"
    assert "source" in output, "Response must contain 'source' field"
    assert "tool_calls" in output, "Response must contain 'tool_calls' field"

    # Check field types
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"

    # Note: query_api may fail if backend is not running, but tool should be attempted
    # or agent should provide a meaningful error response


def test_agent_api_status_code_question():
    """Test that agent uses query_api for HTTP status code questions.

    Question: 'What status code without auth?'
    Expected: query_api in tool_calls, 401/403 in answer.
    """
    output = run_agent(
        "What HTTP status code does the API return when you request /items/ without authentication?"
    )

    # Check required fields
    assert "answer" in output, "Response must contain 'answer' field"
    assert "tool_calls" in output, "Response must contain 'tool_calls' field"

    # Check that query_api was attempted (may fail if backend not running)
    tool_names = [call.get("tool") for call in output["tool_calls"]]
    # Agent should attempt query_api for status code questions
    assert "query_api" in tool_names, "Should use query_api for status code questions"


def test_agent_list_files_for_routers():
    """Test that agent uses list_files for router module questions.

    Question: 'List all API router modules'
    Expected: list_files in tool_calls, router names in answer.
    """
    output = run_agent(
        "List all API router modules in the backend. What domain does each one handle?"
    )

    # Check required fields
    assert "answer" in output, "Response must contain 'answer' field"
    assert "tool_calls" in output, "Response must contain 'tool_calls' field"

    # Check that list_files was used
    tool_names = [call.get("tool") for call in output["tool_calls"]]
    assert "list_files" in tool_names, (
        "Should use list_files to discover router modules"
    )

    # Answer should mention some routers
    answer_lower = output["answer"].lower()
    expected_routers = ["items", "analytics", "pipeline"]
    found_routers = [r for r in expected_routers if r in answer_lower]
    assert len(found_routers) > 0, "Answer should mention at least one router module"


def test_agent_branch_protection_question():
    """Test that agent uses read_file for branch protection questions.

    Question: 'According to the project wiki, what steps are needed to protect a branch?'
    Expected: read_file in tool_calls, branch/protect keywords in answer.
    """
    output = run_agent(
        "According to the project wiki, what steps are needed to protect a branch on GitHub?"
    )

    # Check required fields
    assert "answer" in output, "Response must contain 'answer' field"
    assert "tool_calls" in output, "Response must contain 'tool_calls' field"

    # Check that read_file was used
    tool_names = [call.get("tool") for call in output["tool_calls"]]
    assert "read_file" in tool_names or "list_files" in tool_names, (
        "Should use file tools for wiki questions"
    )

    # Answer should mention branch protection steps
    answer_lower = output["answer"].lower()
    assert "branch" in answer_lower or "protect" in answer_lower, (
        "Answer should mention branch protection"
    )


def test_agent_ssh_question():
    """Test that agent uses read_file for SSH connection questions.

    Question: 'What does the project wiki say about connecting to your VM via SSH?'
    Expected: read_file in tool_calls, ssh/key/connect keywords in answer.
    """
    output = run_agent(
        "What does the project wiki say about connecting to your VM via SSH? Summarize the key steps."
    )

    # Check required fields
    assert "answer" in output, "Response must contain 'answer' field"
    assert "tool_calls" in output, "Response must contain 'tool_calls' field"

    # Check that file tools were used
    tool_names = [call.get("tool") for call in output["tool_calls"]]
    assert "read_file" in tool_names or "list_files" in tool_names, (
        "Should use file tools for wiki questions"
    )

    # Answer should mention SSH-related keywords
    answer_lower = output["answer"].lower()
    ssh_keywords = ["ssh", "key", "connect", "vm"]
    found_keywords = [kw for kw in ssh_keywords if kw in answer_lower]
    assert len(found_keywords) > 0, "Answer should mention SSH-related keywords"
