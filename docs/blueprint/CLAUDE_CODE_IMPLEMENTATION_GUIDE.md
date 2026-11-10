# CLAUDE_CODE_IMPLEMENTATION_GUIDE.md

Operating manual for Claude Code implementing Project Meridian. Read `MASTER_SYSTEM_BLUEPRINT.md` completely first. Then read the supporting file named for the current phase (blueprint section 0).

## 1. Mandatory operating rules

1. **Read before writing.** At the start of every session: read the blueprint sections relevant to the phase, `CLAUDE.md`, `docs/IMPLEMENTATION_CHECKLIST.md`, and recent ADRs. State in one paragraph which phase and tasks you are doing.
2. **Plan first.** Before coding a phase, write a short phased plan into `docs/plans/phase-N.md` (tasks, order, test list, risks). Update the checklist.
3. **Incremental delivery.** Work in small vertical slices (one task at a time, one commit per slice). Never generate the whole repository or a whole phase in one operation.
4. **Follow the architecture.** Layering rules (blueprint 10.4, 17) are enforced by import-linter. Do not add infrastructure (queue brokers, vector DBs, graph DBs, Redis) that the blueprint defers. A deviation requires an ADR in `docs/adr/NNN-title.md` and an amendment note in the blueprint.
5. **Strong typing, minimal abstraction.** `mypy --strict`, Pydantic models at every boundary, no `Any` without a comment. Add an abstraction only when two concrete uses exist or the blueprint specifies the interface.
6. **Never fabricate.** No invented API responses, evidence, citations, benchmark numbers, URLs, model names, package versions, or test results. Recorded fixtures MUST be real captured data labelled with capture date and licence note, or explicitly synthetic and named `synthetic_*`. If you do not know a version or API detail, look it up (documentation, package index) or mark it `TODO(verify)` and add a checklist item.
7. **Validate everything.** All external input (HTTP, feeds, search results, LLM output, files) is validated with Pydantic and length/charset limits before use.
8. **Tests alongside code.** Every module lands with unit tests in the same commit. Integration, adversarial and e2e tests as specified per phase. Run the full relevant suite before declaring a task or phase complete, and paste the real command and result summary into the checklist.
9. **Secrets.** Only through environment variables (`.env` not committed; `.env.example` documents each variable). No credentials in code, tests, fixtures, logs or prompts. Run the secret scanner before each commit.
10. **Migrations.** Every schema change is an Alembic migration with up and down; `make migrate-check` must pass.
11. **Independent testability.** Each component is runnable with fakes (fake model adapter, fake search provider, in-memory object store). No test requires the network unless marked `@pytest.mark.network` and excluded from default CI.
12. **Document as you go.** Update README, config docs, the checklist, runbooks, and the blueprint when decisions change. Record architectural decisions as ADRs.
13. **Honest reporting.** Report unfinished work, skipped tests, known failures, and assumptions in the checklist and your session summary. "Done" means acceptance criteria met and tests green, not "code written".
14. **No silent simplification.** If a requirement is too large to finish now, implement the interface plus a clearly named stub that raises `NotImplementedError("Phase X: <what>")`, register it in the checklist under "Stubs", and do not wire the stub into production paths.
15. **Security first.** Quarantine boundaries (blueprint 12.1) are not optional. Never pass untrusted text into privileged agent prompts, never give quarantined agents tools, never let content select actions. Add an injection test whenever a new component reads external text.
16. **Cost discipline.** Every LLM call goes through the router and the Budget Governor. Tests use recorded fixtures; live-model tests are marked `@pytest.mark.live` and run manually.
17. **Determinism where specified.** The verdict decision table, lineage thresholds, budgets, and validators are pure code with property tests. Do not move them into prompts.
18. **Ask when blocked, not when merely uncertain.** If a decision is covered by the blueprint, follow it. If it is listed as open (D1 to D3, model defaults, thresholds), propose a default with trade-offs, record it as an ADR, and continue unless the owner's input is essential (e.g. paid API keys).

## 2. `CLAUDE.md` (copy to repository root)

```markdown
# Meridian: instructions for Claude Code

Source of truth: MASTER_SYSTEM_BLUEPRINT.md and supporting docs in /docs/blueprint/.
Workflow each session: read checklist -> state phase/task -> plan -> implement small slice -> test -> update checklist -> commit.

Commands:
- make setup        # uv sync, pre-commit install
- make up / down    # docker compose dev profile
- make test         # unit + integration (no network, no live models)
- make test-adv     # adversarial suite
- make lint         # ruff, mypy --strict, import-linter, gitleaks
- make migrate-check
- make eval-smoke   # small deterministic evaluation on fixtures

Hard rules:
- Never fabricate data, citations, results, versions. Cite real fixtures; label synthetic ones.
- Layering is enforced (src/meridian/*); verification/ is pure logic and must not import models/.
- Quarantined agents (A03, A05, reader half of A04, attribution part of A06) have NO tools and never feed raw untrusted text to privileged agents.
- LLM never chooses verdict labels. Labels come from verification/decision.py.
- Every external/LLM output validated by Pydantic. Every LLM call goes through ModelRouter + BudgetGovernor.
- No new infrastructure or dependency without an ADR.
- Update docs/IMPLEMENTATION_CHECKLIST.md honestly (stubs, skipped tests, failures).
```

## 3. Implementation checklist template (`docs/IMPLEMENTATION_CHECKLIST.md`)

```markdown
# Implementation checklist
Last updated: <date> by <session>

## Phase N: <name>  [not started | in progress | blocked | done]
| Task | Status | Tests | Evidence (command, result) | Notes |
|---|---|---|---|---|

### Acceptance criteria (from blueprint)
- [ ] ...

### Stubs (NotImplementedError)
| Location | What is missing | Phase to finish |

### Known issues / deviations
| Issue | ADR | Owner |

### Verification log
<date> `make test` -> <real summary line>
```

## 4. Session workflow

1. Orient: read checklist and plan; run `make test` to confirm a green start (record failures before changing anything).
2. Pick the next unchecked task; write failing tests first when the behavior is specified (decision table, validators, lineage, SSRF guard, quote verifier, budget governor).
3. Implement; run targeted tests, then `make lint`.
4. Commit with message `phaseN(scope): summary` and reference the requirement IDs (e.g. `FR-EVD-02`).
5. Update checklist and docs. If the architecture changed, add an ADR and amend the blueprint.
6. End of session summary: done, in progress, blocked, next steps, honest risk notes.

## 5. Phase kickoff prompts

Use these as the first message of a Claude Code session for each phase. Replace nothing; they reference files in the repo.

**Phase 0:** "Read MASTER_SYSTEM_BLUEPRINT.md sections 0 to 3 and 8. Execute the Phase 0 checklist in section 2.9: verify versions, licences, model candidates on 16 GB CPU-only hardware, embedding/reranker/NLI choices, search provider terms. Write docs/research/phase0_verification.md and docs/research/model_bench.md with real measurements and sources; amend the blueprint where facts differ; write ADR-001..005. Do not write application code."

**Phase 1:** "Create docs/requirements.md and docs/traceability.md from blueprint section 3. Map every P0 requirement to planned test files. Create config/verification_policy.yaml, config/impact_policy.yaml, config/profiles.yaml from blueprint 5.6 and 13.2 with the stated default values and comments."

**Phase 2:** "Implement the walking skeleton per blueprint Phase 2: repo layout (section 17), uv project, Docker Compose dev profile, Postgres+pgvector, Alembic baseline from DATA_AND_DATABASE_DESIGN.md (identity, sources, articles, events, tasks tables first), schemas package from blueprint 4.6, config/logging/ids, job queue with SKIP LOCKED leasing and outbox, FastAPI health/auth stub, CI with lint/type/tests/import-linter/gitleaks, ModelRouter interface with a fake adapter, and a LangGraph hello-graph using the Postgres checkpointer with a kill-and-resume test. Follow rules in CLAUDE_CODE_IMPLEMENTATION_GUIDE.md."

**Phase 3:** "Implement ingestion per blueprint Phase 3: S01 registry API, S02 fetch gateway with the SSRF test suite, RSS ingestion with conditional GET, S03 extraction with a gold-set evaluator, S04 dedup, S05 clustering, S06 entities, snapshots in object storage, search tool abstraction with one provider adapter. Build the gold sets from real captured pages (record capture dates and licence notes). Report measured throughput; do not assume."

**Phase 4:** "Implement the agent runtime per blueprint Phase 4 and AGENT_SPECIFICATIONS.md section 1: BaseAgent, task/message persistence, A01 orchestrator graph with stub agents, Budget Governor, ModelRouter with Ollama and OpenAI-compatible adapters, structured-output repair, prompt registry, tracing, DLQ and replay, LLM record/replay fixtures. Add failure-injection and chaos tests."

**Phase 5:** "Implement A02 (minimal), A04, A05 per AGENT_SPECIFICATIONS.md and blueprint section 6 with the quarantine split, quote verification, evidence and snapshot persistence, adaptive stopping, hybrid retrieval with rerank and diversification. Run the injection suite on readers. Produce docs/research/retrieval_ablation.md from real runs."

**Phase 6:** "Implement A03, A06, S07, A09, A10 (and A07, A08 behind flags) per specs. verification/decision.py must be a pure function with 100% branch coverage and property tests. Implement evidence strength, compound aggregation, calibration pipeline skeleton. Produce the first dev-set metrics snapshot with dataset versions; do not tune on the locked test split."

**Phase 7:** "Implement memory per blueprint section 7: bitemporal facts, KG queries in Postgres, S08 consolidation, source profile updates, claim reuse with TTL and event-version keys, as-of search."

**Phase 8:** "Implement A12, A13, A14, A15 and versioning per specs: constrained writer with sentence-to-claim mapping, refusal on thin ledger, citation integrity pipeline (quote exact-match, NLI, numbers, URL/DOI resolution), neutrality audit with a different-family judge, human approval interrupt, article versioning and correction notes. Build citation_seeded dataset and report A14 recall."

**Phase 9:** "Implement the Next.js frontend per blueprint section 14 in the stated priority order with a generated API client, SSE hooks, loading/empty/error states, responsive layouts, accessibility checks, and Playwright e2e tests. Never display raw model reasoning."

**Phase 10:** "Harden per blueprint Phase 10: Langfuse/OTel dashboards, Prometheus alerts, full red-team suite, RLS, rate limiting, secrets handling, chaos tests in nightly CI, load tests, and measured optimizations. Add Redis only if measurements justify it (ADR)."

**Phase 11:** "Execute EVALUATION_AND_BENCHMARKING.md: finalize datasets and splits, implement baselines B0 to B3, pre-register, run comparisons with statistics and ablations, produce docs/benchmarks/REPORT_v1.md including negative results and threats to validity."

**Phase 12:** "Prepare production deployment per blueprint Phase 12: provisioning, backups and restore drill, TLS, secrets, alerts, runbooks, staged rollout, cost caps, legal documentation."

**Phase 13:** "Implement continuous-improvement items from blueprint Phase 13 one at a time, each with benchmark delta and rollback plan."

## 6. Definition of done (every phase)

- All acceptance criteria in the blueprint phase met, evidenced in the checklist with real command output summaries.
- `make lint` and `make test` green; adversarial suite green where applicable; migrations verified.
- No unregistered stubs; no TODO without an issue entry.
- Docs, config reference, ADRs updated; blueprint amended where needed.
- Honest list of known limitations written.

## 7. Makefile targets to provide (Phase 2)

`setup`, `up`, `down`, `logs`, `migrate`, `migrate-check`, `test`, `test-int`, `test-adv`, `test-e2e`, `lint`, `fmt`, `eval-smoke`, `eval`, `seed`, `ingest-once`, `verify-claim CLAIM="..."`, `export-openapi`, `gen-client`.

## 8. ADR template (`docs/adr/NNN-title.md`)

```markdown
# ADR-NNN: Title
Status: proposed | accepted | superseded by ADR-MMM
Date:
Context: (problem, constraints, blueprint section)
Options considered: (with trade-offs)
Decision:
Consequences: (positive, negative, follow-ups)
Verification: (how we will know it was right; metric or test)
```

## 9. Handling uncertainty and external facts

- Version numbers, licences, provider terms, model names and prices change. Verify at implementation time from primary sources; record source URL and access date in `docs/research/`.
- If a primary source is unavailable, say so in the checklist and choose the conservative option.
- When benchmark numbers from literature are cited, mark them as "reported by authors" with the paper reference.
- When a blueprint threshold is a default (marked as such), treat it as a hypothesis: implement it in config, evaluate, and tune on the dev split only.

## 10. Common failure modes to avoid

| Failure mode | Prevention |
|---|---|
| Letting the LLM pick a verdict "because it's easier" | Decision table in code; test that no agent output field can set `label` |
| Counting URLs instead of origin groups | Unit test: 10 copies of one wire story yield `n_support_groups == 1` |
| Evidence with paraphrased "quotes" | Quote verifier rejects any excerpt not found verbatim in snapshot |
| Prompt injection through search snippets | Snippets treated as untrusted data in privileged half; red-team canaries |
| Checkpoint bloat | Graph state stores IDs only; large artifacts in DB/object store |
| Over-spending | All calls reserve budget first; overruns terminate gracefully |
| Silent partial results | `status="partial"` plus warnings propagate to UI |
| Tuning on the test set | Locked split; CI check that test-split manifests are read-only |
| Same-family judge bias | Router enforces `family` difference for A09/A13/A14-judge versus A02/A10/A12 |
| Scope explosion | Build only what the current phase lists; defer P1/P2 features |
