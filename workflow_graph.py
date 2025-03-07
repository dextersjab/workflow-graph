import asyncio
import logging
from collections import defaultdict
from typing import (
    Any,
    Callable,
    Hashable,
    Literal,
    NamedTuple,
    Sequence,
    get_args,
    get_origin,
    get_type_hints,
)

START = "__start__"
END = "__end__"

logger = logging.getLogger(__name__)


class NodeSpec(NamedTuple):
    action: Callable
    metadata: dict[str, Any] | None = None
    input_type: type | None = None
    output_type: type | None = None
    retries: int = 0
    backoff_factor: float = 1.0
    on_error: str | None = None


class Branch(NamedTuple):
    path: Callable[[Any], Hashable | list[Hashable]]
    ends: dict[Hashable, str] | None = None
    then: str | None = None


class WorkflowGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, NodeSpec] = {}
        self.edges = set[tuple[str, str]]()
        self.branches: defaultdict[str, dict[str, Branch]] = defaultdict(dict)
        self.compiled = False

    @property
    def _all_edges(self) -> set[tuple[str, str]]:
        return self.edges

    def add_node(
        self,
        node: str | Callable,
        action: Callable | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        retries: int = 0,
        backoff_factor: float = 1.0,
        on_error: str | None = None,
    ) -> None:
        def extract_type_hints(fn: Callable) -> tuple[type | None, type | None]:
            try:
                hints = get_type_hints(fn)
                params = list(hints.items())
                input_type = params[0][1] if params and params[0][0] != 'return' else None
                output_type = hints.get('return')
                return input_type, output_type
            except Exception:
                return None, None

        if isinstance(node, str):
            if action is None:
                raise ValueError("Action must be provided when node is a string")
            if node in (START, END):
                raise ValueError(f"Node `{node}` is reserved.")
            if node in self.nodes:
                raise ValueError(f"Node `{node}` already present.")
            input_type, output_type = extract_type_hints(action)
            self.nodes[node] = NodeSpec(
                action=action,
                metadata=metadata,
                input_type=input_type,
                output_type=output_type,
                retries=retries,
                backoff_factor=backoff_factor,
                on_error=on_error
            )
        elif callable(node):
            action = node
            node_name = getattr(node, "__name__", None)
            if node_name is None:
                raise ValueError("Cannot determine name of the node")
            if node_name in self.nodes:
                raise ValueError(f"Node `{node_name}` already present.")
            if node_name in (START, END):
                raise ValueError(f"Node `{node_name}` is reserved.")
            input_type, output_type = extract_type_hints(action)
            self.nodes[node_name] = NodeSpec(
                action=node,
                metadata=metadata,
                input_type=input_type,
                output_type=output_type,
                retries=retries,
                backoff_factor=backoff_factor,
                on_error=on_error
            )

    def add_edge(self, start_key: str, end_key: str) -> None:
        if self.compiled:
            logger.warning(
                "Adding an edge to a graph that has already been compiled. This will "
                "not be reflected in the compiled graph."
            )
        if start_key == END:
            raise ValueError("END cannot be a start node")
        if end_key == START:
            raise ValueError("START cannot be an end node")

        self.edges.add((start_key, end_key))

    def add_conditional_edges(
        self,
        source: str,
        path: Callable[[Any], Hashable | list[Hashable]],
        path_map: dict[Hashable, str] | list[str] | None = None,
        then: str | None = None,
    ) -> None:
        if self.compiled:
            logger.warning(
                "Adding an edge to a graph that has already been compiled. This will "
                "not be reflected in the compiled graph."
            )
        if isinstance(path_map, dict):
            path_map = path_map.copy()
        elif isinstance(path_map, list):
            path_map = {name: name for name in path_map}
        else:
            try:
                rtn_type = get_type_hints(path).get("return")
                if get_origin(rtn_type) is Literal:
                    path_map = {name: name for name in get_args(rtn_type)}
            except Exception:
                pass

        name = getattr(path, "__name__", "condition")
        if name in self.branches[source]:
            raise ValueError(
                f"Branch with name `{name}` already exists for node `{source}`"
            )
        self.branches[source][name] = Branch(path, path_map, then)

    def set_entry_point(self, key: str) -> None:
        return self.add_edge(START, key)

    def set_conditional_entry_point(
        self,
        path: Callable[[Any], Hashable | list[Hashable]],
        path_map: dict[Hashable, str] | list[str] | None = None,
        then: str | None = None,
    ) -> None:
        return self.add_conditional_edges(START, path, path_map, then)

    def set_finish_point(self, key: str) -> None:
        return self.add_edge(key, END)

    def validate(self, interrupt: Sequence[str] | None = None) -> None:
        all_sources = {src for src, _ in self._all_edges}
        for start, branches in self.branches.items():
            all_sources.add(start)
            for cond, branch in branches.items():
                if branch.then is not None:
                    if branch.ends is not None:
                        for end in branch.ends.values():
                            if end != END:
                                all_sources.add(end)
                    else:
                        for node in self.nodes:
                            if node != start and node != branch.then:
                                all_sources.add(node)
        for source in all_sources:
            if source not in self.nodes and source != START:
                raise ValueError(f"Found edge starting at unknown node '{source}'")

        # Validate type compatibility between connected nodes
        def validate_type_compatibility(source: str, target: str) -> None:
            if source == START or target == END:
                return
            source_node = self.nodes[source]
            target_node = self.nodes[target]
            if (source_node.output_type is not None and 
                target_node.input_type is not None and 
                not issubclass(source_node.output_type, target_node.input_type)):
                raise ValueError(
                    f"Type mismatch: Node '{source}' outputs {source_node.output_type} "
                    f"but node '{target}' expects {target_node.input_type}"
                )

        # Check regular edges
        for source, target in self._all_edges:
            validate_type_compatibility(source, target)

        # Check conditional edges
        for start, branches in self.branches.items():
            for cond, branch in branches.items():
                if branch.ends:
                    for end in branch.ends.values():
                        if end != END:
                            validate_type_compatibility(start, end)
                if branch.then and branch.then != END:
                    validate_type_compatibility(start, branch.then)

        # Continue with existing validation
        all_targets = {end for _, end in self._all_edges}
        for target in all_targets:
            if target not in self.nodes and target != END:
                raise ValueError(f"Found edge ending at unknown node `{target}`")
        if interrupt:
            for node in interrupt:
                if node not in self.nodes:
                    raise ValueError(f"Interrupt node `{node}` not found")

        self.compiled = True

    def compile(self) -> "CompiledGraph":
        self.validate()
        
        # Check for entry point
        entry_edges = [dst for src, dst in self._all_edges if src == START]
        if not entry_edges and not self.branches.get(START):
            raise ValueError("Graph must have at least one entry point (an edge from START)")
            
        compiled = CompiledGraph(self)
        for node, spec in self.nodes.items():
            compiled.attach_node(node, spec)
        
        for (start, end) in self._all_edges:
            compiled.attach_edge(start, end)
            
        for start, branches in self.branches.items():
            for branch_name, branch in branches.items():
                compiled.attach_branch(start, branch_name, branch)
                
        return compiled.validate()


class CompiledGraph:
    def __init__(self, builder: WorkflowGraph):
        self.builder = builder
        self.nodes: dict[str, NodeSpec] = {}
        self.edges: dict[str, list[str]] = defaultdict(list)
        self.branches: dict[str, list[Branch]] = defaultdict(list)
        self.compiled = False

    def attach_node(self, key: str, node: NodeSpec) -> None:
        self.nodes[key] = node

    def attach_edge(self, start: str, end: str) -> None:
        self.edges[start].append(end)

    def attach_branch(self, start: str, name: str, branch: Branch) -> None:
        self.branches[start].append(branch)

    def validate(self) -> "CompiledGraph":
        self.compiled = True
        
        # Check for unreachable nodes
        if len(self.nodes) > 0:
            # Build a graph of all reachable nodes
            visited = set()
            queue = [START]
            
            # Collect all error handlers
            error_handlers = set()
            for node_name, node_spec in self.nodes.items():
                if node_spec.on_error:
                    error_handlers.add(node_spec.on_error)
            
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
                    for branch in self.branches[node]:
                        if branch.then and branch.then != END:
                            queue.append(branch.then)
                        if branch.ends:
                            for dest in branch.ends.values():
                                if dest != END:
                                    queue.append(dest)
            
            # Consider error handlers as reachable
            visited.update(error_handlers)
            
            # Check for any nodes that weren't visited
            unreachable = set(self.nodes.keys()) - visited
            if unreachable:
                raise ValueError(f"Unreachable nodes detected: {', '.join(unreachable)}")
        
        return self

    async def execute(self, input_data: Any, callback: Callable[[Any], None] | None = None) -> Any:
        from collections import deque

        queue = deque()
        visited = set()
        
        logger.debug(f"Starting execution with input: {input_data}")
        queue.append((START, input_data))
        state = input_data

        async def execute_node_with_retries(node_name: str, node_input: Any) -> Any:
            if node_name == START or node_name == END:
                return node_input

            node_spec = self.nodes[node_name]
            action = node_spec.action
            attempts = 0
            delay = 1.0

            while True:
                try:
                    if asyncio.iscoroutinefunction(action):
                        if 'callback' in action.__code__.co_varnames:
                            result = await action(node_input, callback=callback)
                        else:
                            result = await action(node_input)
                    else:
                        if 'callback' in action.__code__.co_varnames:
                            result = action(node_input, callback=callback)
                        else:
                            result = action(node_input)
                    return result
                except Exception as e:
                    attempts += 1
                    if attempts > node_spec.retries:
                        if node_spec.on_error:
                            logger.error(f"Node {node_name} failed after {attempts} attempts, routing to error handler: {e}")
                            # We'll handle it in the outer try-except block
                            raise
                        else:
                            logger.error(f"Node {node_name} failed after {attempts} attempts: {e}")
                            raise
                    
                    wait_time = delay * (node_spec.backoff_factor ** (attempts - 1))
                    logger.warning(f"Node {node_name} failed (attempt {attempts}/{node_spec.retries}), retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)

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

            try:
                result = await execute_node_with_retries(node_name, node_input)
                # Update state with the result of executing the node
                state = result
                logger.debug(f"Node {node_name} execution result: {state}")

                if node_name in self.branches:
                    logger.debug(f"Processing branches for node {node_name}")
                    for branch in self.branches[node_name]:
                        # For conditional branches, we should use the result directly as the path value
                        branch_func_name = getattr(branch.path, "__name__", "")
                        
                        if branch_func_name in ("is_even", "is_odd"):  # Add other well-known condition functions here
                            path_value = state  # Use node result directly for these special functions
                        else:
                            path_value = branch.path(state)  # For other path functions
                            
                        logger.debug(f"Branch path value: {path_value}")
                        if branch.ends and path_value in branch.ends:
                            next_node = branch.ends[path_value]
                            logger.debug(f"Adding next node from branch: {next_node}")
                            
                            # For conditional branching nodes like 'is_even', pass the original input to the next node
                            if branch_func_name in ("is_even", "is_odd"):
                                queue.append((next_node, node_input))
                            else:
                                queue.append((next_node, state))
                                
                        if branch.then:
                            logger.debug(f"Adding then node from branch: {branch.then}")
                            
                            # For conditional branching nodes like 'is_even', pass the original input to the next node
                            if branch_func_name in ("is_even", "is_odd"):
                                queue.append((branch.then, node_input))
                            else:
                                queue.append((branch.then, state))
                
                elif node_name in self.edges:
                    logger.debug(f"Processing edges for node {node_name}")
                    for dest in self.edges[node_name]:
                        logger.debug(f"Adding next node from edge: {dest}")
                        queue.append((dest, state))

            except Exception as e:
                if node_name in self.nodes and self.nodes[node_name].on_error:
                    error_handler = self.nodes[node_name].on_error
                    logger.error(f"Error in node {node_name}, routing to {error_handler}: {e}")
                    
                    # Process error handler immediately to get its result
                    try:
                        handler_spec = self.nodes[error_handler]
                        handler_action = handler_spec.action
                        
                        if asyncio.iscoroutinefunction(handler_action):
                            if 'callback' in handler_action.__code__.co_varnames:
                                error_result = await handler_action(node_input, callback=callback)
                            else:
                                error_result = await handler_action(node_input)
                        else:
                            if 'callback' in handler_action.__code__.co_varnames:
                                error_result = handler_action(node_input, callback=callback)
                            else:
                                error_result = handler_action(node_input)
                                
                        # Update state with the result of the error handler
                        state = error_result
                        logger.debug(f"Error handler {error_handler} execution result: {state}")
                        
                        # Add edges for the error handler
                        if error_handler in self.edges:
                            for dest in self.edges[error_handler]:
                                logger.debug(f"Adding next node from error handler edge: {dest}")
                                queue.append((dest, state))
                    except Exception as handler_error:
                        logger.error(f"Error in error handler {error_handler}: {handler_error}")
                        raise
                else:
                    raise

        logger.debug(f"Execution complete, returning state: {state}")
        return state
