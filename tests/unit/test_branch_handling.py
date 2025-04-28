"""Unit tests for branch handling and callback timing in workflow graph."""

import asyncio
from dataclasses import dataclass

import pytest

from workflow_graph import END, START, State


@dataclass
class BranchState:
    """State class for testing branch handling in workflow graphs.

    This class represents a simple state that can be used to test branching
    behavior in workflow graphs. It tracks a numeric value and whether that
    value is considered high or not.
    """

    value: int
    is_high: bool | None = None


TestState = State[BranchState]


@pytest.mark.asyncio
async def test_async_branch_condition(graph):
    """Test async branch condition evaluation."""

    async def check_node(state: TestState) -> TestState:
        """Node function that evaluates condition and stores result."""
        await asyncio.sleep(0.1)
        is_high = state.value.value > 5
        return state.updated(
            value=BranchState(value=state.value.value, is_high=is_high)
        )

    async def branch_condition(state: TestState) -> bool:
        """Branch condition that reads the stored result."""
        return state.value.is_high

    async def high_value_handler(state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        return state.updated(
            value=BranchState(value=state.value.value * 2, is_high=state.value.is_high)
        )

    def low_value_handler(state: TestState) -> TestState:
        return state.updated(
            value=BranchState(value=state.value.value + 1, is_high=state.value.is_high)
        )

    graph.add_node("check", check_node)
    graph.add_node("high", high_value_handler)
    graph.add_node("low", low_value_handler)
    graph.add_edge(START, "check")
    graph.add_conditional_edges(
        "check", branch_condition, path_map={True: "high", False: "low"}
    )
    graph.add_edge("high", END)
    graph.add_edge("low", END)

    # Test high value path
    initial_state = TestState(value=BranchState(value=10))
    final_state = await graph.execute_async(
        initial_state, callback=lambda node, state: print(f"Node '{node}' -> {state}")
    )
    assert final_state.value.value == 20  # 10 * 2
    assert final_state.trajectory == ["check", "high"]
    assert final_state.value.is_high is True

    # Test low value path
    initial_state = TestState(value=BranchState(value=3))
    final_state = await graph.execute_async(initial_state)
    assert final_state.value.value == 4  # 3 + 1
    assert final_state.trajectory == ["check", "low"]
    assert final_state.value.is_high is False


@pytest.mark.asyncio
async def test_callback_timing(graph):
    """Test that callbacks are called at the correct time in the execution flow."""
    callback_results = []

    async def async_node(state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        return state.updated(value=BranchState(value=state.value.value + 1))

    def sync_node(state: TestState) -> TestState:
        return state.updated(value=BranchState(value=state.value.value + 1))

    def async_callback(result: TestState):
        callback_results.append(("async", result.value.value))

    def sync_callback(result: TestState):
        callback_results.append(("sync", result.value.value))

    graph.add_node("async_node", async_node, callback=async_callback)
    graph.add_node("sync_node", sync_node, callback=sync_callback)
    graph.add_edge(START, "async_node")
    graph.add_edge("async_node", "sync_node")
    graph.add_edge("sync_node", END)

    initial_state = TestState(value=BranchState(value=1))
    result = await graph.execute_async(initial_state)

    # Verify the final state value
    assert result.value.value == 3  # 1 + 1 (async) + 1 (sync) = 3

    # Verify callback execution order and timing
    assert len(callback_results) == 2
    assert callback_results[0] == ("async", 2)  # Called after async_node
    assert callback_results[1] == ("sync", 3)  # Called after sync_node


@pytest.mark.asyncio
async def test_callback_error_handling(graph):
    """Test callback behavior when errors occur."""
    callback_results = []
    on_error_called = False

    async def failing_node(state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        raise ValueError("Node failed")

    async def on_error(error: Exception, state: TestState) -> TestState:
        nonlocal on_error_called
        on_error_called = True
        await asyncio.sleep(0.1)
        return state.updated(value=BranchState(value=-1)).add_error(error)

    def node_callback(node_name: str, result: TestState):
        print(f"DEBUG: {node_name} callback -> {result}")
        callback_results.append(result.value.value)

    graph.add_node("failing_node", failing_node, on_error=on_error)
    graph.add_edge(START, "failing_node")
    graph.add_edge("failing_node", END)

    initial_state = TestState(value=BranchState(value=1))
    result = await graph.execute_async(initial_state, callback=node_callback)

    assert on_error_called
    assert len(result.errors) == 1
    assert result.value.value == -1
    assert len(callback_results) == 1
    assert (
        callback_results[0] == -1
    )  # Callback should receive the error handler's state


@pytest.mark.asyncio
async def test_nested_branch_handling(graph):
    """Test handling of nested conditional branches with async conditions."""

    async def is_positive(state: TestState) -> bool:
        await asyncio.sleep(0.1)
        return state.value.value > 0

    async def is_even(state: TestState) -> bool:
        await asyncio.sleep(0.1)
        return state.value.value % 2 == 0

    async def entry_node(state: TestState) -> TestState:
        """Entry node that passes through the state for initial processing."""
        await asyncio.sleep(0.1)
        return state

    async def check_even(state: TestState) -> TestState:
        """Node that just passes through the state for parity checking."""
        await asyncio.sleep(0.1)
        return state

    async def double_it(state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        return state.updated(value=BranchState(value=state.value.value * 2))

    async def increment(state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        return state.updated(value=BranchState(value=state.value.value + 1))

    def absolute(state: TestState) -> TestState:
        return state.updated(value=BranchState(value=abs(state.value.value)))

    # Add nodes for processing
    graph.add_node("entry", entry_node)
    graph.add_node("check_even", check_even)
    graph.add_node("double_it", double_it)
    graph.add_node("increment", increment)
    graph.add_node("absolute", absolute)

    # Add edge from START to entry node
    graph.add_edge(START, "entry")

    # Add conditional branches from entry node
    graph.add_conditional_edges(
        source="entry",
        condition=is_positive,
        path_map={True: "check_even", False: "absolute"},
    )

    # Add conditional branches for parity check
    graph.add_conditional_edges(
        source="check_even",
        condition=is_even,
        path_map={True: "double_it", False: "increment"},
    )

    # Add edges to END
    graph.add_edge("double_it", END)
    graph.add_edge("increment", END)
    graph.add_edge("absolute", END)

    # Test positive even number
    result = await graph.execute_async(TestState(value=BranchState(value=4)))
    assert result.value.value == 8
    assert "double_it" in result.trajectory
    assert "check_even" in result.trajectory
    assert "entry" in result.trajectory

    # Test positive odd number
    result = await graph.execute_async(TestState(value=BranchState(value=3)))
    assert result.value.value == 4
    assert "increment" in result.trajectory
    assert "check_even" in result.trajectory
    assert "entry" in result.trajectory

    # Test negative number
    result = await graph.execute_async(TestState(value=BranchState(value=-5)))
    assert result.value.value == 5
    assert "absolute" in result.trajectory
    assert "check_even" not in result.trajectory
    assert "entry" in result.trajectory
