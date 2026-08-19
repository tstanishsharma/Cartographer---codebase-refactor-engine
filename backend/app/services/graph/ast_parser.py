"""
Cartographer — AST Parser.

Parses source files using Tree-sitter to extract:
  - Modules, classes, functions, methods (graph nodes)
  - Import relationships (graph edges)
  - Call relationships (graph edges)
  - Inheritance relationships (graph edges)

Returns structured ParsedNode and ParsedEdge objects that GraphBuilder
persists to the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ParsedNode:
    """An AST-derived graph node extracted from source code."""

    node_type: str  # "module" | "class" | "function" | "method" | "import" | "variable"
    name: str
    qualified_name: str  # "module.ClassName.method_name"
    file_path: str
    start_line: int
    end_line: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedEdge:
    """A directed relationship between two parsed nodes."""

    source_qualified_name: str
    target_qualified_name: str
    edge_type: str  # "imports" | "calls" | "inherits" | "defines" | "uses"
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ASTParser:
    """
    Multi-language AST parser using Tree-sitter.

    Produces ParsedNode and ParsedEdge lists for each file.
    Currently supports: Python, TypeScript, JavaScript.
    """

    def parse_file(
        self,
        content: str,
        file_path: str,
        language: str,
    ) -> tuple[list[ParsedNode], list[ParsedEdge]]:
        """
        Parse a source file and extract graph nodes and edges.

        Args:
            content:   Source code text.
            file_path: Relative path from repository root.
            language:  Language identifier ("python", "typescript", etc.)

        Returns:
            (nodes, edges) — lists of ParsedNode and ParsedEdge.
        """
        match language:
            case "python":
                return self._parse_python(content, file_path)
            case "typescript" | "javascript":
                return self._parse_typescript(content, file_path, language)
            case _:
                return [], []

    # ── Python parser ──────────────────────────────────────────────────────────

    def _parse_python(
        self, content: str, file_path: str
    ) -> tuple[list[ParsedNode], list[ParsedEdge]]:
        """
        Extract Python AST entities using Tree-sitter.

        Extracts: module, class, function/method nodes.
        Extracts: import, inherits, defines edges.
        """
        parser = self._get_parser("python")
        if parser is None:
            return self._parse_python_stdlib(content, file_path)

        tree = parser.parse(content.encode())
        root = tree.root_node
        lines = content.splitlines()

        module_name = file_path.replace("/", ".").replace("\\", ".").removesuffix(".py")
        nodes: list[ParsedNode] = []
        edges: list[ParsedEdge] = []

        # Module node
        module_node = ParsedNode(
            node_type="module",
            name=module_name.split(".")[-1],
            qualified_name=module_name,
            file_path=file_path,
            start_line=0,
            end_line=len(lines),
        )
        nodes.append(module_node)

        self._walk_python(root, content, file_path, module_name, nodes, edges)
        return nodes, edges

    @staticmethod
    def _resolve_module_ref(module_part: str, module_name: str) -> str:
        """
        Resolve a (possibly relative) import module reference to a qualified name.

        ``from .core import X`` inside ``src/click/decorators.py`` yields
        ``src.click.core`` so it can match a graph node.
        """
        if not module_part.startswith("."):
            return module_part
        # Leading dots: 1 = current package, 2 = parent package, ...
        dots = len(module_part) - len(module_part.lstrip("."))
        rest = module_part[dots:].lstrip(".")
        parts = module_name.split(".")
        package = parts[:-1]  # drop the importing file itself
        if dots > 1:
            package = package[: -(dots - 1)]
        return ".".join(package + ([rest] if rest else []))

    def _walk_python(
        self,
        node: Any,
        content: str,
        file_path: str,
        scope: str,
        nodes: list[ParsedNode],
        edges: list[ParsedEdge],
    ) -> None:
        """Recursively walk a Python Tree-sitter tree."""
        for child in node.children:
            if child.type == "import_statement":
                # import os, sys
                for name_node in child.named_children:
                    target = content[name_node.start_byte : name_node.end_byte].strip()
                    edges.append(
                        ParsedEdge(
                            source_qualified_name=scope,
                            target_qualified_name=target,
                            edge_type="imports",
                        )
                    )

            elif child.type == "import_from_statement":
                # from os.path import join, exists   (may be relative: from .core import X)
                from_kw = next((c for c in child.children if c.type == "from"), None)
                import_kw = next((c for c in child.children if c.type == "import"), None)
                if from_kw and import_kw:
                    module_part = content[from_kw.end_byte : import_kw.start_byte].strip()
                    edges.append(
                        ParsedEdge(
                            source_qualified_name=scope,
                            target_qualified_name=self._resolve_module_ref(module_part, scope),
                            edge_type="imports",
                        )
                    )

            elif child.type in ("function_definition", "async_function_def"):
                name_node = next((c for c in child.children if c.type == "identifier"), None)
                if name_node:
                    fname = content[name_node.start_byte : name_node.end_byte]
                    qname = f"{scope}.{fname}"
                    is_class = any(
                        n.qualified_name == scope and n.node_type == "class" for n in nodes
                    )
                    node_type = "method" if is_class else "function"
                    nodes.append(
                        ParsedNode(
                            node_type=node_type,
                            name=fname,
                            qualified_name=qname,
                            file_path=file_path,
                            start_line=child.start_point[0],
                            end_line=child.end_point[0],
                            metadata={"tree_sitter_type": child.type},
                        )
                    )
                    edges.append(
                        ParsedEdge(
                            source_qualified_name=scope,
                            target_qualified_name=qname,
                            edge_type="defines",
                        )
                    )
                    # Recurse into function body
                    self._walk_python(child, content, file_path, qname, nodes, edges)

            elif child.type == "class_definition":
                name_node = next((c for c in child.children if c.type == "identifier"), None)
                if name_node:
                    cname = content[name_node.start_byte : name_node.end_byte]
                    qname = f"{scope}.{cname}"
                    nodes.append(
                        ParsedNode(
                            node_type="class",
                            name=cname,
                            qualified_name=qname,
                            file_path=file_path,
                            start_line=child.start_point[0],
                            end_line=child.end_point[0],
                        )
                    )
                    edges.append(
                        ParsedEdge(
                            source_qualified_name=scope,
                            target_qualified_name=qname,
                            edge_type="defines",
                        )
                    )
                    # Check for inheritance
                    arg_list = next((c for c in child.children if c.type == "argument_list"), None)
                    if arg_list:
                        for base in arg_list.named_children:
                            base_name = content[base.start_byte : base.end_byte].strip()
                            if base_name not in ("object",):
                                edges.append(
                                    ParsedEdge(
                                        source_qualified_name=qname,
                                        target_qualified_name=base_name,
                                        edge_type="inherits",
                                    )
                                )
                    self._walk_python(child, content, file_path, qname, nodes, edges)

            elif child.type in ("block", "decorated_definition", "expression_statement"):
                self._walk_python(child, content, file_path, scope, nodes, edges)

    def _parse_python_stdlib(
        self, content: str, file_path: str
    ) -> tuple[list[ParsedNode], list[ParsedEdge]]:
        """Fallback: use Python's stdlib ast module."""
        import ast as pyast  # noqa: PLC0415

        module_name = file_path.replace("/", ".").replace("\\", ".").removesuffix(".py")
        nodes: list[ParsedNode] = [
            ParsedNode(
                node_type="module",
                name=module_name.split(".")[-1],
                qualified_name=module_name,
                file_path=file_path,
                start_line=0,
                end_line=len(content.splitlines()),
            )
        ]
        edges: list[ParsedEdge] = []

        try:
            tree = pyast.parse(content, filename=file_path)
        except SyntaxError:
            return nodes, edges

        for node in pyast.walk(tree):
            if isinstance(node, (pyast.FunctionDef, pyast.AsyncFunctionDef)):
                qname = f"{module_name}.{node.name}"
                nodes.append(
                    ParsedNode(
                        node_type="function",
                        name=node.name,
                        qualified_name=qname,
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                    )
                )
                edges.append(
                    ParsedEdge(
                        source_qualified_name=module_name,
                        target_qualified_name=qname,
                        edge_type="defines",
                    )
                )
            elif isinstance(node, pyast.ClassDef):
                qname = f"{module_name}.{node.name}"
                nodes.append(
                    ParsedNode(
                        node_type="class",
                        name=node.name,
                        qualified_name=qname,
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                    )
                )
                edges.append(
                    ParsedEdge(
                        source_qualified_name=module_name,
                        target_qualified_name=qname,
                        edge_type="defines",
                    )
                )
            elif isinstance(node, (pyast.Import, pyast.ImportFrom)):
                if isinstance(node, pyast.Import):
                    for alias in node.names:
                        edges.append(
                            ParsedEdge(
                                source_qualified_name=module_name,
                                target_qualified_name=alias.name,
                                edge_type="imports",
                            )
                        )
                else:
                    # Preserve relative levels (node.level) so `.core` → module path.
                    if node.module or node.level:
                        target = ("." * node.level) + (node.module or "")
                        edges.append(
                            ParsedEdge(
                                source_qualified_name=module_name,
                                target_qualified_name=self._resolve_module_ref(target, module_name),
                                edge_type="imports",
                            )
                        )

        return nodes, edges

    # ── TypeScript / JavaScript parser ─────────────────────────────────────────

    def _parse_typescript(
        self, content: str, file_path: str, language: str
    ) -> tuple[list[ParsedNode], list[ParsedEdge]]:
        """Extract TypeScript/JavaScript entities via Tree-sitter."""
        parser = self._get_parser(language)
        if parser is None:
            return [], []

        tree = parser.parse(content.encode())
        root = tree.root_node
        lines = content.splitlines()

        module_name = file_path.replace("/", ".").replace("\\", ".")
        for ext in (".ts", ".tsx", ".js", ".jsx"):
            module_name = module_name.removesuffix(ext)

        nodes: list[ParsedNode] = [
            ParsedNode(
                node_type="module",
                name=module_name.split(".")[-1],
                qualified_name=module_name,
                file_path=file_path,
                start_line=0,
                end_line=len(lines),
            )
        ]
        edges: list[ParsedEdge] = []

        for child in root.children:
            # Import declarations
            if child.type == "import_declaration":
                source = next((c for c in child.children if c.type == "string"), None)
                if source:
                    target = content[source.start_byte : source.end_byte].strip("\"'")
                    edges.append(
                        ParsedEdge(
                            source_qualified_name=module_name,
                            target_qualified_name=target,
                            edge_type="imports",
                        )
                    )

            # Class declarations
            elif child.type in ("class_declaration", "abstract_class_declaration"):
                name_node = next(
                    (c for c in child.children if c.type in ("identifier", "type_identifier")), None
                )
                if name_node:
                    cname = content[name_node.start_byte : name_node.end_byte]
                    qname = f"{module_name}.{cname}"
                    nodes.append(
                        ParsedNode(
                            node_type="class",
                            name=cname,
                            qualified_name=qname,
                            file_path=file_path,
                            start_line=child.start_point[0],
                            end_line=child.end_point[0],
                        )
                    )
                    edges.append(
                        ParsedEdge(
                            source_qualified_name=module_name,
                            target_qualified_name=qname,
                            edge_type="defines",
                        )
                    )

            # Function declarations
            elif child.type == "function_declaration":
                name_node = next((c for c in child.children if c.type == "identifier"), None)
                if name_node:
                    fname = content[name_node.start_byte : name_node.end_byte]
                    qname = f"{module_name}.{fname}"
                    nodes.append(
                        ParsedNode(
                            node_type="function",
                            name=fname,
                            qualified_name=qname,
                            file_path=file_path,
                            start_line=child.start_point[0],
                            end_line=child.end_point[0],
                        )
                    )
                    edges.append(
                        ParsedEdge(
                            source_qualified_name=module_name,
                            target_qualified_name=qname,
                            edge_type="defines",
                        )
                    )

        return nodes, edges

    def _get_parser(self, language: str) -> Any | None:
        """Load Tree-sitter parser, returning None if unavailable."""
        from app.utils.tree_sitter import get_parser  # noqa: PLC0415

        return get_parser(language)
