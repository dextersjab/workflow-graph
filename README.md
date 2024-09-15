# WorkflowGraph

**WorkflowGraph** is a lightweight, self-contained Python library for building and executing directed graph workflows. It's an alternative to **LangGraph** for those seeking independence from LangChain and the flexibility to implement agent workflows, while still enabling real-time streaming of results.

## Features

- **Graph-based workflows**: Build flexible, directed workflows where nodes are customizable tasks.
- **Synchronous & asynchronous support**: Define both sync and async nodes without any external dependencies.
- **Real-time streaming**: Built-in support for callbacks in each node, allowing real-time token streaming (e.g., for WebSockets).
- **LangGraph alternative**: Unlike LangGraph, WorkflowGraph provides a simpler, fully self-contained solution without needing LangChain for streaming.

## Installation

Either copy the code directly from `workflow_graph.py` or install as a dependency using `pip`.

To install **WorkflowGraph** as a dependency, add the following line to your `requirements.txt`:

```
git+https://github.com/dextersjab/workflow-graph.git@main
```

Then, run:

```shell
pip install -r requirements.txt
```

## Usage

```python
import asyncio
from graph import WorkflowGraph

# Define tasks
def add(data, callback=None):
    result = data + 1
    if callback:
        callback(f"Added 1: {data} -> {result}")
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

# Create and configure the workflow graph
graph = WorkflowGraph()
graph.add_node("addition", add)
graph.add_node("is_even_check", is_even)
graph.add_node("even_handler", handle_even)
graph.add_node("odd_handler", handle_odd)

# Define edges for the main workflow
graph.set_entry_point("addition")
graph.add_edge("addition", "is_even_check")

# Add conditional edges based on the result of is_even_check
graph.add_conditional_edges(
    "is_even_check", 
    path=is_even, 
    path_map={True: "even_handler", False: "odd_handler"}
)

# Set finish points
graph.set_finish_point("even_handler")
graph.set_finish_point("odd_handler")

# Execute with streaming
compiled_graph = graph.compile()

async def run_workflow(input_data):
    result = await compiled_graph.execute(input_data, callback=print)
    print(f"Final Result: {result}")

# Run the workflow
asyncio.run(run_workflow(5))
```

---

**Note**: This project was largely generated using AI assistance.

--- 
