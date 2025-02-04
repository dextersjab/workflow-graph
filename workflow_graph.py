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
    ) -> None:
        if isinstance(node, str):
            if action is None:
                raise ValueError("Action must be provided when node is a string")
            if node in (START, END):
                raise ValueError(f"Node `{node}` is reserved.")
            if node in self.nodes:
                raise ValueError(f"Node `{node}` already present.")
            self.nodes[node] = NodeSpec(action=action, metadata=metadata)
        elif callable(node):
            action = node
            node_name = getattr(node, "__name__", None)
            if node_name is None:
                raise ValueError("Cannot determine name of the node")
            if node_name in self.nodes:
                raise ValueError(f"Node `{node_name}` already present.")
            if node_name in (START, END):
                raise ValueError(f"Node `{node_name}` is reserved.")
            self.nodes[node_name] = NodeSpec(action=node, metadata=metadata)

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

        all_targets = {end for _, end in self._all_edges}
        for start, branches in self.branches.items():
            for cond, branch in branches.items():
                if branch.then is not None:
                    all_targets.add(branch.then)
                if branch.ends is not None:
                    for end in branch.ends.values():
                        if end not in self.nodes and end != END:
                            raise ValueError(
                                f"At '{start}' node, '{cond}' branch found unknown target '{end}'"
                            )
                        all_targets.add(end)
                else:
                    all_targets.add(END)
                    for node in self.nodes:
                        if node != start and node != branch.then:
                            all_targets.add(node)
        for node in self.nodes:
            if node not in all_targets:
                raise ValueError(f"Node `{node}` is not reachable")
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
        compiled = CompiledGraph(builder=self)
        for key, node in self.nodes.items():
            compiled.attach_node(key, node)
        for start, end in self.edges:
            compiled.attach_edge(start, end)
        for start, branches in self.branches.items():
            for name, branch in branches.items():
                compiled.attach_branch(start, name, branch)
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
        return self

    async def execute(self, input_data: Any, callback: Callable[[Any], None] | None = None) -> Any:
        from collections import deque

        queue = deque()
        visited = set()
        
        logger.debug(f"Starting execution with input: {input_data}")
        # Start with the initial input
        queue.append((START, input_data))
        state = input_data

        while queue:
            node_name, node_input = queue.popleft()
            logger.debug(f"Processing node: {node_name} with input: {node_input}")
            
            if node_name == END:
                logger.debug(f"Reached END node, returning state: {state}")
                return state
            
            # Skip if we've seen this exact node+state combination before
            visit_key = (node_name, str(node_input))
            if visit_key in visited:
                logger.debug(f"Skipping already visited node: {node_name}")
                continue
            visited.add(visit_key)

            # Handle regular nodes
            if node_name in self.nodes:
                node_spec = self.nodes[node_name]
                action = node_spec.action
                logger.debug(f"Executing action for node {node_name}: {action.__name__}")

                try:
                    if asyncio.iscoroutinefunction(action):
                        if 'callback' in action.__code__.co_varnames:
                            state = await action(node_input, callback=callback)
                        else:
                            state = await action(node_input)
                    else:
                        if 'callback' in action.__code__.co_varnames:
                            state = action(node_input, callback=callback)
                        else:
                            state = action(node_input)
                    logger.debug(f"Node {node_name} execution result: {state}")
                except Exception as e:
                    logger.error(f"Error executing node {node_name}: {e}")
                    raise

                # Handle conditional branches
                if node_name in self.branches:
                    logger.debug(f"Processing branches for node {node_name}")
                    for branch in self.branches[node_name]:
                        # Execute the path function to get the transformed value for branching
                        path_value = branch.path(state)
                        logger.debug(f"Branch path value: {path_value}")
                        if branch.ends and path_value in branch.ends:
                            next_node = branch.ends[path_value]
                            logger.debug(f"Adding next node from branch: {next_node}")
                            queue.append((next_node, state))
                        if branch.then:
                            logger.debug(f"Adding then node from branch: {branch.then}")
                            queue.append((branch.then, state))
                
                # Handle regular edges
                elif node_name in self.edges:
                    logger.debug(f"Processing edges for node {node_name}")
                    for dest in self.edges[node_name]:
                        logger.debug(f"Adding next node from edge: {dest}")
                        queue.append((dest, state))

            # Handle START node
            elif node_name == START:
                logger.debug("Processing START node")
                if node_name in self.branches:
                    for branch in self.branches[node_name]:
                        path_value = branch.path(node_input)
                        logger.debug(f"START branch path value: {path_value}")
                        if branch.ends and path_value in branch.ends:
                            next_node = branch.ends[path_value]
                            logger.debug(f"Adding next node from START branch: {next_node}")
                            queue.append((next_node, node_input))
                        if branch.then:
                            logger.debug(f"Adding then node from START branch: {branch.then}")
                            queue.append((branch.then, node_input))
                elif node_name in self.edges:
                    for dest in self.edges[node_name]:
                        logger.debug(f"Adding next node from START edge: {dest}")
                        queue.append((dest, node_input))

        logger.debug(f"Execution complete, returning state: {state}")
        return state
