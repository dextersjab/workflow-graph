import asyncio
from workflow_graph import WorkflowGraph, START, END

# Define basic nodes
def add(data, callback=None):
    result = data + 1
    if callback:
        callback(f"add: {data} -> {result}")
    return result

def is_even(data, callback=None):
    result = data % 2 == 0
    if callback:
        callback(f"is_even: {data} -> {result}")
    return result

def handle_even(data, callback=None):
    if callback:
        callback(f"Handling even number: {data}")
    return f"Even: {data}"

def handle_odd(data, callback=None):
    if callback:
        callback(f"Handling odd number: {data}")
    return f"Odd: {data}"

# Create the WorkflowGraph
graph = WorkflowGraph()

# Add nodes to the graph
graph.add_node("addition", add)
graph.add_node("is_even_check", is_even)
graph.add_node("even_handler", handle_even)
graph.add_node("odd_handler", handle_odd)

# Define edges for the main workflow
graph.add_edge(START, "addition")
graph.add_edge("addition", "is_even_check")

# Define conditional edges based on whether the number is even or odd
graph.add_conditional_edges(
    "is_even_check", 
    path=is_even, 
    path_map={True: "even_handler", False: "odd_handler"}
)

# Set finish points
graph.add_edge("even_handler", END)
graph.add_edge("odd_handler", END)

# Compile the graph
compiled_graph = graph.compile()

# Generate and print Mermaid diagram
print("\nMermaid Diagram Representation:")
print(graph.to_mermaid())

# Execute the workflow
async def run_workflow(input_data):
    result = await compiled_graph.execute_async(input_data, callback=print)
    print(f"Final Result: {result}")

# Run with an example input
asyncio.run(run_workflow(5))  # Try changing 5 to an even number like 4
