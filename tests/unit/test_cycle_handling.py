"""Unit tests for cycle handling in workflow graph."""

from dataclasses import dataclass

import pytest

from workflow_graph import END, START, State, WorkflowGraph


@dataclass
class CycleState:
    """State class for testing cycle handling in workflow graphs.

    This class represents a state that can be used to test cycles in workflow
    graphs. It tracks a numeric value, a count of iterations, and a flag to
    indicate when the cycle should terminate.
    """

    value: int
    count: int = 0
    terminate: bool = False


TestState = State[CycleState]


def test_cyclic_graph_allowed_by_default():
    """Test that cyclic graphs are allowed by default configuration."""
    graph = WorkflowGraph()
    graph.add_node("A", lambda state: state)
    graph.add_edge(START, "A")  # Add entry point
    graph.add_edge("A", "A")  # Create a cycle
    graph.add_edge("A", END)  # Add exit point
    graph.compile()  # Should not raise an error


def test_cyclic_graph_disallowed_when_enforce_acyclic():
    """Test that cyclic graphs are disallowed when enforce_acyclic is True."""
    graph = WorkflowGraph(enforce_acyclic=True)
    graph.add_node("A", lambda state: state)
    graph.add_edge(START, "A")  # Add entry point
    graph.add_edge("A", "A")  # Create a cycle
    graph.add_edge("A", END)  # Add exit point
    with pytest.raises(ValueError):
        graph.compile()


def test_acyclic_graph_allowed_when_enforce_acyclic():
    """Test that acyclic graphs are allowed when enforce_acyclic is True."""
    graph = WorkflowGraph(enforce_acyclic=True)
    graph.add_node("A", lambda state: state)
    graph.add_node("B", lambda state: state)
    graph.add_edge(START, "A")  # Add entry point
    graph.add_edge("A", "B")
    graph.add_edge("B", END)  # Add exit point
    graph.compile()  # Should not raise an error


def test_terminating_cycle():
    """Test a cycle that terminates based on a condition."""

    def increment_until_5(state: TestState) -> TestState:
        """Increment the count until it reaches 5."""
        current_value = state.value.value
        current_count = state.value.count
        return state.updated(
            value=CycleState(
                value=current_value,
                count=current_count + 1,
                terminate=current_count >= 4,
            )
        )

    def check_termination(state: TestState) -> bool:
        """Check if the cycle should terminate."""
        return state.value.terminate

    graph = WorkflowGraph()
    graph.add_node("increment", increment_until_5)
    graph.add_edge(START, "increment")  # Add entry point
    graph.add_conditional_edges(
        "increment",
        check_termination,
        path_map={True: END, False: "increment"},
    )

    compiled = graph.compile()
    initial_state = TestState(value=CycleState(value=0))
    result = compiled.execute(initial_state)
    assert result.value.count == 5


def test_self_looping_node():
    """Test a node that loops on itself until a condition is met."""

    def increment_with_counter(state: TestState) -> TestState:
        """Increment the value and count."""
        current_value = state.value.value
        current_count = state.value.count
        return state.updated(
            value=CycleState(
                value=current_value + 1,
                count=current_count + 1,
                terminate=current_count >= 4,
            )
        )

    def check_termination(state: TestState) -> bool:
        """Check if the self-loop should terminate."""
        return state.value.terminate

    graph = WorkflowGraph()
    graph.add_node("increment", increment_with_counter)
    graph.add_edge(START, "increment")  # Add entry point
    graph.add_conditional_edges(
        "increment",
        check_termination,
        path_map={True: END, False: "increment"},
    )

    compiled = graph.compile()
    initial_state = TestState(value=CycleState(value=0))
    result = compiled.execute(initial_state)
    assert result.value.value == 5
    assert result.value.count == 5
