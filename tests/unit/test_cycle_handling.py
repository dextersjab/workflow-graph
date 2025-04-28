"""Unit tests for cycle handling in workflow graph."""

import pytest
from dataclasses import dataclass
from workflow_graph import WorkflowGraph, START, END, State

@dataclass
class CycleState:
    value: int
    count: int = 0
    terminate: bool = False

TestState = State[CycleState]

def test_cyclic_graph_allowed_by_default():
    """Test that a cyclic graph is allowed when enforce_acyclic is False."""
    graph = WorkflowGraph()
    graph.add_node("A", lambda state: state.updated(value=CycleState(value=state.value.value + 1)))
    graph.add_node("B", lambda state: state.updated(value=CycleState(value=state.value.value * 2)))
    
    graph.add_edge(START, "A")
    graph.add_edge("A", "B")
    graph.add_edge("B", "A")  # Creates a cycle
    graph.add_edge("B", END) 
    graph.validate()  # Should not raise an error

def test_cyclic_graph_disallowed_when_enforce_acyclic():
    """Test that a cyclic graph raises an error when enforce_acyclic is True."""
    graph = WorkflowGraph(enforce_acyclic=True)
    graph.add_node("A", lambda state: state.updated(value=CycleState(value=state.value.value + 1)))
    graph.add_node("B", lambda state: state.updated(value=CycleState(value=state.value.value * 2)))
    
    graph.add_edge(START, "A")
    graph.add_edge("A", "B")
    graph.add_edge("B", "A")  # Creates a cycle
    graph.add_edge("B", END) 
    with pytest.raises(ValueError, match="Graph contains cycles"):
        graph.validate()

def test_acyclic_graph_allowed_when_enforce_acyclic():
    """Test that an acyclic graph is allowed when enforce_acyclic is True."""
    graph = WorkflowGraph(enforce_acyclic=True)
    graph.add_node("A", lambda state: state.updated(value=CycleState(value=state.value.value + 1)))
    graph.add_node("B", lambda state: state.updated(value=CycleState(value=state.value.value * 2)))
    
    graph.add_edge(START, "A")
    graph.add_edge("A", "B")
    graph.add_edge("B", END)
    graph.validate()  # Should not raise an error

def test_terminating_cycle():
    """Test a cycle that terminates after a certain number of iterations."""
    graph = WorkflowGraph()
    
    def increment_until_5(state: TestState) -> TestState:
        if state.value.value >= 5:
            return state.updated(value=CycleState(value=state.value.value, terminate=True))
        return state.updated(value=CycleState(value=state.value.value + 1))
    
    def check_termination(state: TestState) -> bool:
        return state.value.terminate
    
    graph.add_node("check", lambda state: state)  # entry node
    graph.add_node("increment", increment_until_5)
    
    graph.add_edge(START, "check")
    graph.add_edge("check", "increment")
    graph.add_edge("increment", "check")  # creates a cycle
    graph.add_conditional_edges(
        "check",
        check_termination,
        path_map={True: END, False: "increment"}
    )
    
    graph.validate()
    
    # run the workflow
    initial_state = TestState(value=CycleState(value=0))
    result = graph.execute(initial_state)
    assert result.value.value == 5  # should increment until reaching 5

def test_self_looping_node():
    """Test a node that loops back to itself to apply the same function multiple times."""
    graph = WorkflowGraph()
    
    def increment_with_counter(state: TestState) -> TestState:
        count = state.value.count + 1
        if count >= 3:  # apply function 3 times
            return state.updated(value=CycleState(value=state.value.value + 1, count=count, terminate=True))
        return state.updated(value=CycleState(value=state.value.value + 1, count=count))
    
    def check_termination(state: TestState) -> bool:
        return state.value.terminate
    
    graph.add_node("increment", increment_with_counter)
    graph.add_node("check", lambda state: state)  # entry node
    
    graph.add_edge(START, "check")
    graph.add_edge("check", "increment")
    graph.add_edge("increment", "check")  # creates a cycle
    graph.add_conditional_edges(
        "check",
        check_termination,
        path_map={True: END, False: "increment"}
    )
    
    graph.validate()
    
    # run the workflow
    initial_state = TestState(value=CycleState(value=0))
    result = graph.execute(initial_state)
    assert result.value.value == 3  # Should increment 3 times
    assert result.value.count == 3  # Should have looped 3 times 