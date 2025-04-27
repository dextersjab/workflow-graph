"""Tests for graph operations."""
import pytest
from dataclasses import dataclass
from typing import Any

from workflow_graph.builder import WorkflowGraph
from workflow_graph.constants import START, END
from workflow_graph.exceptions import (
    InvalidEdgeError,
    InvalidNodeNameError,
    TypeMismatchError,
    ValidationError,
)
from workflow_graph import Edge, State

@dataclass
class TestState(State[int]):
    """Test state class."""
    pass

@pytest.fixture
def graph():
    """Create a new workflow graph for each test."""
    return WorkflowGraph()

def test_add_node_validation(graph):
    """Test validation rules for adding nodes."""
    # Test adding node with reserved name
    with pytest.raises(InvalidNodeNameError):
        graph.add_node(START, lambda x: x)

    # Test adding node with valid name
    graph.add_node("node1", lambda x: x)
    assert "node1" in graph.nodes

def test_add_edge(graph):
    """Test adding edges between nodes."""
    graph.add_node("node1", lambda x: x + 1)
    graph.add_node("node2", lambda x: x * 2)

    # Test adding valid edge
    graph.add_edge("node1", "node2")
    assert any(edge.source == "node1" and edge.target == "node2" for edge in graph.edges["node1"])

    # Test adding edge from non-existent node
    with pytest.raises(InvalidEdgeError):
        graph.add_edge("non_existent", "node2")

    # Test adding edge to non-existent node
    with pytest.raises(InvalidEdgeError):
        graph.add_edge("node1", "non_existent")

def test_conditional_edges(graph):
    """Test adding conditional edges."""
    def is_positive(x: int) -> bool:
        return x > 0

    def is_negative(x: int) -> bool:
        return x <= 0

    graph.add_node("node1", lambda x: x + 1)
    graph.add_node("node2", lambda x: x * 2)
    graph.add_node("node3", lambda x: x - 1)

    # Test adding conditional edges
    graph.add_conditional_edges(
        "node1",
        is_positive,
        {True: "node2", False: "node3"}
    )

    assert len(graph.branches["node1"]) == 1
    assert "is_positive" in graph.branches["node1"]

    # Test adding conditional edges from non-existent node
    with pytest.raises(InvalidNodeNameError):
        graph.add_conditional_edges(
            "non_existent",
            is_negative,
            {True: "node2", False: "node3"}
        )

def test_type_validation(graph):
    """Test type compatibility between connected nodes."""
    def str_func(state: State) -> State[str]:
        return TestState(value=state.value + "a")

    def int_func(state: State) -> State[int]:
        return TestState(value=state.value + 1)

    graph.add_node("str_node", str_func, output_type=str)
    graph.add_node("int_node", int_func, input_type=int)

    # Add entry and exit points
    graph.add_edge(START, "str_node")
    graph.add_edge("str_node", END)
    graph.add_edge("int_node", END)

    # Test connecting incompatible types
    with pytest.raises(TypeMismatchError):
        graph.add_edge("str_node", "int_node")
        graph.validate()

def test_type_validation_with_branches(graph):
    """Test type validation with conditional branches."""
    def add1(state: TestState) -> TestState:
        return TestState(
            value=state.value + 1
        )

    def is_even(state: TestState) -> bool:
        return state.value % 2 == 0

    def to_str(state: TestState) -> TestState:
        return TestState(
            value=str(state.value)
        )

    def to_float(state: TestState) -> TestState:
        return TestState(
            value=float(state.value)
        )

    # Add nodes (only those returning State)
    graph.add_node("add1", add1)
    graph.add_node("to_str", to_str)
    graph.add_node("to_float", to_float)

    # Add entry and exit points
    graph.add_edge(START, "add1")
    graph.add_edge("to_str", END)
    graph.add_edge("to_float", END)

    # Use is_even as a branch condition, not a node
    graph.add_conditional_edges(
        "add1",
        condition=is_even,
        path_map={True: "to_str", False: "to_float"}
    )

    graph.validate()  # Should not raise an exception

def test_mermaid_diagram_generation():
    """Test Mermaid diagram generation."""
    graph = WorkflowGraph()

    def add(state: TestState) -> TestState:
        return TestState(
            value=state.value + 1,
        )

    def check_even(state: TestState) -> TestState:
        return TestState(
            value=state.value,
        )
    
    def is_even(state: TestState) -> bool:
        return state.value % 2 == 0

    def handle_even(state: TestState) -> TestState:
        return TestState(
            value=f"Even: {state.value}"
        )

    def handle_odd(state: TestState) -> TestState:
        return TestState(
            value=f"Odd: {state.value}"
        )

    # Add nodes
    graph.add_node("add", add)
    graph.add_node("check_even", check_even)
    graph.add_node("handle_even", handle_even)
    graph.add_node("handle_odd", handle_odd)

    graph.add_edge(START, "add")
    graph.add_edge("add", "check_even")

    graph.add_conditional_edges(
        "check_even",
        is_even,
        path_map={True: "handle_even", False: "handle_odd"}
    )

    graph.add_edge("handle_even", END)
    graph.add_edge("handle_odd", END)

    # Generate Mermaid diagram
    mermaid = graph.to_mermaid()

    # Basic assertions to ensure the diagram contains expected elements
    assert "```mermaid" in mermaid
    assert "flowchart TD" in mermaid
    assert '__start__["START"]' in mermaid
    assert '__end__["END"]' in mermaid
    assert 'add["add"]' in mermaid
    assert 'check_even["check_even"]' in mermaid
    assert 'handle_even["handle_even"]' in mermaid
    assert 'handle_odd["handle_odd"]' in mermaid

    # Check for regular edges
    assert "__start__ --> add" in mermaid
    assert "add --> check_even" in mermaid
    assert "handle_even --> __end__" in mermaid
    assert "handle_odd --> __end__" in mermaid

    # Check for conditional edges
    assert "check_even -.True.-> handle_even" in mermaid
    assert "check_even -.False.-> handle_odd" in mermaid

def test_compile_no_entry_point():
    """Test compiling a graph with no entry point raises ValueError."""
    graph = WorkflowGraph()
    graph.add_node("task1", lambda state: state)
    graph.add_edge("task1", END)
    with pytest.raises(ValidationError, match="Graph must have at least one entry point"):
        graph.compile()

def test_compile_no_finish_point():
    """Test compiling a graph with no finish point raises ValueError."""
    graph = WorkflowGraph()
    graph.add_node("task1", lambda state: state)
    graph.add_edge(START, "task1")
    # No edge to END
    with pytest.raises(ValidationError, match="Graph must have at least one exit point"):
        graph.compile()

def test_compile_with_conditional_entry():
    """Test compiling a graph with an explicit entry node that branches conditionally."""
    graph = WorkflowGraph()
    graph.add_node("entry", lambda state: state)  # Explicit entry node
    graph.add_node("task_a", lambda state: state)
    graph.add_node("task_b", lambda state: state)
    
    # Connect START to entry node
    graph.add_edge(START, "entry")
    
    # Branch from entry node instead of START
    graph.add_conditional_edges(
        "entry",
        lambda state: "a" if state.value > 5 else "b",
        {"a": "task_a", "b": "task_b"}
    )
    graph.add_edge("task_a", END)
    graph.add_edge("task_b", END)
    # Should compile without error
    graph.compile()

def test_compile_with_conditional_finish():
    """Test compiling a graph with only conditional finish points."""
    graph = WorkflowGraph()
    graph.add_node("task1", lambda state: state)
    graph.add_node("task2", lambda state: state)
    graph.add_edge(START, "task1")
    graph.add_conditional_edges("task1", lambda state: True, {True: END})
    # Should compile without error
    graph.compile() 