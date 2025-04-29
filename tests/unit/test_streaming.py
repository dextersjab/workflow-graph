"""Tests for streaming functionality in workflow graph nodes."""

from typing import Callable, List, Optional

from src.workflow_graph.models import Node, State


def test_node_with_streaming_callback():
    """Test that a node's streaming callback is called for each token."""
    # Setup
    tokens: List[str] = []

    def stream_callback(token: str) -> None:
        tokens.append(token)

    def streaming_func(
        input_text: str, stream_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        result = ""
        for token in ["Hello", " ", "World", "!"]:
            result += token
            if stream_callback:
                stream_callback(token)
        return result

    # Create node with streaming callback
    node = Node(
        name="streaming_test", func=streaming_func, stream_callback=stream_callback
    )

    # Execute
    result = node.func("", stream_callback)

    # Verify
    assert result == "Hello World!"
    assert tokens == ["Hello", " ", "World", "!"]


def test_node_without_streaming_callback():
    """Test that a node works correctly without a streaming callback."""

    def streaming_func(
        input_text: str, stream_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        result = ""
        for token in ["Hello", " ", "World", "!"]:
            result += token
            if stream_callback:
                stream_callback(token)
        return result

    # Create node without streaming callback
    node = Node(name="streaming_test", func=streaming_func)

    # Execute
    result = node.func("")

    # Verify
    assert result == "Hello World!"


def test_streaming_with_state():
    """Test streaming functionality when using State object."""
    tokens: List[str] = []

    def stream_callback(token: str) -> None:
        tokens.append(token)

    def streaming_func(
        input_text: str, stream_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        result = ""
        for token in ["Hello", " ", "World", "!"]:
            result += token
            if stream_callback:
                stream_callback(token)
        return result

    # Create node with streaming callback
    node = Node(
        name="streaming_test", func=streaming_func, stream_callback=stream_callback
    )

    # Execute with state
    initial_state = State(value="")
    result = node.func("", stream_callback)
    final_state = initial_state.updated(value=result)

    # Verify
    assert final_state.value == "Hello World!"
    assert tokens == ["Hello", " ", "World", "!"]


def test_streaming_with_error_handling():
    """Test streaming functionality with error handling."""
    tokens: List[str] = []

    def stream_callback(token: str) -> None:
        tokens.append(token)

    def streaming_func(
        input_text: str, stream_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        result = ""
        for token in ["Hello", " ", "World", "!"]:
            if token == "World":
                raise ValueError("Test error")
            result += token
            if stream_callback:
                stream_callback(token)
        return result

    # Create node with streaming callback and error handler
    def error_handler(error: Exception, state: State) -> State:
        return state.add_error(error, "streaming_test")

    node = Node(
        name="streaming_test",
        func=streaming_func,
        stream_callback=stream_callback,
        on_error=error_handler,
    )

    # Execute with error handling
    state = State(value="")
    try:
        # Wrap the function call to properly handle errors
        def wrapped_func(input_text: str) -> str:
            return node.func(input_text, node.stream_callback)

        wrapped_func("")
    except ValueError as e:
        # Call error handler directly since we're not using the execution engine
        state = error_handler(e, state)

    # Verify
    assert len(state.errors) == 1
    assert "Test error" in state.errors[0]
    assert tokens == ["Hello", " "]
