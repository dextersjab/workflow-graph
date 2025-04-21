import pytest
import asyncio
from dataclasses import dataclass
from typing import Optional, Any
from src.workflow_graph import WorkflowGraph, START, END

@dataclass
class TestState:
    value: Any
    result: Optional[Any] = None

# Define an async node that explicitly returns None
async def async_node_returns_none(state: TestState) -> TestState:
    print(f"Executing async_node_returns_none with state: {state}")
    await asyncio.sleep(0.01) # Simulate async work
    # Return a new state with None result
    return TestState(value=state.value, result=None)

# Define a simple node to follow
def final_node(state: TestState) -> TestState:
    print(f"Executing final_node with state: {state}")
    return TestState(
        value=state.value,
        result=f"Final result with input: {state.result}"
    )

# Define an async error handler that returns None (for a different test)
async def async_error_handler_returns_none(error: Exception, state: TestState) -> None:
    """Async error handler that returns None."""
    assert isinstance(error, ValueError)
    assert str(error) == "This node is designed to fail."
    return None

# Define an async node that raises an error
async def async_node_raises_error(state: TestState) -> TestState:
    print(f"Executing async_node_raises_error with state: {state}")
    await asyncio.sleep(0.01)
    raise ValueError("This node is designed to fail.")

def test_sync_execute_with_async_node_returning_none():
    """
    Tests that graph.execute() (sync) works correctly when an intermediate
    async node returns a state with None result.
    """
    graph = WorkflowGraph()
    graph.add_node("start_node", async_node_returns_none)
    graph.add_node("end_node", final_node)
    graph.add_edge(START, "start_node")
    graph.add_edge("start_node", "end_node")
    graph.add_edge("end_node", END)

    print("\nTesting synchronous execute with async node returning None...")
    # Execute synchronously
    initial_state = TestState(value="test_input")
    result = graph.execute(initial_state)

    # Assert the expected final result
    # The final_node should receive a state with None result
    assert isinstance(result, TestState)
    assert result.value == "test_input"
    assert result.result == "Final result with input: None"
    print("Synchronous execute with async node returning None finished successfully.")

def test_sync_execute_with_failing_async_node_and_async_none_handler():
    """
    Tests that graph.execute() (sync) works correctly when an async node
    fails and its async error handler returns None.
    """
    graph = WorkflowGraph()
    graph.add_node(
        "failing_node",
        async_node_raises_error,
        on_error=async_error_handler_returns_none,
        retries=0 # No retries
    )
    graph.add_node("next_node", final_node) # This node might be skipped if handler returns None

    graph.add_edge(START, "failing_node")
    # If error handler returns a value, it goes to the next node
    graph.add_edge("failing_node", "next_node")
    graph.add_edge("next_node", END)

    print("\nTesting synchronous execute with failing node and async handler returning None...")
    initial_state = TestState(value="test_error_input")
    # Execute synchronously
    result = graph.execute(initial_state)
    assert result is None  # Handler returns None, so execution should stop
    print("Synchronous execute with failing node and async handler returning None finished successfully.")

# To run this test:
# Ensure pytest is installed: pip install pytest
# Run from the root directory: pytest tests/test_sync_execute_none.py -s 