# PROJECT_STATE.md

**Project Meridian: Autonomous News Intelligence and Verification Platform**
Document version: after Step 1 | Written: 2026-11-10 | Audience: any AI assistant or engineer continuing this project

Read this file first. It states what exists, why it was built this way, how to run it, and what to do next. The full design lives in `docs/blueprint/MASTER_SYSTEM_BLUEPRINT.md` (and six supporting files in the same folder); this file records what has actually been built against that design.

---

## 1. Project in one paragraph

Meridian is a planned multi-agent system that acts like an autonomous digital newsroom: it discovers news, clusters it into events, extracts atomic claims, investigates each claim against independent evidence, assigns an explainable verdict with calibrated uncertainty, and writes cited, neutral reports traceable sentence by sentence to evidence. Its two inspirations are the AI-Press paper (multi-agent news drafting, polishing and audience-feedback simulation) and a multi-agent fact-checking paper (FOL claim decomposition, query generation, evidence seeking, verdict prediction). The design deliberately fixes their weaknesses: binary verdicts, counting duplicate sources as corroboration, single-judge evaluation, no citation integrity check.

The owner is a student developer working on a 16 GB RAM laptop with no GPU, building step by step: the assistant supplies complete files, the owner runs them with `pytest`, reports errors, and the assistant fixes them. After each step the assistant produces an updated state document like this one.

## 2. Current status

| Item | Status |
|---|---|
| Planning, research, architecture, requirements | Done (blueprint, 7 files) |
| **Step 1: pure-logic foundations** | **Built. Verified in the author's sandbox. Not yet confirmed on the owner's machine** |
| Step 2 onward | Not started |

Verification evidence for Step 1 (author sandbox, Python 3.12.3, 2026-11-10):
- `pytest`: **117 passed**.
- `mypy` (strict, `src/` only): no issues in 20 source files.
- `ruff check` and `ruff format`: clean.
- Coverage: 99% overall; every logic module at 100% except `verification/policy.py` at 96% (three lines in the policy consistency validator error path).
- Mutation sanity checks: flipping the coverage comparison in `decision.py` made 21 tests fail; changing group counting in `strength.py` made 2 tests fail. The suite is therefore not vacuous.
- Owner-machine result: **pending**. The first thing to do in the next session is to ask the owner for their `pytest` output and Python version.

Nothing in Step 1 touches a database, network, LLM, Docker or the filesystem except reading one YAML file.

## 3. Architecture in brief (from the blueprint)

- **Pattern:** hybrid. An event-driven ingestion plane (Postgres-backed queue) feeds supervised investigation graphs (LangGraph, deterministic orchestrator, no LLM routing by default) that operate over a blackboard "case file" in PostgreSQL. A separate editorial plane writes from the verified claim ledger only.
- **Agents:** 16 (A01 to A16) plus 12 services (S01 to S12). Most things that look like agents are deterministic services.
- **Security:** quarantined agents (A03, A05, reader half of A04, attribution part of A06) read untrusted web text and have no tools; privileged agents never see raw untrusted text.
- **Stores:** PostgreSQL 16 with pgvector for relational, vector and graph-lite data; object storage for snapshots; no Kafka, Neo4j or separate vector DB until measurements justify them.
- **Models:** provider-agnostic router; local 4B to 9B quantized models for cheap roles during development, hosted models for heavy roles; different model families for adversarial, audit and judge roles.
- **Verification:** the label is decided by code (the decision table), never by an LLM. The LLM later writes only the justification.

None of the infrastructure above exists yet. Step 1 implements only the portion that is pure logic.

## 4. What Step 1 built

### 4.1 Repository layout (as it exists)

```
meridian/
├─ pyproject.toml                      setuptools, src layout, deps, pytest/mypy/ruff config
├─ README.md                           setup and run instructions
├─ .gitignore
├─ config/verification_policy.yaml     default thresholds for the decision table
├─ docs/
│  ├─ PROJECT_STATE.md                 this file
│  └─ blueprint/                       the seven blueprint documents
├─ src/meridian/
│  ├─ __init__.py                      __version__ = "0.1.0"
│  ├─ core/        __init__, ids.py, clock.py, errors.py
│  ├─ schemas/     __init__, common.py, claims.py, evidence.py, verification.py,
│  │               agents.py, events.py, articles.py
│  ├─ verification/__init__, policy.py, strength.py, decision.py, aggregation.py
│  └─ evidence/    __init__, quotes.py
└─ tests/
   ├─ conftest.py                      fixtures: policy, make_item, make_features, repo_root
   └─ unit/
      ├─ core/          test_ids.py (7), test_clock.py (3)
      ├─ schemas/       test_schemas.py (17)
      ├─ verification/  test_policy.py (8), test_strength.py (11), test_decision.py (25),
      │                 test_aggregation.py (21), test_properties.py (7)
      ├─ evidence/      test_quotes.py (13)
      └─ test_architecture.py (5)
```
Totals: about 1,080 lines of source, about 1,040 lines of tests, 117 tests.

### 4.2 Module reference

**`meridian.core`**
- `uuid7(timestamp_ms=None) -> UUID`: RFC 9562 UUIDv7 (48-bit ms timestamp, version 7, RFC variant, 74 random bits). `uuid7_timestamp_ms(uuid)` extracts the timestamp and rejects non-v7 values. Time-ordered IDs keep database indexes compact.
- `Clock` protocol, `SystemClock` (UTC now), `FixedClock(at)` (requires a timezone-aware datetime; has `advance(delta)`). Time-dependent logic must take a `Clock`.
- Errors: `MeridianError` (base), `PolicyError`, `DecisionError`.

**`meridian.schemas`** (Pydantic v2; every model forbids unknown fields; all datetimes must be timezone-aware)
- `common.py`: enums `SourceType`, `Directness`, `Stance`, `ClaimType`, `Impact`, `Label`, `AdversarialOutcome`, `TemporalFlag`, `VerificationStatus`, `Trust`; value objects `ConfidenceMeta` (kind is `self_reported`, `rule_derived` or `calibrated`; calibrated requires a value), `Usage`, `BudgetSlice`; base class `MeridianModel`; `SCHEMA_VERSION = "1.0"`.
- `Label` has exactly eight members and deliberately no plain true/false: `strongly_supported`, `supported`, `partially_supported`, `contradicted`, `mixed_evidence`, `insufficient_evidence`, `unverified`, `outdated_or_misleading_context`.
- `claims.py`: `Claim` (text 10 to 600 chars; `original_span` must satisfy 0 <= start < end; non-verifiable claims require a reason; reference period end must not precede start; `claim_version`).
- `evidence.py`: `Evidence` (excerpt 1 to 600 chars; 64-hex snapshot hash; at least one claim id; `excerpt_char_end > excerpt_char_start`; stance, directness, origin group id, verification status).
- `verification.py`: `EvidenceStrength` (support mass, refute mass, coverage, credible group counts, primary flags); `VerificationFeatures` (frozen; the complete input of the decision table); `VerificationResult` (rule id must match `R1` to `R8`; a calibrated probability requires a calibration version).
- `agents.py`: `UntrustedText` (trust field can only be `untrusted`), `FailureCode`, `AgentFailure`, `AgentTask` (agent id must match `A##`), `AgentResult` (status `failed` requires an error and no other status may carry one).
- `events.py`: `NewsEvent`. `articles.py`: `ArticleSentence` (a `claim` sentence must cite claim ids), `GeneratedArticle` (sentence indexes must run 0..n-1).

**`meridian.verification`** (pure logic; may import only `schemas` and `core`)
- `policy.py`: `VerificationPolicy` (frozen Pydantic model with nested rule thresholds), `default_policy()`, `load_policy(path)` which raises `PolicyError` on a missing file, bad YAML, non-mapping content, unknown keys or out-of-range values. A validator requires `strongly_supported.max_refute_mass <= supported.max_refute_mass` and a weight for every directness level. A test asserts `config/verification_policy.yaml` equals `default_policy()`, so the two cannot drift.
- `strength.py`: see section 5.1.
- `decision.py`: `decide(features, policy) -> Decision(label, rule_id, reason)`; see section 5.2.
- `aggregation.py`: `aggregate_compound(labels)`; see section 5.3.

**`meridian.evidence.quotes`**
- `normalize_text` (Unicode NFC only), `sha256_text`, `verify_quote(snapshot, excerpt, start, end) -> QuoteCheck`, `locate_quote(snapshot, excerpt) -> (start, end) | None`.
- Convention: snapshots are stored NFC-normalized by the future extractor (S03), so offsets are stable. `verify_quote` requires `snapshot[start:end]` to equal the excerpt exactly after NFC; there is no fuzzy matching. `locate_quote` tries an exact match, then a whitespace-flexible match (line wraps), and returns offsets into the original text.

## 5. Core algorithms (exact behaviour)

### 5.1 Evidence strength (`strength.py`)

Input: `WeightedEvidence` items (frozen dataclass: evidence id, **origin group id**, stance, directness, reliability r, temporal relevance t, stance quality q; each of r, t, q must be in [0, 1]).

1. Item weight: `w = r * d * t * q`, where d comes from `policy.directness_weights` (defaults: primary 1.0, direct_secondary 0.7, indirect 0.4).
2. Only `supports` and `refutes` stances count; `context` and `irrelevant` are ignored.
3. Per (origin group, stance), keep the **maximum** item weight (not the sum). Ten copies of one wire story are one group and add nothing.
4. Mass per stance is noisy-OR: `M = 1 - product(1 - w_g)` over groups. It is monotone non-decreasing in every input and order independent (property-tested).
5. A group is **credible** when `w_g >= credible_group_threshold` (0.35). `n_support_groups` and `n_refute_groups` count credible groups only.
6. `has_primary_support/refute` is true when some credible group has a primary-directness item whose own weight is at least the credible threshold.

`compute_strength(items, coverage, policy)` returns an `EvidenceStrength`; coverage (in [0, 1]) is supplied by the caller (future research agent).

### 5.2 Decision table (`decision.py`)

`decide` is a pure function of `VerificationFeatures` and a policy. Rules are evaluated in order; the first match fires. Defaults shown are the current policy values.

| Rule | Label | Fires when |
|---|---|---|
| R1 | unverified | `needs_context`, or coverage < 0.6 |
| R2 | outdated_or_misleading_context | a temporal flag in {old_as_new, superseded, missing_qualifier} is present and support mass >= 0.25 |
| R3 | contradicted | (refute mass >= 0.6 and >= 2 credible refuting groups) or a credible primary refuting group; and support mass < 0.25 |
| R4 | strongly_supported | (credible primary support and >= 2 credible support groups, counting the primary group) or >= 3 credible support groups; refute mass < 0.15; adversarial outcome is not found_refutation; if impact is HIGH, the adversarial check must have run; no circular sourcing; no temporal flags of any kind |
| R5 | supported | (support mass >= 0.6 and >= 2 credible groups) or a credible primary support group; refute mass < 0.25; adversarial outcome is not found_refutation |
| R6 | mixed_evidence | support mass >= 0.35 and refute mass >= 0.35 and at least one credible group on each side |
| R7 | partially_supported | `scope_mismatch` is true and support mass >= 0.35 |
| R8 | insufficient_evidence | none of the above, with adequate coverage |

Important semantics:
- **unverified** means "we could not look hard enough"; **insufficient_evidence** means "we looked adequately and found too little". Low coverage always yields R1, even with strong evidence.
- `period_mismatch` alone is not "misleading" (it does not trigger R2) but, like any temporal flag, it blocks R4.
- The rule engine has no path that lets free text or an LLM choose a label.

### 5.3 Compound aggregation (`aggregation.py`)

For a compound claim decomposed into atoms, the precedence is:
1. Any atom `outdated_or_misleading_context` gives that label.
2. Any atom `mixed_evidence` gives `mixed_evidence`.
3. Any atom `contradicted`: partially_supported if any other atom is supported or partially supported, otherwise contradicted.
4. All atoms supported: the weakest supported level (any `supported` makes the result `supported`).
5. Some atoms supported or partial and the rest unknown (unverified or insufficient): `partially_supported`.
6. Only unknown atoms: `unverified` if any is unverified, else `insufficient_evidence`.
Zero atoms raise `DecisionError`. Order of atoms never matters (tested).

## 6. Invariants the tests protect

1. Ten copies of one origin count as exactly one group (`test_strength.py`).
2. Adding an independent supporting group never lowers support mass (hypothesis).
3. `decide` is total (never raises) and always returns a valid label and a rule in R1..R8 (hypothesis, 300 random feature sets).
4. R4 is never returned with circular sourcing, a found refutation, refute mass >= 0.15 or any temporal flag (hypothesis).
5. Coverage below the minimum is always R1 (hypothesis).
6. Quotes must match the snapshot at the stated offsets; paraphrases, wrong case and bad offsets are rejected.
7. Schemas reject unknown fields, naive datetimes, bad spans, malformed hashes, inconsistent confidence or result states.
8. Layering: `schemas` and `core` import nothing else in `meridian`; `verification` and `evidence` may import only `schemas`, `core` and themselves (`test_architecture.py`, using `ast`, no extra tooling).
9. The YAML policy file equals the in-code default policy.

## 7. Differences from the blueprint (decisions made while building)

| Topic | Blueprint | Built | Reason |
|---|---|---|---|
| "Primary group plus 2 independent groups" for R4 | ambiguous whether the primary group counts | counts inclusively (`min_groups_with_primary = 2`) | removes ambiguity; policy-configurable |
| Compound aggregation with an outdated atom, and contradicted + unknown atoms | unspecified | rules 1 and 3 in section 5.3 | needed a total function; any atom that makes the framing misleading should dominate; a conjunction with a false atom is false |
| R2 requires some support | implied | requires support mass >= 0.25 | otherwise flags alone would label unsupported claims as "outdated" |
| Rule IDs | "R1 to R9" in an early draft | R1 to R8 (patched in the blueprint) | eight rules |
| `claim_version` on `Claim`, `version` on `NewsEvent` | in DB design only | present in the Pydantic models | verdict reuse invalidation needs them |
| Tests for layering | import-linter | `ast`-based test | no extra dependency yet; switch to import-linter when more packages exist |

## 8. Conventions to keep following

- Python 3.11+, src layout, `from meridian...` imports, `mypy --strict`, `ruff` with line length 100.
- Pydantic models at every boundary; `extra="forbid"`; timezone-aware datetimes.
- The decision table, strength maths and quote verifier stay pure (no I/O, no randomness, no LLM). `verification` must never import `models`, `db`, `tools`, `agents`, `api` or `workers`.
- The LLM never chooses a verdict label. Evidence only counts if its quote verifies.
- Never fabricate data, results, versions or URLs. Test fixtures must be real captured data or clearly named synthetic data.
- Tests ship with the code. Use `hypothesis` for invariants and a mutation check (deliberately break a rule and see tests fail) after changing decision logic.
- Defaults in the policy YAML are hypotheses: tune them on a dev split only, never on the locked test split, and keep the YAML and `default_policy()` identical.
- Avoid shell brace expansion and POSIX-only commands in instructions; the owner may be on Windows. Prefer shipping files (zip) over long copy-paste steps.

## 9. How to run

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1   |  macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest                         # expect: 117 passed
pytest --cov=meridian --cov-report=term-missing
ruff check . && ruff format --check .
mypy
```

## 10. Known limitations and open items

- **Not built yet:** database, queue, LangGraph orchestration, model router, tools, ingestion, agents, API, frontend, observability, evaluation harness, prompts in code. These exist only as design in the blueprint.
- `WeightedEvidence` is a pure-logic view; mapping from `Evidence` rows plus source profiles to `WeightedEvidence` is not written (needs the lineage and credibility services).
- Origin groups are inputs to the maths; nothing yet *computes* them (Step 2).
- Coverage is an input; nothing yet computes it from answered verification questions.
- Calibration (turning strength into a probability) is not implemented; `calibrated_probability` is always null for now.
- All thresholds are untested defaults, not tuned values. No benchmark has been run; no performance claim is made anywhere.
- Quote verification assumes snapshots are NFC-normalized at storage time; that contract is not enforced until S03 exists.
- The blueprint's Phase 0 re-verification checklist (versions, licences, model benchmarks, search-provider terms) has not been performed. Dependency pins in `pyproject.toml` are minimum versions only.
- Owner-machine test results for Step 1 are pending.

## 11. Recommended next step (Step 2)

Still pure logic, still no database or LLM:
1. **Lineage / independence analysis** (`meridian/evidence/lineage.py`): input documents with text, publication time, optional explicit attributions, links and ownership group; compute text-reuse similarity (shingle/MinHash style, standard library first), derivation edges with confidence, origin groups, and a circular-sourcing flag. Conservative default: unknown relationships with high overlap are treated as dependent. Tests: wire copies with edits, quote chains, circular citation, shared ownership, coincidental same-day reports.
2. **Budget Governor** (`meridian/core/budget.py`): reserve-before-spend accounting for LLM calls, tokens, tool calls, depth and deadline at investigation, claim and node levels; hard stops; kill switch; profiles from the blueprint (lightweight, standard, breaking, deep). Tests include overrun termination and concurrency.
3. Adapter from lineage output to `WeightedEvidence` and a small end-to-end pure test: documents in, label out.

After Step 2, the planned order follows the blueprint roadmap: database and queue skeleton (Phase 2), ingestion (Phase 3), agent runtime and model router (Phase 4), research and evidence retrieval (Phase 5), then the claim extractor and the rest of verification (Phase 6).

## 12. Instructions for the next assistant session

1. Ask the owner for the `pytest` output and `python --version` from their machine; resolve any failures first.
2. Read `docs/blueprint/MASTER_SYSTEM_BLUEPRINT.md` sections 4 to 6 and `AGENT_SPECIFICATIONS.md` before writing new code.
3. Deliver each step as a complete, tested bundle (verify in the sandbox first), tell the owner exactly what to run and what to send back if something fails.
4. After the owner confirms green tests, update this file: status table, module reference, invariants, deviations, limitations and next step.
