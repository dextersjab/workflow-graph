"""Research agent workflow entry point."""

import argparse
import asyncio

from src.agent import build_graph
from src.models import ResearchState


async def main():
    """Run the research agent with the given question."""
    p = argparse.ArgumentParser(description="research agent workflow")
    p.add_argument("question", help="research question")
    p.add_argument(
        "--max-steps", type=int, default=12, help="maximum number of tool calls / steps"
    )
    args = p.parse_args()

    compiled = build_graph()
    init_state = ResearchState(
        value={"question": args.question, "step_count": 0, "max_steps": args.max_steps}
    )
    result: ResearchState = await compiled.execute_async(init_state)
    print(result.value["answer"])


if __name__ == "__main__":
    asyncio.run(main())
