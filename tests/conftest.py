"""Shared fixtures and helper functions for workflow graph tests."""

import logging
import asyncio
import pytest
from workflow_graph import WorkflowGraph

# Configure logging
logger = logging.getLogger('workflow_graph')
logger.setLevel(logging.DEBUG)

# Create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Create formatter and add it to the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(ch)

# Helper functions used across tests
def add_one(x: int) -> int:
    """Add one to the input."""
    print('add_one')
    return x + 1

def multiply_by_two(x: int) -> int:
    """Multiply input by two."""
    return x * 2

def is_even(x: int) -> bool:
    """Check if input is even."""
    return x % 2 == 0

async def async_add_one(x: int) -> int:
    """Asynchronously add one to the input."""
    await asyncio.sleep(0.1)
    return x + 1

def str_to_int(x: str) -> int:
    """Convert string to integer."""
    return int(x)

@pytest.fixture
def graph():
    """Create a fresh WorkflowGraph instance for each test."""
    return WorkflowGraph()
