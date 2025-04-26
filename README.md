# Workflow Graph

A Python library for building and executing directed acyclic graphs (DAGs) of operations, with support for both synchronous and asynchronous execution.

> **BREAKING CHANGES WARNING**: Version 0.3.0 introduced significant API changes. Please review the documentation carefully when upgrading from earlier versions.

## Features

- **Type-Safe Workflows**: Built-in type validation ensures type consistency throughout the workflow
- **Async Support**: Native support for asynchronous operations and coroutines
- **Error Handling**: Configurable error handling and retry policies
- **Branching Logic**: Support for conditional branches with async conditions
- **State Management**: Proper state persistence between nodes
- **Callback Support**: Configurable callbacks for monitoring execution progress
- **Generic Types**: Support for generic types in workflow state

## Installation

```bash
pip install workflow-graph
```

## Usage

### Basic Workflow

```python
from workflow_graph import WorkflowGraph, START, END
from dataclasses import dataclass

@dataclass
class State:
    value: int
    result: int = None

def add_one(state: State) -> State:
    return State(value=state.value, result=state.value + 1)

def multiply_by_two(state: State) -> State:
    return State(value=state.value, result=state.result * 2)

graph = WorkflowGraph()
graph.add_node("add", add_one)
graph.add_node("multiply", multiply_by_two)
graph.add_edge(START, "add")
graph.add_edge("add", "multiply")
graph.add_edge("multiply", END)

initial_state = State(value=1)
result = graph.execute(initial_state)
assert result.result == 4  # (1 + 1) * 2 = 4
```

### Async Workflow

```python
import asyncio
from workflow_graph import WorkflowGraph, START, END

async def async_operation(state: State) -> State:
    await asyncio.sleep(0.1)
    return State(value=state.value, result=state.value + 1)

graph = WorkflowGraph()
graph.add_node("async_op", async_operation)
graph.add_edge(START, "async_op")
graph.add_edge("async_op", END)

initial_state = State(value=1)
result = await graph.execute_async(initial_state)
assert result.result == 2
```

### Conditional Branches

```python
def is_even(state: State) -> bool:
    return state.value % 2 == 0

def process_even(state: State) -> State:
    return State(value=state.value, result=state.value * 2)

def process_odd(state: State) -> State:
    return State(value=state.value, result=state.value + 1)

graph = WorkflowGraph()
graph.add_node("check", is_even)
graph.add_node("even", process_even)
graph.add_node("odd", process_odd)

graph.add_edge(START, "check")
graph.add_conditional_edges(
    "check",
    is_even,
    {True: "even", False: "odd"}
)
graph.add_edge("even", END)
graph.add_edge("odd", END)

# Test with even number
result = graph.execute(State(value=2))
assert result.result == 4  # 2 * 2 = 4

# Test with odd number
result = graph.execute(State(value=3))
assert result.result == 4  # 3 + 1 = 4
```

### Error Handling

```python
def failing_operation(state: State) -> State:
    raise ValueError("Operation failed")

def error_handler(error: Exception, state: State) -> State:
    return State(value=state.value, result=-1)

graph = WorkflowGraph()
graph.add_node(
    "failing_op",
    failing_operation,
    retries=2,
    backoff_factor=0.1,
    on_error=error_handler
)
graph.add_edge(START, "failing_op")
graph.add_edge("failing_op", END)

result = graph.execute(State(value=1))
assert result.result == -1
```

### Callbacks

```python
def process_data(state: State) -> State:
    return State(value=state.value, result=state.value * 10)

def callback(result: State):
    print(f"Processed result: {result.result}")

graph = WorkflowGraph()
graph.add_node("process", process_data, callback=callback)
graph.add_edge(START, "process")
graph.add_edge("process", END)

graph.execute(State(value=5))  # Prints: Processed result: 50
```

### Generic Types

```python
from typing import Generic, TypeVar

T = TypeVar('T')

@dataclass
class GenericState(Generic[T]):
    value: T
    result: T = None

def process_int(state: GenericState[int]) -> GenericState[int]:
    return GenericState(value=state.value, result=state.value + 1)

def process_str(state: GenericState[str]) -> GenericState[str]:
    return GenericState(value=state.value, result=state.value + " processed")

# Create separate graphs for different types
int_graph = WorkflowGraph()
int_graph.add_node("process", process_int)
int_graph.add_edge(START, "process")
int_graph.add_edge("process", END)

str_graph = WorkflowGraph()
str_graph.add_node("process", process_str)
str_graph.add_edge(START, "process")
str_graph.add_edge("process", END)

# Execute with correct types
int_result = int_graph.execute(GenericState[int](value=1))
assert int_result.result == 2

str_result = str_graph.execute(GenericState[str](value="test"))
assert str_result.result == "test processed"
```

## Improvements

The latest version includes several important improvements:

1. **Coroutine Handling**: Proper handling of coroutines returned by nodes
2. **State Management**: Improved state persistence between nodes
3. **Error Handling**: Better error propagation and handling
4. **Type Validation**: Enhanced type checking for START and END nodes
5. **Callback Timing**: Callbacks are now called at the correct time in the execution flow
6. **Branch Handling**: Improved handling of async conditions in branches
7. **Documentation**: Updated examples to match actual implementation

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
