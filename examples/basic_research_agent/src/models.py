"""Models for the research agent."""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from workflow_graph import State


# tool schemas for LLM function calling
class ToolCall(BaseModel):
    """A request to call a tool with arguments."""

    tool: str
    args: Dict[str, Any]


class FinalAnswer(BaseModel):
    """A final answer from the agent."""

    answer: str


class Action(BaseModel):
    """Union type for possible actions."""

    tool: str | None = Field(default=None)
    args: Dict[str, Any] | None = Field(default=None)
    answer: str | None = Field(default=None)

    def is_tool_call(self) -> bool:
        """Check if this is a tool call action."""
        return self.tool is not None and self.args is not None

    def is_final_answer(self) -> bool:
        """Check if this is a final answer action."""
        return self.answer is not None

    def to_tool_call(self) -> ToolCall:
        """Convert to ToolCall if possible."""
        if not self.is_tool_call():
            raise ValueError("Not a tool call")
        return ToolCall(tool=self.tool, args=self.args)

    def to_final_answer(self) -> FinalAnswer:
        """Convert to FinalAnswer if possible."""
        if not self.is_final_answer():
            raise ValueError("Not a final answer")
        return FinalAnswer(answer=self.answer)


@dataclass
class ResearchState(State[dict]):
    """State for the research agent workflow."""

    value: dict = field(default_factory=dict)

    def updated(self, **kwargs):
        """Create a new state with updated values."""
        merged = {**self.value, **kwargs}
        return ResearchState(value=merged)

    @property
    def step_count(self) -> int:
        """Get the current step count."""
        return self.value.get("step_count", 0)

    @property
    def max_steps(self) -> int:
        """Get the maximum number of steps allowed."""
        return self.value.get("max_steps", 10)

    # handy flags
    @property
    def done(self) -> bool:
        """Check if the agent has completed its task."""
        return "answer" in self.value

    @property
    def transcript(self) -> List[str]:
        """Get the conversation transcript."""
        return self.value.setdefault(
            "transcript", []
        )  # mutation safe because new obj created each .updated
