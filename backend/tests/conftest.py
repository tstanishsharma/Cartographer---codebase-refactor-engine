import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio

os.environ["ENVIRONMENT"] = "testing"
os.environ["POSTGRES_DB"] = "cartographer_test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-12345678901234567890123456789012"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-12345678901234567890123456789012"
os.environ["OPENAI_API_KEY"] = "mock-openai-key"
os.environ["ANTHROPIC_API_KEY"] = "mock-anthropic-key"

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token
from app.db.base import Base, get_session
from app.main import app


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(db_engine, expire_on_commit=False, autoflush=False)
    async with async_session() as session:
        yield session


@pytest.fixture
def override_get_db(db_session):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_session] = _get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def test_user():
    return {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "username": "tester",
        "is_active": True,
        "is_superuser": False,
    }


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(str(test_user["id"]))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def async_client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


class MockLLMProvider:
    async def invoke(self, messages, **kwargs):
        return "Mock response"

    async def stream(self, messages, **kwargs):
        yield "Mock "
        yield "response"

    async def generate_structured(self, messages, schema, **kwargs):
        return schema(**{})


@pytest.fixture
def mock_llm():
    return MockLLMProvider()


class MockEmbeddingProvider:
    async def embed_query(self, text: str) -> list[float]:
        return [0.1] * 1536

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 1536 for _ in texts]

    @property
    def model_info(self):
        class ModelInfo:
            name = "text-embedding-3-small"
            dimension = 1536

        return ModelInfo()


@pytest.fixture
def mock_embedding():
    return MockEmbeddingProvider()


class MockSandbox:
    async def initialize(self, *args, **kwargs):
        return True

    async def execute(self, cmd, **kwargs):
        from app.services.agents.state import SandboxResult

        return SandboxResult(
            status="PASS", stdout="Success", stderr="", exit_code=0, execution_time_sec=0.1
        )

    async def apply_edits(self, edits):
        return True

    async def get_diff(self):
        return "+ added line"

    async def cleanup(self):
        pass


@pytest.fixture
def mock_sandbox():
    return MockSandbox()
