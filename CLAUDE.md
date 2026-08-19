# CartoGrapher — CLAUDE.md (Session Memory)

> Read this file first. It records what this project is, its architecture, current
> verified state, and the exact fixes already applied so future sessions don't
> redo or undo work. The product vision/roadmap lives in
> `Cartographer-PROJECT-CONTEXT.md` — this file is the **current on-the-ground state**.

---

## 1. What This Is

CartoGrapher is a **code-intelligence platform** (a lightweight Cursor/Sourcegraph-Cody).
It ingests GitHub repos, builds an AST-derived knowledge graph (symbols + cross-file
dependencies), chunks code into pgvector for hybrid RAG, and runs a LangGraph
multi-agent pipeline to answer questions, estimate change blast-radius, and run code
in an isolated Docker sandbox.

**Tech stack:** FastAPI · SQLAlchemy 2 (async) · Alembic · PostgreSQL+pgvector · Redis ·
Celery · LangGraph/LangChain · Tree-sitter · Docker Compose · Nginx · Prometheus/Grafana ·
React 18 + Vite + TS · React Flow · Monaco · React Query · Zustand.

## 2. Security (important)

- `.env` contains **real secrets** (OpenAI key `sk-proj-…`, `JWT_SECRET_KEY`, `SECRET_KEY`).
  It is gitignored. **Never commit it, never echo its contents.**
- Only `.env.example` is committed (redacted placeholder values).

## 3. Current Verified State (as of 2026-08-04)

The stack runs end-to-end via Docker Compose. All services healthy.

| Service | Port | Notes |
|---|---|---|
| backend (FastAPI) | 8000 | API + Prometheus metrics |
| frontend (Vite) | 5173 | dev server, hot reload |
| postgres+pgvector | 5432 | |
| redis | 6379 | |
| worker (Celery) | — | ingestion jobs |
| nginx | 80 | `--profile proxy` |
| prometheus | 9091 (host) | `--profile monitoring` |
| grafana | 3001 | `--profile monitoring`, provisioned datasource |

**Test login:** `test@example.com` / `testpass123`.

**Test repos in DB:** `click` (5bec4d84-44a3-4069-80ae-1f735e7f2e85, re-ingested with
679 nodes / 856 real edges), `Hello-World` (afaf76a6-29db-43c9-9827-56ce7c17cbe6).

**Frontend build passes clean** (`npm run build`). All 4 main pages wired to real APIs:
- **Repository Graph** — BFS layered layout, node click expands neighbors, search filter.
- **Repository Explorer** — file tree + Monaco viewer served from stored chunks.
- **Blast Radius** — real BFS over incoming edges, risk scoring (LOW<0.3/MEDIUM<0.6/HIGH).
- **Dashboard** — live repo/chunk/node/edge stats.

**Chat works through the full SSE pipeline** (agent trace streams: intent → retrieval →
reasoning → memory), persisted to backend sessions.

### ⚠️ Known external blocker
**OpenAI API key is out of quota** (HTTP 429 `insufficient_quota`). Consequences:
- Chat's final LLM answer fails at the last step (agent pipeline itself runs fine).
- Embeddings fail at ingestion time (new repo ingestion that needs embeddings is affected).
This is a billing issue on the OpenAI account, **not a code bug**. Re-verify once the
quota is topped up. (`.env` `OPENAI_API_KEY`.)

## 4. Key Architecture Decisions & Conventions

- **Repo pattern + DI:** `backend/app/db/repositories/*_repo.py` are injected via
  FastAPI `deps.py` (e.g. `get_sandbox_job_repo`). Sandbox router commits via
  `job_repo._session.commit()`.
- **Tree-sitter parsers:** `tree_sitter_languages` umbrella package is NOT installed.
  `backend/app/utils/tree_sitter.py` `get_parser(language)` falls back to individual
  grammar wheels via a module map (python→`tree_sitter_python`, tsx→`language_tsx`, …).
  AST parsers must use this shared helper — NOT a local `_get_parser` that silently
  falls back to stdlib.
- **Graph edges:** types are `defines`, `imports`, `inherits` (no `calls`). Import/inherit
  targets are resolved by qualified name — exact match, then unique suffix match
  (`q.endswith("." + target)`) in `graph_builder.resolve_target()`. Relative imports
  resolved in `ast_parser._resolve_module_ref`.
- **Blast radius** BFS over `graph_repo.get_neighbors(id, direction="incoming")`
  (dependents), max 4 hops. Risk = `min(1.0, n*0.15 + files*0.2 + depth*0.1)`.
- **Sandbox** lifecycle: queued→initializing→running→testing→completed/failed, persisted
  to `sandbox_jobs` (columns include worktree_path, code_edits, test_command, exit_code).
- **Chat SSE events:** `agent_trace`, `token`, `done`, `error`. Frontend
  `createSSEConnection` (in `frontend/src/api/client.ts`) dispatches these and accepts an
  `onAgentState` callback + request `body`. Backend routes:
  `POST /api/v1/chat/sessions` (`{title?, repository_id?}`) →
  `POST /api/v1/chat/sessions/{id}/message` (`{content, repository_id?}`).
- **Health:** readiness is `/api/v1/health/ready` (not `/health/ready`).
- **Frontend types:** React Flow v11 — use `useNodesState<FlowNodeData>()` and
  `Node<FlowNodeData>`; build `Edge` objects explicitly in `onConnect` (TS null-narrowing).

## 5. Fixes Already Applied (do not re-apply or regress)

1. Tree-sitter parser fallback → shared `app/utils/tree_sitter.py` helper.
2. Missing `imports`/`inherits` edges → qualified-name + suffix resolution in
   GraphBuilder + `_resolve_module_ref`.
3. DELETE repo →500 (ORM ahead of schema) → hand-written Alembic migrations:
   - `20260804_0001_9f3c2a1d5e40` — sandbox_jobs 5 cols (worktree_path, code_edits JSONB,
     test_command, exit_code, started_at).
   - `20260803_1955_02c3ec1a3c88` — agent_runs.citations, agent_runs.error_message,
     chat_sessions.memory.
   - (`20260720_1852_b7dc960a98fb` — chunks start_byte/end_byte, pre-existing.)
   ⚠️ Avoid re-running `alembic revision --autogenerate`: it produces noisy risky diffs
   (embedding vector-dim/index changes). Hand-write migrations when models drift.
4. Blast radius, sandbox, files/chunks, graph, neighbors endpoints — rewritten from stubs.
5. Frontend pages + API hooks (`frontend/src/api/{graph,explorer,blastRadius}.ts`) wired.
6. Chat wiring (wrong URL, no body, local-only sessions) → backend session created on
   first message; SSE streams to correct route with body; agent-state rendered live.
7. `docker-compose.yml` — removed obsolete `version:` key.
8. Grafana provisioned datasource at
   `infra/monitoring/grafana/provisioning/datasources/prometheus.yml`.

## 6. Run Locally

```bash
# from repo root
docker compose up -d --build
docker compose logs -f backend          # tail API logs
# API:   http://localhost:8000  (docs: /docs)
# UI:    http://localhost:5173
# optional: docker compose --profile monitoring up -d   # prometheus + grafana
```

Frontend-only dev without Docker: `cd frontend && npm install && npm run dev`
(VITE_API_BASE_URL defaults to http://localhost:8000).

## 7. Current Uncommitted Work

`git status` shows the full set of fixes from the 2026-08-04 session (backend services,
migrations, docker-compose, all frontend page/API rewrites, infra/grafana) — not yet
committed. **On the next session, decide with the user whether to commit** (suggest a
logical commit per area, e.g. backend-fixes / frontend-wiring / infra / migrations).

## 8. What's Left vs. the Roadmap (Cartographer-PROJECT-CONTEXT.md)

Phases 1–2 are marked done in the roadmap; the current build effectively covers
Phases 2–8 (backend services, frontend pages, Graph RAG, LangGraph agents, sandbox,
Docker deploy). Outstanding gaps if the user wants to push further:
- **OpenAI quota** must be resolved before chat answers / new embeddings work (blocker).
- **Tests** (Phase 7) — unit/integration/e2e coverage is sparse.
- **Docs** (Phase 9) — README exists; architecture/API/deployment/contributor guides pending.
- GitHub OAuth login (JWT email/password works today).
- Agent Trace page, Diff Viewer, Test Results pages exist as stubs; Chat uses inline
  agent-state display instead.
- Re-verify full ingestion on a fresh repo once embeddings quota is restored.

## 9. Memory

Session/project notes are also kept in
`C:\Users\Rishit\.claude\projects\C--Users-Rishit-Desktop-PROJECTS-CartoGrapher\memory\`
(see `MEMORY.md` index). Update `Cartographer-PROJECT-CONTEXT.md`'s Progress Log at the
end of each session.
