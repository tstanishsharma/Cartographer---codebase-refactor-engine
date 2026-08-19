"""
Cartographer — Sandbox Router.

Manages Docker sandbox job lifecycle. Jobs execute structured code
edits against a repository's clone inside an isolated container, run
the test command, and report results (diff + test outcome). Each job
is persisted to the ``sandbox_jobs`` table so results can be polled.

The sandbox requires access to the Docker daemon (docker.sock is
mounted into the backend container in docker-compose). When Docker is
unavailable the job fails with a clear error instead of silently
succeeding.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, RepositoryRepo, SandboxJobRepo  # noqa: TC001, TC002
from app.db.models.sandbox_job import SandboxJobStatus

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/sandbox")


class CreateSandboxJobRequest(BaseModel):
    repository_id: uuid.UUID
    code_edits: list[dict]
    test_command: str = "pytest"
    agent_run_id: uuid.UUID | None = None


class SandboxJobResponse(BaseModel):
    id: str
    repository_id: str
    status: str
    diff: str | None
    test_passed: bool | None
    test_summary: dict
    execution_logs: str | None
    duration_seconds: float | None
    created_at: str


@router.post("/jobs", response_model=SandboxJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_sandbox_job(
    body: CreateSandboxJobRequest,
    current_user: CurrentUser,
    repo: RepositoryRepo,
    job_repo: SandboxJobRepo,
) -> SandboxJobResponse:
    """
    Execute structured code edits inside a Docker sandbox and run tests.

    The call blocks until the sandbox finishes (or errors out) and the
    job result is persisted so it can be polled via GET /jobs/{job_id}.
    """
    repository = await repo.get_by_id(body.repository_id)
    if not repository or repository.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Repository not found.")

    local_path = getattr(repository, "local_path", None)

    job = await job_repo.create(
        repository_id=body.repository_id,
        agent_run_id=body.agent_run_id,
        status=SandboxJobStatus.QUEUED,
        code_edits=body.code_edits,
        test_command=body.test_command,
        test_summary={},
    )
    await job_repo._session.commit()

    if not local_path:
        await job_repo.update(
            job.id,
            status=SandboxJobStatus.FAILED,
            error_message="Repository has no local clone path.",
        )
        await job_repo._session.commit()
        return _job_response(job)

    from app.services.agents.state import EditOperation  # noqa: PLC0415
    from app.services.sandbox.docker_sandbox import DockerSandboxService  # noqa: PLC0415

    sandbox = DockerSandboxService()
    try:
        await job_repo.update(job.id, status=SandboxJobStatus.INITIALIZING)
        initialized = await sandbox.initialize(repository_path=local_path)
        if not initialized:
            raise RuntimeError(
                "Docker sandbox could not be initialized. Ensure the Docker daemon is "
                "running and the socket is available to the backend."
            )

        await job_repo.update(job.id, status=SandboxJobStatus.RUNNING)
        edits = [EditOperation(**edit) for edit in body.code_edits]
        if edits:
            await sandbox.apply_edits(edits)

        await job_repo.update(job.id, status=SandboxJobStatus.TESTING)
        command = body.test_command or "true"
        result = await sandbox.execute(command)
        diff = await sandbox.get_diff()

        test_passed = result.exit_code == 0
        await job_repo.update(
            job.id,
            status=SandboxJobStatus.COMPLETED if test_passed else SandboxJobStatus.FAILED,
            diff=diff or None,
            test_passed=test_passed,
            test_summary={
                "status": result.status,
                "exit_code": result.exit_code,
                "stdout_tail": result.stdout[-2000:],
                "stderr_tail": result.stderr[-2000:],
                "execution_time_sec": result.execution_time_sec,
            },
            execution_logs=result.stdout[-5000:] or None,
            duration_seconds=result.execution_time_sec,
            exit_code=result.exit_code,
            completed_at=datetime.now(UTC),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("sandbox.job_failed", job_id=str(job.id), error=str(exc))
        await job_repo.update(
            job.id,
            status=SandboxJobStatus.FAILED,
            error_message=str(exc)[:2000],
            completed_at=datetime.now(UTC),
        )
    finally:
        try:
            await sandbox.cleanup()
        except Exception:  # noqa: BLE001
            pass

    await job_repo._session.commit()
    return _job_response(job)


@router.get("/jobs/{job_id}", response_model=SandboxJobResponse)
async def get_sandbox_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    job_repo: SandboxJobRepo,
) -> SandboxJobResponse:
    """Get sandbox job status and results."""
    job = await job_repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _job_response(job)


def _job_response(job: object) -> SandboxJobResponse:
    return SandboxJobResponse(
        id=str(getattr(job, "id", "")),
        repository_id=str(getattr(job, "repository_id", "")),
        status=getattr(job, "status", ""),
        diff=getattr(job, "diff", None),
        test_passed=getattr(job, "test_passed", None),
        test_summary=getattr(job, "test_summary", {}) or {},
        execution_logs=getattr(job, "execution_logs", None),
        duration_seconds=getattr(job, "duration_seconds", None),
        created_at=getattr(job, "created_at", datetime.now(UTC)).isoformat(),
    )
