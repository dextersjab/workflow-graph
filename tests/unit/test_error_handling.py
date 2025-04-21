"""Unit tests for workflow graph error handling and retry functionality."""
import pytest
import asyncio
from workflow_graph import WorkflowGraph, START, END
from workflow_graph.exceptions import ExecutionError

def test_retry_policy(graph):
    """Test retry policy for a temporarily failing node."""
    attempts = 0

    def failing_node(x: int) -> int:
        nonlocal attempts
        attempts += 1
        if attempts < 3:  # Fail twice, succeed on third attempt
            raise ValueError("Temporary failure")
        return x + 1

    graph.add_node("retry_node", failing_node, retries=3, backoff_factor=0.1)
    graph.add_edge(START, "retry_node")
    graph.add_edge("retry_node", END)
    result = graph.execute(1)

    assert attempts == 3  # Should have attempted 3 times
    assert result == 2  # Should eventually succeed and return x + 1

def test_error_handler(graph):
    """Test error handler execution on node failure."""
    def failing_node(x: int) -> int:
        raise ValueError("Permanent failure")

    def error_handler(error: Exception) -> int:
        assert isinstance(error, ValueError)
        assert str(error) == "Permanent failure"
        return -1  # Return error value

    graph.add_node("fail_node", failing_node, on_error=error_handler)
    graph.add_edge(START, "fail_node")
    graph.add_edge("fail_node", END)
    result = graph.execute(1)

    assert result == -1  # Should return error handler result

def test_retry_then_error_handler(graph):
    """Test retry policy followed by error handler."""
    attempts = 0

    def failing_node(x: int) -> int:
        nonlocal attempts
        attempts += 1
        raise ValueError(f"Failure #{attempts}")

    def error_handler(error: Exception) -> int:
        assert isinstance(error, ValueError)
        assert str(error) == "Failure #3"  # Should be called after all retries
        return -1

    graph.add_node(
        "retry_fail_node",
        failing_node,
        retries=2,
        backoff_factor=0.1,
        on_error=error_handler
    )
    graph.add_edge(START, "retry_fail_node")
    graph.add_edge("retry_fail_node", END)
    result = graph.execute(1)
    assert attempts == 3  # Should have attempted 3 times (initial + 2 retries)
    assert result == -1  # Should return error handler result

@pytest.mark.asyncio
async def test_async_retry(graph):
    """Test retry policy with async node."""
    attempts = 0

    async def async_failing_node(x: int) -> int:
        nonlocal attempts
        attempts += 1
        await asyncio.sleep(0.1)
        if attempts < 3:
            raise ValueError("Temporary async failure")
        return x + 1

    graph.add_node("async_retry_node", async_failing_node, retries=3, backoff_factor=0.1)
    graph.add_edge(START, "async_retry_node")
    graph.add_edge("async_retry_node", END)
    result = await graph.execute_async(1)

    assert attempts == 3
    assert result == 2 