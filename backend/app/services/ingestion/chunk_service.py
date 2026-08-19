"""
Cartographer — Chunk Service.

Converts source files into semantically meaningful code chunks using
Tree-sitter AST-aware splitting. Falls back to text-based splitting
for languages without a Tree-sitter grammar.

Chunking strategy:
  1. Parse file with Tree-sitter to extract top-level nodes
     (functions, classes, methods) as natural chunk boundaries.
  2. If a node exceeds max_size, sub-chunk it recursively.
  3. For files without AST support, use overlap-aware text splitting.
  4. Attach parent-child relationships for parent-child retrieval.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from app.core.config import get_settings

if TYPE_CHECKING:
    from app.services.ingestion.file_scanner import FileInfo

logger = structlog.get_logger(__name__)
settings = get_settings()

# Tree-sitter language grammars that we support
_TS_LANGUAGE_MAP: dict[str, str] = {
    "python": "python",
    "typescript": "typescript",
    "javascript": "javascript",
    "java": "java",
    "go": "go",
    "rust": "rust",
    "cpp": "cpp",
    "c": "c",
}

# AST node types to use as chunk boundaries per language
_CHUNK_NODE_TYPES: dict[str, list[str]] = {
    "python": [
        "function_definition",
        "async_function_def",
        "class_definition",
        "decorated_definition",
    ],
    "typescript": [
        "function_declaration",
        "method_definition",
        "class_declaration",
        "arrow_function",
        "export_statement",
    ],
    "javascript": [
        "function_declaration",
        "method_definition",
        "class_declaration",
        "arrow_function",
    ],
    "java": [
        "method_declaration",
        "class_declaration",
        "interface_declaration",
        "constructor_declaration",
    ],
    "go": ["function_declaration", "method_declaration", "type_declaration"],
    "rust": ["function_item", "impl_item", "struct_item", "enum_item", "trait_item"],
    "cpp": ["function_definition", "class_specifier", "struct_specifier"],
    "c": ["function_definition"],
}


@dataclass
class ChunkData:
    """Represents a single code chunk ready for storage."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    parent_id: uuid.UUID | None = None
    file_path: str = ""
    language: str = "unknown"
    chunk_type: str = "text"  # "function" | "class" | "method" | "text" | "module"
    chunk_index: int = 0
    content: str = ""
    content_hash: str = ""
    start_line: int = 0
    end_line: int = 0
    start_byte: int | None = None
    end_byte: int | None = None
    symbol_name: str | None = None  # function/class name if extractable
    symbol_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ChunkService:
    """
    AST-aware file chunker.

    Uses Tree-sitter for structured languages and falls back to
    overlap-aware text splitting for everything else.
    """

    def __init__(self) -> None:
        self._max_size = settings.ingestion_chunk_size
        self._overlap = settings.ingestion_chunk_overlap
        self._parsers: dict[str, Any] = {}

    def chunk_file(self, file_info: FileInfo) -> list[ChunkData]:
        """
        Chunk a single file into semantically meaningful pieces.

        Args:
            file_info: File metadata and content from FileScanner.

        Returns:
            Ordered list of ChunkData objects.
        """
        language = file_info.language
        content = file_info.content

        # Attempt AST-aware chunking
        if language in _TS_LANGUAGE_MAP:
            try:
                chunks = self._ast_chunk(content, language, file_info.relative_path)
                if chunks:
                    return self._assign_indices(chunks)
            except Exception as exc:
                logger.warning(
                    "chunk_service.ast_failed",
                    path=file_info.relative_path,
                    language=language,
                    error=str(exc),
                )

        # Fallback: text splitter
        return self._assign_indices(self._text_chunk(content, language, file_info.relative_path))

    def _ast_chunk(self, content: str, language: str, file_path: str) -> list[ChunkData]:
        """Parse with Tree-sitter and extract top-level symbol chunks."""
        parser = self._get_parser(language)
        if parser is None:
            return []

        tree = parser.parse(content.encode("utf-8"))
        root = tree.root_node

        target_types = set(_CHUNK_NODE_TYPES.get(language, []))
        chunks: list[ChunkData] = []
        lines = content.splitlines()

        # Create a "module" parent chunk for the whole file
        module_chunk = ChunkData(
            file_path=file_path,
            language=language,
            chunk_type="module",
            content=content[: self._max_size * 2] if len(content) > self._max_size * 2 else content,
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
            start_line=0,
            end_line=len(lines),
            start_byte=0,
            end_byte=len(content.encode("utf-8")),
            symbol_name=file_path.split("/")[-1],
            symbol_type="module",
        )
        chunks.append(module_chunk)

        # Walk top-level children
        for node in root.children:
            if node.type in target_types:
                node_content = content[node.start_byte : node.end_byte]
                name = self._extract_name(node, content)

                # If node exceeds max_size, sub-chunk it
                if len(node_content) > self._max_size:
                    sub_chunks = self._text_chunk(
                        node_content, language, file_path, start_offset=node.start_point[0]
                    )
                    for sc in sub_chunks:
                        sc.parent_id = module_chunk.id
                        # Byte offsets relative to the node's own start
                        if sc.start_byte is not None:
                            sc.start_byte += node.start_byte
                        if sc.end_byte is not None:
                            sc.end_byte += node.start_byte
                    chunks.extend(sub_chunks)
                else:
                    chunks.append(
                        ChunkData(
                            parent_id=module_chunk.id,
                            file_path=file_path,
                            language=language,
                            chunk_type=self._node_type_to_chunk_type(node.type),
                            content=node_content,
                            content_hash=hashlib.sha256(node_content.encode()).hexdigest(),
                            start_line=node.start_point[0],
                            end_line=node.end_point[0],
                            start_byte=node.start_byte,
                            end_byte=node.end_byte,
                            symbol_name=name,
                            symbol_type=self._node_type_to_chunk_type(node.type),
                            metadata={"tree_sitter_type": node.type},
                        )
                    )

        return chunks

    def _text_chunk(
        self,
        content: str,
        language: str,
        file_path: str,
        start_offset: int = 0,
    ) -> list[ChunkData]:
        """Overlap-aware text splitter for fallback or sub-chunking."""
        chunks: list[ChunkData] = []
        text = content
        start = 0
        content.splitlines()

        while start < len(text):
            end = min(start + self._max_size, len(text))
            chunk_content = text[start:end]

            # Count lines to compute line numbers
            preceding_lines = text[:start].count("\n")
            chunk_lines = chunk_content.count("\n")

            chunks.append(
                ChunkData(
                    file_path=file_path,
                    language=language,
                    chunk_type="text",
                    content=chunk_content,
                    content_hash=hashlib.sha256(chunk_content.encode()).hexdigest(),
                    start_line=start_offset + preceding_lines,
                    end_line=start_offset + preceding_lines + chunk_lines,
                    start_byte=len(text[:start].encode("utf-8")),
                    end_byte=len(text[:end].encode("utf-8")),
                )
            )

            if end >= len(text):
                break
            # Move forward but maintain overlap
            start = end - self._overlap

        return chunks

    def _get_parser(self, language: str) -> Any | None:
        """Load and cache a Tree-sitter parser for a language."""
        if language in self._parsers:
            return self._parsers[language]
        try:
            from app.utils.tree_sitter import get_parser  # noqa: PLC0415

            parser = get_parser(language)
            self._parsers[language] = parser
            return parser
        except Exception as exc:
            logger.debug("chunk_service.no_parser", language=language, error=str(exc))
            self._parsers[language] = None
            return None

    def _extract_name(self, node: Any, content: str) -> str | None:
        """Extract the identifier/name from an AST node."""
        for child in node.children:
            if child.type in ("identifier", "name", "type_identifier"):
                return content[child.start_byte : child.end_byte]
        return None

    def _node_type_to_chunk_type(self, node_type: str) -> str:
        if "function" in node_type or "method" in node_type:
            return "function"
        if "class" in node_type or "struct" in node_type:
            return "class"
        return "text"

    def _assign_indices(self, chunks: list[ChunkData]) -> list[ChunkData]:
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i
        return chunks
