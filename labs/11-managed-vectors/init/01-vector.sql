-- Runs once, when the pg_data volume is created (docker-entrypoint-initdb.d).
CREATE EXTENSION IF NOT EXISTS vector;
SELECT extversion AS pgvector_version FROM pg_extension WHERE extname = 'vector';
