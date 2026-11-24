"""One tree renderer for list, status and fetch, including collapsed summaries."""
from collections import Counter
from dataclasses import dataclass, field

from .manifest import Repository
from .repositories import Result


@dataclass
class Node:
    children: dict[str, "Node"] = field(default_factory=dict)
    repo: Repository | None = None

    def leaves(self) -> list[Repository]:
        if self.repo:
            return [self.repo]
        return [repo for child in self.children.values() for repo in child.leaves()]


def render_tree(name: str, repositories: list[Repository], results: dict[str, Result] | None = None,
                depth: int | None = None) -> str:
    root = Node()
    for repo in repositories:
        node = root
        for part in repo.path.split("/"):
            node = node.children.setdefault(part, Node())
        node.repo = repo
    lines = [name + "/"]

    def label(name: str, node: Node) -> str:
        if node.repo:
            value = f"{name} [{node.repo.github}]"
            if results is not None:
                result = results[node.repo.path]
                value += f"  {result.symbol} {result.detail}"
            return value
        leaves = node.leaves()
        value = f"{name}/ ({len(leaves)} {'repo' if len(leaves) == 1 else 'repos'})"
        if results is not None:
            counts = Counter(results[repo.path].symbol for repo in leaves)
            value += "  " + "  ".join(f"{symbol} {counts[symbol]}" for symbol in ("✅", "🔽", "🔼", "⚠️", "⚪") if counts[symbol])
        return value

    def walk(node: Node, prefix: str, level: int) -> None:
        if depth is not None and level > depth:
            return
        children = sorted(node.children.items(), key=lambda item: item[0].casefold())
        for index, (name, child) in enumerate(children):
            last = index == len(children) - 1
            lines.append(prefix + ("└── " if last else "├── ") + label(name, child))
            walk(child, prefix + ("    " if last else "│   "), level + 1)
    walk(root, "", 1)
    return "\n".join(lines)
