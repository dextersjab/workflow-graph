"""Unit tests for workflow graph error handling and retry functionality."""
import pytest
import asyncio
from dataclasses import dataclass
from typing import Optional, List
from workflow_graph import WorkflowGraph, START, END
from workflow_graph.exceptions import ExecutionError

@dataclass
class TestState:
    value: int
    result: Optional[int] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

def test_retry_policy(graph):
    """Test retry policy for a temporarily failing node."""
    attempts = 0

    def failing_node(state: TestState) -> TestState:
        nonlocal attempts
        attempts += 1
        if attempts < 3:  # Fail twice, succeed on third attempt
            raise ValueError("Temporary failure")
        return TestState(
            value=state.value,
            result=state.value + 1,
            errors=state.errors
        )

    graph.add_node("retry_node", failing_node, retries=3, backoff_factor=0.1)
    graph.add_edge(START, "retry_node")
    graph.add_edge("retry_node", END)
    
    initial_state = TestState(value=1)
    result = graph.execute(initial_state)

    assert attempts == 3  # Should have attempted 3 times
    assert result.result == 2  # Should eventually succeed and return x + 1

def test_error_handling_with_state(graph):
    """Test error handling that preserves state information."""
    def failing_node(state: TestState) -> TestState:
        raise ValueError("Simulated error")

    def error_handler(error: Exception, state: TestState) -> TestState:
        return TestState(
            value=state.value,
            result=-1,
            errors=state.errors + [f"Error handled: {str(error)}"]
        )

    graph.add_node(
        "failing_node",
        failing_node,
        retries=0,
        on_error=error_handler
    )
    graph.add_edge(START, "failing_node")
    graph.add_edge("failing_node", END)

    initial_state = TestState(value=1)
    result = graph.execute(initial_state)

    assert result.result == -1
    assert len(result.errors) == 1
    assert "Error handled: Simulated error" in result.errors[0]

def test_async_error_handling(graph):
    """Test error handling with async nodes."""
    async def failing_async_node(state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        raise ValueError("Async error")

    async def async_error_handler(error: Exception, state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        return TestState(
            value=state.value,
            result=-1,
            errors=state.errors + [f"Async error handled: {str(error)}"]
        )

    graph.add_node(
        "failing_async_node",
        failing_async_node,
        retries=0,
        on_error=async_error_handler
    )
    graph.add_edge(START, "failing_async_node")
    graph.add_edge("failing_async_node", END)

    initial_state = TestState(value=1)
    result = asyncio.run(graph.execute_async(initial_state))

    assert result.result == -1
    assert len(result.errors) == 1
    assert "Async error handled: Async error" in result.errors[0]

def test_error_handler(graph):
    """Test error handler execution on node failure."""
    def failing_node(state: TestState) -> TestState:
        raise ValueError("Permanent failure")

    def error_handler(error: Exception, state: TestState) -> TestState:
        assert isinstance(error, ValueError)
        assert str(error) == "Permanent failure"
        return TestState(
            value=state.value,
            result=-1,
            errors=state.errors + [str(error)]
        )

    graph.add_node("fail_node", failing_node, on_error=error_handler)
    graph.add_edge(START, "fail_node")
    graph.add_edge("fail_node", END)
    result = graph.execute(TestState(value=1))

    assert result.result == -1  # Should return error handler result
    assert len(result.errors) == 1
    assert "Permanent failure" in result.errors[0]

def test_retry_then_error_handler(graph):
    """Test retry policy followed by error handler."""
    attempts = 0

    def failing_node(state: TestState) -> TestState:
        nonlocal attempts
        attempts += 1
        raise ValueError(f"Failure #{attempts}")

    def error_handler(error: Exception, state: TestState) -> TestState:
        assert isinstance(error, ValueError)
        assert str(error) == "Failure #3"  # Should be called after all retries
        return TestState(
            value=state.value,
            result=-1,
            errors=state.errors + [str(error)]
        )

    graph.add_node(
        "retry_fail_node",
        failing_node,
        retries=2,
        backoff_factor=0.1,
        on_error=error_handler
    )
    graph.add_edge(START, "retry_fail_node")
    graph.add_edge("retry_fail_node", END)
    result = graph.execute(TestState(value=1))
    assert attempts == 3  # Should have attempted 3 times (initial + 2 retries)
    assert result.result == -1  # Should return error handler result
    assert len(result.errors) == 1
    assert "Failure #3" in result.errors[0]

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