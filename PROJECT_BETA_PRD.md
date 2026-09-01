# PROJECT BETA — Product Requirements Document (PRD)

**Version:** 1.9 (solo project. **v1.9 (2026-08-30) records the verified data architecture** — dual-feed on Alpaca's free tier, `data.start` fixed at 2016-06-10, mandatory RTH filtering, scale-free volume features with a transfer-validation gate, and the live-path recency finding. v1.8 added publication constraints; v1.7 the verified licensing; v1.6 §5.15 and the Phase 1 alignment.)
**Governing document:** Project Outline (Revision 9). *The Outline governs scope, timeline, evaluation methodology, the data architecture (§9), upgrade paths (§9B), the Responsible AI charter (§20) and publication constraints (§20.5). This PRD adds engineering specifications: module contracts, data schemas, interfaces, and per-module acceptance criteria. Where any conflict exists, the Outline wins and this PRD must be amended.*

**Note on this document's role.** The Phase 1 repo-hygiene lecture poses a stress test worth taking literally: *"can you regenerate the project from your spec and tests?"* This PRD is that spec.

---

## 1. Product Vision

PROJECT BETA is an AI-assisted paper-trading research platform for a single liquid ETF (SPY), built as a solo AI Capstone project on the **AI Engineering track**. AI augments — never replaces — a transparent rule-based strategy, through market-regime classification, signal-quality filtering, grounded explanation, and (conditionally) structured news understanding. Every trade decision is logged, auditable, explainable, and reproducible.

## 2. Goals and Non-Goals

**Required (guaranteed core):** end-to-end workflow; one primary rule-based strategy (momentum breakout) with full evaluation rigor; regime classifier; signal-quality model; deterministic risk engine; execution simulator + Alpaca paper trading; decision logging; LLM explanation service; failure-analysis assistant; dashboard; evaluation harness; model cards, a system card, a containerized release candidate, and a latency & cost report (§5.15).

**Conditional:** Plan A news gate (Week 2 gate). **Optional:** Plan B news features, interactive query layer (Week 10 gate).

**Non-goals (permanent):** live-money trading; reinforcement learning; autonomous LLM trading decisions; HFT/tick data; multiple assets; multiple *fully-evaluated, graded* strategies; SEC-filing RAG; AI-controlled risk rules.

**Account type:** **Alpaca Trading API, Basic (free) tier.** Not Broker API — that serves end users other than the account holder, breaching the personal, non-commercial data licenses this plan relies on and moving the project into the LLM provider's consumer-facing high-risk category.

## 3. System Architecture

```text
Market Data — Alpaca Basic tier, DUAL FEED (Outline §9)
    backtest mode → SIP consolidated, 2016-06-10 onward
    paper mode    → IEX real-time
→ 1. Data Pipeline (ingest, validate, RTH filter)
→ 2. Feature Engineering (scale-free volume features, §5.2)
→ 3. Strategy Engine (primary: momentum breakout; secondary: exploratory toggle)
→ 4. Regime Classifier ─┐
→ 5. Signal-Quality Model ─┤
→ 6. News Gate (conditional) ─┤
→ 7. Trade Decision Engine (combines gate votes)
→ 8. Risk Engine (deterministic)
→ 9. Execution Layer (simulator | Alpaca paper — paper endpoints only)
→ 10. Decision Log (single source of truth)
→ 11. Explanation Service (reads log only)
→ 12. Dashboard
→ 13. Failure Analysis
→ 14. Evaluation Harness (enforces primary-vs-secondary distinction, §5.14)
→ 15. Packaging, Cards & Release Engineering
```

**The two run modes use different data feeds.** This is deliberate and is the single most important thing a new reader must understand about the data layer — see §5.2 for the consequence and its mitigation.

## 4. Core Data Contracts

### 4.1 CandidateTrade

```json
{
  "trade_id": "uuid",
  "timestamp": "2026-07-15T14:00:00Z",
  "bar_timeframe": "5Min",
  "symbol": "SPY",
  "direction": "long",
  "signal_type": "momentum_breakout",
  "signal_strength": 0.71,
  "entry_price_ref": 552.31,
  "stop_price": 549.10,
  "target_price": 558.75,
  "features_snapshot_id": "feat_2026-07-15T14:00:00Z",
  "strategy_version": "mom_v1.2"
}
```

### 4.2 DecisionRecord (single source of truth)

```json
{
  "decision_id": "uuid",
  "trade_id": "uuid",
  "timestamp": "2026-07-15T14:00:01Z",
  "run_id": "run_2026q3_wf_fold3",
  "mode": "backtest",
  "feed": "sip",
  "regime": {"label": "uptrend", "probs": {"uptrend": 0.72, "downtrend": 0.08, "choppy": 0.20}, "vol_flag": "low", "model_version": "regime_xgb_v0.4"},
  "signal_quality": {"p_profit": 0.64, "p_target_before_stop": 0.58, "model_version": "sq_xgb_v0.2"},
  "news_gate": {"status": "not_enabled"},
  "decision": "approved",
  "decision_reason_codes": ["REGIME_PERMITS", "SQ_ABOVE_THRESHOLD"],
  "risk": {"position_size": 100, "sizing_rule": "vol_adjusted_v1", "active_constraints": [], "drawdown_state": 0.031},
  "execution": {"fill_price": 552.35, "slippage_bps": 0.7, "commission": 0.0, "fill_delay_bars": 1},
  "outcome": {"exit_timestamp": "2026-07-17T18:00:00Z", "exit_reason": "target", "pnl": 612.40, "mae": -180.00, "mfe": 655.00},
  "latency_ms": {"features": 12, "regime": 4, "signal_quality": 3, "decision": 1, "explanation": 900}
}
```

`decision` ∈ {approved, reduced, delayed, rejected}. `decision_reason_codes` come from a fixed, documented enum. **`feed` is new in v1.9** and is mandatory: a record produced from IEX is not comparable to one produced from SIP, and the field makes that inspectable rather than inferred. `latency_ms` feeds the Week 12 report.

**Publication note.** This record carries market prices. Full-history logs must not be committed to the public repo (Outline §20.5); enforcement is in §5.10. Contains no personal data.

### 4.3 RunConfig

```yaml
run_id: run_2026q3_wf_fold3
mode: backtest                       # backtest | paper
data:
  symbol: SPY
  timeframe: 5Min
  feed: sip                          # sip for backtest, iex for paper — see §5.2
  session: rth_only                  # RTH filter applied at the pipeline stage (§5.1)
  start: 2016-06-10                  # VERIFIED floor: 2015 returns nothing on either feed
  end: 2026-06-30
  dataset_hash: "sha256:..."
strategy: {name: momentum_breakout, version: mom_v1.2, params: {...}, tier: primary}
models:
  regime: {version: regime_xgb_v0.4, artifact_hash: "sha256:..."}
  signal_quality: {version: sq_xgb_v0.2, artifact_hash: "sha256:..."}
  llm: {provider: ..., model_version: "pinned-id", purpose: explanation_only}
  sentiment: {repo: ..., revision: "pinned-sha", license: "..."}   # Plan A only
news_gate: {enabled: false}
risk: {max_position: ..., max_drawdown: 0.15, daily_loss_limit: ..., sizing: vol_adjusted_v1}
costs: {commission_bps: 0.5, spread_bps: 1.0, slippage_model: sqrt_vol_v1, fill_delay_bars: 1, cost_multiplier: 1.0}
walk_forward: {train_months: 36, test_months: 6, step_months: 6}   # ~14 folds over 2016-06 → 2026-06
seed: 42
```

**All three data fields are now settled facts, not placeholders.** `start: 2016-06-10` and the fold design are confirmed by direct API probe (Outline §9); `feed` and `session` are new required fields.

## 5. Module Specifications

### 5.1 Data Pipeline
- **Responsibility:** ingest and validate OHLCV; apply the RTH filter; produce a versioned, hashed dataset.
- **In → Out:** provider API → validated bar store + `dataset_hash`.
- **Feed selection:** `sip` in backtest mode, `iex` in paper mode, from `data.feed`. The module must refuse a `mode`/`feed` combination the account cannot serve (SIP recent data returns 403) with a clear error rather than an empty result set.
- **RTH filtering (mandatory, new in v1.9).** SIP returns 192 bars/day (04:00–20:00 ET); **~60% are extended-hours**. The strategy trades regular hours only, and the filter is applied **here**, at ingestion, so no downstream component can forget it. Extended-hours liquidity and spreads behave nothing like the regular session; letting those bars into feature computation is a silent source of inflated backtests.
- **Validation rules:** gaps, duplicate bars, outliers, timestamp anomalies; UTC everywhere. **Must distinguish a partial day at a query-window boundary from a genuine gap** — the 2026-06-30 "13-bar day" observed in verification was the 60-day window edge, not a defect, and a naive rule would flag it forever.
- **Licensing:** Alpaca's Terms & Conditions *and* Customer Agreement §30 both prohibit redistribution, so the repo ships a **small sample fixture + a documented re-fetch script**, never the full bar store. The re-fetch script must reproduce a dataset matching the recorded `dataset_hash`.
- **AC:** validation report per ingest; a corrupted fixture is caught by tests; identical inputs produce identical `dataset_hash`; **RTH filter verified by a test asserting exactly 78 bars on a known full session**; **no raw vendor bar data committed (CI check on tracked file paths/sizes)**; a mode/feed mismatch raises rather than silently returning nothing.
- **Documentation deliverable:** **Data Card** (Wk 4) — both feeds, coverage windows, the 3.16% volume finding, validation rules, licensing constraint, and how to obtain the data.

### 5.2 Feature Engineering
- **Responsibility:** compute features (returns, realized vol, MA slopes, ADX, volume measures, VWAP distance, range expansion) with strict point-in-time discipline.
- **In → Out:** RTH-filtered validated bars → feature matrix keyed by `features_snapshot_id`.
- **Requirements:** every feature uses only data available at bar close; feature code self-reviewed for lookahead bias before merge.

#### The train/live feed mismatch — the constraint that shapes this module

Backtests run on SIP; live paper trading runs on IEX (§3). **Verified 2026-08-30: IEX carries a median 3.16% of consolidated volume** (2.79–3.36% across six sessions — structural, not noise). A feature defined on *absolute* volume would therefore be trained on values ~30× larger than it meets at inference, and would fail silently the moment the system went live.

**Requirement: every volume-derived feature is scale-free.** Volume enters the feature set only as a ratio or standardized score against its own trailing window on the same feed — never a raw count or raw delta. The feature reference table tags each feature `price_derived` or `volume_derived`, and no `volume_derived` feature may be defined in absolute units.

**Requirement: the transfer assumption is tested, not assumed (Week 1–2, blocking).** The feeds overlap historically from 2021, so:

> Compute the scale-free volume features from IEX and from SIP over the same 2021–2026 period; correlate bar-by-bar and compare distributions.
> - **Strong agreement** → volume features are retained; the correlation is published in the Data Card and both Model Cards.
> - **Weak agreement** → volume-derived features are **dropped entirely** and the Model Card records that IEX proved unrepresentative.

**This experiment must conclude before Week 7's signal-quality work begins** — the outcome determines that model's feature set. The decision is pre-committed above so it is settled by evidence rather than by whatever is convenient in week 7.

- **AC:** automated leakage test passes — shifting input data forward one bar changes no historical feature values; feature reference table complete with derivation tags; **no volume feature is expressed in absolute units (enforced by a test over the feature registry)**; **the transfer-validation result is recorded in the experiment log with its correlation figures before the signal-quality model is trained.**

### 5.3 Strategy Engine
- **Responsibility:** `generate_candidates(features, bars) -> list[CandidateTrade]` from a transparent rule set.
- **Primary — momentum breakout:** the only strategy with full evaluation rigor this semester.
- **Secondary — MA trend, mean reversion:** same interface, backtest-only, labeled exploratory/not graded.
- **Requirements:** parameters in RunConfig, not code (each tags `tier: primary|secondary`); primary rules documented in plain language.
- **AC:** same data + config ⇒ byte-identical candidate list; **the harness (§5.14) refuses to produce a graded ablation table for any `tier: secondary` strategy.**

### 5.4 Regime Classifier
- **Responsibility:** per-bar regime probabilities.
- **Label scheme:** 3 trend states + separate binary volatility flag. Rules documented; changes require a decision-log entry.
- **Models:** logistic regression baseline → RF/XGBoost; optional HMM comparison.
- **AC:** trained via walk-forward only across the ~14 folds; calibration curve + Brier score per fold; M1-vs-B2 ablation table; **per-regime and per-volatility-state breakdown (Outline §20.3)**; Model Card records the feed.

### 5.5 Signal-Quality Model
- **Responsibility:** score each CandidateTrade.
- **In → Out:** CandidateTrade + features + regime output → `{p_profit, p_target_before_stop, model_version}`.
- **Requirements:** labels from simulated outcomes under the same cost model as evaluation; probabilities calibrated; acceptance threshold a swept RunConfig parameter. Trained only against the primary strategy's candidates. **Feature set is contingent on the §5.2 transfer verdict** — do not begin training until that result is logged.
- **AC:** calibration report per fold; M2-vs-M1 ablation table; documented behavior when trade count is insufficient (pass-through with a logged warning); accept/reject rates and realized performance sliced by regime.

### 5.6 News Gate (conditional — Plan A)
- **Build trigger:** Week 2 feasibility gate = GO or CONDITIONAL. If NO-GO, not built; `news_gate.status = "not_enabled"`.
- **Architecture:** a small local sentiment model scores bulk *historical* headlines; the LLM handles *live* extraction. **All outputs cached by headline hash — backtests read cache only.** The cache stores the hash plus extracted fields, **not full headline text** (licensing).
- **Model selection:** FinBERT's published weights carry **no declared license** (Outline §20.1 row 4). Either don't vendor them — pinned revision, citation, Model Card disclosure — or select an explicitly-licensed model. **Decide at the Week 2 gate**; record revision and license in `models.sentiment`.
- **Requirements:** deduplication before scoring; freshness from first-publication timestamp; thresholds in RunConfig. **Injection containment:** extraction returns only the constrained schema; no free headline text reaches the trading path or the explanation prompt.
- **AC:** cache hit rate = 100% in backtest mode (enforced by test); policy decisions reproduce exactly from cached extractions; suppression metrics reported; **adversarial-headline red-team suite passes (Week 10).**

### 5.7 Trade Decision Engine
- **Responsibility:** combine strategy signal, regime permission, signal-quality threshold, and news verdict into one decision with reason codes.
- **Requirements:** pure function of its inputs; every path emits reason codes from the documented enum; precedence (risk > news > quality > regime) documented. *Its determinism is load-bearing for Outline §20.1 row 6 — no AI output reaches it as an instruction.*
- **AC:** unit tests cover every reason-code path; identical inputs ⇒ identical output.

### 5.8 Risk Engine
- **Responsibility:** deterministic position sizing and constraint enforcement.
- **Requirements:** no ML inside this module, ever; all limits in RunConfig; every activated constraint appears in `risk.active_constraints`.
- **AC:** property-based tests — no input sequence can exceed configured drawdown/exposure limits; each constraint has a dedicated triggering test.

### 5.9 Execution Layer
- **Responsibility:** fill simulation (backtest) and Alpaca paper-account submission (paper mode) behind one interface.
- **Cost model:** commissions, spread, slippage, delayed fills, market hours; `cost_multiplier` supports 2–3× stress runs.
- **Paper-only constraint:** paper endpoints and paper credentials only; **no live-money code path exists.**
- **Data-recency status (updated v1.9).** The Basic tier's 15-minute restriction applies to **SIP**, which returns `403` on recent data and `409` on streaming. **The live path is therefore IEX**, whose real-time websocket is available on this tier. *Final confirmation of IEX streaming latency during market hours is the one outstanding verification.* If IEX real-time proves unusable, the documented mitigations are: lengthen the live bar interval (documenting the backtest/live granularity mismatch), or upgrade to Algo Trader Plus (Outline §9B).
- **AC:** simulator results shift monotonically with cost_multiplier; paper mode round-trips an order end-to-end; both modes emit identical DecisionRecord execution fields; **a non-paper endpoint or live credential set is rejected with an explicit error (unit test).**

### 5.10 Decision Log
- **Responsibility:** append-only store of DecisionRecords; the single source of truth.
- **Publication constraint:** full-history logs **are not committed** to the public repo. Sample logs are bounded to a short window — target a few trading days.
- **AC:** every candidate trade in a run has exactly one record; records immutable once written; queryable by run_id, decision, reason code, regime **and feed**; no credential ever appears in a record; **committed sample logs stay within the configured bound (CI check on row count / file size).**

### 5.11 Explanation Service
- **Grounding rule (hard requirement):** the prompt contains only DecisionRecord fields and the reason-code documentation; no market data, no models, no external source.
- **AC:** automated audit — for ≥50 random explanations, every factual claim maps to a field in the source record (target 100%; **any hallucinated claim is a release blocker**); explanations exist for all four decision types.
- **Optional extension (Week 10 gate):** interactive query mode. **If built, Outline §20.4 gains a retention line for user-typed queries.**

### 5.12 Dashboard
- **Responsibility:** current regime, open positions, equity curve, recent decisions with explanations, model confidence, strategy-toggle panel.
- **Requirements:** a persistent, non-dismissible "paper trading only — not investment advice" statement (Harm 1, and the provider's AI-use disclosure standard). **Results views display the feed and session filter that produced them.**
- **AC:** measured via Outline §10.2 (≥8/9 correct across 3 unfamiliar readers, median audit under 60 s); refreshes with live paper-mode data; toggle panel labeled exploratory; disclaimer string CI-asserted.

### 5.13 Failure Analysis
- **Responsibility:** statistical clustering of losing trades, then LLM-written interpretation and targeted-test suggestions.
- **Order requirement:** statistics first, LLM narrative second.
- **AC:** top 3 failure modes documented, each with a targeted test merged; the narrative references no cluster that was not computed.

### 5.14 Evaluation Harness
- **Responsibility:** run the ablation ladder under walk-forward validation and produce the results tables, **for the primary strategy only.**
- **AC:** one command produces the full results table for a RunConfig set; subperiod and cost-stress runs are config variants, not code changes; **a `tier: secondary` RunConfig is rejected with a clear error**; results include the per-regime disaggregation with slice counts; **every results table records `feed` and `session`, and the harness refuses to place SIP-derived and IEX-derived runs in the same comparison table.**

### 5.15 Packaging, Cards & Release Engineering

- **Deliverables:**
  1. **Model Cards** (Wk 9) — regime and signal-quality models: intended use, training data and window, **feed provenance and the §5.2 transfer result**, features, walk-forward results, calibration, limitations, out-of-scope uses.
  2. **System Card** (Wk 9) — the composed pipeline, where AI sits and where it deliberately does not, the §20.2 guardrails, known failure modes, and the paper-trading/not-advice statement.
  3. **Container** (Wk 12) — a Dockerfile producing an image that runs a documented backtest end-to-end from a clean environment.
  4. **Latency & cost report** (Wk 12) — per-stage latency from `latency_ms`, bar-to-decision latency in paper mode, LLM cost per decision, cache hit rate, total spend against the Outline §9A budget.
  5. **Repo hygiene set** (Wk 1–2) — README (incl. the data-licensing constraint and §20.5 rules), LICENSE (MIT), CONTRIBUTING, CODE_OF_CONDUCT, issue labels, CI smoke test.
- **AC:** `docker build` succeeds from a clean checkout and the documented backtest runs inside the image; the latency & cost report regenerates from logged data with one command; cards exist for every shipped model and are linked from the README; CI green with no test disabled.

## 6. Cross-Cutting Requirements

| Requirement | Verifiable condition |
|---|---|
| Reproducible | Fresh clone + documented commands (incl. the re-fetch step) regenerate headline results; all model artifacts and datasets hashed |
| Leakage-safe | Feature leakage test (§5.2), backtest cache-only enforcement (§5.6), walk-forward everywhere, **RTH filter applied pre-feature (§5.1)** |
| Explainable | 100% of decisions have grounded explanations passing the §5.11 audit |
| Testable | CI runs unit + property + leakage tests on every merge; CI stays fast; no test disabled to force a green check |
| Auditable | Any reported number traces to a run_id and its DecisionRecords |
| Logged | Decision, experiment, AI-usage logs and risk register live in-repo from Week 1 |
| Evaluation rigor protected | Secondary strategies structurally cannot enter the graded ablation harness (§5.14) |
| Safe by construction | No live-money code path (§5.9); disclaimers CI-asserted; grounding audit at 100% or release blocked |
| License-compliant | No raw vendor data, headline text, or unlicensed model weights committed; sentiment model revision and license pinned; MIT LICENSE present |
| Publication-constrained | Committed decision logs stay within the bounded window (§5.10, CI-checked) |
| **Feed-honest** | **Every RunConfig, DecisionRecord, results table, Model Card and dashboard results view records `feed` and `session`; the harness refuses cross-feed comparisons (§5.14); no volume feature is expressed in absolute units (§5.2)** |
| Privacy-minimal | No personal data collected; no credential in a log, record, or prompt; secrets only in environment/CI secrets |
| Portable | `docker build` + documented command runs the system end-to-end from a clean environment |
| Fairness-disaggregated | Results report per-regime and per-volatility-state performance with slice counts |
| Provider-policy aligned | The LLM never enters the trade decision path; the dashboard carries an AI-use disclosure |

## 7. Milestones

| Weeks | Internal focus | PRD modules due | Official milestone |
|---|---|---|---|
| 1–2 | Foundation | 5.1 (**RTH filter, dual-feed selection, hashing**), 5.2 (**incl. the blocking transfer-validation experiment**), schemas §4, logs, leakage tests, **news feasibility verdict**, **repo hygiene set**, **Responsible AI charter**, **focus-area declaration**, **pitch artifact** | **Milestone 1 — end of Wk 2** |
| 3–4 | Baselines + harness | 5.3, 5.8, 5.9 (simulator), 5.10, 5.14 core; B1/B2 results over ~14 folds; **Data Card** | — |
| 5 | Regime prototype | 5.4 first-cut, wired end-to-end | **Milestone 2 — end of Wk 5** |
| 6 | Regime intelligence | 5.4 finalized; M1 ablation. *Fallback checkpoint* | — |
| 7–8 | Signal intelligence | 5.5 (feature set per the §5.2 verdict); M2 ablation. *Fallback checkpoint at end of Wk 8* | — |
| 9 | **ALPHA** | 5.9 on the Alpaca paper account via **IEX**, basic 5.12. **No news components.** **Plus Model Cards + System Card** | **Milestone 3 — end of Wk 9** |
| 9–10 | Conditional news | 5.6 if GO; M3 | — |
| 10 | Plan B gate · safety checks | Decision logged; **red-team pass on 5.6 / 5.11** | — |
| 11–12 | Interpretability + robustness + release candidate | 5.11, 5.13, robustness suite, fresh-clone test, docs, architecture diagram, demo script, **demo video draft**, **container**, **latency & cost report**, **user-impact run**. *Fallback checkpoint at end of Wk 11* | **Milestone 4 — end of Wk 12** |
| 13 | Polish for portfolio | Package repo/demo/report for employers | — |
| 14 | Ship | Demo video, final report, live presentation; second user-impact run | **Final Presentation — end of Wk 14** |

## 8. Release Acceptance Criteria

1. End-to-end run in both modes completes from ingestion through decision, logging, and dashboard, for the primary strategy.
2. Ablation B1→M2 complete under walk-forward with costs across the confirmed fold set; M3/M4 included iff gated in.
3. The prespecified primary metric comparison (M-tier vs. B2) is reported — improvement **or** a rigorously characterized negative result.
4. Explanation audit passes at 100% grounded on the sample (§5.11).
5. Every candidate trade is auditable: candidate → decision → reason codes → execution → outcome.
6. Top 3 failure modes documented with targeted tests merged.
7. Fresh-clone reproduction succeeds using the quick-start instructions plus the documented re-fetch step.
8. Container builds and runs the documented backtest from a clean environment.
9. Model Cards and System Card published and linked from the README, each recording feed provenance.
10. Latency & cost report published alongside the results tables.
11. The Outline §10.2 user-impact protocol has been run and reported.
12. Per-regime disaggregated results reported, including any regime where the filtered system underperforms B2.
13. Nothing in the public repo violates Outline §20.5.
14. **Every reported result records its feed and session filter, and the §5.2 transfer-validation result is published with the Model Cards.**
15. The strategy-toggle panel functions for at least one secondary strategy and is clearly labeled exploratory (nice-to-have, not release-blocking).

## 9. Open Questions

**Resolved:**
- ~~Which rule-based strategy ships~~ — **2026-08-26: momentum breakout.**
- ~~Bar timeframe~~ — **2026-08-26: 5-minute bars**, confirmed viable by verification.
- ~~Multi-strategy architecture~~ — **2026-08-26.**
- ~~Generative AI usage policy~~ — **2026-08-24: coding agents allowed course-wide.**
- ~~Team-up~~ — **2026-08-28: solo.**
- ~~Whether vendor terms permit redistributing bars~~ — **2026-08-30: they do not.**
- ~~Whether the Alpaca account carries an agreement beyond the T&C~~ — **2026-08-30: yes, Customer Agreement §30.**
- ~~Trading API vs Broker API~~ — **2026-08-30: Trading API.**
- ~~LLM output rights and provider policy~~ — **2026-08-30:** outputs assigned to the user; project sits outside the high-risk finance category by design; consumer terms cover dev assistance, commercial terms cover the API.
- ~~**Data source and tier**~~ — **2026-08-30: Alpaca Basic (free), dual-feed.** SIP for backtest (2016-06-10 onward, 10.2 years), IEX for live paper. $0. Outline §9.
- ~~**`data.start` and walk-forward fold design**~~ — **2026-08-30: 2016-06-10**, 36/6/6 giving ~14 folds.
- ~~**Whether volume features survive**~~ — **2026-08-30: conditionally, as scale-free features**, with a pre-committed drop decision if the §5.2 transfer experiment fails.
- ~~**Regular vs extended hours**~~ — **2026-08-30: regular hours only**, filtered at the pipeline stage (§5.1).

**Still open:**
- **IEX real-time streaming latency during market hours** — the one outstanding verification; determines whether Milestone 3's live loop works as designed (§5.9).
- **The §5.2 transfer-validation result** — scheduled Week 1–2, blocking for §5.5.
- **Professional vs Non-Professional subscriber classification** — self-declared at signup; default is Professional. Confirm what the account recorded.
- **Sentiment model choice** — FinBERT (no declared license) vs an explicitly-licensed alternative. Week 2 gate.
- **Signal-quality acceptance threshold default** — after first M2 calibration.
- **Dashboard stack** — Week 3, choose the cheaper one.
- **Compute-budget LLM figure** — needs a real cost-per-decision measurement.
- **Final Technical Report due date**, and **M1 due week (Week 2 vs "week ~3")** — confirm on Canvas.