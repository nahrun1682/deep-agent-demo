from __future__ import annotations

from pathlib import Path

from deep_agent_demo.mcp_server import get_blackboard_facts, get_memory_policy


def test_local_mcp_tools_are_deterministic() -> None:
    facts = get_blackboard_facts(topic="blackboard pattern")
    policy = get_memory_policy()

    assert "blackboard pattern" in facts
    assert "structured outputs" in facts
    assert "proposal-first" in policy


def test_skill_directories_exist_with_skill_md() -> None:
    root = Path("skills")
    expected = [
        root / "common" / "SKILL.md",
        root / "planner" / "SKILL.md",
        root / "critic" / "SKILL.md",
        root / "synthesizer" / "SKILL.md",
    ]

    for path in expected:
        assert path.exists(), path
        assert "SKILL" in path.read_text()

