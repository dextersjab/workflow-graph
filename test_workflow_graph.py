import pytest
import logging
from workflow_graph import WorkflowGraph, START, END

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
def add_one(x):
    return x + 1

def multiply_by_two(x):
    return x * 2

def is_even(x):
    return x % 2 == 0

async def async_add_one(x):
    return x + 1

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

if __name__ == "__main__":
    pytest.main([__file__]) 