import os
import tempfile
import time

import docker
import structlog
from docker.errors import DockerException

from app.services.agents.state import EditOperation, SandboxResult

logger = structlog.get_logger(__name__)


class DockerSandboxService:
    """
    Isolated Docker sandbox for Cartographer to execute arbitrary code.
    Runs tests and commands in a highly restricted container (no network, readonly rootfs, mem limits).
    """

    def __init__(self, image: str = "python:3.12-slim"):
        self.image = image
        try:
            self.client = docker.from_env()
        except DockerException as e:
            logger.error("Failed to initialize Docker client", error=str(e))
            self.client = None

        self.container = None
        self.workdir = "/workspace"
        self._temp_dir = tempfile.TemporaryDirectory()

    async def initialize(self, repository_path: str | None = None) -> bool:
        """Create and start the isolated sandbox container."""
        if not self.client:
            logger.error("Docker client not available. Cannot initialize sandbox.")
            return False

        try:
            # Pull image if not exists
            try:
                self.client.images.get(self.image)
            except docker.errors.ImageNotFound:
                logger.info(f"Pulling image {self.image}")
                self.client.images.pull(self.image)

            # Security settings:
            # network_disabled=True -> No internet access
            # read_only=True -> Readonly root filesystem (except volumes)
            # mem_limit -> 2GB
            # cpu_quota -> limits CPU

            # Map temp dir to /workspace to allow writes (since rootfs is readonly)
            host_path = os.path.abspath(self._temp_dir.name)
            volumes = {host_path: {"bind": self.workdir, "mode": "rw"}}

            # Since the user requested read-only filesystem but we need to run tests
            # we will mount the workspace as rw and make the rest readonly.
            # We also drop all capabilities for security.

            self.container = self.client.containers.run(
                self.image,
                command="tail -f /dev/null",  # Keep alive
                detach=True,
                network_disabled=True,
                read_only=True,
                volumes=volumes,
                working_dir=self.workdir,
                mem_limit="2g",
                nano_cpus=2_000_000_000,  # 2 CPUs
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                user="1000:1000",  # Run as non-root
                remove=True,
            )
            logger.info("Sandbox container started", container_id=self.container.short_id)

            # If a repository path is provided, copy its contents to the temp directory
            # For this demo, we assume the host path is accessible.
            if repository_path and os.path.exists(repository_path):
                import shutil

                # Copy everything from repository to temp workspace
                for item in os.listdir(repository_path):
                    s = os.path.join(repository_path, item)
                    d = os.path.join(host_path, item)
                    if os.path.isdir(s):
                        if item not in [".git", "node_modules", "venv", ".venv"]:
                            shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)

            return True
        except Exception as e:
            logger.error("Failed to initialize sandbox", error=str(e))
            return False

    async def execute(self, command: str, timeout_sec: int = 300) -> SandboxResult:
        """Run a command inside the container and return the result."""
        if not self.container:
            return SandboxResult(
                status="ERROR",
                stdout="",
                stderr="Container not running",
                exit_code=-1,
                execution_time_sec=0.0,
            )

        start_time = time.time()
        try:
            # We use docker exec
            exec_log = self.container.exec_run(
                cmd=["/bin/sh", "-c", command],
                workdir=self.workdir,
                user="1000:1000",
                demux=True,  # separates stdout and stderr
            )

            execution_time = time.time() - start_time
            exit_code = exec_log.exit_code
            stdout_bytes, stderr_bytes = exec_log.output

            stdout = stdout_bytes.decode("utf-8") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8") if stderr_bytes else ""

            status = "PASS" if exit_code == 0 else "FAIL"

            return SandboxResult(
                status=status,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                execution_time_sec=execution_time,
            )
        except Exception as e:
            logger.error("Command execution failed", error=str(e))
            return SandboxResult(
                status="ERROR",
                stdout="",
                stderr=str(e),
                exit_code=-1,
                execution_time_sec=time.time() - start_time,
            )

    async def apply_edits(self, edits: list[EditOperation]) -> bool:
        """Apply structured SEARCH/REPLACE edits to files in the worktree."""
        host_path = os.path.abspath(self._temp_dir.name)

        for edit in edits:
            target_file = os.path.join(host_path, edit.file_path)

            if edit.operation_type == "SEARCH_REPLACE":
                if not os.path.exists(target_file):
                    continue

                with open(target_file, encoding="utf-8") as f:
                    content = f.read()

                if edit.search_block and edit.replace_block:
                    if edit.search_block in content:
                        content = content.replace(edit.search_block, edit.replace_block)
                        with open(target_file, "w", encoding="utf-8") as f:
                            f.write(content)
            elif edit.operation_type == "INSERT":
                # Very basic append for now
                with open(target_file, "a", encoding="utf-8") as f:
                    f.write(edit.insert_block or "")

        return True

    async def get_diff(self) -> str:
        """Generate a unified diff of the changes made in the sandbox using Git."""
        if not self.container:
            return ""

        res = await self.execute("git diff")
        return res.stdout

    async def cleanup(self):
        """Tear down the container and clean up temporary files."""
        if self.container:
            try:
                self.container.stop(timeout=2)
            except Exception as e:
                logger.warning("Error stopping container", error=str(e))
            self.container = None

        self._temp_dir.cleanup()
