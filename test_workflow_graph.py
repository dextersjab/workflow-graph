import pytest
import logging
from workflow_graph import WorkflowGraph, START, END
import asyncio

# Configure logging
logger = logging.getLogger('workflow_graph')
logger.setLevel(logging.DEBUG)

# Create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Create formatter and add it to the handler
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(ch)

# Test fixtures and helper functions
def add_one(x: int) -> int:
    print('add_one')
    return x + 1

def multiply_by_two(x: int) -> int:
    return x * 2

def is_even(x: int) -> bool:
    return x % 2 == 0

async def async_add_one(x: int) -> int:
    return x + 1

def str_to_int(x: str) -> int:
    return int(x)

def test_basic_graph_creation():
    graph = WorkflowGraph()
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0
    assert len(graph.branches) == 0

def test_add_node():
    graph = WorkflowGraph()
    
    # Test adding node with string name
    graph.add_node("add", add_one)
    assert "add" in graph.nodes
    assert graph.nodes["add"].action == add_one
    
    # Test adding node with function directly
    graph.add_node(multiply_by_two)
    assert "multiply_by_two" in graph.nodes
    
    # Test adding node with metadata
    metadata = {"description": "test node"}
    graph.add_node("test", add_one, metadata=metadata)
    assert graph.nodes["test"].metadata == metadata

def test_add_node_validation():
    graph = WorkflowGraph()
    
    # Test adding reserved node names
    with pytest.raises(ValueError):
        graph.add_node(START, add_one)
    
    with pytest.raises(ValueError):
        graph.add_node(END, add_one)
    
    # Test adding duplicate node
    graph.add_node("test", add_one)
    with pytest.raises(ValueError):
        graph.add_node("test", multiply_by_two)

def test_add_edge():
    graph = WorkflowGraph()
    graph.add_node("add", add_one)
    graph.add_node("multiply", multiply_by_two)
    
    graph.add_edge("add", "multiply")
    assert ("add", "multiply") in graph.edges
    
    # Test invalid edges
    with pytest.raises(ValueError):
        graph.add_edge(END, "multiply")
    
    with pytest.raises(ValueError):
        graph.add_edge("add", START)

def test_conditional_edges():
    graph = WorkflowGraph()
    graph.add_node("check", is_even)
    graph.add_node("handle_even", add_one)
    graph.add_node("handle_odd", multiply_by_two)
    
    path_map = {True: "handle_even", False: "handle_odd"}
    graph.add_conditional_edges("check", is_even, path_map)
    
    assert "check" in graph.branches
    assert len(graph.branches["check"]) == 1
    branch = list(graph.branches["check"].values())[0]
    assert branch.path == is_even
    assert branch.ends == path_map

@pytest.mark.asyncio
async def test_simple_workflow_execution():
    graph = WorkflowGraph()
    graph.add_node("add", add_one)
    graph.add_node("multiply", multiply_by_two)
    
    graph.set_entry_point("add")
    graph.add_edge("add", "multiply")
    graph.set_finish_point("multiply")
    
    compiled = graph.compile()
    result = await compiled.execute(1)
    assert result == 4  # (1 + 1) * 2

@pytest.mark.asyncio
async def test_conditional_workflow_execution():
    graph = WorkflowGraph()
    graph.add_node("check", is_even)
    graph.add_node("handle_even", add_one)
    graph.add_node("handle_odd", multiply_by_two)
    
    graph.set_entry_point("check")
    graph.add_conditional_edges(
        "check",
        is_even,
        {True: "handle_even", False: "handle_odd"}
    )
    graph.set_finish_point("handle_even")
    graph.set_finish_point("handle_odd")
    
    compiled = graph.compile()
    
    # Test with even number
    result_even = await compiled.execute(2)
    print(f'{result_even=}')
    assert result_even == 3  # 2 is even -> add_one -> 3
    
    # Test with odd number
    result_odd = await compiled.execute(3)
    assert result_odd == 6  # 3 is odd -> multiply_by_two -> 6

@pytest.mark.asyncio
async def test_async_node_execution():
    graph = WorkflowGraph()
    graph.add_node("async_add", async_add_one)
    
    graph.set_entry_point("async_add")
    graph.set_finish_point("async_add")
    
    compiled = graph.compile()
    result = await compiled.execute(1)
    assert result == 2

@pytest.mark.asyncio
async def test_callback_execution():
    graph = WorkflowGraph()
    
    def node_with_callback(x, callback=None):
        if callback:
            callback(f"Processing {x}")
        return x + 1
    
    graph.add_node("callback_node", node_with_callback)
    graph.set_entry_point("callback_node")
    graph.set_finish_point("callback_node")
    
    compiled = graph.compile()
    
    callback_called = False
    callback_value = None
    
    def test_callback(value):
        nonlocal callback_called, callback_value
        callback_called = True
        callback_value = value
    
    result = await compiled.execute(1, callback=test_callback)
    assert callback_called
    assert callback_value == "Processing 1"
    assert result == 2

def test_graph_validation():
    graph = WorkflowGraph()
    graph.add_node("node1", add_one)
    
    # Test missing entry point
    with pytest.raises(ValueError):
        graph.compile()
    
    # Test unreachable node
    graph.add_node("node2", multiply_by_two)
    graph.set_entry_point("node1")
    graph.set_finish_point("node1")
    with pytest.raises(ValueError):
        graph.compile()

def test_type_validation():
    graph = WorkflowGraph()
    
    # Test compatible types
    graph.add_node("add", add_one)
    graph.add_node("multiply", multiply_by_two)
    graph.set_entry_point("add")
    graph.add_edge("add", "multiply")
    graph.set_finish_point("multiply")
    # Should compile without errors
    graph.compile()
    
    # Test incompatible types
    graph = WorkflowGraph()
    graph.add_node("str_to_int", str_to_int)
    graph.add_node("is_even", is_even)
    graph.set_entry_point("is_even")
    graph.add_edge("is_even", "str_to_int")  # bool -> str is incompatible
    graph.set_finish_point("str_to_int")
    
    with pytest.raises(ValueError, match="Type mismatch"):
        graph.compile()

def test_type_validation_with_branches():
    graph = WorkflowGraph()
    
    # Test compatible types in conditional branches
    graph.add_node("check", is_even)
    graph.add_node("handle_even", add_one)
    graph.add_node("handle_odd", multiply_by_two)
    
    graph.set_entry_point("check")
    graph.add_conditional_edges(
        "check",
        is_even,
        {True: "handle_even", False: "handle_odd"}
    )
    graph.set_finish_point("handle_even")
    graph.set_finish_point("handle_odd")
    
    # Should compile without errors since both handlers expect int
    graph.compile()
    
    # Test incompatible types in conditional branches
    graph = WorkflowGraph()
    graph.add_node("check", is_even)
    graph.add_node("str_to_int", str_to_int)  # expects str, but check outputs bool
    
    graph.set_entry_point("check")
    graph.add_conditional_edges(
        "check",
        is_even,
        {True: "str_to_int"}
    )
    graph.set_finish_point("str_to_int")
    
    with pytest.raises(ValueError, match="Type mismatch"):
        graph.compile()

def test_retry_policy():
    attempts = 0
    
    def failing_node(x: int) -> int:
        nonlocal attempts
        attempts += 1
        if attempts < 3:  # Fail twice, succeed on third try
            raise ValueError("Temporary failure")
        return x + 1
    
    graph = WorkflowGraph()
    graph.add_node("retry_node", failing_node, retries=3, backoff_factor=0.1)  # Fast backoff for testing
    graph.set_entry_point("retry_node")
    graph.set_finish_point("retry_node")
    
    compiled = graph.compile()
    result = asyncio.run(compiled.execute(1))
    assert result == 2  # Should succeed after retries
    assert attempts == 3  # Should have attempted exactly 3 times

def test_error_handler():
    def failing_node(x: int) -> int:
        raise ValueError("Permanent failure")
    
    def error_handler(x: int) -> str:
        return f"Error handled: {x}"
    
    graph = WorkflowGraph()
    graph.add_node("main_node", failing_node, on_error="handle_error")
    graph.add_node("handle_error", error_handler)
    
    graph.set_entry_point("main_node")
    graph.set_finish_point("handle_error")
    
    compiled = graph.compile()
    result = asyncio.run(compiled.execute(1))
    assert result == "Error handled: 1"

@pytest.mark.asyncio
async def test_retry_then_error_handler():
    attempts = 0
    
    def failing_node(x: int) -> int:
        nonlocal attempts
        attempts += 1
        raise ValueError(f"Failure #{attempts}")
    
    def error_handler(x: int) -> str:
        return f"Gave up after {attempts} attempts with input {x}"
    
    graph = WorkflowGraph()
    graph.add_node(
        "retry_node",
        failing_node,
        retries=2,
        backoff_factor=0.1,
        on_error="handle_error"
    )
    graph.add_node("handle_error", error_handler)
    
    graph.set_entry_point("retry_node")
    graph.set_finish_point("handle_error")
    
    compiled = graph.compile()
    result = await compiled.execute(1)
    
    assert attempts == 3  # Initial attempt + 2 retries
    assert result == "Gave up after 3 attempts with input 1"

@pytest.mark.asyncio
async def test_async_retry():
    attempts = 0
    
    async def async_failing_node(x: int) -> int:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("Temporary async failure")
        return x + 1
    
    graph = WorkflowGraph()
    graph.add_node("async_retry", async_failing_node, retries=3, backoff_factor=0.1)
    graph.set_entry_point("async_retry")
    graph.set_finish_point("async_retry")
    
    compiled = graph.compile()
    result = await compiled.execute(1)
    
    assert result == 2
    assert attempts == 3

if __name__ == "__main__":
    pytest.main([__file__]) 