"""Research agent implementation using workflow-graph."""

import json
from typing import Callable, Optional

from workflow_graph import END, START, WorkflowGraph

from .llm_client import call_llm
from .models import Action, ResearchState
from .tools import tools


async def llm_decide(
    state: ResearchState, stream_callback: Optional[Callable[[str], None]] = None
) -> ResearchState:
    """Produce the next action from the LLM."""
    system = """You are a research agent. You have access to the following tools:

{tools}

You should use these tools to research the user's question and provide a final answer.
When you have enough information to answer the question, use the final_answer tool.
You can use the search tool to find relevant information, and the fetch tool to read web pages.

Respond with a JSON object that has either:
- tool and args fields for a tool call
- answer field for a final answer
"""
    user_input = f"""Question: {state.value['question']}

Current transcript:
{chr(10).join(state.transcript)}

What is your next action?"""

    # Call LLM with tool schemas and streaming
    response = await call_llm(
        system=system.format(
            tools="\n".join(f"- {name}: {func.__doc__}" for name, func in tools.items())
        ),
        user=user_input,
        stream_callback=stream_callback,
    )

    # Parse string response into dict
    try:
        if isinstance(response, str):
            response_dict = json.loads(response)
        else:
            response_dict = response
    except json.JSONDecodeError as e:
        return state.updated(observation=f"Error: LLM returned invalid JSON: {str(e)}")

    # Validate and convert to Action
    try:
        action = Action.model_validate(response_dict)
        return state.updated(action=action.model_dump())
    except Exception as e:
        return state.updated(observation=f"Error: Invalid action format: {str(e)}")


async def tool_on_error(state: ResearchState, error: Exception) -> ResearchState:
    """Handle tool execution errors."""
    return state.updated(observation=f"Error executing tool: {str(error)}")


async def dispatch_tool(state: ResearchState) -> ResearchState:
    """Execute a tool based on the action in state."""
    action = Action.model_validate(state.value["action"])

    # Handle terminal actions
    if action.is_final_answer():
        return state.updated(answer=action.answer)

    # Validate tool exists
    if not action.is_tool_call():
        return state.updated(observation="Error: Invalid action format")

    tool_call = action.to_tool_call()
    if tool_call.tool not in tools:
        return state.updated(observation=f"Error: Tool {tool_call.tool} not found")

    # Execute tool
    try:
        result = await tools[tool_call.tool](**tool_call.args)
        return state.updated(observation=str(result))
    except Exception as e:
        return await tool_on_error(state, e)


async def integrate_observation(state: ResearchState) -> ResearchState:
    """Integrate observations into state."""
    transcript = state.transcript
    transcript.append(f"Action: {state.value['action']}")
    if "observation" in state.value:
        transcript.append(f"Observation: {state.value['observation']}")

    # Check for final answer
    if "answer" in state.value:
        return state.updated(done=True)

    # Check step limit
    if state.step_count >= state.max_steps:
        return await synthesise_final_answer(state)

    return state.updated(step_count=state.step_count + 1, transcript=transcript)


async def synthesise_final_answer(
    state: ResearchState, stream_callback: Optional[Callable[[str], None]] = None
) -> ResearchState:
    """Synthesize a final answer when step limit reached."""
    system = """You are a research agent. Based on the following transcript, provide a final answer to the user's question.
Respond with a JSON object in this format:
{
    "answer": "your detailed answer here"
}
"""
    user_input = f"""Question: {state.value['question']}

Transcript:
{chr(10).join(state.transcript)}

Provide a final answer:"""

    response = await call_llm(
        system=system, user=user_input, stream_callback=stream_callback
    )

    # Parse response
    try:
        if isinstance(response, str):
            response_dict = json.loads(response)
        else:
            response_dict = response

        action = Action.model_validate(response_dict)
        if not action.is_final_answer():
            return state.updated(answer="Error: Failed to generate final answer")
        return state.updated(answer=action.answer, done=True)
    except Exception as e:
        return state.updated(
            answer=f"Error generating final answer: {str(e)}", done=True
        )


def build_graph() -> WorkflowGraph:
    """Build the workflow graph for the research agent."""
    graph = WorkflowGraph()

    # Callbacks for logging
    def log_reason(state: ResearchState) -> None:
        print(f"\nThought: {state.value.get('thought', '')}")

    def log_tool(state: ResearchState) -> None:
        action = Action.model_validate(state.value["action"])
        if action.is_tool_call():
            tool_call = action.to_tool_call()
            print(f"\nAction: {tool_call.tool}({tool_call.args})")

    def log_observation(state: ResearchState) -> None:
        if "observation" in state.value:
            print(f"\nObservation: {state.value['observation']}")

    def stream_token(token: str) -> None:
        print(token, end="", flush=True)

    # Add nodes with callbacks
    graph.add_node(
        "reasoning", llm_decide, callback=log_reason, stream_callback=stream_token
    )
    graph.add_node("tool", dispatch_tool, callback=log_tool, on_error=tool_on_error)
    graph.add_node(
        "integrate_observation", integrate_observation, callback=log_observation
    )
    graph.add_node(
        "synthesise_final_answer", synthesise_final_answer, stream_callback=stream_token
    )

    # Add edges
    graph.add_edge(START, "reasoning")
    graph.add_edge("reasoning", "tool")
    graph.add_edge("tool", "integrate_observation")

    # Add direct edge to END with callback
    graph.add_edge("integrate_observation", END, callback=synthesise_final_answer)

    # Update conditional edge from integrate_observation
    def next_step(state: ResearchState):
        if state.done:
            return "done"
        if state.step_count >= state.max_steps:
            return "limit"
        return "loop"

    # Add conditional edge back to reasoning (only if not done and not at step limit)
    graph.add_conditional_edges(
        "integrate_observation",
        next_step,
        path_map={"done": END, "limit": "synthesise_final_answer", "loop": "reasoning"},
    )

    compiled_graph = graph.compile()

    # print mermaid diagram
    print("\nMermaid diagram representation:\n")
    print(compiled_graph.to_mermaid())
    print("\n")

    return compiled_graph
