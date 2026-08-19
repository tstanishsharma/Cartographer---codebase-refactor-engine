import pytest

from app.core.config import get_settings
from app.services.sandbox.docker_sandbox import DockerSandboxService

settings = get_settings()


@pytest.mark.asyncio
async def test_sandbox_execution(mocker):
    # Mock docker client to avoid actual docker daemon dependency
    mock_docker_client = mocker.Mock()
    mock_container = mocker.Mock()

    # Mock exec_run
    mock_exec_result = mocker.Mock()
    mock_exec_result.exit_code = 0
    mock_exec_result.output = (b"hello world\n", b"")
    mock_container.exec_run.return_value = mock_exec_result
    mock_container.short_id = "mock_container_123"

    mock_docker_client.containers.run.return_value = mock_container
    mocker.patch("docker.from_env", return_value=mock_docker_client)

    sandbox = DockerSandboxService(image="python:3.12-slim")

    # Test initialization
    res = await sandbox.initialize()
    assert res is True

    # Test execution
    result = await sandbox.execute("echo 'hello world'")
    assert result.status == "PASS"
    assert "hello world" in result.stdout
    assert result.exit_code == 0

    # Test cleanup
    await sandbox.cleanup()
    mock_container.stop.assert_called_once()


@pytest.mark.asyncio
async def test_sandbox_timeout(mocker):
    # Test that exception during execution results in status=ERROR
    mock_docker_client = mocker.Mock()
    mock_container = mocker.Mock()

    # Force exception
    mock_container.exec_run.side_effect = Exception("Docker timeout")

    mock_docker_client.containers.run.return_value = mock_container
    mocker.patch("docker.from_env", return_value=mock_docker_client)

    sandbox = DockerSandboxService()
    await sandbox.initialize()

    result = await sandbox.execute("sleep 100", timeout_sec=1)
    assert result.status == "ERROR"
    assert "Docker timeout" in result.stderr

    await sandbox.cleanup()
