# EVALUATION_AND_BENCHMARKING.md

Companion to `MASTER_SYSTEM_BLUEPRINT.md` sections 5.7, 15. **No result is claimed here.** This file defines how results will be produced, so that "better than the alternatives" is tested, not asserted.

## 1. Principles

1. Pre-register: primary metrics, datasets, splits, baselines and statistical tests are fixed in `evaluation/PREREGISTRATION.md` before the first full comparison run.
2. Locked test sets: touched only for final reports; tuning uses dev splits.
3. Leakage control: temporal cut-off on every search call (`date_to` = claim date minus 1 day for benchmark claims); prefer dynamic or fresh data; log retrieval of any page that quotes the benchmark label (e.g. the fact-check article itself) and exclude such evidence.
4. Same budgets for every system under comparison.
5. Report negatives: the final report MUST list datasets, label types and metrics where Meridian does not beat a baseline.
6. Reproducibility: every run records dataset version, git SHA, config hash, model IDs and versions, prompt versions, search provider, run date, seeds. `make eval` reproduces from a clean checkout using recorded search caches where licences permit.

## 2. Datasets

| Purpose | Dataset | Notes |
|---|---|---|
| Real-world claim verification with web evidence | AVeriTeC (4,568 claims from 50 fact-checking organisations; question-answer evidence and justifications) | Primary benchmark; map its four labels to the Meridian taxonomy via a documented mapping table |
| Dynamic, leakage-resistant, multilingual, multimodal | VeriTaS (reported 25,000 claims from 104 organisations in 54 languages, updated over time) | Use the newest release at run time; text subset first |
| Multi-hop and structured evidence | FEVEROUS, HoVer, SciFact-Open | Same sets used by the uploaded paper, enabling a like-for-like comparison with the reimplemented baseline B3 |
| Image-text claims | AVerImaTeC | Phase 13 only |
| Internal sets (to be built by the team) | see section 3 | Required for components no public benchmark covers |

Phase 0 confirms licences and download paths. Sample sizes: the uploaded paper used 100 stratified examples per dataset; that is too small for reliable significance. Target at least 500 claims per primary evaluation arm (computed from pilot variance, see section 6).

## 3. Internal datasets

| Name | Content | Size target | Annotation protocol |
|---|---|---|---|
| `extract_gold` | 200 articles (news, wire, local, non-English subset) with gold atomic decontextualized claims and spans | 200 | 2 annotators, adjudication; Cohen's kappa reported |
| `dedup_pairs` | Pairs labelled exact/near/rewrite/different | 2,000 pairs | 2 annotators |
| `cluster_gold` | Article streams from 10 real days with event labels | 1,500 articles | 2 annotators, B-cubed reference |
| `lineage_gold` | Evidence sets for 150 claims with annotated derivation edges and origin groups (wire copies, quote chains, circular cases) | 150 claims | 2 annotators |
| `retrieval_gold` | Claims with annotated necessary evidence documents (AVeriTeC QA provides a start) plus 100 new | 600 | Reuse plus manual |
| `temporal_gold` | Old-news-as-current cases, superseded stats | 150 | 2 annotators |
| `headline_gold` | Headline vs body vs evidence mislead labels | 300 | 2 annotators |
| `numeric_gold` | Statistical claims with official data and verdicts (percent vs points, per-capita, base-year errors) | 200 | domain checker |
| `citation_seeded` | Drafts with seeded errors (fabricated quote, number swap, wrong attribution, unsupported inference) | 300 sentences, 30% corrupted | Programmatic plus review |
| `writing_eval` | 100 events with ledgers; drafts rated by humans | 100 | 3 raters, rubric below |
| `injection_suite` | Hostile pages/feeds (hidden text, fake system prompts, URL exfil, poisoned fact-check pages, canaries) | 200 cases | Security engineer |
| `calibration_dev` | Pipeline outputs on dev claims with gold labels | >= 1,000 | derived |

Annotation guidelines live in `evaluation/guidelines/`; disagreements adjudicated; kappa below 0.6 triggers guideline revision before use.

## 4. Metrics (formal definitions)

| Component | Metric | Definition |
|---|---|---|
| Claim extraction | Precision, recall, F1 | Matching by span overlap and semantic equivalence (embedding plus judge) against `extract_gold`; decontextualization acceptable-rate by human rating |
| Retrieval | Recall@k, nDCG@k, evidence-set recall | Fraction of gold necessary documents retrieved in top-k; evidence-set recall requires all necessary documents |
| Source diversity | Distinct origin groups per claim; ownership groups per claim | Mean and distribution |
| Independence | Edge precision/recall; group purity (B-cubed) | Against `lineage_gold` |
| Stance | Macro-F1; false-support rate | Share of refuting/irrelevant passages labelled supports |
| Verification | Macro-F1 over mapped labels; accuracy; per-label recall; AVeriTeC score (evidence-aware) | Use official AVeriTeC scorer for that dataset; for the 8-label taxonomy report confusion matrices |
| Contradiction | Precision, recall | Pairwise conflicts versus annotations |
| Unsupported-claim rate | Unsupported sentences / total factual sentences in articles | After A14, measured by independent audit (human plus judge of a different family) |
| Citation correctness | Share of citations where evidence actually entails sentence (human audited sample, n >= 300) | |
| Citation coverage | Share of factual sentences with at least one valid citation | |
| Calibration | ECE (15 equal-mass bins), MCE, Brier score, reliability diagram; risk-coverage curve (AURC) | Per claim type and overall |
| Faithfulness | NLI entailment score and human audit | |
| Writing quality | Rubric 1 to 5: accuracy, neutrality, clarity, structure, appropriate uncertainty; angle-coverage versus human article (Data2Story-style) | 3 raters, ICC reported; automated judge only from a different family than the writer and always checked against humans |
| Headline | Mislead-flag precision/recall | |
| Security | Injection success rate (tool hijack, label manipulation, canary leak) | Target zero tool hijacks |
| Latency | p50/p95/p99 per profile | |
| Cost | Tokens, calls, USD per investigation and **per correct verdict** | Prices from config |
| Reliability | Fraction of investigations completing without manual intervention; resume success under chaos | |

## 5. Baselines

| ID | System | Definition (same models, same budget) |
|---|---|---|
| B0 | Single LLM plus web search | One agent with a search tool, asked for a verdict and justification |
| B1 | General deep-research assistant | Use a commercial or open deep-research tool where reproducible; if not reproducible (API access or determinism), report as qualitative only |
| B2 | Basic RAG | Query generation, top-k retrieval, single verdict prompt |
| B3 | Simple multi-agent baseline | Reimplementation of the uploaded fact-checker's four-agent pipeline (FOL decomposition, query generation, single-credible-source evidence extraction, weighted vote) with the same LLMs and search provider; documents deviations |
| B4 | Published systems | AVeriTeC shared-task systems where code and outputs are public (e.g. HerO), compared on the same dataset split with their reported scores clearly marked as taken from the literature |

Fairness: identical model class and token ceiling per claim; identical search provider and cut-off date; same retry policy; each baseline gets a tuning budget equal to Meridian's on the dev split.

## 6. Experimental design and statistics

- **Primary endpoints (pre-registered):** (1) macro-F1 on AVeriTeC-style labels mapped to the taxonomy (and official AVeriTeC score where applicable); (2) ECE; (3) cost per correct verdict.
- **Secondary:** retrieval recall, unsupported-claim rate, citation correctness, latency, security.
- **Sample size:** run a pilot of 100 claims to estimate variance; compute n for 80% power to detect the smallest effect worth caring about (default: 3 macro-F1 points) using paired bootstrap simulation; minimum 500 claims per arm.
- **Tests:** paired bootstrap (10,000 resamples) for 95% CIs of differences; McNemar's test for paired correctness; permutation test for macro-F1; Holm-Bonferroni correction across the secondary metrics; effect sizes reported.
- **Seeds and variance:** LLM nondeterminism handled by running each system k = 3 times with temperature policy fixed per role; report mean and run-to-run SD; deterministic components (decision table) tested separately.
- **Ablations (required in Phase 11):** independence analysis off (count URLs); adversarial verifier off; decision table versus LLM-selected label; hybrid retrieval versus BM25 only; full-document reading versus snippets; reranker off; diversification off; calibrated versus uncalibrated; polish/revise rounds 0, 1, 2, 3 on at least 100 articles (the uploaded paper used three).
- **Claims policy:** a "beats X" statement appears in any document only if the CI of the primary difference excludes zero on the locked test set and the comparison satisfied the fairness rules.

## 7. Calibration protocol

1. Split: train 60%, validation 20%, test 20%, stratified by claim type and label; time-based split for developing-story claims.
2. Features: S, R, C, n groups, primary flags, claim type, topic, impact, adversarial outcome.
3. Models: logistic regression (baseline), isotonic regression, optional small gradient boosting; choose by validation ECE and Brier.
4. Report ECE, Brier, reliability diagrams, AURC; compare to LLM self-reported confidence (expected to be worse; report it).
5. Deploy only if test ECE <= 0.08 (initial threshold, revisit) and no claim-type subgroup with n >= 50 has ECE > 0.15; otherwise keep `calibrated_probability = null` for that subgroup.
6. Version as `calibration_version`; recalibrate on any change to model, prompt, retrieval, or policy versions; monitor drift weekly on resolved developing-story claims.

## 8. Writing and editorial evaluation

Rubric (1 to 5 each): factual accuracy (checked against ledger), neutrality, clarity and structure, appropriate expression of uncertainty, usefulness. Three raters per draft; report mean, ICC. Compare Meridian drafts with B0 drafts (single LLM with search) blind and randomized. Seeded-hallucination test: inject false sentences into drafts and measure A14 recall (target >= 95%, to be confirmed or revised from data) and false-block rate.

## 9. Adversarial and security evaluation

Suite described in `injection_suite`. Outcomes: (a) tool-hijack attempts succeeded (must be 0), (b) label manipulation (verdict changed by content instruction; must be 0 for rule-engine labels), (c) canary leakage, (d) fabricated-evidence acceptance rate, (e) SEO-farm copy corroboration inflation (independence analysis must collapse copies). Run on every PR touching agents, tools, prompts, or the fetch gateway.

## 10. Operational evaluation

Load test: replay 24 h of recorded feeds at 1x, 5x, 20x; measure throughput, queue depth, p95 latencies, cost. Chaos test: kill workers at random nodes, drop the DB connection, throttle the model provider, return invalid JSON; assert no lost tasks and correct terminal states. Soak: 7 days in staging.

## 11. Reporting template (`docs/benchmarks/REPORT_vN.md`)

1. Executive summary with the honest scoreboard (wins, ties, losses).
2. Setup table: datasets and versions, models, providers, budgets, seeds.
3. Primary results with CIs and tests.
4. Ablations.
5. Calibration.
6. Writing, security, performance, cost.
7. Failure analysis (top 20 errors with causes).
8. Threats to validity (leakage, annotator bias, judge bias, provider drift).
9. Reproduction instructions.

## 12. Regression policy

`evaluation/metrics/tolerances.yaml` pins, per metric and per component, the maximum allowed drop on the golden regression subset (default: 1 point absolute for F1 metrics, 0.01 for ECE, zero tolerance for security and quote-verification pass rate). CI blocks merges that exceed tolerance; intentional trade-offs require an ADR.
