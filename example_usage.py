import asyncio
from dataclasses import dataclass
from typing import Optional, List
from workflow_graph import WorkflowGraph, START, END

# Define your state class
@dataclass
class WorkflowState:
    input_value: int
    current_value: Optional[int] = None
    is_even: Optional[bool] = None
    result: Optional[str] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

# Define basic nodes that work with state
def add(state: WorkflowState, callback=None) -> WorkflowState:
    result = state.input_value + 1
    if callback:
        callback(f"add: {state.input_value} -> {result}")
    return WorkflowState(
        input_value=state.input_value,
        current_value=result,
        errors=state.errors
    )

def is_even(state: WorkflowState) -> bool:
    return state.current_value % 2 == 0

def handle_even(state: WorkflowState, callback=None) -> WorkflowState:
    result = f"Even: {state.current_value}"
    if callback:
        callback(result)
    return WorkflowState(
        input_value=state.input_value,
        current_value=state.current_value,
        is_even=True,
        result=result,
        errors=state.errors
    )

def handle_odd(state: WorkflowState, callback=None) -> WorkflowState:
    result = f"Odd: {state.current_value}"
    if callback:
        callback(result)
    return WorkflowState(
        input_value=state.input_value,
        current_value=state.current_value,
        is_even=False,
        result=result,
        errors=state.errors
    )

# Create the WorkflowGraph
graph = WorkflowGraph()

# Add nodes to the graph
graph.add_node("addition", add)
graph.add_node("is_even_check", is_even)
graph.add_node("even_handler", handle_even)
graph.add_node("odd_handler", handle_odd)

# Define edges for the main workflow
graph.add_edge(START, "addition")
graph.add_edge("addition", "is_even_check")

# Define conditional edges based on whether the number is even or odd
graph.add_conditional_edges(
    "is_even_check", 
    path=is_even, 
    path_map={True: "even_handler", False: "odd_handler"}
)

# Set finish points
graph.add_edge("even_handler", END)
graph.add_edge("odd_handler", END)

# Compile the graph
compiled_graph = graph.compile()

# Generate and print Mermaid diagram
print("\nMermaid diagram representation:")
print(graph.to_mermaid())

# Execute the workflow
async def run_workflow(input_value):
    initial_state = WorkflowState(input_value=input_value)
    result = await compiled_graph.execute_async(initial_state, callback=print)
    print(f"Final Result: {result.result}")

# Run the workflow with different inputs
asyncio.run(run_workflow(5))  # Will output: "Even: 6"
asyncio.run(run_workflow(6))  # Will output: "Odd: 7"
