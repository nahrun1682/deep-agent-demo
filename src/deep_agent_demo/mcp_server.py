from __future__ import annotations

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("deep-agent-demo")


@mcp.tool()
def get_blackboard_facts(topic: str) -> str:
    """Return deterministic facts about the study demo topic."""
    normalized = topic.strip().lower()
    if "blackboard" in normalized:
        return (
            f"The study demo uses structured outputs as canonical state for {topic.strip()}, "
            "with markdown blackboard files as the observable projection. "
            "Planner, Critic, and Synthesizer collaborate through the blackboard."
        )
    if "memory" in normalized:
        return (
            "Memory is proposal-first in this demo. "
            "Subagents can propose memory writes, but the orchestrator decides what persists."
        )
    return f"Deterministic facts for {topic.strip()}."


@mcp.tool()
def get_memory_policy() -> str:
    """Return the memory policy used by the demo."""
    return (
        "Memory policy: proposal-first. "
        "The orchestrator records the proposal, asks for approval, and then promotes the memory entry. "
        "Auto-approve is available for unattended runs."
    )


@mcp.tool()
def list_blackboard_sections() -> list[str]:
    """Return the canonical blackboard sections used by the demo."""
    return [
        "goal",
        "plan",
        "critique",
        "synthesis",
        "trace",
        "memory-proposals",
        "mcp-log",
        "state-summary",
        "decisions",
        "open-questions",
    ]


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
