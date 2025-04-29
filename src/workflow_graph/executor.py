"""Executor for compiled workflow graphs."""

import asyncio
import copy
import inspect
import logging
from collections import defaultdict
from typing import Any, Callable, get_args, get_origin

from .constants import END, START
from .exceptions import ExecutionError, ValidationError
from .models import Branch, Edge, Node, State

logger = logging.getLogger(__name__)


class CompiledGraph:
    """Compiled workflow graph ready for execution.

    This class represents a compiled workflow graph that can be executed
    with a given input to produce an output.
    """

    def __init__(
        self,
        nodes: dict[str, Node],
        edges: dict[str, set[Edge]],
        branches: dict[str, dict[str, Branch]],
    ):
        """Initialize a compiled graph."""
        self.nodes = nodes
        self.edges = defaultdict(list)
        self.edge_callbacks = defaultdict(dict)
        for start, edge_set in edges.items():
            for edge in edge_set:
                self.edges[start].append(edge.target)
                if edge.callback is not None:
                    self.edge_callbacks[start][edge.target] = edge.callback
        self.branches = branches
        self.compiled = False

    def to_mermaid(self) -> str:
        """Generate a Mermaid diagram representation of the workflow graph.

        Returns:
            A string containing the Mermaid diagram code.
        """
        mermaid_code = ["```mermaid", "flowchart TD"]

        # Define node styles
        mermaid_code.append(f'    {START}(["START"])')
        mermaid_code.append(f'    {END}(["END"])')

        # Add custom nodes
        for node_name in self.nodes:
            mermaid_code.append(f'    {node_name}["{node_name}"]')

        if len(self.nodes) > 0:
            mermaid_code.append("")

        # Track edges that are part of conditional branches
        conditional_edges = set()
        for source, branch_dict in self.branches.items():
            for _, branch in branch_dict.items():
                if branch.ends:
                    for target in branch.ends.values():
                        conditional_edges.add((source, target))

        # Add direct edges (only if not part of a conditional branch)
        for start, ends in self.edges.items():
            for end in ends:
                if (start, end) not in conditional_edges:
                    mermaid_code.append(f"    {start} --> {end}")

        # Add conditional edges with dashed lines
        for source, branch_dict in self.branches.items():
            for _, branch in branch_dict.items():
                # Handle the conditional paths in 'ends'
                if branch.ends:
                    for condition, target in branch.ends.items():
                        # Add label to the edge showing the condition
                        label = f"{condition}"
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
                        if branch.ends:
                            for dest in branch.ends.values():
                                if dest != END:
                                    queue.append(dest)

            # Check for any nodes that weren't visited
            unreachable = set(self.nodes.keys()) - visited
            if unreachable:
                raise ValueError(
                    f"Unreachable nodes detected: {', '.join(unreachable)}"
                )

        # Helper functions for type validation
        def get_node_output_type(node_name: str) -> type | None:
            """Get the output type of a node."""
            if node_name == START or node_name == END:
                return Any
            node = self.nodes[node_name]
            # First try to get from output_type hint
            if node.output_type is not None:
                return node.output_type
            # Then try to infer from function return type
            sig = inspect.signature(node.func)
            if sig.return_annotation != inspect.Signature.empty:
                return sig.return_annotation
            return None

        def get_node_input_type(node_name: str) -> type | None:
            """Get the input type of a node."""
            if node_name == START or node_name == END:
                return Any
            node = self.nodes[node_name]
            # First try to get from input_type hint
            if node.input_type is not None:
                return node.input_type
            # Then try to infer from function parameter type
            sig = inspect.signature(node.func)
            if len(sig.parameters) > 0:
                param = next(iter(sig.parameters.values()))
                if param.annotation != inspect.Signature.empty:
                    return param.annotation
            return None

        def check_type_compatibility(source: str, dest: str, context: str = "") -> None:
            """Check if types are compatible between two nodes."""
            # Skip type checks for END nodes only
            if dest == END:
                return

            source_output = get_node_output_type(source)
            dest_input = get_node_input_type(dest)

            if source_output is not None and dest_input is not None:
                # Get the base type (e.g., State[int] -> State)
                source_base = get_origin(source_output) or source_output
                dest_base = get_origin(dest_input) or dest_input

                # If source is Any, it's compatible with any State type
                if source_output == Any:
                    return

                # Check if both are State types
                if not (
                    issubclass(source_base, State) and issubclass(dest_base, State)
                ):
                    raise ValidationError(
                        f"Type mismatch {context}: {source} ({source_base}) -> {dest} ({dest_base})"
                    )

                # Get type parameters
                source_args = get_args(source_output)
                dest_args = get_args(dest_input)

                # If either has no type parameters, they're compatible
                if not source_args or not dest_args:
                    return

                # Check if type parameters are compatible
                if source_args != dest_args:
                    raise ValidationError(
                        f"Type parameter mismatch {context}: {source} ({source_args}) -> {dest} ({dest_args})"
                    )

        # Check each edge for type compatibility
        for source, destinations in self.edges.items():
            for dest in destinations:
                check_type_compatibility(source, dest, "in edge")

        # Check each branch for type compatibility
        for source, branches in self.branches.items():
            for branch_name, branch in branches.items():
                if branch.ends:
                    for condition_value, dest in branch.ends.items():
                        check_type_compatibility(
                            source,
                            dest,
                            f"in branch '{branch_name}' (condition={condition_value})",
                        )

        return self

    async def _invoke_callbacks(
        self,
        node: Node,
        node_name: str,
        result: State,
        callback: Callable[[str, State], None] | None = None,
    ) -> None:
        """Invoke both node-specific and global callbacks with the given result.

        Args:
            node: The node that produced the result
            node_name: Name of the node
            result: The state to pass to callbacks
            callback: Optional global callback function
        """
        # Node-level callback
        if node.callback:
            if asyncio.iscoroutinefunction(node.callback):
                await node.callback(result)
            else:
                node.callback(result)

        # Global callback
        if callback:
            if asyncio.iscoroutinefunction(callback):
                await callback(node_name, result)
            else:
                callback(node_name, result)

    async def execute_node(
        self,
        node_name: str,
        input_data: Any,
        callback: Callable[[str, Any], None] | None = None,
    ) -> Any:
        """Execute a single node in the workflow graph."""
        if node_name not in self.nodes:
            raise ValueError(f"Node {node_name} not found in graph")

        node = self.nodes[node_name]
        logger.debug(f"Executing node {node_name} with input: {input_data}")

        try:
            # Extract the value from the state if it's a State object
            if not isinstance(input_data, State):
                raise ValueError("Node input must be a State object")

            # Create a defensive copy of the state
            state_copy = copy.deepcopy(input_data)

            # Execute the node's function with retry logic
            retries = node.retries
            attempt = 0
            while True:
                try:
                    func_kwargs = {}
                    if node.stream_callback is not None:
                        func_kwargs["stream_callback"] = node.stream_callback

                    if asyncio.iscoroutinefunction(node.func):
                        result = await node.func(state_copy, **func_kwargs)
                    else:
                        result = node.func(state_copy, **func_kwargs)
                    break
                except Exception:
                    attempt += 1
                    if attempt <= retries:
                        delay = node.retry_delay * (
                            node.backoff_factor ** (attempt - 1)
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise

            # If the function didn't return a new state, use the copied state
            if not isinstance(result, State):
                result = state_copy

            # Call callbacks with the result
            await self._invoke_callbacks(node, node_name, result, callback)

            return result

        except Exception as e:
            logger.error(f"Error in node {node_name}: {str(e)}")
            if node.on_error:
                try:
                    if asyncio.iscoroutinefunction(node.on_error):
                        result = await node.on_error(e, state_copy)
                    else:
                        result = node.on_error(e, state_copy)

                    # If error handler didn't return a state, use the copied state
                    if not isinstance(result, State):
                        result = state_copy

                    # Call callbacks with the error handler result
                    await self._invoke_callbacks(node, node_name, result, callback)

                    return result
                except Exception as handler_error:
                    logger.error(
                        f"Error handler for node {node_name} failed: {str(handler_error)}"
                    )
                    raise ExecutionError(f"Error handler failed: {str(handler_error)}")
            raise ExecutionError(f"Node {node_name} failed: {str(e)}")

    def _validate_condition_result(self, result: Any, condition_name: str) -> None:
        """Validate that a condition result is valid for branching.

        Args:
            result: The result to validate
            condition_name: Name of the condition function for error messages

        Raises:
            ValidationError: If the result is not valid for branching
        """
        if isinstance(result, State):
            raise ValidationError(
                f"Condition function '{condition_name}' must return a hashable value "
                f"(bool, str, int, float, tuple, or frozenset), not a State object"
            )

        # Check if the result is hashable
        try:
            hash(result)
        except TypeError:
            raise ValidationError(
                f"Condition function '{condition_name}' must return a hashable value "
                f"(bool, str, int, float, tuple, or frozenset), not {type(result)}"
            )

    async def execute_async(
        self, input_data: Any, callback: Callable[[str, Any], None] | None = None
    ) -> State:
        """Execute the workflow graph asynchronously."""
        # Initialize state
        if isinstance(input_data, State):
            state = input_data
        else:
            state = State(value=input_data)

        # Create execution queue
        queue = asyncio.Queue()
        await queue.put(START)

        while not queue.empty():
            current_node = await queue.get()
            if current_node == END:
                break

            # Special handling for START node
            if current_node == START:
                # Add all direct edge destinations from START
                for next_node in self.edges[START]:
                    await queue.put(next_node)
                # Add all conditional branch destinations from START
                if START in self.branches:
                    for branch in self.branches[START].values():
                        if branch.ends:
                            for dest in branch.ends.values():
                                await queue.put(dest)
                continue

            if current_node not in self.nodes:
                raise ValueError(f"Node {current_node} not found in graph")

            try:
                result = await self.execute_node(current_node, state, callback)
                state = result
                state.trajectory.append(current_node)

                # Handle branches first
                branch_taken = False
                if current_node in self.branches:
                    for branch_name, branch in self.branches[current_node].items():
                        # Create a defensive copy for the condition
                        condition_state = copy.deepcopy(state)

                        # Evaluate condition
                        if asyncio.iscoroutinefunction(branch.condition):
                            condition_result = await branch.condition(condition_state)
                        else:
                            condition_result = branch.condition(condition_state)

                        # Validate condition result
                        self._validate_condition_result(condition_result, branch_name)

                        # Find matching end node
                        target = branch.ends.get(condition_result)
                        if target is None:
                            # Try string representation
                            target = branch.ends.get(str(condition_result))

                        if target is not None:
                            # Call branch callback if defined
                            if branch.callback is not None:
                                if asyncio.iscoroutinefunction(branch.callback):
                                    await branch.callback(current_node, target, state)
                                else:
                                    branch.callback(current_node, target, state)

                            # Queue next node
                            await queue.put(target)
                            branch_taken = True
                            break
                        else:
                            raise ValueError(
                                f"No matching end node for condition result: {condition_result}"
                            )

                # If no branch was taken, handle normal edges
                if not branch_taken and current_node in self.edges:
                    for next_node in self.edges[current_node]:
                        await queue.put(next_node)

            except Exception as e:
                logger.exception(f"Error during execution at node {current_node}: {e}")
                state.add_error(e, current_node)
                if (
                    current_node in self.nodes
                    and self.nodes[current_node].on_error is not None
                ):
                    if asyncio.iscoroutinefunction(self.nodes[current_node].on_error):
                        await self.nodes[current_node].on_error(e, state)
                    else:
                        self.nodes[current_node].on_error(e, state)
                # Always raise the error after logging and error handling
                raise ExecutionError(f"Node {current_node} failed: {str(e)}")

        return state

    def execute(
        self, input_data: Any, callback: Callable[[Any], None] | None = None
    ) -> State:
        """Execute the workflow graph synchronously."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self.execute_async(input_data, callback)
                )
                return result
            finally:
                loop.close()
                asyncio.set_event_loop(None)
        except Exception as e:
            # If it's already an ExecutionError, re-raise it
            if isinstance(e, ExecutionError):
                raise
            # Otherwise, wrap it in an ExecutionError
            raise ExecutionError(f"Graph execution failed: {str(e)}")

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

                if node.on_error:
                    try:
                        if asyncio.iscoroutinefunction(node.on_error):
                            result = await node.on_error(e, data)
                        else:
                            result = node.on_error(e, data)
                        # If error handler returns None, stop execution
                        if result is None:
                            return None
                        return result
                    except Exception as handler_error:
                        logger.exception(
                            f"Error handler for node {node_name} failed: {str(handler_error)}"
                        )
                        raise ExecutionError(
                            f"Error handler failed: {str(handler_error)}"
                        )
                logger.exception(f"Node {node_name} failed: {str(e)}")
                raise ExecutionError(f"Node {node_name} failed: {str(e)}")
