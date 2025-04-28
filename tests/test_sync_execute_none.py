"""Tests for synchronous execution with nodes that return None or raise errors.

This module contains tests that verify the behavior of synchronous execution
when dealing with async nodes that return None or raise errors.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from workflow_graph import END, START, State, WorkflowGraph


@dataclass
class TestState(State[Any]):
    """Test state class for testing workflow execution."""

    value: Any


# Define an async node that explicitly returns None
async def async_node_returns_none(state: TestState) -> TestState:
    """Async node that returns a state with None value."""
    print(f"Executing async_node_returns_none with state: {state}")
    await asyncio.sleep(0.01)  # Simulate async work
    # Return a new state with None value
    return TestState(value=None)


# Define a simple node to follow
def output_node(state: TestState) -> TestState:
    """Node that processes the final output state."""
    print(f"Executing output_node with state: {state}")
    return TestState(
        value=f"Final result with input: {state.value.value if isinstance(state.value, State) else state.value}"
    )


# Define an async error handler that returns None (for a different test)
async def async_on_error_returns_none(error: Exception, state: TestState) -> TestState:
    """Async error handler that returns a State with None value."""
    assert isinstance(error, ValueError)
    assert str(error) == "This node is designed to fail."
    return TestState(value=None)


# Define an async node that raises an error
async def async_node_raises_error(state: TestState) -> TestState:
    """Async node that raises a ValueError."""
    print(f"Executing async_node_raises_error with state: {state}")
    await asyncio.sleep(0.01)
    raise ValueError("This node is designed to fail.")


def test_sync_execute_with_async_node_returning_none():
    """Test synchronous execution with an async node returning None.

    Verifies that graph.execute() works correctly when an intermediate
    async node returns a state with None value.
    """
    graph = WorkflowGraph()
    graph.add_node("async_node_returns_none", async_node_returns_none)
    graph.add_node("output_node", output_node)
    graph.add_edge(START, "async_node_returns_none")
    graph.add_edge("async_node_returns_none", "output_node")
    graph.add_edge("output_node", END)

    print("\nTesting synchronous execute with async node returning None...")
    # Execute synchronously
    initial_state = TestState(value="test_input")
    result = graph.execute(initial_state)

    # Assert the expected final result
    # The output_node should receive a state with None value
    assert isinstance(result, TestState)
    assert result.value == "Final result with input: None"
    print("Synchronous execute with async node returning None finished successfully.")


def test_sync_execute_with_failing_async_node_and_async_none_handler():
    """Test synchronous execution with a failing async node and async error handler.

    Verifies that graph.execute() works correctly when an async node fails
    and is handled by an async error handler that returns None.
    """
    graph = WorkflowGraph()
    graph.add_node(
        "failing_node",
        async_node_raises_error,
        on_error=async_on_error_returns_none,
        retries=0,  # No retries
    )
    graph.add_node("next_node", output_node)  # This node will process the None value

    graph.add_edge(START, "failing_node")
    graph.add_edge("failing_node", "next_node")
    graph.add_edge("next_node", END)

    print(
        "\nTesting synchronous execute with failing node and async handler returning State with None..."
    )
    initial_state = TestState(value="test_error_input")
    # Execute synchronously
    result = graph.execute(initial_state)

    # The error handler returns a State with None value, which is processed by next_node
    assert isinstance(result, TestState)
    assert result.value == "Final result with input: None"
    print(
        "Synchronous execute with failing node and async handler returning State with None finished successfully."
    )


# To run this test:
# Ensure pytest is installed: pip install pytest
# Run from the root directory: pytest tests/test_sync_execute_none.py -s
