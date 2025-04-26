"""Unit tests for type validation and graph compilation in workflow graph."""
import pytest
from typing import Any, Generic, TypeVar, List
from dataclasses import dataclass
from workflow_graph import WorkflowGraph, START, END
from workflow_graph.exceptions import ValidationError

T = TypeVar('T')

@dataclass
class GenericState(Generic[T]):
    value: T
    result: T = None

def test_start_end_type_validation():
    """Test that type validation is properly enforced for START and END nodes."""
    graph = WorkflowGraph()

    def process_int(state: GenericState[int]) -> GenericState[int]:
        return GenericState(value=state.value, result=state.value + 1)

    def process_str(state: GenericState[str]) -> GenericState[str]:
        return GenericState(value=state.value, result=state.value + " processed")

    # Add nodes with different types
    graph.add_node("process_int", process_int)
    graph.add_node("process_str", process_str)

    # This should fail because START and END nodes must have consistent types
    with pytest.raises(ValidationError):
        graph.add_edge(START, "process_int")
        graph.add_edge("process_int", "process_str")
        graph.add_edge("process_str", END)
        graph.validate()

def test_generic_type_validation():
    """Test that generic types are properly validated."""
    graph = WorkflowGraph()

    def process_int(state: GenericState[int]) -> GenericState[int]:
        return GenericState(value=state.value, result=state.value + 1)

    def process_float(state: GenericState[float]) -> GenericState[float]:
        return GenericState(value=state.value, result=state.value * 2.0)

    # Add nodes with different generic types
    graph.add_node("process_int", process_int)
    graph.add_node("process_float", process_float)

    # This should fail because generic types don't match
    with pytest.raises(ValidationError):
        graph.add_edge(START, "process_int")
        graph.add_edge("process_int", "process_float")
        graph.add_edge("process_float", END)
        graph.validate()

def test_type_consistency_validation():
    """Test that type consistency is maintained throughout the graph."""
    graph = WorkflowGraph()

    def process_a(state: GenericState[int]) -> GenericState[int]:
        return GenericState(value=state.value, result=state.value + 1)

    def process_b(state: GenericState[int]) -> GenericState[int]:
        return GenericState(value=state.value, result=state.result * 2)

    def process_c(state: GenericState[int]) -> GenericState[int]:
        return GenericState(value=state.value, result=state.result + 3)

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
    result = graph.execute(initial_state)
    assert result.result == 7  # ((1 + 1) * 2) + 3 = 7

    # Test execution with incorrect type
    with pytest.raises(TypeError):
        initial_state = GenericState[str](value="1")
        graph.execute(initial_state)

def test_duplicate_validation():
    """Test that duplicate validation is properly handled."""
    graph = WorkflowGraph()

    def process_node(state: GenericState[int]) -> GenericState[int]:
        return GenericState(value=state.value, result=state.value + 1)

    # Add the same node twice
    graph.add_node("process", process_node)

    # This should fail because the node is already added
    with pytest.raises(ValueError):
        graph.add_node("process", process_node)

def test_entry_exit_validation():
    """Test that entry and exit point validation is properly handled."""
    graph = WorkflowGraph()

    def process_node(state: GenericState[int]) -> GenericState[int]:
        return GenericState(value=state.value, result=state.value + 1)

    graph.add_node("process", process_node)

    # This should fail because there's no path to END
    with pytest.raises(ValidationError):
        graph.add_edge(START, "process")
        graph.validate()

    # This should fail because there's no path from START
    with pytest.raises(ValidationError):
        graph = WorkflowGraph()
        graph.add_node("process", process_node)
        graph.add_edge("process", END)
        graph.validate()

def test_conditional_type_validation():
    """Test that type validation works with conditional branches."""
    graph = WorkflowGraph()

    def condition(state: GenericState[int]) -> bool:
        return state.value > 0

    def process_positive(state: GenericState[int]) -> GenericState[int]:
        return GenericState(value=state.value, result=state.value * 2)

    def process_negative(state: GenericState[int]) -> GenericState[int]:
        return GenericState(value=state.value, result=abs(state.value))

    def process_string(state: GenericState[str]) -> GenericState[str]:
        return GenericState(value=state.value, result=state.value + " processed")

    # Add nodes with consistent types
    graph.add_node("check", condition)
    graph.add_node("positive", process_positive)
    graph.add_node("negative", process_negative)

    # This should succeed because all types are consistent
    graph.add_edge(START, "check")
    graph.add_conditional_edges(
        "check",
        condition,
        then="positive",
        else_="negative"
    )
    graph.add_edge("positive", END)
    graph.add_edge("negative", END)

    # This should fail because process_string has a different type
    with pytest.raises(ValidationError):
        graph.add_node("string", process_string)
        graph.add_edge("positive", "string")
        graph.add_edge("string", END)
        graph.validate() 