# WorkflowGraph Package

This package implements a type-safe, asynchronous workflow engine that enables developers to build complex computational pipelines while maintaining type consistency and proper error handling.

## Core Motivations

1. **Type Safety**: Ensure type consistency throughout the workflow by validating input/output types between connected nodes
2. **Asynchronous Execution**: Support both synchronous and asynchronous operations without blocking
3. **Error Resilience**: Provide configurable error handling and retry mechanisms at the node level
4. **Branching Logic**: Enable conditional execution paths based on node outputs
5. **State Management**: Maintain proper state persistence between nodes with type-safe state objects

## Module Architecture

### `models.py`
Defines the core data structures that make up the workflow graph:
- `State[T]`: Generic state container that tracks execution progress and errors
- `Node[T]`: Represents a computational unit with type-safe input/output
- `Edge`: Connects nodes in the graph with support for callbacks and branches
- `Branch[T]`: Defines conditional execution paths

### `builder.py`
Provides the `WorkflowGraph` class for constructing and validating workflow graphs:
- Type-safe node and edge creation
- Validation of graph structure (cycles, unreachable nodes)
- Support for conditional branching
- Compilation into an executable form

### `executor.py`
Implements the `CompiledGraph` class for executing workflow graphs:
- Asynchronous execution with proper coroutine handling
- State management and error propagation
- Branch condition evaluation
- Callback execution timing
- Centralised type validation

### `constants.py`
Defines special nodes and constants:
- `START`: Entry point for workflow execution
- `END`: Exit point for workflow execution

### `exceptions.py`
Custom exceptions for error handling:
- Type validation errors
- Graph structure errors
- Execution errors

## Design Principles

1. **Type safety first**: All operations maintain type consistency through generics
2. **Async by default**: Core execution engine is async-first with sync wrappers
3. **Error handling**: Errors are propagated and handled at the appropriate level
4. **State immutability**: State objects are immutable to prevent side effects
5. **Branch isolation**: Branches operate independently with their own state
6. **Explicit entry points**: Conditional branches must start from explicit entry nodes

## Next Steps

- [ ] Add support for parallel node execution
- [ ] Implement state persistence between executions
- [ ] Add support for dynamic graph modification
- [ ] Improve error recovery mechanisms
- [ ] Add support for distributed execution