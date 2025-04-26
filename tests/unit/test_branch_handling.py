"""Unit tests for branch handling and callback timing in workflow graph."""
import pytest
import asyncio
from dataclasses import dataclass
from typing import Optional, List
from workflow_graph import WorkflowGraph, START, END

@dataclass
class TestState:
    value: int
    result: Optional[int] = None
    errors: List[str] = None
    callbacks: List[str] = None
    branch_taken: Optional[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.callbacks is None:
            self.callbacks = []

@pytest.mark.asyncio
async def test_async_branch_condition(graph):
    """Test async branch condition evaluation."""
    async def async_condition(state: TestState) -> bool:
        await asyncio.sleep(0.1)
        return state.value > 5

    async def high_value_handler(state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        return TestState(
            value=state.value,
            result=state.value * 2,
            branch_taken="high"
        )

    def low_value_handler(state: TestState) -> TestState:
        return TestState(
            value=state.value,
            result=state.value + 1,
            branch_taken="low"
        )

    graph.add_node("check", async_condition)
    graph.add_node("high", high_value_handler)
    graph.add_node("low", low_value_handler)
    graph.add_edge(START, "check")
    graph.add_conditional_edges(
        "check",
        async_condition,
        path_map={"True": "high", "False": "low"}
    )
    graph.add_edge("high", END)
    graph.add_edge("low", END)

    # Test high value path
    initial_state = TestState(value=10)
    result = await graph.execute_async(initial_state)
    assert result.result == 20  # 10 * 2
    assert result.branch_taken == "high"

    # Test low value path
    initial_state = TestState(value=3)
    result = await graph.execute_async(initial_state)
    assert result.result == 4  # 3 + 1
    assert result.branch_taken == "low"

@pytest.mark.asyncio
async def test_callback_timing(graph):
    """Test that callbacks are called at the correct time in the execution flow."""
    callback_results = []

    async def async_node(state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        return TestState(
            value=state.value,
            result=state.value + 1,
            callbacks=state.callbacks + ["async_node"]
        )

    def sync_node(state: TestState) -> TestState:
        return TestState(
            value=state.value,
            result=state.result + 1,
            callbacks=state.callbacks + ["sync_node"]
        )

    def async_callback(result: TestState):
        callback_results.append(("async", result.result))

    def sync_callback(result: TestState):
        callback_results.append(("sync", result.result))

    graph.add_node("async_node", async_node, callback=async_callback)
    graph.add_node("sync_node", sync_node, callback=sync_callback)
    graph.add_edge(START, "async_node")
    graph.add_edge("async_node", "sync_node")
    graph.add_edge("sync_node", END)

    initial_state = TestState(value=1)
    result = await graph.execute_async(initial_state)

    assert result.result == 3  # 1 + 1 (async) + 1 (sync) = 3
    assert len(callback_results) == 2
    assert callback_results[0] == ("async", 2)  # Called after async_node
    assert callback_results[1] == ("sync", 3)   # Called after sync_node

@pytest.mark.asyncio
async def test_callback_error_handling(graph):
    """Test callback behavior when errors occur."""
    callback_results = []
    error_handler_called = False

    async def failing_node(state: TestState) -> TestState:
        print("DEBUG: Entering failing_node")
        await asyncio.sleep(0.1)
        raise ValueError("Node failed")

    async def error_handler(error: Exception, state: TestState) -> TestState:
        print("DEBUG: Entering error_handler")
        nonlocal error_handler_called
        error_handler_called = True
        await asyncio.sleep(0.1)
        print("DEBUG: Error handler completed")
        return TestState(
            value=state.value,
            result=-1,
            errors=state.errors + [str(error)]
        )

    def node_callback(result: TestState):
        print("DEBUG: Entering callback")
        callback_results.append(result.result)

    graph.add_node("failing_node", failing_node, error_handler=error_handler)
    graph.add_edge(START, "failing_node")
    graph.add_edge("failing_node", END)

    initial_state = TestState(value=1)
    result = await graph.execute_async(initial_state)

    assert error_handler_called
    assert len(result.errors) == 1
    assert result.result == -1

@pytest.mark.asyncio
async def test_nested_branch_handling(graph):
    """Test handling of nested conditional branches with async conditions."""
    async def first_condition(state: TestState) -> bool:
        await asyncio.sleep(0.1)
        return state.value > 0

    async def second_condition(state: TestState) -> bool:
        await asyncio.sleep(0.1)
        return state.value % 2 == 0

    async def process_positive_even(state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        return TestState(
            value=state.value,
            result=state.value * 2,
            branch_taken="positive_even"
        )

    async def process_positive_odd(state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        return TestState(
            value=state.value,
            result=state.value + 1,
            branch_taken="positive_odd"
        )

    def process_negative(state: TestState) -> TestState:
        return TestState(
            value=state.value,
            result=abs(state.value),
            branch_taken="negative"
        )

    graph.add_node("check_sign", first_condition)
    graph.add_node("check_parity", second_condition)
    graph.add_node("positive_even", process_positive_even)
    graph.add_node("positive_odd", process_positive_odd)
    graph.add_node("negative", process_negative)

    graph.add_edge(START, "check_sign")
    graph.add_conditional_edges(
        "check_sign",
        first_condition,
        path_map={"True": "check_parity", "False": "negative"}
    )
    graph.add_conditional_edges(
        "check_parity",
        second_condition,
        path_map={"True": "positive_even", "False": "positive_odd"}
    )
    graph.add_edge("positive_even", END)
    graph.add_edge("positive_odd", END)
    graph.add_edge("negative", END)

    # Test positive even path
    initial_state = TestState(value=4)
    result = await graph.execute_async(initial_state)
    assert result.result == 8  # 4 * 2
    assert result.branch_taken == "positive_even"

    # Test positive odd path
    initial_state = TestState(value=3)
    result = await graph.execute_async(initial_state)
    assert result.result == 4  # 3 + 1
    assert result.branch_taken == "positive_odd"

    # Test negative path
    initial_state = TestState(value=-5)
    result = await graph.execute_async(initial_state)
    assert result.result == 5  # abs(-5)
    assert result.branch_taken == "negative" 