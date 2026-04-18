-- Phase 2: pgvector embeddings + document metadata for RAG
-- Apply after 001_initial_schema.sql. Requires PostgreSQL with pgvector (Supabase includes it).

begin;

create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- Document metadata (filters for retrieval)
-- ---------------------------------------------------------------------------
alter table public.documents
  add column if not exists tags text[] not null default '{}'::text[];

alter table public.documents
  add column if not exists source_type text not null default 'upload';

comment on column public.documents.source_type is
  'Origin of content, e.g. upload, url, ticket_export — extend as needed.';

create index if not exists documents_tags_gin on public.documents using gin (tags);
create index if not exists documents_owner_source_idx on public.documents (owner_id, source_type);

-- ---------------------------------------------------------------------------
-- Chunk embeddings (OpenAI text-embedding-3-small = 1536 dims by default)
-- If you change model dimensions, alter column + rebuild indexes.
-- ---------------------------------------------------------------------------
alter table public.document_chunks
  add column if not exists embedding vector(1536);

comment on column public.document_chunks.embedding is
  'Dense embedding for similarity search. Dimension must match EMBEDDING_DIMENSIONS / OpenAI model.';

-- HNSW index for cosine distance queries (pgvector 0.5+)
create index if not exists document_chunks_embedding_hnsw
  on public.document_chunks
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

-- Filtered lookups while iterating a version
create index if not exists document_chunks_version_embedding_idx
  on public.document_chunks (document_version_id)
  where embedding is not null;

commit;
