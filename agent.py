#!/usr/bin/env python3
"""Agent CLI - Call an LLM and return a structured JSON answer.

Usage:
    uv run agent.py "What does REST stand for?"

Output:
    {"answer": "Representational State Transfer.", "tool_calls": []}
"""

import json
import os
import sys

import httpx
from dotenv import load_dotenv

# Load environment variables from .env.agent.secret
load_dotenv(".env.agent.secret")

# LLM configuration from environment
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_API_BASE = os.getenv("LLM_API_BASE")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3-coder-plus")

# System prompt for the agent
SYSTEM_PROMPT = """You are a helpful assistant. Answer the user's question concisely and accurately.
Your response must be valid JSON with the following structure:
{"answer": "your answer here", "tool_calls": []}"""


def call_llm(question: str, timeout: int = 60) -> dict:
    """Call the LLM API and return the parsed response."""
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
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
    }

    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    # Extract the answer from the LLM response
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


def main():
    """Main entry point for the agent CLI."""
    if len(sys.argv) < 2:
        print('Usage: uv run agent.py "<question>"', file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    try:
        result = call_llm(question)

        # Ensure required fields are present
        if "answer" not in result:
            result["answer"] = "No answer provided."
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
            "tool_calls": [],
        }
        print(json.dumps(fallback))
        sys.exit(0)


if __name__ == "__main__":
    main()
