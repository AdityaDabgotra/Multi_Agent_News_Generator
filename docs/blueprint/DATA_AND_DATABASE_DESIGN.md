# DATA_AND_DATABASE_DESIGN.md

Companion to `MASTER_SYSTEM_BLUEPRINT.md` sections 7 and 11. PostgreSQL 16 with extensions `pgvector`, `pg_trgm`, `pgcrypto`, `citext`, and `btree_gist`. Claude Code MUST turn this file into Alembic migrations (one baseline migration per logical group, then incremental).

## 1. Conventions

- Primary keys: `uuid`, generated in application as UUIDv7 (time-ordered); DB default `gen_random_uuid()` as fallback.
- Timestamps: `timestamptz`, UTC. `created_at default now()`.
- Embedding dimension is a deployment constant `EMBED_DIM` (set in Phase 0 after model choice). The DDL below uses `1024` as a placeholder; migration templating MUST read `EMBED_DIM` and store the model name in `system_settings`.
- Large text/blobs live in object storage; DB keeps `*_ref` and `sha256`.
- Append-only tables are marked (A). They have triggers that reject UPDATE and DELETE except via retention jobs running as a dedicated role.
- Soft deletion via `deleted_at` only where stated.
- All enums are PostgreSQL enum types, versioned by migrations.

## 2. Enums

```sql
CREATE TYPE user_role AS ENUM ('admin','editor','analyst','viewer');
CREATE TYPE source_type AS ENUM ('primary_official','primary_original_reporting','secondary','aggregator','fact_check','social','academic');
CREATE TYPE directness AS ENUM ('primary','direct_secondary','indirect');
CREATE TYPE stance AS ENUM ('supports','refutes','context','irrelevant');
CREATE TYPE claim_type AS ENUM ('event','statistic','quote','attribution','causal','prediction','opinion','definition');
CREATE TYPE impact AS ENUM ('low','medium','high');
CREATE TYPE verdict_label AS ENUM ('strongly_supported','supported','partially_supported','contradicted','mixed_evidence','insufficient_evidence','unverified','outdated_or_misleading_context');
CREATE TYPE adversarial_outcome AS ENUM ('none_found','found_refutation','found_caveat','not_run');
CREATE TYPE task_status AS ENUM ('queued','leased','running','succeeded','partial','failed_retryable','failed_permanent','cancelled','dead_letter');
CREATE TYPE investigation_status AS ENUM ('created','running','paused_human','completed','partial','failed','cancelled');
CREATE TYPE article_status AS ENUM ('draft','audited','pending_human','approved','published','retracted');
CREATE TYPE event_status AS ENUM ('developing','stable','closed');
CREATE TYPE verification_status AS ENUM ('quote_verified','unverified','rejected');
```

## 3. Identity and configuration

```sql
CREATE TABLE users (
  user_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email citext UNIQUE NOT NULL,
  display_name text NOT NULL,
  role user_role NOT NULL DEFAULT 'viewer',
  password_hash text,                       -- null when external IdP
  idp_subject text UNIQUE,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_login_at timestamptz
);

CREATE TABLE system_settings (
  key text PRIMARY KEY,
  value jsonb NOT NULL,
  updated_by uuid REFERENCES users(user_id),
  updated_at timestamptz NOT NULL DEFAULT now()
);  -- includes embed_model, embed_dim, publish_requires_human, kill_switch

CREATE TABLE model_configs (
  model_config_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role text NOT NULL,                        -- e.g. 'claim_extract'
  priority int NOT NULL,                     -- fallback order
  provider text NOT NULL,
  model_id text NOT NULL,
  params jsonb NOT NULL DEFAULT '{}',
  max_context int,
  enabled boolean NOT NULL DEFAULT true,
  family text NOT NULL,                      -- for different-family judge rules
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (role, priority)
);

CREATE TABLE audit_log (                    -- (A)
  audit_id bigserial PRIMARY KEY,
  at timestamptz NOT NULL DEFAULT now(),
  actor_user_id uuid REFERENCES users(user_id),
  actor_kind text NOT NULL,                  -- 'user','system','agent'
  action text NOT NULL,
  object_type text NOT NULL,
  object_id text,
  before_hash text, after_hash text,
  details jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX ON audit_log (at DESC);
CREATE INDEX ON audit_log (object_type, object_id);
```

## 4. Sources, articles, events

```sql
CREATE TABLE sources (
  source_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  domain text NOT NULL UNIQUE,
  homepage_url text,
  feed_urls text[] NOT NULL DEFAULT '{}',
  source_type source_type NOT NULL,
  country char(2), languages text[] NOT NULL DEFAULT '{}',
  owner_entity_id uuid,                      -- FK added after entities
  ownership_group text,                      -- normalized group key used by A06
  fetch_policy jsonb NOT NULL,               -- {allow:bool, robots:'respect', rps:0.2, snapshot:true, tos_reviewed_at, tos_notes}
  poll_interval_s int NOT NULL DEFAULT 900,
  enabled boolean NOT NULL DEFAULT false,    -- cannot enable without tos_reviewed_at
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (NOT enabled OR (fetch_policy ? 'tos_reviewed_at'))
);
CREATE INDEX ON sources (ownership_group);

CREATE TABLE source_profiles (               -- versioned credibility profiles
  profile_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id uuid NOT NULL REFERENCES sources(source_id),
  topic text NOT NULL DEFAULT 'general',
  version int NOT NULL,
  dimensions jsonb NOT NULL,                 -- {D1:{score,features,asof}, ...}
  beta_alpha real NOT NULL DEFAULT 2, beta_beta real NOT NULL DEFAULT 2,
  reliability real NOT NULL CHECK (reliability BETWEEN 0 AND 1),
  low_information boolean NOT NULL DEFAULT true,
  override_by uuid REFERENCES users(user_id), override_reason text,
  computed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_id, topic, version)
);

CREATE TABLE articles (
  article_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id uuid NOT NULL REFERENCES sources(source_id),
  url text NOT NULL,
  canonical_url text NOT NULL,
  title text NOT NULL,
  author text,
  published_at timestamptz,
  modified_at timestamptz,
  fetched_at timestamptz NOT NULL,
  lang text NOT NULL,
  text_ref text NOT NULL, text_sha256 char(64) NOT NULL,   -- extracted text in object store
  raw_ref text, raw_sha256 char(64),
  content_hash char(64) NOT NULL,
  simhash bigint,
  embedding vector(1024),
  dup_of uuid REFERENCES articles(article_id),
  event_id uuid,                              -- FK added after events
  extraction_quality real,
  UNIQUE (canonical_url),
  UNIQUE (source_id, content_hash)
);
CREATE INDEX ON articles (published_at DESC);
CREATE INDEX ON articles (event_id);
CREATE INDEX ON articles USING hnsw (embedding vector_cosine_ops);
CREATE INDEX articles_title_trgm ON articles USING gin (title gin_trgm_ops);

CREATE TABLE events (
  event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  status event_status NOT NULL DEFAULT 'developing',
  impact impact NOT NULL DEFAULT 'low',
  first_seen_at timestamptz NOT NULL,
  last_updated_at timestamptz NOT NULL,
  centroid vector(1024),
  version int NOT NULL DEFAULT 1,            -- bumps on material change, invalidates verdict reuse
  merged_into uuid REFERENCES events(event_id),
  created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE articles ADD FOREIGN KEY (event_id) REFERENCES events(event_id);
CREATE INDEX ON events (status, last_updated_at DESC);
CREATE INDEX ON events USING hnsw (centroid vector_cosine_ops);

CREATE TABLE event_links (
  event_id uuid REFERENCES events(event_id),
  related_event_id uuid REFERENCES events(event_id),
  relation text NOT NULL,                    -- 'causes','part_of','follow_up'
  evidence_ids uuid[] NOT NULL DEFAULT '{}',
  PRIMARY KEY (event_id, related_event_id, relation)
);
```

## 5. Entities and knowledge graph (relational graph-lite, bitemporal)

```sql
CREATE TABLE entities (
  entity_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind text NOT NULL,                        -- person, org, place, law, product, ...
  canonical_name text NOT NULL,
  wikidata_id text,
  description text,
  embedding vector(1024),
  is_private_person boolean NOT NULL DEFAULT false,   -- triggers high-impact handling
  created_at timestamptz NOT NULL DEFAULT now(),
  merged_into uuid REFERENCES entities(entity_id)
);
CREATE INDEX ON entities USING gin (canonical_name gin_trgm_ops);
CREATE INDEX ON entities (wikidata_id) WHERE wikidata_id IS NOT NULL;
ALTER TABLE sources ADD FOREIGN KEY (owner_entity_id) REFERENCES entities(entity_id);

CREATE TABLE entity_aliases (
  entity_id uuid REFERENCES entities(entity_id),
  alias text NOT NULL, lang text,
  PRIMARY KEY (entity_id, alias)
);

CREATE TABLE article_entities (
  article_id uuid REFERENCES articles(article_id),
  entity_id uuid REFERENCES entities(entity_id),
  mentions int NOT NULL DEFAULT 1, salience real,
  PRIMARY KEY (article_id, entity_id)
);

CREATE TABLE facts (                         -- bitemporal semantic memory
  fact_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_entity_id uuid NOT NULL REFERENCES entities(entity_id),
  predicate text NOT NULL,
  object_entity_id uuid REFERENCES entities(entity_id),
  object_value jsonb,
  valid_range tstzrange NOT NULL,            -- when true in the world
  recorded_at timestamptz NOT NULL DEFAULT now(),
  superseded_at timestamptz,                 -- when Meridian stopped believing it
  evidence_ids uuid[] NOT NULL,
  derived_from_verification uuid,
  created_by text NOT NULL,                  -- agent id/version or 'human:<id>'
  conflict_group uuid,
  CHECK (object_entity_id IS NOT NULL OR object_value IS NOT NULL)
);
CREATE INDEX ON facts (subject_entity_id, predicate);
CREATE INDEX ON facts USING gist (valid_range);
-- Current facts: WHERE superseded_at IS NULL AND upper_inf(valid_range)
```

## 6. Claims, evidence, lineage, verification

```sql
CREATE TABLE claims (
  claim_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  article_id uuid NOT NULL REFERENCES articles(article_id),
  event_id uuid REFERENCES events(event_id),
  parent_claim_id uuid REFERENCES claims(claim_id),
  text text NOT NULL CHECK (char_length(text) BETWEEN 10 AND 600),
  span_start int NOT NULL, span_end int NOT NULL CHECK (span_end > span_start),
  claim_type claim_type NOT NULL,
  check_worthiness real NOT NULL CHECK (check_worthiness BETWEEN 0 AND 1),
  verifiable boolean NOT NULL,
  non_verifiable_reason text,
  needs_context boolean NOT NULL DEFAULT false,
  impact impact NOT NULL,
  reference_period tstzrange,
  embedding vector(1024),
  canonical_claim_id uuid REFERENCES claims(claim_id),   -- equivalence cluster representative
  claim_version int NOT NULL DEFAULT 1,
  created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON claims (article_id);
CREATE INDEX ON claims (event_id);
CREATE INDEX ON claims USING hnsw (embedding vector_cosine_ops);

CREATE TABLE claim_entities (
  claim_id uuid REFERENCES claims(claim_id),
  entity_id uuid REFERENCES entities(entity_id),
  PRIMARY KEY (claim_id, entity_id)
);

CREATE TABLE evidence_snapshots (            -- (A)
  snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  url text NOT NULL,
  retrieved_at timestamptz NOT NULL,
  http_status int, content_type text,
  text_ref text NOT NULL, text_sha256 char(64) NOT NULL,
  raw_ref text, raw_sha256 char(64),
  tool text NOT NULL, query text,
  UNIQUE (text_sha256, url)
);

CREATE TABLE origin_groups (
  origin_group_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  investigation_id uuid NOT NULL,
  claim_id uuid NOT NULL REFERENCES claims(claim_id),
  root_evidence_id uuid,
  ownership_merged boolean NOT NULL DEFAULT false,
  circular_sourcing boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE evidence (                      -- (A) append-only; corrections supersede
  evidence_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  claim_id uuid NOT NULL REFERENCES claims(claim_id),
  investigation_id uuid NOT NULL,
  source_id uuid NOT NULL REFERENCES sources(source_id),
  article_id uuid REFERENCES articles(article_id),
  snapshot_id uuid NOT NULL REFERENCES evidence_snapshots(snapshot_id),
  url text NOT NULL, publisher text NOT NULL, author text,
  published_at timestamptz, event_date timestamptz,
  retrieved_at timestamptz NOT NULL,
  excerpt text NOT NULL CHECK (char_length(excerpt) <= 600),
  excerpt_start int NOT NULL, excerpt_end int NOT NULL,
  evidence_type source_type NOT NULL,
  directness directness NOT NULL,
  stance stance NOT NULL,
  stance_confidence real CHECK (stance_confidence BETWEEN 0 AND 1),
  attribution jsonb,                         -- {attributed_to, relation}
  origin_group_id uuid REFERENCES origin_groups(origin_group_id),
  profile_id uuid REFERENCES source_profiles(profile_id),
  extraction_method text NOT NULL,
  verification_status verification_status NOT NULL,
  supersedes_id uuid REFERENCES evidence(evidence_id),
  created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (excerpt_end > excerpt_start),
  CHECK (verification_status <> 'quote_verified' OR snapshot_id IS NOT NULL)
);
CREATE INDEX ON evidence (claim_id, stance);
CREATE INDEX ON evidence (origin_group_id);
-- Quote verification invariant is enforced by service code AND a nightly audit job
-- that re-checks excerpt == snapshot_text[excerpt_start:excerpt_end].

CREATE TABLE derivation_edges (
  from_evidence_id uuid REFERENCES evidence(evidence_id),   -- derived document
  to_evidence_id uuid REFERENCES evidence(evidence_id),     -- origin document
  relation text NOT NULL,                    -- 'text_reuse','attribution','link','ownership'
  confidence real NOT NULL,
  PRIMARY KEY (from_evidence_id, to_evidence_id, relation)
);

CREATE TABLE evidence_conflicts (
  claim_id uuid REFERENCES claims(claim_id),
  a_evidence_id uuid REFERENCES evidence(evidence_id),
  b_evidence_id uuid REFERENCES evidence(evidence_id),
  conflict_kind text NOT NULL,               -- 'direct','temporal','definitional','source_error','unresolved'
  note text,
  PRIMARY KEY (a_evidence_id, b_evidence_id)
);

CREATE TABLE verifications (                 -- (A) versioned verdicts
  verification_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  claim_id uuid NOT NULL REFERENCES claims(claim_id),
  investigation_id uuid NOT NULL,
  claim_version int NOT NULL,
  label verdict_label NOT NULL,
  rule_id text NOT NULL,
  support_mass real NOT NULL, refute_mass real NOT NULL, coverage real NOT NULL,
  n_support_groups int NOT NULL, n_refute_groups int NOT NULL,
  has_primary_support boolean NOT NULL, has_primary_refute boolean NOT NULL,
  calibrated_probability real, calibration_version text,
  adversarial adversarial_outcome NOT NULL,
  adversarial_queries text[] NOT NULL DEFAULT '{}',
  missing_information text[] NOT NULL DEFAULT '{}',
  key_evidence_ids uuid[] NOT NULL, refuting_evidence_ids uuid[] NOT NULL DEFAULT '{}',
  justification text NOT NULL,
  policy_version text NOT NULL, pipeline_version text NOT NULL,
  event_version int,
  computed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON verifications (claim_id, computed_at DESC);
CREATE VIEW current_verifications AS
  SELECT DISTINCT ON (claim_id) * FROM verifications ORDER BY claim_id, computed_at DESC;
```

## 7. Agents, tasks, execution

```sql
CREATE TABLE investigations (
  investigation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_by uuid REFERENCES users(user_id),
  kind text NOT NULL,                        -- 'event','article','claim','viral','watch_trigger'
  input_ref jsonb NOT NULL,
  profile text NOT NULL,
  status investigation_status NOT NULL DEFAULT 'created',
  budget jsonb NOT NULL, usage jsonb NOT NULL DEFAULT '{}',
  pipeline_version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz, finished_at timestamptz,
  summary text
);

CREATE TABLE agent_tasks (
  task_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  investigation_id uuid NOT NULL REFERENCES investigations(investigation_id),
  parent_task_id uuid REFERENCES agent_tasks(task_id),
  agent_id text NOT NULL, agent_version text NOT NULL, prompt_version text,
  objective text NOT NULL,
  input_refs jsonb NOT NULL, params jsonb NOT NULL DEFAULT '{}',
  budget jsonb NOT NULL,
  status task_status NOT NULL DEFAULT 'queued',
  attempt int NOT NULL DEFAULT 0, max_attempts int NOT NULL DEFAULT 3,
  idempotency_key text NOT NULL,
  lease_owner text, lease_expires_at timestamptz, heartbeat_at timestamptz,
  available_at timestamptz NOT NULL DEFAULT now(),
  priority int NOT NULL DEFAULT 5,
  result jsonb, error jsonb,
  created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
  UNIQUE (agent_id, idempotency_key)
);
CREATE INDEX agent_tasks_claim ON agent_tasks (priority, available_at) WHERE status IN ('queued','failed_retryable');

CREATE TABLE agent_messages (                -- (A) full message log for audit
  message_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  investigation_id uuid NOT NULL, task_id uuid,
  direction text NOT NULL CHECK (direction IN ('in','out')),
  agent_id text NOT NULL, schema_version text NOT NULL,
  payload jsonb NOT NULL, payload_sha256 char(64) NOT NULL,
  at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON agent_messages (investigation_id, at);

CREATE TABLE tool_calls (                    -- (A)
  tool_call_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  investigation_id uuid, task_id uuid,
  tool text NOT NULL, tool_version text NOT NULL,
  args_sha256 char(64) NOT NULL, args_redacted jsonb,
  status text NOT NULL, http_status int,
  latency_ms int, bytes int, cost_usd numeric(10,6),
  error jsonb, at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE llm_calls (                     -- (A) usage and trace pointers (full prompts in Langfuse/object store)
  llm_call_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  investigation_id uuid, task_id uuid,
  role text NOT NULL, provider text NOT NULL, model_id text NOT NULL,
  prompt_name text NOT NULL, prompt_version text NOT NULL,
  tokens_in int, tokens_out int, latency_ms int, cost_usd numeric(10,6),
  outcome text NOT NULL, repair_attempts int NOT NULL DEFAULT 0,
  trace_id text, at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON llm_calls (investigation_id);

CREATE TABLE dead_letters (
  dead_letter_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id uuid NOT NULL REFERENCES agent_tasks(task_id),
  reason text NOT NULL, context jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  replayed_at timestamptz
);

CREATE TABLE outbox (                        -- transactional enqueue and notifications
  outbox_id bigserial PRIMARY KEY,
  topic text NOT NULL, payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), processed_at timestamptz
);

CREATE TABLE cache_entries (
  cache_key text PRIMARY KEY,                -- hash of (kind, normalized input, versions)
  kind text NOT NULL, value jsonb NOT NULL,
  expires_at timestamptz NOT NULL, hits int NOT NULL DEFAULT 0
);
CREATE INDEX ON cache_entries (expires_at);
```

LangGraph checkpoint tables are created by the library's Postgres checkpointer setup (version pinned in Phase 0); retention: delete checkpoints 30 days after investigation completion.

## 8. Generated articles, citations, feedback, monitoring

```sql
CREATE TABLE generated_articles (
  gen_article_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  story_key uuid NOT NULL,                   -- groups versions of the same story
  version int NOT NULL,
  event_id uuid REFERENCES events(event_id),
  investigation_id uuid REFERENCES investigations(investigation_id),
  genre text NOT NULL, headline text NOT NULL,
  unknowns text[] NOT NULL DEFAULT '{}',
  status article_status NOT NULL DEFAULT 'draft',
  model_ids text[] NOT NULL, prompt_versions jsonb NOT NULL,
  verdict_snapshot jsonb NOT NULL,           -- map claim_id -> verification_id used
  stale boolean NOT NULL DEFAULT false,
  correction_note text,
  approved_by uuid REFERENCES users(user_id), approved_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (story_key, version)
);

CREATE TABLE article_sentences (              -- (A) once article leaves draft
  gen_article_id uuid REFERENCES generated_articles(gen_article_id),
  idx int NOT NULL,
  kind text NOT NULL CHECK (kind IN ('claim','connective','attribution','uncertainty_note')),
  text text NOT NULL,
  claim_ids uuid[] NOT NULL DEFAULT '{}',
  evidence_ids uuid[] NOT NULL DEFAULT '{}',
  PRIMARY KEY (gen_article_id, idx),
  CHECK (kind <> 'claim' OR cardinality(claim_ids) > 0)   -- NFR-INT-01
);

CREATE TABLE citations (
  citation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  gen_article_id uuid NOT NULL, sentence_idx int NOT NULL,
  evidence_id uuid NOT NULL REFERENCES evidence(evidence_id),
  FOREIGN KEY (gen_article_id, sentence_idx) REFERENCES article_sentences(gen_article_id, idx),
  quote_exact boolean, nli_entailment real, number_match boolean,
  url_resolved boolean, check_status text NOT NULL,   -- 'pass','fail','borderline_judged'
  checked_by text NOT NULL, checked_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE audit_findings (                 -- A13 output
  finding_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  gen_article_id uuid NOT NULL REFERENCES generated_articles(gen_article_id),
  sentence_idx int, kind text NOT NULL, severity text NOT NULL,
  message text NOT NULL, suggestion text, acknowledged_by uuid REFERENCES users(user_id)
);

CREATE TABLE watches (
  watch_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL REFERENCES users(user_id),
  kind text NOT NULL,                        -- 'event','entity','topic','claim'
  target jsonb NOT NULL, rules jsonb NOT NULL,
  notify jsonb NOT NULL DEFAULT '{}',
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE feedback (
  feedback_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(user_id),
  object_type text NOT NULL, object_id uuid NOT NULL,
  rating text, comment text, proposed_label verdict_label,
  status text NOT NULL DEFAULT 'new',
  created_at timestamptz NOT NULL DEFAULT now()
);
```

## 9. Row-level security and roles

- DB roles: `meridian_app` (API), `meridian_worker`, `meridian_ingest`, `meridian_ro` (analytics), `meridian_retention` (only role allowed to delete from append-only tables).
- Append-only triggers on tables marked (A) raise on UPDATE/DELETE unless `current_user = 'meridian_retention'`.
- RLS on `feedback`, `watches`, `generated_articles` (viewer sees approved/published; editors see all).
- Workers MUST NOT have access to `users.password_hash`.

## 10. Retention and expiry

| Data | Policy |
|---|---|
| Raw HTML snapshots | 1 year (per source `fetch_policy` may shorten); then delete raw, keep extracted text and hash |
| Extracted text and evidence snapshots | Retained while referenced by any evidence or published article; otherwise 2 years |
| `agent_messages`, `tool_calls`, `llm_calls` | 18 months, then aggregate to daily summaries |
| LangGraph checkpoints | 30 days after completion |
| `cache_entries` | by `expires_at` (default 7 days retrieval cache, 24 h verdict cache) |
| `audit_log` | 7 years (configurable) |
| `generated_articles`, `verifications`, `evidence` metadata | permanent |
| PII | bylines only; user data deleted on request within 30 days (anonymize audit entries) |

## 11. Migration strategy

Alembic with linear history; one migration per logical change; every migration reversible except destructive retention steps (documented); `make migrate-check` runs up/down/up on a scratch DB in CI; embedding dimension change handled by a dedicated migration adding a new column, backfill job, swap, drop; schema version recorded in `system_settings.schema_version`; seed data (sources, impact policy) via idempotent seed scripts, not migrations.

## 12. Key query patterns (for index validation)

1. Next task: `SELECT ... FROM agent_tasks WHERE status IN ('queued','failed_retryable') AND available_at <= now() ORDER BY priority, available_at FOR UPDATE SKIP LOCKED LIMIT 1`.
2. Nearest events for new article: ANN on `events.centroid` within a time window, then entity overlap rerank.
3. Claim ledger for an event: `claims` join `current_verifications` by `event_id`.
4. As-of facts: `facts WHERE valid_range @> :t AND recorded_at <= :t AND (superseded_at IS NULL OR superseded_at > :t)`.
5. Evidence by group: `evidence WHERE claim_id = :c` grouped by `origin_group_id`.
