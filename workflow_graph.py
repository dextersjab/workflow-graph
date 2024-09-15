import asyncio
import logging
from collections import defaultdict
from typing import (
    Any,
    Callable,
    Hashable,
    Literal,
    NamedTuple,
    Optional,
    Sequence,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

START = "__start__"
END = "__end__"

logger = logging.getLogger(__name__)


class NodeSpec(NamedTuple):
    action: Callable
    metadata: Optional[dict[str, Any]] = None


class Branch(NamedTuple):
    path: Callable[[Any], Union[Hashable, list[Hashable]]]
    ends: Optional[dict[Hashable, str]] = None
    then: Optional[str] = None


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
        node: Union[str, Callable],
        action: Optional[Callable] = None,
        *,
        metadata: Optional[dict[str, Any]] = None,
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
        else:
            raise ValueError("Invalid arguments for add_node")

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
        path: Callable[[Any], Union[Hashable, list[Hashable]]],
        path_map: Optional[Union[dict[Hashable, str], list[str]]] = None,
        then: Optional[str] = None,
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
        path: Callable[[Any], Union[Hashable, list[Hashable]]],
        path_map: Optional[Union[dict[Hashable, str], list[str]]] = None,
        then: Optional[str] = None,
    ) -> None:
        return self.add_conditional_edges(START, path, path_map, then)

    def set_finish_point(self, key: str) -> None:
        return self.add_edge(key, END)

    def validate(self, interrupt: Optional[Sequence[str]] = None) -> None:
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

    async def execute(
        self, input_data: Any, callback: Optional[Callable[[Any], None]] = None
    ) -> Any:
        from collections import deque

        queue = deque()
        visited = set()

        queue.append((START, input_data))

        while queue:
            node_name, data = queue.popleft()
            if node_name == END:
                return data
            if node_name in visited:
                continue
            visited.add(node_name)

            if node_name in self.nodes:
                node_spec = self.nodes[node_name]
                action = node_spec.action
                if asyncio.iscoroutinefunction(action):
                    result = await action(data, callback=callback)
                else:
                    result = action(data, callback=callback)
                if node_name in self.branches:
                    for branch in self.branches[node_name]:
                        path_result = branch.path(result)
                        destinations = (
                            path_result if isinstance(path_result, list) else [path_result]
                        )
                        if branch.ends:
                            destinations = [
                                branch.ends.get(dest, dest) for dest in destinations
                            ]
                        if branch.then:
                            for dest in destinations:
                                if dest == END:
                                    queue.append((END, result))
                                else:
                                    queue.append((dest, result))
                            queue.append((branch.then, result))
                        else:
                            for dest in destinations:
                                if dest == END:
                                    queue.append((END, result))
                                else:
                                    queue.append((dest, result))
                elif node_name in self.edges:
                    for dest in self.edges[node_name]:
                        queue.append((dest, result))
                else:
                    return result
            elif node_name == START:
                if node_name in self.branches:
                    for branch in self.branches[node_name]:
                        path_result = branch.path(data)
                        destinations = (
                            path_result if isinstance(path_result, list) else [path_result]
                        )
                        if branch.ends:
                            destinations = [
                                branch.ends.get(dest, dest) for dest in destinations
                            ]
                        if branch.then:
                            for dest in destinations:
                                if dest == END:
                                    queue.append((END, data))
                                else:
                                    queue.append((dest, data))
                            queue.append((branch.then, data))
                        else:
                            for dest in destinations:
                                if dest == END:
                                    queue.append((END, data))
                                else:
                                    queue.append((dest, data))
                elif node_name in self.edges:
                    for dest in self.edges[node_name]:
                        queue.append((dest, data))
                else:
                    return data
            else:
                raise ValueError(f"Node '{node_name}' not found in the graph")

        return data
