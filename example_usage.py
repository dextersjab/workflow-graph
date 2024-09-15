import asyncio
from workflow_graph import WorkflowGraph

# Define basic nodes
def add(data, callback=None):
    result = data + 1
    if callback:
        callback(f"add: {data} -> {result}")
    return result

def multiply(data, callback=None):
    result = data * 2
    if callback:
        callback(f"multiply: {data} -> {result}")
    return result

async def async_multiply(data, callback=None):
    result = data * 3
    if callback:
        callback(f"async_multiply: {data} -> {result}")
    return result

# Create a callback function to stream results
def stream_callback(message):
    print(f"Stream: {message}")

# Instantiate the graph
graph = WorkflowGraph()

# Add nodes to the graph
graph.add_node("addition", add)
graph.add_node("multiplication", multiply)
graph.add_node("async_multiplication", async_multiply)

# Define edges to control the workflow
graph.set_entry_point("addition")  # The first node to run is the 'addition' node
graph.add_edge("addition", "multiplication")  # After addition, multiply the result
graph.add_edge("multiplication", "async_multiplication")  # Async multiply next
graph.set_finish_point("async_multiplication")  # Mark the final node

# Compile the graph
compiled_graph = graph.compile()

# Define a function to execute the graph
async def run_graph(input_data):
    result = await compiled_graph.execute(input_data, callback=stream_callback)
    print(f"Final Result: {result}")

# Run the graph with input data
asyncio.run(run_graph(5))
