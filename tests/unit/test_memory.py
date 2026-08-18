"""
Unit tests for the 6-Tier Memory Hierarchy.
"""

from zen.memory.memory_manager import MemoryManager
from zen.memory.models import MemoryCategory, MemoryItem


def test_preferences_tier(memory_manager: MemoryManager) -> None:
    # Save preferences
    memory_manager.set_preference("editor", "vscode")
    memory_manager.set_preference("speech_speed", "1.1x")

    # Read back
    assert memory_manager.get_preference("editor") == "vscode"
    assert memory_manager.get_preference("speech_speed") == "1.1x"
    assert memory_manager.get_preference("nonexistent", default="default") == "default"

    all_prefs = memory_manager.get_all_preferences()
    assert len(all_prefs) == 2
    assert all_prefs["editor"] == "vscode"


def test_corrections_tier(memory_manager: MemoryManager) -> None:
    # Record a correction
    memory_manager.record_correction(
        trigger_context="creating async loops",
        mistake_description="using time.sleep",
        correct_behavior="use asyncio.sleep",
        project_scope="my_project",
    )

    corrections = memory_manager.get_corrections("my_project")
    assert len(corrections) == 1
    assert corrections[0].trigger_context == "creating async loops"
    assert corrections[0].correct_behavior == "use asyncio.sleep"


def test_learned_facts_and_certainty(memory_manager: MemoryManager) -> None:
    # Verified fact with high certainty
    memory_manager.record_fact("cpu_model", "Intel i7 13th Gen", certainty_score=1.0)
    # Inferred fact with lower certainty
    memory_manager.record_fact("user_timezone", "EST", certainty_score=0.6, verified=False)

    high_certainty_items = memory_manager.store.get_items_by_category(
        MemoryCategory.LEARNED_FACT, min_certainty=0.8
    )
    assert len(high_certainty_items) == 1
    assert high_certainty_items[0].key == "cpu_model"


def test_prompt_injection_generation(memory_manager: MemoryManager) -> None:
    memory_manager.set_preference("tone", "concise")
    memory_manager.record_correction("writing tests", "skipping asserts", "always include assertions")
    memory_manager.set_project_context("zen_core", "Core assistant orchestration package")

    injection = memory_manager.build_memory_prompt_injection(active_project="zen_core")
    assert "tone: concise" in injection
    assert "always include assertions" in injection
    assert "Active Project (zen_core)" in injection
