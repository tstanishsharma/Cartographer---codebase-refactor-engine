# Cartographer

**Cartographer** is an autonomous code understanding and mapping platform. It ingests software repositories, builds an intelligent context graph (using AST parsing and vector embeddings), and uses LLM-powered agents to help developers navigate, query, and refactor complex codebases.

## Core Features

- **Codebase Ingestion & AST Parsing**: Parses source code into Abstract Syntax Trees (ASTs) to understand dependencies, classes, and function structures.
- **Hybrid Retrieval System**: Combines graph-based traversal with semantic vector search (via `pgvector`) to find the most relevant code context.
- **Agentic Workflow**: Uses a LangGraph-orchestrated team of specialized agents (Planner, Retriever, Critic, Sandboxed Execution) to answer queries and plan code changes.
- **Sandboxed Execution**: Automatically runs tests and validates proposed code changes in an isolated, secure Docker environment.
- **Visual Graph & Editor**: Features a modern React frontend with ReactFlow for codebase visualization and Monaco Editor for seamless code viewing.
- **Blast Radius Analysis**: Identifies how a change in one component affects downstream dependencies before you write any code.

## Technology Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy (Async), LangChain, LangGraph, Tree-sitter (AST Parsing)
- **Database / Cache**: PostgreSQL (with `pgvector`), Redis
- **Frontend**: React 18, Vite, Tailwind CSS, ReactFlow, Zustand, Monaco Editor
- **Infrastructure**: Docker & Docker Compose

## Quickstart (Local Development)

The easiest way to run the entire stack locally is using Docker Compose.

### Prerequisites
- Docker & Docker Compose installed.
- (Optional) Anthropic / OpenAI API keys for the LLM agents.

### Running the Stack

1. **Clone the repository**
   ```bash
   git clone https://github.com/rizzit17/Cartographer.git
   cd Cartographer
   ```

2. **Configure Environment Variables**
   Create a `.env` file in the root directory based on `.env.example` and populate it with your LLM API keys and database configurations.

3. **Start the Application**
   ```bash
   docker-compose up --build -d
   ```
   This command spins up the following services:
   - **Frontend**: http://localhost:5173
   - **Backend API**: http://localhost:8000
   - **PostgreSQL Database**
   - **Redis Cache**
   - **Celery Worker**

4. **Run Database Migrations**
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

5. **Access the App**
   Open your browser and navigate to `http://localhost:5173`.

## Architecture Overview

Cartographer operates in two primary phases:
1. **Ingestion**: When a repository is linked, the backend pulls the code, parses it into an AST, extracts semantic chunks, and generates vector embeddings, persisting everything into a structured relational graph in PostgreSQL.
2. **Interaction**: When a user queries the codebase, the Orchestrator Agent routes the query through a pipeline that retrieves relevant code snippets, forms a plan, drafts code edits, and optionally verifies them in a secure Docker sandbox.

## License
MIT License
