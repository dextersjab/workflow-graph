"""Utility functions for workflow graph."""

import inspect
from typing import Any, Callable, Type, TypeVar, get_type_hints

T = TypeVar("T")


def get_return_type_hint(func: Callable[..., Any]) -> Type[Any] | None:
    """Get the return type hint of a function."""
    try:
        hints = get_type_hints(func)
        return hints.get("return")
    except Exception:
        return None


def get_first_param_type_hint(func: Callable[..., Any]) -> Type[Any] | None:
    """Get the type hint of the first parameter of a function."""
    try:
        hints = get_type_hints(func)
        sig = inspect.signature(func)
        first_param = next(iter(sig.parameters))
        return hints.get(first_param)
    except Exception:
        return None


def is_type_compatible(type1: Type[Any], type2: Type[Any]) -> bool:
    """Check if two types are compatible."""
    # Handle generic types
    if hasattr(type1, "__origin__") and hasattr(type2, "__origin__"):
        # Check if base types are compatible
        if type1.__origin__ != type2.__origin__:
            return False
        # Check type arguments
        args1 = getattr(type1, "__args__", None)
        args2 = getattr(type2, "__args__", None)
        if args1 and args2:
            return args1 == args2
        return True
    # Handle non-generic types
    return issubclass(type1, type2) or issubclass(type2, type1)
