"""
Cartographer — Domain Exception Hierarchy.

All custom exceptions live here. FastAPI exception handlers in main.py
catch CartographerError and its subclasses and return appropriate HTTP responses.

Design:
    CartographerError (base)
    ├── AuthenticationError (401)
    ├── AuthorizationError (403)
    ├── NotFoundError (404)
    ├── ConflictError (409)
    ├── ValidationError (422)
    ├── ServiceUnavailableError (503)
    ├── IngestionError (500 / subclass)
    ├── RetrievalError (500 / subclass)
    ├── AgentError (500 / subclass)
    └── SandboxError (500 / subclass)
"""

from __future__ import annotations

from typing import Any


class CartographerError(Exception):
    """
    Base exception for all Cartographer domain errors.

    Attributes:
        message:    Human-readable error description.
        error_code: Machine-readable slug for the frontend (e.g. "repo_not_found").
        status_code: HTTP status code to return.
        detail:     Optional structured extra data.
    """

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        if error_code:
            self.error_code = error_code
        self.detail = detail


# ── 401 ───────────────────────────────────────────────────────────────────────
class AuthenticationError(CartographerError):
    """Raised when a request lacks valid credentials."""

    status_code = 401
    error_code = "authentication_required"


class InvalidTokenError(AuthenticationError):
    """Raised when a JWT token is invalid or expired."""

    error_code = "invalid_token"


# ── 403 ───────────────────────────────────────────────────────────────────────
class AuthorizationError(CartographerError):
    """Raised when an authenticated user lacks permission."""

    status_code = 403
    error_code = "forbidden"


# ── 404 ───────────────────────────────────────────────────────────────────────
class NotFoundError(CartographerError):
    """Raised when a requested resource does not exist."""

    status_code = 404
    error_code = "not_found"


class RepositoryNotFoundError(NotFoundError):
    error_code = "repository_not_found"


class ChunkNotFoundError(NotFoundError):
    error_code = "chunk_not_found"


class AgentRunNotFoundError(NotFoundError):
    error_code = "agent_run_not_found"


# ── 409 ───────────────────────────────────────────────────────────────────────
class ConflictError(CartographerError):
    """Raised on resource conflicts (e.g. duplicate repository URL)."""

    status_code = 409
    error_code = "conflict"


class RepositoryAlreadyExistsError(ConflictError):
    error_code = "repository_already_exists"


# ── 422 ───────────────────────────────────────────────────────────────────────
class CartographerValidationError(CartographerError):
    """Raised when domain-level validation fails (beyond Pydantic schema)."""

    status_code = 422
    error_code = "validation_error"


# ── 503 ───────────────────────────────────────────────────────────────────────
class ServiceUnavailableError(CartographerError):
    """Raised when a downstream service (LLM, DB, Redis) is unreachable."""

    status_code = 503
    error_code = "service_unavailable"


class LLMUnavailableError(ServiceUnavailableError):
    error_code = "llm_unavailable"


class EmbeddingUnavailableError(ServiceUnavailableError):
    error_code = "embedding_unavailable"


# ── 500 domain subclasses ─────────────────────────────────────────────────────
class IngestionError(CartographerError):
    """Raised during repository ingestion (parsing, chunking, embedding)."""

    error_code = "ingestion_error"


class RetrievalError(CartographerError):
    """Raised during hybrid retrieval pipeline failures."""

    error_code = "retrieval_error"


class AgentError(CartographerError):
    """Raised when an agent encounters an unrecoverable failure."""

    error_code = "agent_error"


class SandboxError(CartographerError):
    """Raised when the Docker sandbox encounters an error."""

    error_code = "sandbox_error"


class GraphBuildError(CartographerError):
    """Raised during knowledge graph construction failures."""

    error_code = "graph_build_error"


class EmbeddingError(CartographerError):
    """Raised when embedding generation fails."""

    error_code = "embedding_error"


class ProviderConfigurationError(CartographerError):
    """Raised when an LLM or embedding provider is misconfigured."""

    error_code = "provider_configuration_error"
