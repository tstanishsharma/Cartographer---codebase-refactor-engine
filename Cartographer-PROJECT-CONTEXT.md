# Cartographer — Project Context

> Paste this file into any AI coding tool (Claude Code, Cursor, ChatGPT, etc.) at the start of a session to re-establish full project context. Update the **Progress Log** at the bottom as you go.

---

## 1. What This Is

**Cartographer** is an autonomous code-understanding platform — a lightweight version of Cursor + Sourcegraph Cody. It ingests full repositories, builds an AST-derived knowledge graph, and uses multi-agent reasoning + hybrid RAG (vector + keyword + graph) to answer questions, estimate blast radius of changes, and autonomously propose/execute refactors in a sandboxed environment, producing PR-ready Git diffs.

**Target quality bar:** production-grade, modular, SOLID, Clean Architecture — not a prototype/MVP/demo.

---

## 2. Core Capabilities

- Ingest and parse complete repositories (Tree-sitter + Python AST)
- Build a knowledge graph: dependency, import, call, class, and function graphs
- Hybrid retrieval: vector (pgvector) + keyword + graph traversal, with re-ranking, context compression, parent-child and self-query retrieval
- Multi-agent reasoning pipeline (planning → retrieval → reasoning → edit → test → critique → reflection)
- Blast-radius estimation for proposed changes
- Isolated Docker sandbox: clone repo, create Git worktree, apply edits, run tests, rollback on failure, generate diff
- Chat interface with streaming, citations, and agent trace visibility
- Graph visualization and code explorer UI with Monaco editor

---

## 3. Tech Stack

**Frontend:** React, TypeScript, Vite, TailwindCSS, ShadCN, React Flow, Monaco Editor, React Query, Zustand

**Backend:** FastAPI, Python 3.12+, LangGraph, LangChain, Pydantic AI (where useful), SQLAlchemy 2, Alembic, PostgreSQL, Redis, pgvector, Docker, Docker Compose, Nginx

**Auth:** JWT, GitHub OAuth

**LLMs:** Claude, GPT-4.1, OpenAI-compatible APIs, Ollama fallback

**Embeddings:** OpenAI text-embedding-3-large, BGE, Nomic Embed

**Vector DB:** pgvector

**Parsing:** Tree-sitter, Python AST, GitPython

**Sandbox:** Isolated Docker container per session

**Observability:** OpenTelemetry, Prometheus, Grafana, Structlog

---

## 4. Architectural Principles

- SOLID principles, Clean Architecture, Repository Pattern, Dependency Injection
- Type hints everywhere; async where appropriate
- Every module independently testable
- Prompts are configurable, never hardcoded
- Every file documents its own purpose
- No merging/removing agents unless truly required; no swapping Graph RAG for plain RAG; no swapping LangGraph for simple chains

---

## 5. Agents (all required)

Each agent needs: **Prompt, Responsibilities, Tools, State, Memory, Failure Recovery, Retries, Streaming, Metrics.**

1. **Planner Agent** — decomposes user request into a task plan
2. **Retriever Agent** — hybrid retrieval (vector + keyword + graph)
3. **Reasoning Agent** — synthesizes retrieved context into an answer/plan
4. **Blast Radius Agent** — estimates impact of a proposed change across the graph
5. **Code Edit Agent** — generates concrete code edits
6. **Test Runner Agent** — executes tests in the sandbox
7. **Critic Agent** — reviews edits/output for correctness and quality
8. **Memory Agent** — manages long-term/session memory
9. **Supervisor Agent** — orchestrates agent handoffs (LangGraph)
10. **Reflection Agent** — evaluates failures and triggers retry/replan loops

---

## 6. Graph RAG Pipeline

**Graph construction:** AST parsing → dependency graph, import graph, call graph, class graph, function graph → metadata extraction → recursive graph traversal

**Retrieval:** hybrid (vector + keyword + graph) → re-ranking → context compression → parent-child retrieval → self-query retrieval

**End-to-end RAG pipeline:** repo ingestion → file parsing → chunk generation → metadata extraction → embedding generation → vector storage (pgvector) → graph storage → hybrid retrieval → prompt assembly → context compression → response generation → citation generation

---

## 7. Sandbox Requirements

Isolated Docker sandbox that can: clone repositories, create Git worktrees, execute edits, run tests, roll back failures, generate a Git diff, and return execution logs.

---

## 8. Frontend Pages

Dashboard · Repository Management · Repository Graph · Repository Explorer · Chat · Agent Trace · Blast Radius · Diff Viewer · Test Results · Settings · Authentication

**Must include:** dark mode, streaming responses, code syntax highlighting, real-time logs, graph visualization, Monaco editor, polished animations.

---

## 9. Database & API

- Complete SQLAlchemy 2 models + Alembic migrations + indexes
- pgvector schema + graph schema
- Full REST API with OpenAPI docs, request/response validation, JWT + GitHub OAuth auth, streaming endpoints

---

## 10. DevOps & Testing

**DevOps:** Dockerfiles, docker-compose, Nginx config, env configs, GitHub Actions CI/CD, pre-commit hooks, linting, formatting

**Testing:** unit, integration, agent, RAG, API, frontend, and end-to-end tests

**Docs to produce:** README, architecture doc, API doc, deployment guide, developer guide, contribution guide

---

## 11. Build Order (Phased)

Work through these phases one at a time. After each phase: review, refactor if needed, confirm architectural consistency before moving on.

- [x] **Phase 1** — Complete software architecture (folder structure, module boundaries, data flow diagrams)
- [x] **Phase 2** — Backend (FastAPI app, DB models, migrations, core services)
- [ ] **Phase 3** — Frontend (React app shell, pages, state management)
- [ ] **Phase 4** — Graph RAG (parsing, graph construction, hybrid retrieval)
- [ ] **Phase 5** — Agents (LangGraph orchestration, all 10 agents)
- [ ] **Phase 6** — Sandbox (Docker isolation, worktrees, test execution, diffs)
- [ ] **Phase 7** — Tests (unit → integration → e2e)
- [ ] **Phase 8** — Deployment (Docker Compose, Nginx, CI/CD)
- [ ] **Phase 9** — Documentation

---

## 12. Progress Log

_Update this section each session so future AI sessions know exactly where things stand._

| Date | Phase | What was done | Open questions / next step |
|------|-------|----------------|------------------------------|
| 2026-07-10 | Phase 1 | Complete architecture scaffolding: `.env.example`, `docker-compose.yml`, backend `pyproject.toml`, `Dockerfile`, `alembic.ini`, all 9 SQLAlchemy ORM models (User, Repository, CodeChunk, Embedding, GraphNode, GraphEdge, AgentRun, ChatSession, SandboxJob), all 5 DB repositories (BaseRepository + UserRepo, RepositoryRepo, ChunkRepo, GraphRepo, AgentRepo), `LLMProvider` ABC + 3 providers (Anthropic, OpenAI, Ollama), `EmbeddingProvider` ABC + 3 providers (OpenAI, BGE, Nomic), both factories, Redis service, 8 FastAPI routers (health, auth, repositories, chat, agents, graph, sandbox, blast_radius), FastAPI `deps.py`, Alembic `env.py`, `AgentState` TypedDict, `BaseAgent`, 10 YAML prompt files, frontend `package.json`/`vite.config.ts`/`tailwind.config.ts`/`index.html`, global CSS design system, `main.tsx`/`App.tsx`, Zustand auth store, axios+SSE API client, TypeScript types, 11 page stubs, Layout + Sidebar, pre-commit hooks, GitHub Actions CI, sandbox Dockerfile, Nginx config, Prometheus config, PostgreSQL init SQL. | Proceed to Phase 2 — full backend service implementations (ingestion, Graph RAG retrieval, complete service layer). |
| 2026-07-10 | Phase 2 | Full backend service implementations: AST parsing (`ast_parser.py`), graph construction (`graph_builder.py`), repository clone service (`clone_service.py`), file scanning (`file_scanner.py`), AST-aware chunking (`chunk_service.py`), embeddings (`embedding_service.py`), ingestion worker (`ingestion_orchestrator.py`), auth service (`auth_service.py`), hybrid retrieval pipeline (`vector_retriever.py`, `keyword_retriever.py`, `graph_retriever.py`, `hybrid_retriever.py`, `reranker.py`, `context_compressor.py`, `parent_child_retriever.py`), `alembic` initial migration. | Proceed to Phase 3 — Frontend implementation (React app shell, pages, state management). |

---

## 13. How to Use This File

1. Start a new AI coding session (Claude Code, Cursor, etc.)
2. Paste or attach this file as context
3. Say which phase you're working on and paste the current state of relevant code
4. Ask the AI to continue from the last entry in the Progress Log
5. Update the Progress Log before ending the session
