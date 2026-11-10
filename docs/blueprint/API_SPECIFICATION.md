# API_SPECIFICATION.md

Companion to `MASTER_SYSTEM_BLUEPRINT.md` section 20. FastAPI generates OpenAPI from the Pydantic models in `src/meridian/schemas/` and `src/meridian/api/schemas/`. The generated `openapi.json` is the contract; this file defines intent, shapes and rules. The frontend client is generated from it.

## 1. Global rules

- Base path `/api/v1`. JSON UTF-8. Timestamps ISO 8601 UTC. IDs are UUIDs.
- **Auth:** `Authorization: Bearer <JWT>`. Access token TTL 15 min, refresh token rotation. Roles: `admin > editor > analyst > viewer`. Deny by default; each route declares `required_role`.
- **Pagination:** cursor-based: `?limit=50&cursor=<opaque>`; response `{items:[], next_cursor: str|null}`. Max limit 200.
- **Idempotency:** `POST` creating investigations or reports accepts `Idempotency-Key` header; replays return the original response.
- **Rate limits:** per user and per IP; `429` with `Retry-After`. Defaults: 60 req/min viewers, 120 analysts/editors; investigation creation 10/min.
- **Errors** (RFC 7807 style):

```json
{"type":"https://meridian.local/errors/validation","title":"Validation error","status":422,
 "detail":"profile must be one of lightweight|standard|breaking|deep","code":"validation_error",
 "request_id":"01...","errors":[{"loc":["body","profile"],"msg":"..."}]}
```

Standard codes: 400 bad request, 401 unauthenticated, 403 forbidden, 404 not found, 409 conflict (state or idempotency), 422 validation, 429 rate limit, 503 dependency unavailable (with `Retry-After`), 500 internal (no internals leaked; `request_id` for logs).

- **Security headers**, CORS allow-list, request size limit 1 MB (2 MB for source import), all outputs HTML-escaped by the UI; Markdown sanitized server-side.
- **Versioning:** URL major version; additive changes allowed within a major; deprecations announced via `Deprecation` header.

## 2. Endpoints

Notation: **Auth** column is the minimum role. `-` means public.

### 2.1 Authentication

| Method | Path | Purpose | Request | Response | Errors | Auth |
|---|---|---|---|---|---|---|
| POST | `/auth/login` | Exchange credentials for tokens | `{email, password}` | `{access_token, refresh_token, expires_in, user}` | 401, 429 | - |
| POST | `/auth/refresh` | Rotate tokens | `{refresh_token}` | tokens | 401 | - |
| GET | `/auth/me` | Current user | none | `User` | 401 | viewer |

### 2.2 Sources and discovery

| Method | Path | Purpose | Request | Response | Errors | Auth |
|---|---|---|---|---|---|---|
| GET | `/sources` | List sources | filters: `enabled`, `country`, `q` | `Page[Source]` | 401 | viewer |
| POST | `/sources` | Create source (disabled until ToS reviewed) | `SourceCreate{name, domain, feed_urls[], source_type, country, languages[], fetch_policy}` | `Source` | 409 duplicate domain, 422 | admin |
| GET | `/sources/{id}` | Detail with latest profile | | `SourceDetail` | 404 | viewer |
| PATCH | `/sources/{id}` | Update; enabling requires `fetch_policy.tos_reviewed_at` | partial `SourceCreate` | `Source` | 409, 422 | admin |
| DELETE | `/sources/{id}` | Disable (soft) | | 204 | 404 | admin |
| GET | `/sources/{id}/profile` | Credibility profile with dimension history | `topic` | `SourceProfile` | 404 | viewer |
| GET | `/articles` | List ingested articles | `source_id, event_id, lang, from, to, q` | `Page[ArticleSummary]` | | viewer |
| GET | `/articles/{id}` | Article with extracted metadata (text via snapshot endpoint) | | `Article` | 404 | viewer |
| GET | `/events` | List events | `status, impact, from, to, q, entity_id` | `Page[EventSummary]` | | viewer |
| GET | `/events/{id}` | Event with claim ledger summary | | `EventDetail{event, articles, claims:[{claim, current_verification}]}` | 404 | viewer |
| GET | `/events/{id}/timeline` | Timeline of verified claims and article arrivals | `as_of` optional | `Timeline` | 404 | viewer |
| GET | `/events/{id}/lineage` | Origin-group graph | | `LineageGraph` | 404 | analyst |

### 2.3 Monitoring

| Method | Path | Purpose | Request | Response | Errors | Auth |
|---|---|---|---|---|---|---|
| GET | `/watches` | List own watches | | `Page[Watch]` | | analyst |
| POST | `/watches` | Create watch | `WatchCreate{kind, target, rules, notify}` | `Watch` | 422 | analyst |
| PATCH | `/watches/{id}` | Update/pause | partial | `Watch` | 404 | analyst |
| DELETE | `/watches/{id}` | Delete | | 204 | 404 | analyst |

### 2.4 Investigations

| Method | Path | Purpose | Request | Response | Errors | Auth |
|---|---|---|---|---|---|---|
| POST | `/investigations` | Start investigation | `InvestigationCreate{kind: event\|article\|claim\|viral, input: {event_id? article_id? claim_text? url?}, profile, produce_report: bool, genre?}` | `202 Investigation{status:"created"}` | 422, 429, 503 if kill switch | analyst |
| GET | `/investigations/{id}` | Status, budget usage, claim ledger refs | | `InvestigationDetail` | 404 | viewer |
| POST | `/investigations/{id}/cancel` | Cancel | | `Investigation` | 409 if terminal | analyst |
| POST | `/investigations/{id}/resume` | Resume paused/partial (e.g. after human review or budget top-up) | `{extra_budget?}` | `Investigation` | 409 | editor |
| GET | `/investigations/{id}/stream` | SSE of progress | `Last-Event-ID` header | `text/event-stream` | 404 | viewer |
| GET | `/investigations/{id}/trace` | Execution trace (steps, tools, usage; no chain-of-thought) | | `Trace` | 404 | analyst |

SSE event envelope: `id: <seq>`, `event: <type>`, `data: <json>`. Types: `investigation.step {node, status, agent_id}`, `investigation.budget {used, limit}`, `claim.verdict {claim_id, label, rule_id}`, `evidence.added {evidence_id, claim_id, stance}`, `report.status {gen_article_id, status}`, `system.alert {level, message}`, `heartbeat` every 15 s. Events are replayable from `agent_messages`/outbox using the sequence.

### 2.5 Claims, evidence, verification

| Method | Path | Purpose | Request | Response | Errors | Auth |
|---|---|---|---|---|---|---|
| GET | `/claims/{id}` | Claim with current verification and parent/child atoms | | `ClaimDetail` | 404 | viewer |
| GET | `/claims/{id}/verifications` | Version history | | `Page[Verification]` | | viewer |
| GET | `/claims/{id}/evidence` | Evidence grouped by stance and origin group | `stance, group` | `EvidenceBundle` | | viewer |
| GET | `/evidence/{id}` | Evidence with provenance and source profile | | `Evidence` | 404 | viewer |
| GET | `/evidence/{id}/snapshot` | Snapshot text with highlighted quote range (access-controlled; licence-aware) | | `SnapshotView{text_window, quote_range, retrieved_at, sha256}` | 403 if source policy forbids display, 404 | analyst |
| POST | `/verify` | Ad-hoc verification of claim text or URL | `{claim_text? url?, profile, language?}` | `202 Investigation` | 422 | analyst |
| GET | `/verifications/{id}` | One verification result | | `Verification` | 404 | viewer |
| POST | `/claims/{id}/override` | Human override of a label (logged; does not alter rule outputs, creates a human-annotated verification record) | `{label, reason}` | `Verification` | 403, 422 | editor |

### 2.6 Generated articles (reports)

| Method | Path | Purpose | Request | Response | Errors | Auth |
|---|---|---|---|---|---|---|
| POST | `/reports` | Generate from an investigation or event ledger | `{investigation_id? event_id?, genre}` | `202 Report` | 409 if ledger too thin (`insufficient_verified_material`), 422 | analyst |
| GET | `/reports/{id}` | Sentences with claim/evidence mapping, audit findings, citation checks | | `ReportDetail` | 404 | viewer (published) / analyst (drafts) |
| GET | `/reports/{id}/versions` | Version list with diffs | | `Page[ReportVersion]` | | analyst |
| POST | `/reports/{id}/approve` | Approve (A15 policy re-checked server-side) | `{note?}` | `Report` | 409 if blocking checks fail, 403 | editor |
| POST | `/reports/{id}/reject` | Reject | `{reason}` | `Report` | 403 | editor |
| POST | `/reports/{id}/revise` | Request revision with editor instructions (instructions are trusted input but still length-limited and logged) | `{instructions, sentence_idx?[]}` | `202 Report` | 409 | editor |
| POST | `/reports/{id}/retract` | Retract with correction note | `{reason}` | `Report` | 403 | editor |

### 2.7 Search

| Method | Path | Purpose | Request | Response | Auth |
|---|---|---|---|---|---|
| GET | `/search` | Hybrid search over claims, events, evidence, articles | `q, kind, label, entity_id, from, to, as_of, limit, cursor` | `Page[SearchHit]` | viewer |

`as_of` returns the state of verdicts and facts as known at that time (bitemporal).

### 2.8 Feedback

| Method | Path | Purpose | Request | Response | Auth |
|---|---|---|---|---|---|
| POST | `/feedback` | Submit feedback on a claim, evidence item, or report | `{object_type, object_id, rating?, comment?, proposed_label?}` | `Feedback` | viewer |
| GET | `/feedback` | Review queue | `status` | `Page[Feedback]` | editor |
| PATCH | `/feedback/{id}` | Triage | `{status}` | `Feedback` | editor |

### 2.9 System and administration

| Method | Path | Purpose | Response | Auth |
|---|---|---|---|---|
| GET | `/healthz` | Liveness | `{status:"ok"}` | - |
| GET | `/readyz` | Readiness: DB, queue, object store, at least one model route | `{ready, checks:{...}}` (503 when not ready) | - |
| GET | `/admin/metrics` | Queue depth, DLQ, provider status, cost burn, circuit breaker states | `SystemMetrics` | admin |
| GET/PUT | `/admin/config` | Profiles, policies, model routing, flags; PUT validates and writes `audit_log` | `Config` | admin |
| POST | `/admin/kill-switch` | `{enabled: bool, reason}`; stops new LLM calls within 10 s | `{enabled, at}` | admin |
| GET | `/admin/dead-letters` and POST `/admin/dead-letters/{id}/replay` | Inspect and replay failed tasks | | admin |

Prometheus metrics are exposed on a separate internal port at `/metrics` (not routed through the public API).

## 3. Key response schemas (abbreviated)

```python
class Page(BaseModel, Generic[T]):
    items: list[T]; next_cursor: str | None

class ClaimDetail(BaseModel):
    claim: Claim
    current_verification: Verification | None
    atoms: list[Claim]                       # if compound
    evidence_summary: dict[str, int]         # counts by stance, groups
    uncalibrated: bool                       # true when calibrated_probability is null

class Verification(BaseModel):               # public projection of VerificationResult
    verification_id: UUID; claim_id: UUID; label: Label; rule_id: str
    strength: EvidenceStrength
    calibrated_probability: float | None
    justification: str; missing_information: list[str]
    adversarial_outcome: str; computed_at: datetime; claim_version: int

class ReportDetail(BaseModel):
    report: GeneratedArticle
    audit_findings: list[AuditFinding]
    citation_checks: list[CitationCheck]
    stale: bool; correction_note: str | None
    versions: list[int]
```

## 4. Contract tests

- Schemathesis (property-based) against OpenAPI in CI.
- Role matrix test: every route x every role asserts allowed/denied.
- SSE test: reconnect with `Last-Event-ID` yields no gaps or duplicates.
- Idempotency test: repeated POST with same key returns same investigation.
- No endpoint returns chain-of-thought or raw prompts; a test greps responses for prompt markers.
