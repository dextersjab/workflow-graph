"""Unit tests for basic graph operations."""
import pytest
from workflow_graph import WorkflowGraph, START, END
from workflow_graph.exceptions import (
    InvalidNodeNameError,
    DuplicateNodeError,
    InvalidEdgeError,
    TypeMismatchError
)

def test_basic_graph_creation(graph):
    """Test creating an empty graph."""
    assert isinstance(graph, WorkflowGraph)
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0

def test_add_node(graph):
    """Test adding nodes to the graph."""
    # Test adding node with string name
    graph.add_node("node1", lambda x: x + 1)
    assert "node1" in graph.nodes

    # Test adding node with function reference
    def test_func(x): return x * 2
    graph.add_node(test_func.__name__, test_func)
    assert "test_func" in graph.nodes

    # Test adding node with metadata
    graph.add_node("node3", lambda x: x + 1, metadata={"description": "Adds one"})
    assert graph.nodes["node3"].metadata["description"] == "Adds one"

def test_add_node_validation(graph):
    """Test validation rules for adding nodes."""
    # Test adding node with reserved name
    with pytest.raises(InvalidNodeNameError):
        graph.add_node(START, lambda x: x)

    # Test adding duplicate node
    graph.add_node("node1", lambda x: x)
    with pytest.raises(DuplicateNodeError):
        graph.add_node("node1", lambda x: x)

def test_add_edge(graph):
    """Test adding edges between nodes."""
    graph.add_node("node1", lambda x: x + 1)
    graph.add_node("node2", lambda x: x * 2)
    
    # Test adding valid edge
    graph.add_edge("node1", "node2")
    assert ("node1", "node2") in graph.edges

    # Test adding edge with non-existent nodes
    with pytest.raises(InvalidEdgeError):
        graph.add_edge("non_existent", "node2")

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

def test_type_validation(graph):
    """Test type compatibility between connected nodes."""
    def str_func(x: str) -> str:
        return x + "a"
    
    def int_func(x: int) -> int:
        return x + 1

    graph.add_node("str_node", str_func)
    graph.add_node("int_node", int_func)

    # Test connecting incompatible types
    with pytest.raises(TypeMismatchError):
        graph.add_edge("str_node", "int_node")
        graph.validate()

def test_type_validation_with_branches(graph):
    """Test type validation in conditional branches."""
    def num_to_str(x: int) -> str:
        return str(x)
    
    def str_append(x: str) -> str:
        return x + "a"
    
    def str_to_int(x: str) -> int:
        return int(x)

    graph.add_node("num_to_str", num_to_str)
    graph.add_node("str_append", str_append)
    graph.add_node("str_to_int", str_to_int)

    # These should work as types are compatible
    graph.add_edge("num_to_str", "str_append")
    graph.add_edge("str_append", "str_to_int") 