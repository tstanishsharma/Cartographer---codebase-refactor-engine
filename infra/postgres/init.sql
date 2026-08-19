-- =============================================================================
-- Cartographer — PostgreSQL Initialization Script
-- Runs once when the PostgreSQL container starts (if database doesn't exist)
-- =============================================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable full-text search dictionary
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Set default timezone
SET timezone = 'UTC';
