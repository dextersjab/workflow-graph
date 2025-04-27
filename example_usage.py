import asyncio
from workflow_graph import WorkflowGraph, START, END, State

# Define your state class
NumberProcessingState = State[int]

# Define basic nodes that work with state
def increment_number(state: NumberProcessingState) -> NumberProcessingState:
    return NumberProcessingState(value=state.value + 1)

def check_if_even(state: NumberProcessingState) -> bool:
    return state.value % 2 == 0

def process_even_number(state: NumberProcessingState) -> NumberProcessingState:
    return NumberProcessingState(value=f"Even: {state.value}")

def process_odd_number(state: NumberProcessingState) -> NumberProcessingState:
    return NumberProcessingState(value=f"Odd: {state.value}")

# Create the WorkflowGraph
number_classifier_workflow = WorkflowGraph()

# Add nodes to the graph
number_classifier_workflow.add_node("increment_number", increment_number)
number_classifier_workflow.add_node("check", lambda state: state)  # Entry node
number_classifier_workflow.add_node("process_even_number", process_even_number)
number_classifier_workflow.add_node("process_odd_number", process_odd_number)

# Define edges for the main workflow
number_classifier_workflow.add_edge(START, "increment_number")
number_classifier_workflow.add_edge("increment_number", "check")

# Define conditional edges based on whether the number is even or odd
number_classifier_workflow.add_conditional_edges(
    "check", 
    check_if_even, 
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
async def run_number_classifier(input_value: int):
    initial_state = NumberProcessingState(value=input_value)
    result = await compiled_number_classifier.execute_async(initial_state)
    print(f"Final Result: {result.value}")

# Run the workflow with different inputs
asyncio.run(run_number_classifier(5))  # Will output: "Odd: 6"
asyncio.run(run_number_classifier(6))  # Will output: "Even: 7"
