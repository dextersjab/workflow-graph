"""Unit tests for workflow graph execution."""
import pytest
import asyncio
from workflow_graph import WorkflowGraph

def test_simple_workflow_execution(graph):
    """Test execution of a simple linear workflow."""
    def add_one(x: int) -> int:
        return x + 1

    def multiply_by_two(x: int) -> int:
        return x * 2

    graph.add_node("add", add_one)
    graph.add_node("multiply", multiply_by_two)
    graph.add_edge("add", "multiply")
    graph.set_entry_point("add")
    graph.set_finish_point("multiply")

    result = graph.execute(1)
    assert result == 4  # (1 + 1) * 2 = 4

def test_conditional_workflow_execution(graph):
    """Test execution of a workflow with conditional branches."""
    def is_even(x: int) -> bool:
        return x % 2 == 0

    def add_one(x: int) -> int:
        return x + 1

    def multiply_by_two(x: int) -> int:
        return x * 2

    graph.add_node("check", is_even)
    graph.add_node("add", add_one)
    graph.add_node("multiply", multiply_by_two)

    graph.add_conditional_edges(
        "check",
        is_even,
        {True: "add", False: "multiply"}
    )
    graph.set_entry_point("check")

    # Test with even number
    result = graph.execute(2)
    assert result == 3  # 2 is even, so add_one is called: 2 + 1 = 3

    # Test with odd number
    result = graph.execute(3)
    assert result == 6  # 3 is odd, so multiply_by_two is called: 3 * 2 = 6

@pytest.mark.asyncio
async def test_async_node_execution(graph):
    """Test execution of a workflow with async nodes."""
    async def async_add_one(x: int) -> int:
        await asyncio.sleep(0.1)
        return x + 1

    graph.add_node("async_add", async_add_one)
    graph.set_entry_point("async_add")
    result = await graph.execute_async(1)
    assert result == 2

def test_callback_execution(graph):
    """Test execution with callback functions."""
    messages = []

    def callback(msg: str):
        messages.append(msg)

    def add_one(x: int) -> int:
        return x + 1

    graph.add_node("add", add_one, callback=lambda: callback("Node executed"))
    graph.set_entry_point("add")
    result = graph.execute(1)

    assert result == 2
    assert len(messages) == 1
    assert messages[0] == "Node executed" 