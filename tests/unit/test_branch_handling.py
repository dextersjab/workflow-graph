"""Unit tests for branch handling and callback timing in workflow graph."""
import pytest
import asyncio
from dataclasses import dataclass, field
from typing import Optional, List
from workflow_graph import START, END, State
import traceback

@dataclass
class TestState(State[int]):
    """Test state that extends State with additional fields for testing.
    
    This state class tracks callback execution history and maintains
    the standard State functionality for workflow execution.
    """
    callback_history: List[str] = field(default_factory=list)

    def copy(self) -> 'TestState':
        """Create a deep copy of this state."""
        return TestState(
            value=self.value,
            data=self.data.copy(),
            current_node=self.current_node,
            processed_by=self.processed_by.copy(),
            trajectory=self.trajectory.copy(),
            errors=self.errors.copy(),
            callback_history=self.callback_history.copy()
        )

    def add_callback_history(self, callback_name: str) -> None:
        """Add a callback execution to the history."""
        self.callback_history.append(callback_name)

@pytest.mark.asyncio
async def test_async_branch_condition(graph):
    """Test async branch condition evaluation."""
    async def check_node(state: State[int]) -> State[int]:
        """Node function that evaluates condition and stores result."""
        await asyncio.sleep(0.1)
        is_high = state.value > 5
        state.set_data("is_high", is_high)
        return state

    async def branch_condition(state: State[int]) -> bool:
        """Branch condition that reads the stored result."""
        return state.get_data("is_high")

    async def high_value_handler(state: State[int]) -> State[int]:
        await asyncio.sleep(0.1)
        new_state = State(
            value=state.value * 2,
            data=state.data.copy(),
            current_node=state.current_node,
            processed_by=state.processed_by.copy(),
            trajectory=state.trajectory.copy() + ["high"],
            errors=state.errors.copy()
        )
        return new_state

    def low_value_handler(state: State[int]) -> State[int]:
        new_state = State(
            value=state.value + 1,
            data=state.data.copy(),
            current_node=state.current_node,
            processed_by=state.processed_by.copy(),
            trajectory=state.trajectory.copy() + ["low"],
            errors=state.errors.copy()
        )
        return new_state

    graph.add_node("check", check_node)
    graph.add_node("high", high_value_handler)
    graph.add_node("low", low_value_handler)
    graph.add_edge(START, "check")
    graph.add_conditional_edges(
        "check",
        branch_condition,
        path_map={"True": "high", "False": "low"}
    )
    graph.add_edge("high", END)
    graph.add_edge("low", END)

    # Test high value path
    initial_state = State(value=10)
    final_state = await graph.execute_async(initial_state, callback=lambda node, state: print(f"Node '{node}' -> {state}"))
    assert final_state.value == 20  # 10 * 2
    assert final_state.trajectory == ["high"]
    assert final_state.get_data("is_high") is True

    # Test low value path
    initial_state = State(value=3)
    final_state = await graph.execute_async(initial_state, callback=lambda node, state: print(f"Node '{node}' -> {state}"))
    assert final_state.value == 4  # 3 + 1
    assert final_state.trajectory == ["low"]
    assert final_state.get_data("is_high") is False

@pytest.mark.asyncio
async def test_callback_timing(graph):
    """Test that callbacks are called at the correct time in the execution flow."""
    callback_results = []

    async def async_node(state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        new_state = state.copy()
        new_state.update_value(state.value + 1)
        return new_state

    def sync_node(state: TestState) -> TestState:
        new_state = state.copy()
        new_state.update_value(state.value + 1)
        return new_state

    def async_callback(result: TestState):
        callback_results.append(("async", result.value))

    def sync_callback(result: TestState):
        callback_results.append(("sync", result.value))

    graph.add_node("async_node", async_node, callback=async_callback)
    graph.add_node("sync_node", sync_node, callback=sync_callback)
    graph.add_edge(START, "async_node")
    graph.add_edge("async_node", "sync_node")
    graph.add_edge("sync_node", END)

    initial_state = TestState(value=1)
    result = await graph.execute_async(initial_state)

    # Verify the final state value
    assert result.value == 3  # 1 + 1 (async) + 1 (sync) = 3
    
    # Verify callback execution order and timing
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
        new_state = state.copy()
        new_state.update_value(-1)
        new_state.add_error(error)
        return new_state

    def node_callback(result: TestState):
        print("DEBUG: Entering callback")
        callback_results.append(result.value)

    graph.add_node("failing_node", failing_node, error_handler=error_handler)
    graph.add_edge(START, "failing_node")
    graph.add_edge("failing_node", END)

    initial_state = TestState(value=1)
    result = await graph.execute_async(initial_state)

    assert error_handler_called
    assert len(result.errors) == 1
    assert result.value == -1
    assert len(callback_results) == 1
    assert callback_results[0] == -1  # Callback should receive the error handler's state

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
        new_state = TestState(
            value=state.value,
            data=state.data.copy(),
            current_node=state.current_node,
            processed_by=state.processed_by.copy(),
            trajectory=state.trajectory.copy() + ["positive_even"],
            errors=state.errors.copy(),
            callbacks=state.callbacks.copy()
        )
        new_state.update_value(state.value * 2)
        return new_state

    async def process_positive_odd(state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        new_state = TestState(
            value=state.value,
            data=state.data.copy(),
            current_node=state.current_node,
            processed_by=state.processed_by.copy(),
            trajectory=state.trajectory.copy() + ["positive_odd"],
            errors=state.errors.copy(),
            callbacks=state.callbacks.copy()
        )
        new_state.update_value(state.value + 1)
        return new_state

    def process_negative(state: TestState) -> TestState:
        new_state = TestState(
            value=state.value,
            data=state.data.copy(),
            current_node=state.current_node,
            processed_by=state.processed_by.copy(),
            trajectory=state.trajectory.copy() + ["negative"],
            errors=state.errors.copy(),
            callbacks=state.callbacks.copy()
        )
        new_state.update_value(abs(state.value))
        return new_state

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
    assert result.value == 8  # 4 * 2
    assert result.trajectory == ["positive_even"]

    # Test positive odd path
    initial_state = TestState(value=3)
    result = await graph.execute_async(initial_state)
    assert result.value == 4  # 3 + 1
    assert result.trajectory == ["positive_odd"]

    # Test negative path
    initial_state = TestState(value=-5)
    result = await graph.execute_async(initial_state)
    assert result.value == 5  # abs(-5)
    assert result.trajectory == ["negative"] 