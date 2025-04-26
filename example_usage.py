import asyncio
from dataclasses import dataclass
from typing import Optional, List
from workflow_graph import WorkflowGraph, START, END

# Define your state class
@dataclass
class NumberProcessingState:
    input_value: int
    current_value: Optional[int] = None
    is_even: Optional[bool] = None
    result: Optional[str] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

# Define basic nodes that work with state
def increment_number(state: NumberProcessingState, callback=None) -> NumberProcessingState:
    result = state.input_value + 1
    if callback:
        callback(f"increment: {state.input_value} -> {result}")
    return NumberProcessingState(
        input_value=state.input_value,
        current_value=result,
        errors=state.errors
    )

def check_if_even(state: NumberProcessingState) -> bool:
    return state.current_value % 2 == 0

def process_even_number(state: NumberProcessingState, callback=None) -> NumberProcessingState:
    result = f"Even: {state.current_value}"
    if callback:
        callback(result)
    return NumberProcessingState(
        input_value=state.input_value,
        current_value=state.current_value,
        is_even=True,
        result=result,
        errors=state.errors
    )

def process_odd_number(state: NumberProcessingState, callback=None) -> NumberProcessingState:
    result = f"Odd: {state.current_value}"
    if callback:
        callback(result)
    return NumberProcessingState(
        input_value=state.input_value,
        current_value=state.current_value,
        is_even=False,
        result=result,
        errors=state.errors
    )

# Create the WorkflowGraph
number_classifier_workflow = WorkflowGraph()

# Add nodes to the graph
number_classifier_workflow.add_node("increment_number", increment_number)
number_classifier_workflow.add_node("check_if_even", check_if_even)
number_classifier_workflow.add_node("process_even_number", process_even_number)
number_classifier_workflow.add_node("process_odd_number", process_odd_number)

# Define edges for the main workflow
number_classifier_workflow.add_edge(START, "increment_number")
number_classifier_workflow.add_edge("increment_number", "check_if_even")

# Define conditional edges based on whether the number is even or odd
number_classifier_workflow.add_conditional_edges(
    "check_if_even", 
    path=check_if_even, 
    path_map={True: "process_even_number", False: "process_odd_number"}
)

# Set finish points
number_classifier_workflow.add_edge("process_even_number", END)
number_classifier_workflow.add_edge("process_odd_number", END)

# Compile the graph
compiled_number_classifier = number_classifier_workflow.compile()

# Generate and print Mermaid diagram
print("\nMermaid diagram representation:")
print(number_classifier_workflow.to_mermaid())

# Execute the workflow
async def run_number_classifier(input_value):
    initial_state = NumberProcessingState(input_value=input_value)
    result = await compiled_number_classifier.execute_async(initial_state, callback=print)
    print(f"Final Result: {result.result}")

# Run the workflow with different inputs
asyncio.run(run_number_classifier(5))  # Will output: "Even: 6"
asyncio.run(run_number_classifier(6))  # Will output: "Odd: 7"
