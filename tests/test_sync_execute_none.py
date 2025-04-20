import pytest
import asyncio
from src.workflow_graph import WorkflowGraph

# Define an async node that explicitly returns None
async def async_node_returns_none(data):
    print(f"Executing async_node_returns_none with data: {data}")
    await asyncio.sleep(0.01) # Simulate async work
    # Explicitly return None
    return None

# Define a simple node to follow
def final_node(data):
    print(f"Executing final_node with data: {data}")
    return f"Final result with input: {data}"

# Define an async error handler that returns None (for a different test)
async def async_error_handler_returns_none(error):
    print(f"Async error handler caught: {error}, returning None")
    await asyncio.sleep(0.01)
    return None

# Define an async node that raises an error
async def async_node_raises_error(data):
    print(f"Executing async_node_raises_error with data: {data}")
    await asyncio.sleep(0.01)
    raise ValueError("This node is designed to fail.")

def test_sync_execute_with_async_node_returning_none():
    """
    Tests that graph.execute() (sync) works correctly when an intermediate
    async node returns None.
    """
    graph = WorkflowGraph()
    graph.add_node("start_node", async_node_returns_none)
    graph.add_node("end_node", final_node)
    graph.set_entry_point("start_node")
    graph.add_edge("start_node", "end_node")
    graph.set_finish_point("end_node")

    print("\nTesting synchronous execute with async node returning None...")
    # Execute synchronously
    # If the bug exists, this might raise "await NoneType"
    initial_data = "test_input"
    result = graph.execute(initial_data)

    # Assert the expected final result
    # The final_node should receive None as input from async_node_returns_none
    assert result == "Final result with input: None"
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

    graph.set_entry_point("failing_node")
    # If error handler returns a value, it goes to the next node
    graph.add_edge("failing_node", "next_node")
    # Assuming the result of the error handler should end the graph path
    graph.set_finish_point("next_node")

    print("\nTesting synchronous execute with failing node and async handler returning None...")
    initial_data = "test_error_input"
    # Execute synchronously
    result = graph.execute(initial_data)

    # The async error handler returns None.
    # The current implementation passes this result to the next node ('next_node').
    # Therefore, the final result should be the output of final_node(None).
    expected_result = final_node(None) # Calculate expected result based on actual behavior
    assert result == expected_result
    print("Synchronous execute with failing node and async handler returning None finished successfully.")

# To run this test:
# Ensure pytest is installed: pip install pytest
# Run from the root directory: pytest tests/test_sync_execute_none.py -s 