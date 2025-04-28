"""Example demonstrating basic usage of the workflow-graph package.

This example shows how to create a simple workflow that:
1. Adds one to a number
2. Checks if the result is even or odd
3. Processes the number differently based on its parity
"""

import asyncio
import sys

from workflow_graph import END, START, State, WorkflowGraph

# define your state class
NumberProcessingState = State[int]


def add_one(state: NumberProcessingState) -> NumberProcessingState:
    """Add one to the current state value."""
    return state.updated(value=state.value + 1)


def process_even_number(state: NumberProcessingState) -> NumberProcessingState:
    """Process an even number by appending 'even' to its string representation."""
    return state.updated(value=f"{state.value}, even")


def process_odd_number(state: NumberProcessingState) -> NumberProcessingState:
    """Process an odd number by appending 'odd' to its string representation."""
    return state.updated(value=f"{state.value}, odd")


# create the workflow graph
add_one_and_classify_workflow = WorkflowGraph()

# add nodes to the graph
add_one_and_classify_workflow.add_node("add_one", add_one)
add_one_and_classify_workflow.add_node(
    "check_if_even", lambda state: state
)  # Entry node
add_one_and_classify_workflow.add_node("process_even_number", process_even_number)
add_one_and_classify_workflow.add_node("process_odd_number", process_odd_number)

# add fixed edges between nodes
add_one_and_classify_workflow.add_edge(START, "add_one")
add_one_and_classify_workflow.add_edge("add_one", "check_if_even")

# add conditional edge between nodes
# i.e. choose the target node based on whether the number is even or odd
add_one_and_classify_workflow.add_conditional_edges(
    "check_if_even",
    lambda state: state.value % 2 == 0,
    path_map={True: "process_even_number", False: "process_odd_number"},
)

# set fixed finish points
add_one_and_classify_workflow.add_edge("process_even_number", END)
add_one_and_classify_workflow.add_edge("process_odd_number", END)

# compile and validate the graph
compiled_add_one_and_classify = add_one_and_classify_workflow.compile()

# print mermaid diagram
print("\nMermaid diagram representation:\n")
print(add_one_and_classify_workflow.to_mermaid())
print("\n")


# run the workflow
async def run_workflow(input_value: int, delay: float = 0.0):
    """Run the workflow with the given input value and optional delay.

    Args:
        input_value: The initial number to process
        delay: Optional delay between steps in seconds
    """
    print("---")
    print(f"Input value: {input_value}")
    initial_state = NumberProcessingState(value=input_value)

    spinner = ["|", "/", "-", "\\"]
    spinner_index = 0
    running = True

    async def spinner_task():
        nonlocal spinner_index
        while running:
            sys.stdout.write(
                f"\r{input_value} -[add_one_and_classify]-> {spinner[spinner_index % len(spinner)]}"
            )
            sys.stdout.flush()
            spinner_index += 1
            await asyncio.sleep(0.1)

    _ = asyncio.create_task(spinner_task())
    await asyncio.sleep(delay)  # Simulate processing delay
    result = await compiled_add_one_and_classify.execute_async(initial_state)
    running = False
    await asyncio.sleep(0.1)  # Let spinner clear

    sys.stdout.write(f"\r{input_value} -[add_one_and_classify]-> {result.value}\n")
    sys.stdout.flush()
    print("---\n")


# run the workflow with different inputs
# simulate real workflows by faking delays
asyncio.run(run_workflow(5, delay=1.0))
asyncio.run(run_workflow(6, delay=2.0))
