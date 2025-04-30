"""Tests for the workflow graph builder."""

from typing import Callable, List, Optional

import pytest

from src.workflow_graph.builder import WorkflowGraph
from src.workflow_graph.exceptions import InvalidEdgeError
from src.workflow_graph.models import State


def test_add_node_with_streaming():
    """Test adding a node with streaming callback."""
    graph = WorkflowGraph()

    # Setup streaming test
    tokens: List[str] = []

    def stream_callback(token: str) -> None:
        tokens.append(token)

    def streaming_func(
        input_text: str, stream_callback: Optional[Callable[[str], None]] = None
    ) -> State:
        result = ""
        for token in ["Hello", " ", "World", "!"]:
            result += token
            if stream_callback:
                stream_callback(token)
        return State(value=result)

    # Add node with streaming callback
    graph.add_node(
        name="streaming_test", func=streaming_func, stream_callback=stream_callback
    )

    # Verify node was added with streaming callback
    node = graph.nodes["streaming_test"]
    assert node.stream_callback == stream_callback

    # Test the streaming functionality
    state = node.func("", node.stream_callback)
    assert state.value == "Hello World!"
    assert tokens == ["Hello", " ", "World", "!"]


def test_add_node_without_streaming():
    """Test adding a node without streaming callback."""
    graph = WorkflowGraph()

    def streaming_func(
        input_text: str, stream_callback: Optional[Callable[[str], None]] = None
    ) -> State:
        result = ""
        for token in ["Hello", " ", "World", "!"]:
            result += token
            if stream_callback:
                stream_callback(token)
        return State(value=result)

    # Add node without streaming callback
    graph.add_node(name="streaming_test", func=streaming_func)

    # Verify node was added without streaming callback
    node = graph.nodes["streaming_test"]
    assert node.stream_callback is None

    # Test the function still works without streaming
    state = node.func("")
    assert state.value == "Hello World!"


def test_add_node_with_streaming_and_state():
    """Test adding a node with streaming callback and state handling."""
    graph = WorkflowGraph()

    # Setup streaming test
    tokens: List[str] = []

    def stream_callback(token: str) -> None:
        tokens.append(token)

    def streaming_func(
        input_text: str, stream_callback: Optional[Callable[[str], None]] = None
    ) -> State:
        result = ""
        for token in ["Hello", " ", "World", "!"]:
            result += token
            if stream_callback:
                stream_callback(token)
        return State(value=result)

    # Add node with streaming callback
    graph.add_node(
        name="streaming_test", func=streaming_func, stream_callback=stream_callback
    )

    # Verify node was added with streaming callback
    node = graph.nodes["streaming_test"]
    assert node.stream_callback == stream_callback

    # Test the streaming functionality with state
    state = node.func("", node.stream_callback)
    assert state.value == "Hello World!"
    assert tokens == ["Hello", " ", "World", "!"]


def test_edge_branch_exclusivity():
    """Test that nodes cannot have both direct and conditional edges."""
    graph = WorkflowGraph()

    # Add some nodes
    graph.add_node("node1", lambda x: x)
    graph.add_node("node2", lambda x: x)
    graph.add_node("node3", lambda x: x)

    # First add a direct edge
    graph.add_edge("node1", "node2")

    # Then try to add conditional edges - this should fail
    with pytest.raises(InvalidEdgeError) as exc_info:
        graph.add_conditional_edges(
            "node1", lambda x: True, {True: "node3", False: "node2"}
        )
    assert "already has direct edges" in str(exc_info.value)

    # Now try the reverse - first add conditional edges
    graph = WorkflowGraph()
    graph.add_node("node1", lambda x: x)
    graph.add_node("node2", lambda x: x)
    graph.add_node("node3", lambda x: x)

    graph.add_conditional_edges(
        "node1", lambda x: True, {True: "node3", False: "node2"}
    )

    # Then try to add a direct edge - this should fail
    with pytest.raises(InvalidEdgeError) as exc_info:
        graph.add_edge("node1", "node2")
    assert "already has conditional branches" in str(exc_info.value)
