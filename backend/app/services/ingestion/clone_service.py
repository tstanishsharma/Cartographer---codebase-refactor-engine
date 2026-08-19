"""
Cartographer — Repository Clone Service.

Handles cloning and updating Git repositories using GitPython.
Runs git operations in a thread executor to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)


class CloneService:
    """
    Async wrapper around GitPython for repository cloning and updating.

    All git I/O runs in a thread pool executor so the async event loop
    is never blocked.
    """

    def __init__(self, workspace_base: str = "/tmp/cartographer/repos") -> None:
        self._base = Path(workspace_base)
        self._base.mkdir(parents=True, exist_ok=True)

    def repo_path(self, repo_id: str) -> Path:
        return self._base / repo_id

    async def clone(
        self,
        url: str,
        repo_id: str,
        branch: str = "main",
        on_progress: Callable[[str], None] | None = None,
    ) -> Path:
        """
        Clone a repository into the workspace.

        Returns the local path to the cloned repo.
        Raises on git errors.
        """
        target = self.repo_path(repo_id)

        if target.exists():
            logger.info("clone_service.already_exists", repo_id=repo_id, path=str(target))
            return await self.pull(repo_id, branch)

        loop = asyncio.get_event_loop()
        logger.info("clone_service.cloning", url=url, target=str(target))

        def _do_clone() -> Path:
            import git  # noqa: PLC0415

            class _Progress(git.RemoteProgress):
                def update(
                    self,
                    op_code: int,
                    cur_count: object,
                    max_count: object = None,
                    message: str = "",
                ) -> None:
                    if on_progress and message:
                        on_progress(message)

            progress = _Progress() if on_progress else None
            git.Repo.clone_from(url, str(target), branch=branch, progress=progress, depth=1)  # type: ignore[arg-type]
            return target

        return await loop.run_in_executor(None, _do_clone)

    async def pull(self, repo_id: str, branch: str = "main") -> Path:
        """Pull latest changes for an already-cloned repository."""
        target = self.repo_path(repo_id)
        loop = asyncio.get_event_loop()

        def _do_pull() -> Path:
            import git  # noqa: PLC0415

            repo = git.Repo(str(target))
            origin = repo.remotes.origin
            origin.pull(branch)
            return target

        logger.info("clone_service.pulling", repo_id=repo_id)
        return await loop.run_in_executor(None, _do_pull)

    async def get_head_sha(self, repo_id: str) -> str | None:
        """Return the HEAD commit SHA of a cloned repository."""
        target = self.repo_path(repo_id)
        if not target.exists():
            return None

        loop = asyncio.get_event_loop()

        def _get_sha() -> str:
            import git  # noqa: PLC0415

            repo = git.Repo(str(target))
            return repo.head.commit.hexsha

        return await loop.run_in_executor(None, _get_sha)

    def cleanup(self, repo_id: str) -> None:
        """Remove the local clone from disk."""
        target = self.repo_path(repo_id)
        if target.exists():
            shutil.rmtree(str(target), ignore_errors=True)
            logger.info("clone_service.cleanup", repo_id=repo_id)
