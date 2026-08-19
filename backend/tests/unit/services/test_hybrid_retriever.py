import uuid

import pytest

from app.db.models.chunk import CodeChunk
from app.db.models.graph_node import GraphNode
from app.services.retrieval.hybrid_retriever import HybridRetriever


@pytest.fixture
def mock_chunk_repo(mocker):
    repo = mocker.Mock()
    # Mock vector search
    repo.vector_search = mocker.AsyncMock(
        return_value=[
            (
                CodeChunk(
                    id=uuid.uuid4(),
                    file_path="main.py",
                    content="def main(): pass",
                    start_line=1,
                    end_line=2,
                    chunk_metadata={"function": "main"},
                ),
                0.95,
            )
        ]
    )
    # Mock keyword search
    repo.keyword_search = mocker.AsyncMock(
        return_value=[
            CodeChunk(
                id=uuid.uuid4(),
                file_path="auth.py",
                content="class Auth:",
                start_line=1,
                end_line=5,
                chunk_metadata={"class": "Auth"},
            )
        ]
    )
    repo.get_by_file = mocker.AsyncMock(
        return_value=[
            CodeChunk(
                id=uuid.uuid4(),
                file_path="auth.py",
                content="def verify_token(): pass",
                start_line=10,
                end_line=15,
                chunk_metadata={"function": "verify_token"},
            )
        ]
    )
    repo.get_by_id = mocker.AsyncMock(
        return_value=CodeChunk(
            id=uuid.uuid4(),
            file_path="main.py",
            content="def main(): pass",
            start_line=1,
            end_line=2,
            chunk_metadata={"function": "main"},
        )
    )
    return repo


@pytest.fixture
def mock_graph_repo(mocker):
    repo = mocker.Mock()
    # Mock graph traversal
    repo.get_neighbors = mocker.AsyncMock(
        return_value=[
            GraphNode(
                id=uuid.uuid4(),
                name="verify_token",
                node_type="function",
                file_path="auth.py",
                start_line=10,
                end_line=15,
            )
        ]
    )
    repo.get_by_repository = mocker.AsyncMock(
        return_value=[
            GraphNode(
                id=uuid.uuid4(),
                name="auth",
                node_type="module",
                file_path="auth.py",
                start_line=1,
                end_line=50,
            )
        ]
    )
    return repo


@pytest.mark.asyncio
async def test_hybrid_retrieval(mock_chunk_repo, mock_graph_repo, mock_llm, mock_embedding):
    retriever = HybridRetriever(
        llm_provider=mock_llm,
        embedding_provider=mock_embedding,
        chunk_repo=mock_chunk_repo,
        graph_repo=mock_graph_repo,
    )

    results = await retriever.retrieve(
        query="How does auth work?", repository_id=uuid.uuid4(), top_k_final=5
    )

    # Verify we got chunks back
    assert len(results) > 0
    # Verify reciprocal rank fusion sorted them
    assert "file_path" in results[0]
    assert "content" in results[0]

    # Verify repos were called
    mock_chunk_repo.vector_search.assert_called_once()
    mock_chunk_repo.keyword_search.assert_called_once()
