# Research Agent Example

A ReAct-style research agent implemented using `workflow-graph`.

## Purpose

This example demonstrates:
- Building a ReAct agent with workflow-graph
- Using LLMs for reasoning (OpenRouter / OpenAI)
- Tool calling and state management
- Async / await patterns in workflow nodes

## Structure

```
src/
  agent.py      # Core agent logic and workflow
  llm_client.py # LLM providers (OpenRouter / OpenAI)
  tools.py      # Search and fetch tools
  models.py     # Pydantic models and state
run_basic_research_agent.py # Entry point
```

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
export OPENROUTER_API_KEY=<your-key>  # or OPENAI_API_KEY
export BRAVE_API_KEY=<optional>

# Run the agent
python run_basic_research_agent.py "Your research question"
```
