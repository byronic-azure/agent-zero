#!/usr/bin/env python3
"""
Sovereign Execution Agent - PyraClaw Cognition Fabric
Swarms 16.0.1 compatible
"""

import os
import sys

from swarms import Agent

# 1. Ensure API Key is configured
api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")

if not api_key:
    print("[WARNING] No API key detected. Set OPENAI_API_KEY or GEMINI_API_KEY.")

# 2. Initialize Optimized Autonomous Agent
agent = Agent(
    agent_name="Sovereign-Execution-Agent",
    system_prompt=(
        "You are an optimized autonomous swarm worker operating under "
        "the PyraClaw Sovereign Cognition Fabric. Provide concise, "
        "mathematically rigorous, and actionable solutions."
    ),
    model_name="gpt-4o",  # Or: 'gemini/gemini-1.5-pro', 'claude-3-5-sonnet-20241022'
    max_loops=1,
    autosave=True,
    verbose=True,
    dynamic_temperature_enabled=True,
    saved_state_path="sovereign_agent_state.json",
    user_name="iAiA_Governor"
)

# 3. Synchronous Execution Wrapper
def run_task(prompt: str) -> str:
    try:
        response = agent.run(prompt)
        return response
    except Exception as e:
        print(f"[ERROR] Swarm agent execution fault: {e}", file=sys.stderr)
        return ""

if __name__ == "__main__":
    test_task = "Analyze the stability parameters of an autonomous agent swarm."
    print(f"[RUNNING] Dispatching task to Swarms 16.0.1...")
    result = run_task(test_task)
    print(f"\n[OUTPUT]:\n{result}")
