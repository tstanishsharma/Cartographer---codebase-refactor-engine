"""
Cartographer — FastAPI Dependency Providers.

Centralises all DI wiring. Routers import from here, not from individual
service/repository modules, maintaining clean layer separation.

Pattern:
    - get_*_repo()     → Database repositories (bound to session)
    - get_*_service()  → Service layer (may depend on repos + providers)
    - get_current_user() → Authenticated user (JWT extraction)
    - get_llm / get_embedder → Provider singletons
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.security import decode_token
from app.db.base import get_session
from app.db.models.user import User
from app.db.repositories.agent_repo import AgentRepository
from app.db.repositories.chunk_repo import ChunkRepository
from app.db.repositories.graph_repo import GraphRepository
from app.db.repositories.repository_repo import RepositoryRepository
from app.db.repositories.sandbox_job_repo import SandboxJobRepository
from app.db.repositories.user_repo import UserRepository
from app.services.cache.redis_service import CacheService, get_redis
from app.services.embedding.base import EmbeddingProvider
from app.services.embedding.factory import get_embedding_provider
from app.services.llm.base import LLMProvider
from app.services.llm.factory import get_llm_provider
from app.services.retrieval.hybrid_retriever import HybridRetriever

logger = structlog.get_logger(__name__)
_bearer = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------
DbSession = Annotated[AsyncSession, Depends(get_session)]

# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------


def get_user_repo(db: DbSession) -> UserRepository:
    return UserRepository(db)


def get_repository_repo(db: DbSession) -> RepositoryRepository:
    return RepositoryRepository(db)


def get_chunk_repo(db: DbSession) -> ChunkRepository:
    return ChunkRepository(db)


def get_graph_repo(db: DbSession) -> GraphRepository:
    return GraphRepository(db)


def get_agent_repo(db: DbSession) -> AgentRepository:
    return AgentRepository(db)


def get_sandbox_job_repo(db: DbSession) -> SandboxJobRepository:
    return SandboxJobRepository(db)


UserRepo = Annotated[UserRepository, Depends(get_user_repo)]
RepositoryRepo = Annotated[RepositoryRepository, Depends(get_repository_repo)]
ChunkRepo = Annotated[ChunkRepository, Depends(get_chunk_repo)]
GraphRepo = Annotated[GraphRepository, Depends(get_graph_repo)]
AgentRepo = Annotated[AgentRepository, Depends(get_agent_repo)]
SandboxJobRepo = Annotated[SandboxJobRepository, Depends(get_sandbox_job_repo)]

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


async def get_cache(redis: Any = Depends(get_redis)) -> CacheService:  # type: ignore[type-arg]
    return CacheService(redis)


Cache = Annotated[CacheService, Depends(get_cache)]

# ---------------------------------------------------------------------------
# LLM + Embedding providers (singletons resolved by factories)
# ---------------------------------------------------------------------------


def get_llm() -> LLMProvider:
    return get_llm_provider()


def get_embedder() -> EmbeddingProvider:
    return get_embedding_provider()


LLM = Annotated[LLMProvider, Depends(get_llm)]
Embedder = Annotated[EmbeddingProvider, Depends(get_embedder)]

# ---------------------------------------------------------------------------
# Retrieval Services
# ---------------------------------------------------------------------------


def get_hybrid_retriever(
    chunk_repo: ChunkRepo,
    graph_repo: GraphRepo,
    embedder: Embedder,
    llm: LLM,
) -> HybridRetriever:
    return HybridRetriever(
        chunk_repo=chunk_repo,
        graph_repo=graph_repo,
        embedding_provider=embedder,
        llm_provider=llm,
    )


Retriever = Annotated[HybridRetriever, Depends(get_hybrid_retriever)]

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_session),
) -> User:
    """
    Extract and validate the JWT bearer token, then load the user.

    Raises HTTP 401 on any authentication failure.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = payload.get("sub")
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    return user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require superuser role."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required.",
        )
    return current_user


CurrentUser = Annotated[User, Depends(get_current_user)]
SuperUser = Annotated[User, Depends(get_current_superuser)]
