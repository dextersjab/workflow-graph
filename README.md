# WorkflowGraph

**WorkflowGraph** is a lightweight, self-contained Python library for building and executing directed graph workflows. It's an alternative to **LangGraph** for those seeking independence from LangChain and the flexibility to implement agent workflows, while still enabling real-time streaming of results.

## Features

- **Graph-based Workflows**: Build flexible, directed workflows where nodes are customizable tasks.
- **Synchronous & Asynchronous Support**: Define both sync and async nodes without any external dependencies.
- **Real-time Streaming**: Built-in support for callbacks in each node, allowing real-time token streaming (e.g., for WebSockets).
- **LangGraph Alternative**: Unlike LangGraph, WorkflowGraph provides a simpler, fully self-contained solution without needing LangChain for streaming.

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

def multiply(data, callback=None):
    result = data * 2
    if callback:
        callback(f"Multiplied by 2: {data} -> {result}")
    return result

async def async_multiply(data, callback=None):
    result = data * 3
    if callback:
        callback(f"Multiplied by 3 asynchronously: {data} -> {result}")
    return result

# Create and configure the workflow graph
graph = WorkflowGraph()
graph.add_node("addition", add)
graph.add_node("multiplication", multiply)
graph.add_node("async_multiplication", async_multiply)
graph.set_entry_point("addition")
graph.add_edge("addition", "multiplication")
graph.add_edge("multiplication", "async_multiplication")
graph.set_finish_point("async_multiplication")

# Execute with streaming
compiled_graph = graph.compile()
asyncio.run(compiled_graph.execute(5, callback=print))
```
---

**Note**: This project was largely generated using AI assistance.

--- 
