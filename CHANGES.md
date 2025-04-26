# Workflow Graph Changes

## Overview
The codebase has undergone significant changes to improve type safety, error handling, and state management. The changes focus on making the workflow graph more robust and maintainable while providing better type validation and error handling capabilities.

## Major Changes

### 1. Type System Improvements
- Added generic type support with `TypeVar('T')` throughout the codebase
- Made `WorkflowGraph`, `Node`, and `State` classes generic
- Improved type validation for edges and nodes
- Added proper handling of generic type arguments in type compatibility checks

### 2. State Management
- Introduced a new `State` class with improved error tracking
- Added `processed_by` and `branch_taken` tracking
- Enhanced error propagation through the workflow
- Improved state persistence between nodes

### 3. Error Handling
- Renamed `on_error` to `error_handler` for consistency
- Fixed error handler parameter order (now takes error first, then state)
- Added better error message formatting
- Improved error propagation through the workflow

### 4. Graph Structure
- Changed edge storage from tuples to `Edge` objects
- Improved branch handling with better condition evaluation
- Enhanced validation of graph structure
- Added better handling of START and END nodes

### 5. Async Support
- Improved coroutine handling
- Better async/await support throughout the codebase
- Fixed callback timing issues
- Enhanced async error handling

### 6. Documentation
- Updated README.md with clearer examples
- Added better type hints and docstrings
- Improved error messages
- Added more comprehensive test cases

## Breaking Changes

1. **Type System**
   - All classes are now generic
   - Type validation is more strict
   - Generic type arguments must match exactly

2. **Error Handling**
   - `on_error` parameter renamed to `error_handler`
   - Error handler signature changed to `(error, state)`
   - Error messages now include node names

3. **State Management**
   - New `State` class with additional fields
   - Required tracking of processed nodes
   - Better error state management

4. **Graph Structure**
   - Edges are now stored as objects instead of tuples
   - Branch conditions must be more explicit
   - START and END nodes have stricter validation

## Migration Guide

1. **Update Node Definitions**
   ```python
   # Old
   graph.add_node("node", func, on_error=handler)
   
   # New
   graph.add_node("node", func, error_handler=handler)
   ```

2. **Update Error Handlers**
   ```python
   # Old
   def error_handler(state, error):
       return state
   
   # New
   def error_handler(error, state):
       return state
   ```

3. **Update State Classes**
   ```python
   # Old
   class MyState:
       value: Any
       result: Any
   
   # New
   class MyState(Generic[T]):
       value: T
       result: Any
       errors: list[str] = field(default_factory=list)
       branch_taken: str | None = None
       processed_by: list[str] = field(default_factory=list)
   ```

4. **Update Type Annotations**
   ```python
   # Old
   graph = WorkflowGraph()
   
   # New
   graph = WorkflowGraph[MyState]()
   ```

## Future Improvements

1. **Performance Optimization**
   - Consider caching compiled graphs
   - Optimize state copying
   - Improve async execution

2. **Additional Features**
   - Add support for parallel execution
   - Implement graph visualization
   - Add support for graph composition

3. **Documentation**
   - Add more examples
   - Improve API documentation
   - Add migration guides

## Conclusion
These changes make the workflow graph more robust, type-safe, and easier to maintain. While there are breaking changes, they provide significant improvements in reliability and usability. The new type system and error handling make it easier to catch issues at compile time rather than runtime. 