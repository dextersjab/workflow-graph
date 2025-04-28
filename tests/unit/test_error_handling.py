"""Unit tests for workflow graph error handling and retry functionality."""
import pytest
import asyncio
from dataclasses import dataclass
from typing import Optional, List
from workflow_graph import State, START, END
from workflow_graph.exceptions import ExecutionError

TestState = State[int]

def test_retry_policy(graph):
    """Test retry policy for a temporarily failing node."""
    attempts = 0

    def failing_node(state: TestState) -> TestState:
        nonlocal attempts
        attempts += 1
        if attempts < 3:  # Fail twice, succeed on third attempt
            raise ValueError("Temporary failure")
        return state.updated(value=state.value + 1)

    graph.add_node("retry_node", failing_node, retries=3, backoff_factor=0.1)
    graph.add_edge(START, "retry_node")
    graph.add_edge("retry_node", END)
    
    initial_state = TestState(value=1)
    result = graph.execute(initial_state)

    assert attempts == 3  # Should have attempted 3 times
    assert result.value == 2  # Should eventually succeed and return x + 1

def test_error_handling_with_state(graph):
    """Test error handling that preserves state information."""
    def failing_node(state: TestState) -> TestState:
        raise ValueError("Simulated error")

    def on_error(error: Exception, state: TestState) -> TestState:
        return state.updated(value=-1).add_error(error, "Error handled")

    graph.add_node(
        "failing_node",
        failing_node,
        retries=0,
        on_error=on_error
    )
    graph.add_edge(START, "failing_node")
    graph.add_edge("failing_node", END)

    initial_state = TestState(value=1)
    result = graph.execute(initial_state)

    assert result.value == -1
    assert len(result.errors) == 1
    assert "Error handled: Simulated error" in result.errors[0]

def test_async_error_handling(graph):
    """Test error handling with async nodes."""
    async def failing_async_node(state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        raise ValueError("Async error")

    async def async_on_error(error: Exception, state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        return state.updated(value=-1).add_error(error, "Async error handled")

    graph.add_node(
        "failing_async_node",
        failing_async_node,
        retries=0,
        on_error=async_on_error
    )
    graph.add_edge(START, "failing_async_node")
    graph.add_edge("failing_async_node", END)

    initial_state = TestState(value=1)
    result = asyncio.run(graph.execute_async(initial_state))

    assert result.value == -1
    assert len(result.errors) == 1
    assert "Async error handled: Async error" in result.errors[0]

def test_on_error(graph):
    """Test error handler execution on node failure."""
    def failing_node(state: TestState) -> TestState:
        raise ValueError("Permanent failure")

    def on_error(error: Exception, state: TestState) -> TestState:
        assert isinstance(error, ValueError)
        assert str(error) == "Permanent failure"
        return state.updated(value=-1).add_error(error)

    graph.add_node("fail_node", failing_node, on_error=on_error)
    graph.add_edge(START, "fail_node")
    graph.add_edge("fail_node", END)
    result = graph.execute(TestState(value=1))

    assert result.value == -1  # Should return error handler result
    assert len(result.errors) == 1
    assert "Permanent failure" in result.errors[0]

def test_retry_then_on_error(graph):
    """Test retry policy followed by error handler."""
    attempts = 0

    def failing_node(state: TestState) -> TestState:
        nonlocal attempts
        attempts += 1
        raise ValueError(f"Failure #{attempts}")

    def on_error(error: Exception, state: TestState) -> TestState:
        assert isinstance(error, ValueError)
        assert str(error) == "Failure #3"  # Should be called after all retries
        return state.updated(value=-1).add_error(error)

    graph.add_node(
        "retry_fail_node",
        failing_node,
        retries=2,
        backoff_factor=0.1,
        on_error=on_error
    )
    graph.add_edge(START, "retry_fail_node")
    graph.add_edge("retry_fail_node", END)
    result = graph.execute(TestState(value=1))
    assert attempts == 3  # Should have attempted 3 times (initial + 2 retries)
    assert result.value == -1  # Should return error handler result
    assert len(result.errors) == 1
    assert "Failure #3" in result.errors[0]

@pytest.mark.asyncio
async def test_async_retry(graph):
    """Test retry policy with async node."""
    attempts = 0

    async def async_failing_node(state: State) -> State:
        nonlocal attempts
        attempts += 1
        await asyncio.sleep(0.1)
        if attempts < 3:
            raise ValueError("Temporary async failure")
        return state.updated(value=state.value + 1)

    graph.add_node("async_retry_node", async_failing_node, retries=3, backoff_factor=0.1)
    graph.add_edge(START, "async_retry_node")
    graph.add_edge("async_retry_node", END)
    initial_state = State(value=1)
    result = await graph.execute_async(initial_state)

    assert attempts == 3
    assert result.value == 2 