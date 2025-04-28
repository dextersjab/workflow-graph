# State API Improvements

## Overview

This document outlines proposed improvements to the `State` class API to make it more robust, user-friendly, and maintainable.

## Current Issues

- Manual field copying is verbose and error-prone
- Inconsistent error handling (mixing Exception objects and strings)
- No clear immutable update pattern
- Limited data access methods

## Proposed Improvements

### 1. Add Immutable Update Method

```python
from dataclasses import replace

@dataclass
class State(Generic[T]):
    # ... existing fields and methods ...

    def updated(self, **kwargs) -> "State[T]":
        """Return a new State with updated fields (immutable pattern)."""
        return replace(self, **kwargs)
```

**Usage:**
```python
new_state = state.updated(value="new value", data={...})
```

### 2. Clarify Error Handling

- Change `errors` field from `list[Exception]` to `list[str]` to match actual usage
- Ensure consistent error message format

### 3. Improve Data Access

Add a `with_data` method for immutable updates to the `data` dict:

```python
def with_data(self, key: str, value: Any) -> "State[T]":
    new_data = self.data.copy()
    new_data[key] = value
    return self.updated(data=new_data)
```

### 4. Make State Hashable (Optional)

- Add `frozen=True` to the dataclass
- Ensure all fields are hashable
- Note: This makes the object immutable

### 5. Docstring and Typing Consistency

- Update docstrings to match actual usage
- Ensure type hints are consistent with implementation

## Example: Improved State API

```python
from dataclasses import dataclass, field, replace
from typing import Any, Generic, TypeVar

T = TypeVar("T")

@dataclass
class State(Generic[T]):
    value: T | None
    data: dict[str, Any] = field(default_factory=dict)
    current_node: str | None = None
    trajectory: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # Store error messages as strings

    def add_error(self, error: Exception, node: str | None = None) -> "State[T]":
        """Return a new State with an added error message."""
        error_msg = str(error)
        if node:
            error_msg = f"{node}: {error_msg}"
        new_errors = self.errors + [error_msg]
        return self.updated(errors=new_errors)

    def updated(self, **kwargs) -> "State[T]":
        """Return a new State with updated fields (immutable pattern)."""
        return replace(self, **kwargs)

    def with_data(self, key: str, value: Any) -> "State[T]":
        new_data = self.data.copy()
        new_data[key] = value
        return self.updated(data=new_data)
```

## Method Summary

| Method         | Purpose                                 | Returns      |
|----------------|-----------------------------------------|--------------|
| `updated`      | Immutable update of any field(s)        | new State    |
| `with_data`    | Immutable update of a data key          | new State    |
| `add_error`    | Immutable add error message             | new State    |

## Benefits

- **Consistency:** All updates are immutable and chainable
- **Clarity:** No more manual copying of fields
- **Pythonic:** Follows dataclass and functional best practices
- **Maintainability:** Easier to add new fields without updating all node functions

## Next Steps

1. Implement the improved State API
2. Update all node functions to use the new immutable pattern
3. Add tests for the new methods
4. Update documentation and examples 