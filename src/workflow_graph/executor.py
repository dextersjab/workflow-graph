"""Executor for compiled workflow graphs."""

import asyncio
import logging
from collections import defaultdict, deque
from typing import Any, Callable, Hashable

from .constants import START, END
from .models import Branch, NodeSpec

logger = logging.getLogger(__name__)


class CompiledGraph:
    """Compiled workflow graph ready for execution.
    
    This class represents a compiled workflow graph that can be executed
    with a given input to produce an output.
    """
    
    def __init__(self, nodes: dict[str, NodeSpec], edges: set[tuple[str, str]], branches: dict[str, dict[str, Branch]]):
        """Initialize a compiled graph."""
        self.nodes = nodes
        self.edges = defaultdict(list)
        for start, end in edges:
            self.edges[start].append(end)
        self.branches = branches  # Keep the original branch dictionary structure
        self.compiled = False

    def to_mermaid(self) -> str:
        """Generate a Mermaid diagram representation of the workflow graph.
        
        Returns:
            A string containing the Mermaid diagram code.
        """
        mermaid_code = ["```mermaid", "flowchart TD"]
        
        # Define node styles
        mermaid_code.append(f"    {START}[\"START\"]")
        mermaid_code.append(f"    {END}[\"END\"]")
        
        # Add custom nodes
        for node_name in self.nodes:
            mermaid_code.append(f"    {node_name}[\"{node_name}\"]")
        
        # Add direct edges
        for start, ends in self.edges.items():
            for end in ends:
                mermaid_code.append(f"    {start} --> {end}")
        
        # Add conditional edges with dashed lines
        for source, branch_dict in self.branches.items():
            for branch_id, branch in branch_dict.items():
                # Handle the 'then' case
                if branch.then:
                    # Use dashed lines for conditional edges
                    mermaid_code.append(f"    {source} -.-> {branch.then}")
                
                # Handle the conditional paths in 'ends'
                if branch.ends:
                    for condition, target in branch.ends.items():
                        # Add label to the edge showing the condition
                        label = f"|{condition}|"
                        # Use dashed lines for conditional edges
                        mermaid_code.append(f"    {source} -.{label}.-> {target}")
        
        mermaid_code.append("```")
        return "\n".join(mermaid_code)

    def validate(self) -> "CompiledGraph":
        """Validate the compiled graph.
        
        Returns:
            Self for method chaining
            
        Raises:
            ValueError: If validation fails (e.g., unreachable nodes)
        """
        self.compiled = True
        
        # Check for unreachable nodes
        if len(self.nodes) > 0:
            # Build a graph of all reachable nodes
            visited = set()
            queue = [START]
            
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                    
                visited.add(node)
                
                # Add all nodes reachable from outgoing edges
                if node in self.edges:
                    for dest in self.edges[node]:
                        if dest != END:
                            queue.append(dest)
                
                # Add all nodes reachable from branches
                if node in self.branches:
                    for branch in self.branches[node].values():  # Use values() to iterate over branches
                        if branch.then and branch.then != END:
                            queue.append(branch.then)
                        if branch.ends:
                            for dest in branch.ends.values():
                                if dest != END:
                                    queue.append(dest)
            
            # Check for any nodes that weren't visited
            unreachable = set(self.nodes.keys()) - visited
            if unreachable:
                raise ValueError(f"Unreachable nodes detected: {', '.join(unreachable)}")
        
        return self

    async def execute_node(self, node_name: str, node_input: Any, callback: Callable[[Any], None] | None = None) -> Any:
        """Execute a node with retry logic."""
        if node_name == START or node_name == END:
            return node_input

        node_spec = self.nodes[node_name]
        action = node_spec.action
        attempts = 0

        while True:
            try:
                if asyncio.iscoroutinefunction(action):
                    result = await action(node_input)
                else:
                    result = action(node_input)

                if node_spec.callback:
                    node_spec.callback()

                if callback:
                    callback(result)

                return result
            except Exception as e:
                attempts += 1
                if attempts > node_spec.retry_count:
                    if node_spec.error_handler:
                        logger.error(f"Node {node_name} failed after {attempts} attempts, calling error handler: {e}")
                        return node_spec.error_handler(e)
                    else:
                        logger.error(f"Node {node_name} failed after {attempts} attempts: {e}")
                        raise
                
                wait_time = node_spec.retry_delay
                logger.warning(f"Node {node_name} failed (attempt {attempts}/{node_spec.retry_count}), retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)

    async def execute_async(self, input_data: Any, callback: Callable[[Any], None] | None = None) -> Any:
        """Execute the workflow graph asynchronously."""
        queue = deque()
        visited = set()
        
        logger.debug(f"Starting execution with input: {input_data}")
        queue.append((START, input_data))
        state = input_data

        while queue:
            node_name, node_input = queue.popleft()
            logger.debug(f"Processing node: {node_name} with input: {node_input}")
            
            if node_name == END:
                logger.debug(f"Reached END node, returning state: {state}")
                return state
            
            visit_key = (node_name, str(node_input))
            if visit_key in visited:
                logger.debug(f"Skipping already visited node: {node_name}")
                continue
            visited.add(visit_key)

            result = await self.execute_node(node_name, node_input, callback)
            state = result
            logger.debug(f"Node {node_name} execution result: {state}")

            if node_name in self.branches:
                logger.debug(f"Processing branches for node {node_name}")
                for branch in self.branches[node_name].values():
                    path_value = branch.path(node_input)  # Use node_input to determine path
                    logger.debug(f"Branch path value: {path_value}")
                    if branch.ends and path_value in branch.ends:
                        next_node = branch.ends[path_value]
                        logger.debug(f"Adding next node from branch: {next_node}")
                        queue.append((next_node, node_input))  # Use node_input for next node
                    elif branch.then:
                        logger.debug(f"Adding then node from branch: {branch.then}")
                        queue.append((branch.then, node_input))  # Use node_input for next node
            
            elif node_name in self.edges:
                logger.debug(f"Processing edges for node {node_name}")
                for dest in self.edges[node_name]:
                    logger.debug(f"Adding next node from edge: {dest}")
                    queue.append((dest, result))  # Use result for next node in regular edges

        # If we've exhausted the queue without reaching END, return the final state
        logger.debug(f"No more nodes to process, returning final state: {state}")
        return state

    def execute(self, input_data: Any, callback: Callable[[Any], None] | None = None) -> Any:
        """Execute the workflow graph synchronously."""
        try:
            # Check if we're already in an event loop
            loop = asyncio.get_running_loop()
            # If we are, create a new task in the current loop
            return loop.run_until_complete(self.execute_async(input_data, callback))
        except RuntimeError:
            # If we're not in an event loop, create a new one
            return asyncio.run(self.execute_async(input_data, callback)) 