"""Executor for compiled workflow graphs."""

import asyncio
import logging
from collections import defaultdict, deque
from typing import Any, Callable, Hashable
import inspect

from .constants import START, END
from .models import Branch, Node, State
from .exceptions import ExecutionError, ValidationError

logger = logging.getLogger(__name__)


class CompiledGraph:
    """Compiled workflow graph ready for execution.
    
    This class represents a compiled workflow graph that can be executed
    with a given input to produce an output.
    """
    
    def __init__(self, nodes: dict[str, Node], edges: set[tuple[str, str]], branches: dict[str, dict[str, Branch]]):
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
            for _, branch in branch_dict.items():
                # Handle the 'then' case
                if branch.then:
                    # Use dashed lines for conditional edges
                    mermaid_code.append(f"    {source} -.-> {branch.then}")
                
                # Handle the conditional paths in 'ends'
                if branch.ends:
                    for condition, target in branch.ends.items():
                        # Add label to the edge showing the condition
                        label = f"{condition}"
                        # Use dashed lines for conditional edges
                        mermaid_code.append(f"    {source} -.{condition}.-> {target}")
        
        mermaid_code.append("```")
        return "\n".join(mermaid_code)

    def validate(self) -> "CompiledGraph":
        """Validate the compiled graph.
        
        Returns:
            Self for method chaining
            
        Raises:
            ValueError: If validation fails (e.g., unreachable nodes)
            ValidationError: If type validation fails
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
                    for branch in self.branches[node].values():
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
        
        # Validate type consistency
        def get_node_type(node_name: str) -> type:
            if node_name == START or node_name == END:
                return Any
            return self.nodes[node_name].output_type
        
        # Check each edge for type compatibility
        for source, destinations in self.edges.items():
            source_type = get_node_type(source)
            for dest in destinations:
                dest_type = get_node_type(dest)
                if source_type != Any and dest_type != Any and source_type != dest_type:
                    raise ValidationError(f"Type mismatch between nodes: {source} ({source_type}) -> {dest} ({dest_type})")
        
        # Check each branch for type compatibility
        for source, branches in self.branches.items():
            source_type = get_node_type(source)
            for branch_name, branch in branches.items():
                # Check condition return type
                if branch.condition and not isinstance(branch.condition, bool):
                    # TODO: Add proper type checking for condition functions
                    pass
                
                # Check destination types
                if branch.then:
                    then_type = get_node_type(branch.then)
                    if source_type != Any and then_type != Any and source_type != then_type:
                        raise ValidationError(f"Type mismatch in branch {branch_name}: {source} ({source_type}) -> then: {branch.then} ({then_type})")
                
                if branch.else_:
                    else_type = get_node_type(branch.else_)
                    if source_type != Any and else_type != Any and source_type != else_type:
                        raise ValidationError(f"Type mismatch in branch {branch_name}: {source} ({source_type}) -> else: {branch.else_} ({else_type})")
                
                if branch.ends:
                    for condition_value, dest in branch.ends.items():
                        dest_type = get_node_type(dest)
                        if source_type != Any and dest_type != Any and source_type != dest_type:
                            raise ValidationError(f"Type mismatch in branch {branch_name}: {source} ({source_type}) -> {dest} ({dest_type})")
        
        return self

    async def execute_node(self, node_name: str, input_data: Any, callback: Callable[[Any], None] | None = None) -> Any:
        """Execute a single node in the workflow graph."""
        if node_name not in self.nodes:
            raise ValueError(f"Node {node_name} not found in graph")
        
        node = self.nodes[node_name]
        logger.debug(f"Executing node {node_name} with input: {input_data}")
        
        try:
            # Extract the value from the state if it's a State object
            if not isinstance(input_data, State):
                raise ValueError("Node input must be a State object")
            # Execute the node's function
            if asyncio.iscoroutinefunction(node.func):
                result = await node.func(input_data)
            else:
                result = node.func(input_data)
            
            # Call the node's callback if it exists
            if node.callback:
                if asyncio.iscoroutinefunction(node.callback):
                    await node.callback(result)
                else:
                    node.callback(result)
            
            # Call the global callback if it exists
            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback(result)
                else:
                    callback(result)
            
            # Return a new state with the result
            return State(
                value=result,
                processed_by=input_data.processed_by.copy(),
                branch_taken=input_data.branch_taken
            )
            
        except Exception as e:
            logger.error(f"Error in node {node_name}: {e}")
            if node.error_handler:
                if asyncio.iscoroutinefunction(node.error_handler):
                    return await node.error_handler(e, input_data)
                else:
                    return node.error_handler(e, input_data)
            raise

    async def execute_async(self, input_data: Any, callback: Callable[[Any], None] | None = None) -> Any:
        """Execute the workflow graph asynchronously."""
        queue = deque()
        visited = set()
        
        logger.debug(f"Starting execution with input: {input_data}")
        
        # Validate input state
        if not isinstance(input_data, State):
            raise ValueError("Input must be a State object")
        if not hasattr(input_data, 'processed_by'):
            raise ValueError("State object must have 'processed_by' attribute")
        if not hasattr(input_data, 'branch_taken'):
            raise ValueError("State object must have 'branch_taken' attribute")

        queue.append((START, input_data))
        
        while queue:
            current_node, node_input = queue.popleft()
            logger.debug(f"Processing node: {current_node} with input: {node_input}")
            
            if current_node == END:
                logger.debug(f"Reached END node, returning state: {node_input}")
                return node_input.value
            
            visit_key = (current_node, str(node_input))
            if visit_key in visited:
                logger.debug(f"Skipping already visited node: {current_node}")
                continue
            visited.add(visit_key)

            try:
                # Handle START node - just enqueue its outgoing edges
                if current_node == START:
                    # Add all direct edge destinations from START
                    for next_node in self.edges[START]:
                        queue.append((next_node, node_input))
                    # Add all conditional branch destinations from START
                    if START in self.branches:
                        for branch_name, branch in self.branches[START].items():
                            if branch.ends:
                                for dest in branch.ends.values():
                                    queue.append((dest, node_input))
                    continue

                # Execute the node and get the result
                result = await self.execute_node(current_node, node_input, callback)
                if result is None:
                    return None
                
                # Validate result state
                if not isinstance(result, State):
                    raise ValueError("Node must return a State object")
                
                # Update processed nodes
                result.processed_by.append(current_node)
                
                # Check for branches first
                if current_node in self.branches:
                    branch_taken = False
                    for branch_name, branch in self.branches[current_node].items():
                        # Evaluate the condition with the state value
                        if asyncio.iscoroutinefunction(branch.condition):
                            condition_result = await branch.condition(result.value)
                        else:
                            condition_result = branch.condition(result.value)
                        
                        # Update branch taken in state
                        if condition_result:
                            result.branch_taken = branch_name
                            branch_taken = True
                            
                            # Determine next node based on condition
                            next_node = None
                            if branch.ends:
                                if condition_result in branch.ends:
                                    next_node = branch.ends[condition_result]
                                elif str(condition_result) in branch.ends:
                                    next_node = branch.ends[str(condition_result)]
                            
                            if next_node:
                                queue.append((next_node, result))
                    
                    # Fail fast if no branch condition matches
                    if not branch_taken:
                        raise ValueError(f"No branch condition matched for node {current_node}")
                else:
                    # Add all direct edge destinations to the queue
                    for next_node in self.edges[current_node]:
                        queue.append((next_node, result))
                
            except Exception as e:
                logger.error(f"Error executing node {current_node}: {e}")
                raise
        
        return node_input.value

    def execute(self, input_data: Any, callback: Callable[[Any], None] | None = None) -> Any:
        """Execute the workflow graph synchronously."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as e:
            # Check if the RuntimeError is specifically "no running event loop"
            if "no running event loop" in str(e).lower():
                # This is expected if called from a sync context without a loop.
                logger.debug("No running event loop found, creating new one with asyncio.run().")
                return asyncio.run(self.execute_async(input_data, callback))
            else:
                # Unexpected error during loop detection
                logger.error(f"Unexpected RuntimeError during event loop detection: {e}")
                raise e
        else:
            # A loop was found. Check if it's running.
            if loop.is_running():
                # Cannot block in a running loop using the synchronous execute method.
                raise RuntimeError(
                    "Synchronous execute() called from within an existing running event loop. "
                    "Use execute_async() instead or run execute() from a synchronous context."
                )
            else:
                # Loop exists but is not running. Use run_until_complete.
                logger.debug("Existing event loop found but not running, using loop.run_until_complete().")
                return loop.run_until_complete(self.execute_async(input_data, callback)) 

    async def _execute_node(self, node_name: str, data: Any) -> Any:
        """Execute a single node in the graph."""
        node = self.nodes[node_name]
        retries = node.retries
        attempt = 0

        while True:
            try:
                if asyncio.iscoroutinefunction(node.func):
                    result = await node.func(data)
                else:
                    result = node.func(data)
                return result
            except Exception as e:
                attempt += 1
                if attempt <= retries:
                    delay = node.retry_delay * (node.backoff_factor ** (attempt - 1))
                    await asyncio.sleep(delay)
                    continue
                
                if node.error_handler:
                    try:
                        if asyncio.iscoroutinefunction(node.error_handler):
                            result = await node.error_handler(e, data)
                        else:
                            result = node.error_handler(e, data)
                        # If error handler returns None, stop execution
                        if result is None:
                            return None
                        return result
                    except Exception as handler_error:
                        logger.error(f"Error handler for node {node_name} failed: {str(handler_error)}")
                        raise ExecutionError(f"Error handler failed: {str(handler_error)}")
                raise ExecutionError(f"Node {node_name} failed: {str(e)}") 