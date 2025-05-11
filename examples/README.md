# Workflow Graph Examples

This directory contains example implementations using the `workflow-graph` library.

## Examples

- `basic_usage/` - A simple workflow example demonstrating core concepts
- `basic_research_agent/` - A ReAct-style research agent that uses pydantic for data validation

## Development

Each example is self-contained with its own:
- `README.md` - Example-specific documentation
- `requirements.txt` - Example-specific dependencies
- `main.py` - Example implementation

## Setup

1. Install the package with example dependencies:
```bash
# From the project root
pip install -e ".[dev,examples]"
```

2. Run the examples:
```bash
# Basic usage example
python examples/basic_usage/main.py

# Research agent example
python examples/basic_research_agent/main.py
```

3. Run example tests:
```bash
# Run all tests including examples
pytest

# Run only example tests
pytest examples/
```