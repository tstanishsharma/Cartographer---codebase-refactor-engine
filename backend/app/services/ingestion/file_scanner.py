"""
Cartographer — File Scanner Service.

Walks a repository directory tree, filters files by extension and size,
detects programming languages, and yields FileInfo records for ingestion.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

from app.core.config import get_settings

if TYPE_CHECKING:
    from pathlib import Path

logger = structlog.get_logger(__name__)
settings = get_settings()

# Map file extensions → language names
EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".sh": "bash",
    ".bash": "bash",
}

# Directories to always skip
IGNORED_DIRS: set[str] = {
    ".git",
    ".github",
    ".vscode",
    ".idea",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".next",
    "dist",
    "build",
    ".yarn",
    "venv",
    ".venv",
    "env",
    ".env",
    "vendor",
    "third_party",
    ".cache",
    "coverage",
    "htmlcov",
    ".tox",
}


@dataclass
class FileInfo:
    """Metadata about a single file to be ingested."""

    path: Path
    relative_path: str
    language: str
    size_bytes: int
    content_hash: str
    content: str = field(repr=False)


@dataclass
class ScanResult:
    """Result of scanning a repository directory."""

    files: list[FileInfo]
    language_counts: dict[str, int]
    total_files: int
    skipped_files: int


class FileScanner:
    """
    Walks a repository directory and collects files for ingestion.

    Respects extension allowlist, size limits, and ignores common
    non-code directories (node_modules, .git, etc.).
    """

    def __init__(self) -> None:
        self._max_size_bytes = settings.ingestion_max_file_size_mb * 1024 * 1024
        self._supported_exts = set(settings.ingestion_supported_extensions)

    def scan(self, repo_path: Path) -> ScanResult:
        """
        Walk the repository and collect all eligible files.

        Args:
            repo_path: Absolute path to the cloned repository root.

        Returns:
            ScanResult with all files and language statistics.
        """
        files: list[FileInfo] = []
        language_counts: dict[str, int] = {}
        skipped = 0

        for file_path in self._walk(repo_path):
            ext = file_path.suffix.lower()
            if ext not in self._supported_exts:
                skipped += 1
                continue

            size = file_path.stat().st_size
            if size > self._max_size_bytes:
                logger.debug("file_scanner.skip_large", path=str(file_path), size=size)
                skipped += 1
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                logger.warning("file_scanner.read_error", path=str(file_path), error=str(exc))
                skipped += 1
                continue

            if not content.strip():
                skipped += 1
                continue

            language = EXTENSION_LANGUAGE_MAP.get(ext, "unknown")
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            relative = str(file_path.relative_to(repo_path))

            files.append(
                FileInfo(
                    path=file_path,
                    relative_path=relative,
                    language=language,
                    size_bytes=size,
                    content_hash=content_hash,
                    content=content,
                )
            )
            language_counts[language] = language_counts.get(language, 0) + 1

        logger.info(
            "file_scanner.complete",
            total=len(files) + skipped,
            accepted=len(files),
            skipped=skipped,
            languages=list(language_counts.keys()),
        )

        return ScanResult(
            files=files,
            language_counts=language_counts,
            total_files=len(files),
            skipped_files=skipped,
        )

    def _walk(self, root: Path):
        """Yield file paths, skipping ignored directories."""
        for item in root.rglob("*"):
            # Skip ignored directory names anywhere in the path
            if any(part in IGNORED_DIRS for part in item.parts):
                continue
            if item.is_file():
                yield item
