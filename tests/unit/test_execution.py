"""Unit tests for workflow graph execution."""
import pytest
import asyncio
from dataclasses import dataclass
from typing import Optional
from workflow_graph import WorkflowGraph, START, END

@dataclass
class TestState:
    value: int
    result: Optional[int] = None

def test_simple_workflow_execution(graph):
    """Test execution of a simple linear workflow."""
    def add_one(state: TestState) -> TestState:
        return TestState(
            value=state.value,
            result=state.value + 1
        )

    def multiply_by_two(state: TestState) -> TestState:
        return TestState(
            value=state.value,
            result=state.result * 2
        )

    graph.add_node("add", add_one)
    graph.add_node("multiply", multiply_by_two)
    graph.add_edge(START, "add")
    graph.add_edge("add", "multiply")
    graph.add_edge("multiply", END)

    initial_state = TestState(value=1)
    result = graph.execute(initial_state)
    assert result.result == 4  # (1 + 1) * 2 = 4

def test_conditional_workflow_execution(graph):
    """Test execution of a workflow with conditional branches."""
    def check_even(state: TestState) -> bool:
        return state.value % 2 == 0

    def add_one(state: TestState) -> TestState:
        return TestState(
            value=state.value,
            result=state.value + 1
        )

    def multiply_by_two(state: TestState) -> TestState:
        return TestState(
            value=state.value,
            result=state.value * 2
        )

    # Add nodes
    graph.add_node("check", check_even)
    graph.add_node("add", add_one)
    graph.add_node("multiply", multiply_by_two)

    graph.add_edge(START, "check")
    graph.add_conditional_edges(
        "check",
        check_even,
        path_map={"True": "add", "False": "multiply"}
    )
    graph.add_edge("add", END)
    graph.add_edge("multiply", END)

    # Test with even number
    initial_state = TestState(value=2)
    result = graph.execute(initial_state)
    assert result.result == 3  # 2 is even, so add_one is called: 2 + 1 = 3

    # Test with odd number
    initial_state = TestState(value=3)
    result = graph.execute(initial_state)
    assert result.result == 6  # 3 is odd, so multiply_by_two is called: 3 * 2 = 6

@pytest.mark.asyncio
async def test_async_node_execution(graph):
    """Test execution of a workflow with async nodes."""
    async def async_add_one(state: TestState) -> TestState:
        await asyncio.sleep(0.1)
        return TestState(
            value=state.value,
            result=state.value + 1
        )

    graph.add_node("async_add", async_add_one)
    graph.add_edge(START, "async_add")
    graph.add_edge("async_add", END)
    
    initial_state = TestState(value=1)
    result = await graph.execute_async(initial_state)
    assert result.result == 2

def test_callback_execution(graph):
    """Test execution with callbacks for streaming partial results.
    
    This test demonstrates how callbacks can be used to stream intermediate results
    during workflow execution, similar to how you might want to update a client
    with progress or partial results in a real application.
    """
    # This will store our streaming results from each node
    streaming_results = []
    
    # Node functions that will capture their own results via closure
    def process_data(state: TestState) -> TestState:
        result = state.value * 10
        # Store the result for later verification
        process_data.last_result = result
        return TestState(
            value=state.value,
            result=result
        )
    
    def analyze_result(state: TestState) -> TestState:
        result = state.result + 5
        # Store the result for later verification
        analyze_result.last_result = result
        return TestState(
            value=state.value,
            result=result
        )
    
    def format_output(state: TestState) -> TestState:
        result = state.result * 2
        # Store the result for later verification
        format_output.last_result = result
        return TestState(
            value=state.value,
            result=result
        )
    
    # Node-specific callbacks that will stream results to the client
    def process_callback(result: TestState):
        streaming_results.append({
            "node": "process",
            "value": process_data.last_result,
            "timestamp": "2024-01-01T00:00:00Z"
        })
    
    def analyze_callback(result: TestState):
        streaming_results.append({
            "node": "analyze",
            "value": analyze_result.last_result,
            "timestamp": "2024-01-01T00:00:00Z"
        })
    
    def format_callback(result: TestState):
        streaming_results.append({
            "node": "format",
            "value": format_output.last_result,
            "timestamp": "2024-01-01T00:00:00Z"
        })
    
    # Build a pipeline that processes data and streams results at each step
    graph.add_node("process", process_data, callback=process_callback)
    graph.add_node("analyze", analyze_result, callback=analyze_callback)
    graph.add_node("format", format_output, callback=format_callback)
    
    graph.add_edge(START, "process")
    graph.add_edge("process", "analyze")
    graph.add_edge("analyze", "format")
    graph.add_edge("format", END)
    
    # Execute the workflow
    initial_state = TestState(value=5)
    final_result = graph.execute(initial_state)
    
    # Verify the final result
    assert final_result.result == 110  # ((5 * 10) + 5) * 2
    
    # Verify that we received streaming updates from each step
    assert len(streaming_results) == 3
    assert streaming_results[0] == {"node": "process", "value": 50, "timestamp": "2024-01-01T00:00:00Z"}
    assert streaming_results[1] == {"node": "analyze", "value": 55, "timestamp": "2024-01-01T00:00:00Z"}
    assert streaming_results[2] == {"node": "format", "value": 110, "timestamp": "2024-01-01T00:00:00Z"}