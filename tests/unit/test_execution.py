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
    """Test execution with callbacks for streaming partial results.
    
    This test demonstrates how callbacks can be used to stream intermediate results
    during workflow execution, similar to how you might want to update a client
    with progress or partial results in a real application.
    """
    # This will store our streaming results from each node
    streaming_results = []
    
    # Node functions that will capture their own results via closure
    def process_data(x: int) -> int:
        result = x * 10
        # Store the result for later verification
        process_data.last_result = result
        return result
    
    def analyze_result(x: int) -> int:
        result = x + 5
        # Store the result for later verification
        analyze_result.last_result = result
        return result
    
    def format_output(x: int) -> int:
        result = x * 2
        # Store the result for later verification
        format_output.last_result = result
        return result
    
    # Node-specific callbacks that will stream results to the client
    def process_callback():
        streaming_results.append({
            "node": "process",
            "value": process_data.last_result,
            "timestamp": "2024-01-01T00:00:00Z"
        })
    
    def analyze_callback():
        streaming_results.append({
            "node": "analyze",
            "value": analyze_result.last_result,
            "timestamp": "2024-01-01T00:00:00Z"
        })
    
    def format_callback():
        streaming_results.append({
            "node": "format",
            "value": format_output.last_result,
            "timestamp": "2024-01-01T00:00:00Z"
        })
    
    # Build a pipeline that processes data and streams results at each step
    graph.add_node("process", process_data, callback=process_callback)
    graph.add_node("analyze", analyze_result, callback=analyze_callback)
    graph.add_node("format", format_output, callback=format_callback)
    
    graph.add_edge("process", "analyze")
    graph.add_edge("analyze", "format")
    graph.set_entry_point("process")
    graph.set_finish_point("format")
    
    # Execute the workflow
    final_result = graph.execute(5)
    
    # Verify the final result
    assert final_result == 110  # ((5 * 10) + 5) * 2
    
    # Verify that we received streaming updates from each step
    assert len(streaming_results) == 3
    assert streaming_results[0] == {"node": "process", "value": 50, "timestamp": "2024-01-01T00:00:00Z"}
    assert streaming_results[1] == {"node": "analyze", "value": 55, "timestamp": "2024-01-01T00:00:00Z"}
    assert streaming_results[2] == {"node": "format", "value": 110, "timestamp": "2024-01-01T00:00:00Z"} 