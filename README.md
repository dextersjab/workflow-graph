# Workflow Graph

A Python library for building and executing directed graphs of operations, with support for both synchronous and asynchronous execution.

> **BREAKING CHANGES WARNING**: Version 0.3.0 introduced significant API changes. Please review the documentation carefully when upgrading from earlier versions.

## Features

- **Type-Safe Workflows**: Built-in type validation ensures type consistency throughout the workflow
- **Async Support**: Native support for asynchronous operations and coroutines
- **Error Handling**: Configurable error handling and retry policies
- **Branching Logic**: Support for conditional branches with async conditions
- **State Management**: Proper state persistence between nodes
- **Callback Support**: Configurable callbacks for monitoring execution progress
- **Generic Types**: Support for generic types in workflow state
- **Cycle Support**: By default, cycles are allowed. Use `enforce_acyclic=True` to enforce a DAG structure.

## Development Tools

This project uses several development tools to maintain code quality and consistency:

- **Black**: Code formatter that enforces consistent Python code style
- **isort**: Sorts and organizes imports alphabetically and by sections
- **Flake8**: Linter that checks for style guide enforcement and logical errors
- **mypy**: Static type checker for Python

### Installation

To install all development dependencies:

```bash
pip install -e ".[dev]"
```

### Usage

Format code with Black and isort:

```bash
black .
isort .
```

Run Flake8 linting:

```bash
flake8
```

Run mypy type checking:

```bash
mypy .
```

### Pre-commit Hooks

To set up pre-commit hooks that automatically run these tools before each commit:

1. Install pre-commit:
```bash
pip install pre-commit
```

2. Install the hooks:
```bash
pre-commit install
```

The hooks will automatically run Black, isort, Flake8, and mypy before each commit.

## Installation

```bash
pip install workflow-graph
```

## Usage

For a complete example with visualization and async execution, see [examples/basic_usage.py](./examples/basic_usage.py).

### Basic Workflow

```python
from workflow_graph import WorkflowGraph, START, END, State

# Define your state class
NumberProcessingState = State[int]

# Define basic nodes that work with state
def add_one(state: NumberProcessingState) -> NumberProcessingState:
    return state.updated(value=state.value + 1)

def check_if_even(state: NumberProcessingState) -> bool:
    return state.value % 2 == 0

def process_even_number(state: NumberProcessingState) -> NumberProcessingState:
    return state.updated(value=f"{state.value} ==> Even")

def process_odd_number(state: NumberProcessingState) -> NumberProcessingState:
    return state.updated(value=f"{state.value} ==> Odd")

# Create the WorkflowGraph
workflow = WorkflowGraph()

# Add nodes to the graph
workflow.add_node("add_one", add_one)
workflow.add_node("check", lambda state: state)  # Entry node
workflow.add_node("process_even_number", process_even_number)
workflow.add_node("process_odd_number", process_odd_number)

# Define edges for the main workflow
workflow.add_edge(START, "add_one")
workflow.add_edge("add_one", "check")

# Define conditional edges based on whether the number is even or odd
workflow.add_conditional_edges(
    "check", 
    check_if_even, 
    path_map={True: "process_even_number", False: "process_odd_number"}
)

# Set finish points
workflow.add_edge("process_even_number", END)
workflow.add_edge("process_odd_number", END)

# Execute the workflow
initial_state = NumberProcessingState(value=5)
result = workflow.execute(initial_state)
print(result.value)  # Output: "6 ==> Odd"
```

This example demonstrates a simple workflow that:
1. Takes a number as input
2. Adds one to it
3. Checks if the result is even or odd
4. Labels the result accordingly

For a more complete example with visualization and async execution, see [example_usage.py](./example_usage.py).

### Async Workflow

```python
import asyncio
from workflow_graph import WorkflowGraph, START, END, State

@dataclass
class NumberState(State[int]):
    """State for number processing workflow."""
    pass

async def async_operation(state: NumberState) -> NumberState:
    await asyncio.sleep(0.1)
    return state.updated(value=state.value + 1)

graph = WorkflowGraph()
graph.add_node("async_op", async_operation)
graph.add_edge(START, "async_op")
graph.add_edge("async_op", END)

initial_state = NumberState(value=1)
result = await graph.execute_async(initial_state)
assert result.value == 2
```

### Conditional Branches

```python
def is_even(state: NumberState) -> bool:
    return state.value % 2 == 0

def process_even(state: NumberState) -> NumberState:
    return state.updated(value=state.value * 2)

def process_odd(state: NumberState) -> NumberState:
    return state.updated(value=state.value + 1)

graph = WorkflowGraph()
graph.add_node("check", lambda state: state)  # Entry node
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
result = graph.execute(NumberState(value=2))
assert result.value == 4  # 2 * 2 = 4

# Test with odd number
result = graph.execute(NumberState(value=3))
assert result.value == 4  # 3 + 1 = 4
```

### Error Handling

```python
def failing_operation(state: NumberState) -> NumberState:
    raise ValueError("Operation failed")

def error_handler(error: Exception, state: NumberState) -> NumberState:
    return state.updated(value=-1).add_error(error, "failing_op")

graph = WorkflowGraph()
graph.add_node(
    "failing_op",
    failing_operation,
    retries=2,
    backoff_factor=0.1,
    error_handler=error_handler
)
graph.add_edge(START, "failing_op")
graph.add_edge("failing_op", END)

result = graph.execute(NumberState(value=1))
assert result.value == -1
assert len(result.errors) > 0
```

### Callbacks

```python
def process_data(state: NumberState) -> NumberState:
    return state.updated(value=state.value * 10)

def callback(result: NumberState):
    print(f"Processed result: {result.value}")

graph = WorkflowGraph()
graph.add_node("process", process_data, callback=callback)
graph.add_edge(START, "process")
graph.add_edge("process", END)

graph.execute(NumberState(value=5))  # Prints: Processed result: 50
```

### Generic Types

```python
from typing import Generic, TypeVar

T = TypeVar('T')

# No need for custom GenericState class - use State[T] directly
def process_int(state: State[int]) -> State[int]:
    return state.updated(value=state.value + 1)

def process_str(state: State[str]) -> State[str]:
    return state.updated(value=state.value + " processed")

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
int_result = int_graph.execute(State[int](value=1))
assert int_result.value == 2

str_result = str_graph.execute(State[str](value="test"))
assert str_result.value == "test processed"
```

## Improvements

The latest version includes several important improvements:

1. **Type Safety**: Enhanced type validation and generic type support
2. **State Management**: Simplified state structure with value and data fields
3. **Error Handling**: Consistent on_error naming and improved error propagation
4. **Edge Objects**: Edge objects for better graph structure representation
5. **Branch Handling**: Explicit entry nodes for conditional branches
6. **Callback Timing**: Improved callback execution timing
7. **Documentation**: Updated examples to match actual implementation
8. **Cycle Support**: By default, cycles are allowed. Use `enforce_acyclic=True` to enforce a DAG structure.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.
