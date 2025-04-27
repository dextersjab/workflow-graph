"""Unit tests for type validation and graph compilation in workflow graph."""
import pytest
import pytest_asyncio
from typing import Any, TypeVar, List
from dataclasses import dataclass
from workflow_graph import State, WorkflowGraph, START, END
from workflow_graph.exceptions import ValidationError, ExecutionError

T = TypeVar('T')

@dataclass
class GenericState(State[T]):
    pass

@pytest.mark.asyncio
async def test_type_consistency_validation():
    """Test that type consistency is maintained throughout the graph."""
    graph = WorkflowGraph()

    def process_a(state: GenericState[int]) -> GenericState[int]:
        return GenericState(value=state.value + 1)

    def process_b(state: GenericState[int]) -> GenericState[int]:
        return GenericState(value=state.value * 2)

    def process_c(state: GenericState[int]) -> GenericState[int]:
        return GenericState(value=state.value + 3)

    # Add nodes with consistent types
    graph.add_node("a", process_a)
    graph.add_node("b", process_b)
    graph.add_node("c", process_c)

    # This should succeed because all types are consistent
    graph.add_edge(START, "a")
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")
    graph.add_edge("c", END)

    # Test execution with correct type
    initial_state = GenericState[int](value=1)
    result = await graph.execute_async(initial_state)
    assert result.value == 7  # ((1 + 1) * 2) + 3 = 7

    # Test execution with incorrect type
    with pytest.raises(ExecutionError) as excinfo:
        initial_state = GenericState[str](value="1")
        await graph.execute_async(initial_state)
    # Check that the original TypeError message is present
    assert "can only concatenate str (not \"int\") to str" in str(excinfo.value)

def test_conditional_type_validation():
    """Test that type validation works with conditional branches."""
    graph = WorkflowGraph()

    def condition(state: GenericState[int]) -> bool:
        return state.value > 0

    def check(state: GenericState[int]) -> GenericState[int]:
        return GenericState(value=state.value)

    def process_positive(state: GenericState[int]) -> GenericState[int]:
        return GenericState(value=state.value * 2)

    def process_negative(state: GenericState[int]) -> GenericState[int]:
        return GenericState(value=abs(state.value))

    def process_string(state: GenericState[str]) -> GenericState[str]:
        return GenericState(value=state.value + " processed")

    # Add nodes with consistent types
    graph.add_node("check", check)  # Renamed from "positive"
    graph.add_node("positive", process_positive)
    graph.add_node("negative", process_negative)

    # This should succeed because all types are consistent
    graph.add_edge(START, "check")
    graph.add_conditional_edges(
        "check",  # Branch from check node
        condition,
        {True: "positive", False: "negative"}  # No cycle now
    )
    graph.add_edge("positive", END)
    graph.add_edge("negative", END)

    # Compile and validate the initial graph
    compiled = graph.compile()
    compiled.validate()

    # This should fail because process_string has a different type
    with pytest.raises(ValidationError):
        graph = WorkflowGraph()
        graph.add_node("string", process_string)
        graph.add_node("positive", process_positive)
        graph.add_edge(START, "positive")
        graph.add_edge("positive", "string")
        graph.add_edge("string", END)
        compiled = graph.compile()
