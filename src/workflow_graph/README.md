# WorkflowGraph package

This package provides a lightweight framework for building and executing directed, computational workflow graphs in Python. It allows you to define nodes as functions, connect them with edges, and execute the workflow with input data.

## Modules

- `builder.py`: Contains the `WorkflowGraph` class for constructing and validating workflow graphs
- `executor.py`: Contains the `CompiledGraph` class for executing workflow graphs
- `models.py`: Defines data models for nodes and branches
- `constants.py`: Defines constants like START and END nodes
- `exceptions.py`: Custom exceptions for the workflow graph

## Core concepts

- **Nodes**: Functions that process data
- **Edges**: Connections between nodes that define the flow of data
- **Branches**: Conditional paths in the workflow
- **Callbacks**: Functions that can be called after node execution for streaming results

## Features

- Create directed graphs of computational tasks
- Add conditional branches based on function outputs
- Type validation between connected nodes
- Synchronous and asynchronous execution
- Error handling and retries
- Generate Mermaid diagrams of the workflow

## Basic usage

```python
from workflow_graph import WorkflowGraph, START, END

# Create a workflow graph
graph = WorkflowGraph()

# Set entry point
graph.add_edge(START, "add_one")

# Add nodes (functions)
graph.add_node("add_one", lambda x: x + 1)
graph.add_node("multiply_by_two", lambda x: x * 2)

# Add edges between nodes
graph.add_edge("add_one", "multiply_by_two")

# Set exit point
graph.add_edge("multiply_by_two", END)

# Execute the workflow
result = graph.execute(5)  # Result: (5 + 1) * 2 = 12
```

## Conditional branching

For conditional branching, use `add_conditional_edges`:

```python
def is_even(x):
    return x % 2 == 0

graph.add_node("check", is_even)
graph.add_node("handle_even", lambda x: f"Even: {x}")
graph.add_node("handle_odd", lambda x: f"Odd: {x}")

# Add conditional branching
graph.add_conditional_edges(
    "check",
    path=is_even,
    path_map={True: "handle_even", False: "handle_odd"}
)

# Add edges to endpoints
graph.add_edge("handle_even", END)
graph.add_edge("handle_odd", END)
```

See the project's [root README.md](../../README.md) for more detailed examples and usage instructions.