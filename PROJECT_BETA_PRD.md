# PROJECT BETA - Product Requirements Document (PRD)

**Version:** 3.0. **v3.0 (2026-09-01)** removes the news gate, adds the options execution layer (§5.6), makes every contract and config **asset-class-aware**, records the completed data verification, and specifies the six architecture seams (§3B) that keep the post-course upgrade bounded. **v2.1** hardened §5.11. **v2.0** added halt control, replay mode and the layered architecture. **v1.9** recorded the dual-feed data architecture.

**Governing document:** Project Outline (**Revision 11**). *The Outline governs scope, timeline, evaluation methodology, the data architecture (§9), the scheduled-execution constraint (§9C), asset-class tiers (§7A), the upgrade path (§7B), the Responsible AI charter (§20), publication constraints (§20.5) and the AI application design answers (§22). This PRD adds engineering specifications. Where any conflict exists, the Outline wins and this PRD must be amended.*

**Architecture seams:** described in `Project_Outline.md` §7B. Post-course roadmap and vendor comparison are maintained separately.

**Note on this document's role.** The repo-hygiene lecture's stress test - *"can you regenerate the project from your spec and tests?"* - is why this PRD is kept current.

---

## 1. Product Vision

PROJECT BETA is an **interactive AI strategy workbench for paper trading**, built as a two-person AI Capstone project on the **AI Engineering track**. **The user picks a strategy family at setup** - momentum breakout, moving-average trend or mean reversion - and it runs the whole pipeline (§5.3). AI augments - never replaces - the transparent rule set the user chose, through market-regime classification, signal-quality filtering and grounded explanation. The guaranteed interaction is **decision-level interrogation** (§5.11B): select one decision or timestamp and ask why it was sized, rejected, reduced or absent, using only that record's stored fields. The optional cross-artifact layer (§5.11A) widens that reach to questions over fold results, failure clusters, sweeps and other strategy evidence. The system is an instrument, not an advisor: it never recommends a trade and never proposes a change to trading logic. The graded core is SPY equities; the same pipeline extends to BTC/USD as a validated secondary track and to single-leg SPY options as an execution layer. Every trade decision is logged, auditable, explainable, and reproducible - **and every reported result states which asset class it came from and how many folds stand behind it.**

## 2. Goals and Non-Goals

**Required (guaranteed core = the MVP):** end-to-end workflow; **three selectable rule-based strategy families, each running the full pipeline (§5.3)**, with the pre-registered evaluation rigor carried out on the primary one within the course; regime classifier; signal-quality model; deterministic risk engine **with halt control (§5.8A)**; execution simulator + Alpaca paper trading; decision logging; LLM explanation service **with grounding enforcement (§5.11)**; failure-analysis assistant; dashboard **with replay mode (§5.12A)**; evaluation harness; model cards, system card, container, latency & cost report (§5.15). **Plus the six architecture seams (§3B).**

**Graded secondary:** crypto (BTC/USD) - same pipeline, ~4 folds, fold count reported with every figure.
**Validated execution layer:** single-leg SPY options (§5.6) - no strategy-performance claim.
**Scoped deliverable (Weeks 6-10):** the **evidence manifest and cross-artifact query layer (§5.11A)**. This is the *broader* analysis surface, not the product's only interaction: per-decision interrogation is §5.11B and ships in the core above. **Gated on its own prerequisite:** grounding must be generalised from one record to the manifest before any question is answered. **Fallback at end of Week 8:** if that is not done, the cross-artifact layer is cut. **The decision inspector is unaffected**, so the user can still select any decision or non-decision and ask why; what is lost is asking across many runs at once.

**Planned validation expansion:** a *validated* claim for more than one strategy family is in the scope plan, but not a guaranteed course deliverable. Validation is per strategy and takes a full pre-registered protocol run each (§5.3). The course deliverable implements all three selectable families and funds one full validation run; MA trend and mean reversion are named follow-on validation candidates after the course, queued one family at a time under the same protocol, unless schedule allows one to be pulled forward. Neither can carry a performance claim before that run. This is a budgeted sequence, not an unspecific future wish.

**Non-goals (permanent):** live-money trading; reinforcement learning; autonomous LLM trading decisions; HFT/tick data;  SEC-filing RAG; AI-controlled risk rules; **news/sentiment gate (dropped 2026-08-31)**; **generative what-if scenarios (§5.11 - excluded on grounding grounds, not scope)**.

**Account type:** **Alpaca Trading API, Basic (free) tier.** Not Broker API - that serves end users other than the account holder, breaching the personal, non-commercial data licences and moving the project into the LLM provider's consumer-facing high-risk category.

## 3. System Architecture - data flow

```text
Market Data - Alpaca Basic tier, DUAL FEED (Outline §9), via MarketDataProvider (§3B.1)
    backtest mode → SIP consolidated, 2016-06-10 onward
    paper mode → IEX - VERIFIED real-time, streaming entitled (2026-09-01)
→ 1. Data Pipeline (ingest, validate, RTH filter)
→ 2. Feature Engineering (scale-free volume features, §5.2)
→ 3. Strategy Engine
→ 4. Regime Classifier ─┐
→ 5. Signal-Quality Model ─┤
→ 7. Trade Decision Engine
→ 8. Risk Engine (deterministic) + 8A Halt Control
→ 6. Instrument Selection / Options Execution Layer (deterministic)
→ 9. Execution Layer (simulator | Alpaca paper - paper endpoints only)
→ 10. Decision Log (single source of truth)
→ 11. Explanation Service (reads log only) → grounding filter → store/display
→ 12. Dashboard (live | replay) + 12A Replay Mode
→ 13. Failure Analysis
→ 14. Evaluation Harness
→ 15. Packaging, Cards & Release Engineering
```

**Ordering note:** instrument selection sits *after* the risk engine. The decision to trade is made on the underlying; choosing the instrument that expresses it is a separate, deterministic step. This keeps the options layer out of the decision path entirely.

## 3A. System Architecture - layered view

| Layer | Modules | Constraint |
|---|---|---|
| **Frontend** | 5.12 Dashboard, 5.12A Replay Mode | Browser UI served locally. Single user, no auth surface, no public exposure - licensing, not preference (Outline §22.3) |
| **Backend** | **MarketDataProvider (§3B.1)** · 5.1 Data Pipeline · 5.2 Features · 5.3 Strategy Engine · 5.6 Instrument Selection · 5.7 Trade Decision Engine · 5.8 Risk Engine · 5.8A Halt Control · 5.9 Execution · 5.10 Decision Log · 5.14 Evaluation Harness · **grounding filter (§5.11)** | Fully deterministic. **No AI in the trade decision path, and none in instrument selection** |
| **AI layer** | 5.4 Regime Classifier · 5.5 Signal-Quality Model (local classical ML) · 5.11 Explanation Service · 5.13 Failure-Analysis narrative (hosted LLM) | Contributes classifications the backend consumes, and reads the log to produce prose. **Never writes into the decision path** |

**The load-bearing property:** the AI layer's outputs enter the backend as *data*, never as instructions - and, for generated prose, only after passing the grounding filter.

## 3B. Architecture Seams (new, v3.0)

Six extension points, built during the course so the post-course options upgrade is an adapter-and-config job rather than a rewrite (Outline §7B). Roughly 10% overhead now; 4–6 weeks retrofitted. **Each has a named second implementation already on the roadmap - none is speculative.**

### 3B.1 MarketDataProvider

```python
class MarketDataProvider(Protocol):
    def get_bars(symbol, timeframe, start, end, feed) -> DataFrame: ...
    def list_contracts(underlying, as_of, filters) -> list[Contract]: ...
    def get_quotes(symbol, start, end) -> DataFrame: ... # NotSupported on Alpaca
    def get_chain_snapshot(underlying, as_of) -> Chain: ... # NotSupported on Alpaca
```

**Define the full interface, including what the current vendor cannot do.** The Alpaca adapter raises `NotSupported` for quotes and chain snapshots; the pipeline degrades **explicitly and loudly**, never silently. Shaping the interface around one vendor's limits makes those limits architectural.

**AC:** a test asserts `NotSupported` propagates as a typed error, not an empty result; a stub second adapter satisfies the Protocol.

### 3B.2 Asset-class-parameterised RunConfig

`data_start`, session calendar, fold scheme, feature set and fill model are **per asset class**, never global constants. **AC:** adding a new asset class requires no change to harness or pipeline code - a config test proves it by registering a dummy class.

### 3B.3 Results schema with provenance

Every results row carries `asset_class`, `vendor`, `feed`, `data_start`, `fold_scheme`, `n_folds`, `strategy`, `strategy_version`, `strategy_tier`, `config_hash`. **This puts the comparability caveat in the data rather than in prose.** **AC:** schema coverage rejects a results row missing `asset_class`, `n_folds`, `strategy` or `strategy_version` (§5.14).

### 3B.4 Point-in-time universe

`universe_as_of(t) -> list[Symbol]`, returning `["SPY"]` today. **AC:** no module hardcodes `"SPY"` (grep test); the options implementation is a drop-in.

### 3B.5 Pluggable fill model

`FillModel.fill(candidate, bar_context, quote_context | None) -> Fill | NoFill`. Implementations: `BarFillModel` (equities), `SparseBarFillModel` (options), `QuoteFillModel` (post-course). **AC:** each model has its own test suite; the harness selects by config.

### 3B.6 Feature registry with declared requirements

Each feature declares `requires: bars | quotes | chain_snapshots`. The pipeline refuses to run a feature the active provider cannot satisfy. **AC:** a feature declaring `chain_snapshots` against the Alpaca provider raises at config time, not at runtime.

## 4. Core Data Contracts

### 4.1 CandidateTrade

```json
{
  "trade_id": "uuid", "timestamp": "2026-07-15T14:00:00Z", "bar_timeframe": "5Min",
  "asset_class": "equity", "symbol": "SPY", "direction": "long",
  "signal_type": "momentum_breakout", "signal_strength": 0.71,
  "entry_price_ref": 552.31, "stop_price": 549.10, "target_price": 558.75,
  "features_snapshot_id": "feat_2026-07-15T14:00:00Z",
  "strategy_version": "mom_v1.2"
}
```

`asset_class` ∈ {equity, crypto, option_underlying}. A candidate is always generated **on the underlying**; the options layer selects an instrument downstream (§5.6).

### 4.2 DecisionRecord (single source of truth)

```json
{
  "decision_id": "uuid", "trade_id": "uuid", "timestamp": "2026-07-15T14:00:01Z",
  "run_id": "run_2026q3_wf_fold3", "mode": "backtest",
  "asset_class": "equity", "feed": "sip", "vendor": "alpaca",
  "regime": {"label": "uptrend", "probs": {"uptrend": 0.72, "downtrend": 0.08, "choppy": 0.20}, "vol_flag": "low", "model_version": "regime_xgb_v0.4"},
  "signal_quality": {"p_profit": 0.64, "p_target_before_stop": 0.58, "model_version": "sq_xgb_v0.2"},
  "decision": "approved",
  "decision_reason_codes": ["REGIME_PERMITS", "SQ_ABOVE_THRESHOLD"],
  "risk": {"position_size": 100, "sizing_rule": "vol_adjusted_v1", "active_constraints": [], "drawdown_state": 0.031},
  "instrument": {"selected": "SPY", "selection_rule": "passthrough_v1", "tradeable": true},
  "execution": {"fill_price": 552.35, "slippage_bps": 0.7, "commission": 0.0, "fill_delay_bars": 1},
  "outcome": {"exit_timestamp": "2026-07-17T18:00:00Z", "exit_reason": "target", "pnl": 612.40, "mae": -180.00, "mfe": 655.00},
  "latency_ms": {"features": 12, "regime": 4, "signal_quality": 3, "decision": 1, "explanation": 900}
}
```

`decision` ∈ {approved, reduced, delayed, rejected}. Reason codes come from a fixed documented enum. `asset_class`, `feed` and `vendor` are **mandatory**.

**The `instrument` block (new, v3.0).** For equities and crypto, `selection_rule: passthrough_v1` and `selected` equals the underlying. For options it carries the OCC symbol, the rule version, and - critically - **`tradeable`**, recording whether a bar actually existed at decision time. A `tradeable: false` record is a *result*, not an error: it is the raw material of the fill-feasibility study (§5.6).

**A structural subtlety the grounding checker depends on.** `regime.probs` contains every regime *name* as a key, but the record only *asserts* the one in `regime.label`. A grounding check that treats keys as permitted values silently accepts a wrong regime claim. Keys are not claims; values are.

**Halt events** are logged to the same store as a distinct record type carrying `{halt_id, timestamp, trigger, reason_code, mode, state_snapshot}` (§5.8A).

### 4.3 RunConfig

```yaml
run_id: run_2026q3_wf_fold3
mode: backtest # backtest | paper | replay
asset_class: equity # equity | crypto | option (§3B.2)
provider: alpaca # resolves a MarketDataProvider (§3B.1)
data:
  symbol: SPY
  timeframe: 5Min
  feed: sip
  session: rth_only # rth_only | continuous | options_rth
  start: 2016-06-10 # ASSET-CLASS SPECIFIC - see below
  end: 2026-06-30
  dataset_hash: "sha256:..."
strategy: {name: momentum_breakout, version: mom_v1.2, params: {...}, tier: primary}
models:
  regime: {version: regime_xgb_v0.4, artifact_hash: "sha256:..."}
  signal_quality: {version: sq_xgb_v0.2, artifact_hash: "sha256:..."}
  llm: {provider: ..., model_version: "pinned-id", purpose: explanation_only}
instrument:
  selection_rule: passthrough_v1 # passthrough_v1 | occ_single_leg_v1
  expiry_window_days: [7, 45] # options only
  moneyness_band: [0.98, 1.02] # options only
  min_liquidity_bars: 20 # options only, from the measured screen
fill_model: bar_v1 # bar_v1 | sparse_bar_v1 | quote_v1 (§3B.5)
risk:
  max_position: ...
  max_drawdown: 0.15
  daily_loss_limit: ...
  sizing: vol_adjusted_v1
  halt: {data_staleness_bars: 3, max_consecutive_api_errors: 5, auth_failure: true, auto_halt_enabled: true}
  regime_abstain: []
costs: {commission_bps: 0.5, spread_bps: 1.0, slippage_model: sqrt_vol_v1, fill_delay_bars: 1, cost_multiplier: 1.0}
walk_forward: {train_months: 30, validation_months: 6, test_months: 6, step_months: 6}
seed: 42
```

**`data.start` and fold counts are asset-class specific** (Outline §7A):

| asset_class | data.start | session | folds at 30/6/6 |
|---|---|---|---|
| `equity` | 2016-06-10 | `rth_only` | ~14 |
| `crypto` | ≥2021-06-10 | `continuous` | ~4 |
| `option` | **2024-01-18** | `options_rth` | **0 - no walk-forward** |

An `asset_class: option` RunConfig with a `walk_forward` block **must be rejected at load time.** Options makes no walk-forward claim, and a config that silently accepts one invites a result nobody can defend.

## 5. Module Specifications

### 5.1 Data Pipeline
- **Responsibility:** ingest and validate OHLCV **through a `MarketDataProvider` (§3B.1)**; apply the session filter; produce a versioned, hashed dataset.
- **Feed selection:** `sip` in backtest, `iex` in paper. Must refuse a mode/feed combination the account cannot serve (SIP recent returns 403) with a clear error, not an empty result.
- **Session filtering (mandatory).** SIP returns 192 bars/day (04:00–20:00 ET). **IEX returns 74–87 bars/day against a 78-bar regular-session maximum, and options bars show the same pattern** - the filter is load-bearing on all three feeds. Applied **here**, at ingestion.
- **Coverage rules (revised v3.0, from measurement):**
  - **Do not assert exactly 78 bars/day** as a completeness test on IEX or options. Post-filter counts legitimately fall short when 5-minute intervals contain no trades on a feed carrying ~3% of consolidated volume. *The v2.1 criterion requiring exactly 78 bars was correct for SIP and wrong for IEX; it is now feed-specific.*
  - **Flag days below ~90% coverage for review**, do not auto-reject.
  - **Exclude the first and last day of any fetch window from coverage statistics.** A 9-bar session observed at a window edge was a boundary artifact, not an outage.
  - **A missing bar is a no-trade interval, not missing data** (§5.9).
- **Licensing:** the repo ships a **sample fixture + documented re-fetch script**, never the full bar store. Applies to equity, crypto and options bars alike.
- **AC:** validation report per ingest; identical inputs ⇒ identical `dataset_hash`; **RTH filter verified by a test asserting exactly 78 bars on a known full SIP session, and a bounded range (74–87) on IEX**; window-edge days excluded from coverage stats by test; no raw vendor data committed (CI check); mode/feed mismatch raises.
- **Data Card** (Wk 4): all feeds and asset classes, coverage windows, the 3.16% volume finding, the coverage rules above, licensing constraint.

### 5.2 Feature Engineering
- **Responsibility:** compute features with strict point-in-time discipline from session-filtered bars, **through the feature registry (§3B.6)**.
- **Feed-mismatch requirement.** IEX carries a median **3.16%** of consolidated volume (2.79–3.78% across six sessions). **Every volume-derived feature is scale-free.**
- **Transfer validation (Week 1–2, blocking §5.5).** Compute the scale-free volume features from IEX and SIP over 2021–2026; correlate bar-by-bar. Strong agreement → retain and publish the correlation. Weak agreement → **drop volume-derived features entirely**. **Must conclude before Week 7.** This is **the first build task** and the only open data-side risk.
- **AC:** leakage test passes (shift-forward invariance); feature reference table complete with derivation tags; **no volume feature in absolute units (test over the feature registry)**; the transfer result is logged before the signal-quality model is trained.

### 5.3 Strategy Engine

`generate_candidates(features, bars) -> list[CandidateTrade]`.

**Three selectable families, chosen at setup.** `strategy.name` in `RunConfig`
selects **momentum breakout**, **moving-average trend** or **mean reversion**.
All three are transparent rule sets: no model, no fit, no learned parameter,
and everything downstream can only remove or shrink the candidates they produce.

**All three run the whole pipeline.** Whichever family is selected goes through
backtest, the AI filters (§5.4, §5.5), the deterministic risk engine (§5.8) and
halt control, the decision log (§5.10), grounded explanations (§5.11), failure
analysis (§5.13) and the evidence workbench (§5.11A). **This is the v3.1 change:
the secondary families were previously backtest-only.** They are selectable
paths, not decorative toggles, and a user who picks mean reversion gets the same
instrumentation as one who picks momentum.

**What is gated is the claim, not the path.** `strategy.tier` is the claim
status, and it is per strategy:

| Status | Meaning |
|---|---|
| `primary` | Has been through the full pre-registered protocol: walk-forward at the locked fold scheme, cost stress, leakage checks, ablation, failure analysis. Only such a strategy may carry a performance claim |
| `secondary` | Runs everything and reports its own behaviour, and **may not carry a performance claim**. No headline metric, no ablation figure, no Sharpe |

A strategy moves from `secondary` to `primary` **only** by passing the same
protocol, in full, pre-registered before the run. There is no other door, and
`build_strategy` refuses to promote one by configuration.

**Honest status today:** momentum breakout is the only family that has been
through the protocol, and its first graded run returned `no_claim`. **No
strategy family is currently validated**, and the documents say so rather than
letting `primary` be read as "works".

**Claims are strategy-scoped, and there is no best-of-three.** Every results row
records its strategy name and version alongside asset class, feed and fold count
(§5.14). Comparing strategies to pick a winner is **not a supported claim**:
three families each hunting a positive result is three chances at one finding,
which is the multiple-comparisons failure the pre-registration exists to prevent.
Each family's claim stands alone, pre-registered separately, reported with its
own interval.

**AC:**
- Same data and config produce a **byte-identical candidate list** for every
  family.
- The harness **refuses a graded ablation** for any `tier: secondary` strategy,
  and `build_strategy` refuses a config that promotes one.
- Every family must produce decision records, explanations and workbench
  evidence that pass the same checks as the primary; the required test runs the
  full pipeline on a secondary family and asserts the records are complete.
- **No results table places two strategy families in one comparison**; the
  required schema check rejects a row missing `strategy` or `strategy_version`.

### 5.4 Regime Classifier
Per-bar regime probabilities; 3 trend states + binary volatility flag. The built model is hand-written logistic regression; RF/XGBoost remain behind the classifier seam only if later evidence shows model capacity is the constraint. **AC:** walk-forward only across ~14 folds (equity) or ~4 (crypto); calibration curve + Brier per fold; M1-vs-B2 ablation; **per-regime and per-volatility-state breakdown**; Model Card records the feed **and asset class**; **no options-trained variant exists** (§5.6).

### 5.5 Signal-Quality Model
Scores each CandidateTrade → `{p_profit, p_target_before_stop, model_version}`. Labels from simulated outcomes under the evaluation cost model; probabilities calibrated. **Feature set contingent on the §5.2 verdict.**
- **Scope:** this model scores the **underlying**. It is never trained on options bars - contract selection is deterministic and downstream (§5.6), which is why the options track needs no folds of its own.
- **Regime abstention.** Where evaluation shows the model underperforms B2 in a regime, that regime is listed in `risk.regime_abstain` and the model **abstains**. This is Outline §20.3's fairness mitigation, implemented rather than intended.
- **AC:** calibration report per fold; M2-vs-M1 ablation; accept/reject rates sliced by regime; **abstention has a dedicated test asserting no SQ-driven rejection occurs in an abstaining regime.**

### 5.6 Instrument Selection / Options Execution Layer (new v3.0 - replaces the deleted News Gate)

**Deterministic. No AI, ever.** Given an approved candidate on the underlying, selects the instrument that expresses it and records whether that instrument was tradeable.

- **Equities and crypto:** `passthrough_v1` - `selected` equals the underlying, `tradeable: true`.
- **Options:** `occ_single_leg_v1`. Contracts are enumerated via `/v2/options/contracts` with **`status=inactive`** for historical windows (verified 2026-09-01, `HTTP 200`); hand-built OCC symbology is a fallback, not a requirement. Selection is by expiry window, moneyness band and a **measured** minimum-liquidity threshold, all from RunConfig.
- **Point-in-time correctness (critical).** The candidate universe comes from `universe_as_of(t)` (§3B.4). Selecting a contract *because it turns out to have bars* uses knowledge that it traded - look-ahead bias in its purest form, and the project's most likely correctness defect.
- **Liquidity screen.** Bar presence by moneyness bucket, **fitted on the first ~25 months of options history and tested on the last ~6** - a genuine held-out split validating the selection rule. *Note: the exploratory probes sampled mid-range strikes rather than near-the-money, which understates ATM liquidity; the screen must be built from an ATM-anchored sample.*
- **What it reports:** fill-feasibility rate with confidence intervals; execution-cost characterisation by moneyness and regime; and the stated limitation that **Alpaca provides no historical options quotes**, so spread and slippage are bar-derived proxies.
- **What it never reports:** Sharpe, drawdown, or any strategy-performance metric for the options track (Outline §7A).

**AC:** identical inputs ⇒ identical contract selection; a test asserts the universe builder cannot see bars dated after the decision timestamp; `tradeable: false` records are retained and counted, never dropped; the harness refuses to compute a Sharpe for `asset_class: option`.

### 5.7 Trade Decision Engine
Combines strategy signal, regime permission, signal-quality threshold and **regime abstention** into one decision with reason codes. Pure function of its inputs; documented precedence (**risk > quality > regime**). **AC:** unit tests cover every reason-code path including abstention; identical inputs ⇒ identical output.

### 5.8 Risk Engine
Deterministic sizing and constraint enforcement. No ML inside, ever. **AC:** property-based tests - no input sequence can exceed configured drawdown/exposure limits; each constraint has a dedicated triggering test.

### 5.8A Halt Control

- **Responsibility:** stop the autonomous loop, immediately and auditably.
- **Manual kill switch:** one command, and a dashboard control.
- **Position policy on halt:** open positions are **left as they are**, not liquidated. An automatic unwind is itself a risky unsupervised action.
- **Auto-halt triggers**, each with a distinct reason code: daily loss limit · drawdown breach · consecutive broker API errors · data staleness · failed pre-trade sanity check · **authentication failure (new v3.0)**.
- **Restart is deliberate** - explicit operator action.
- **Rollback:** versioned, hashed artifacts.
- **Postmortem:** every auto-halt gets an experiment-log entry, feeding §5.13.
- **AC:** a test triggers **each** auto-halt condition and asserts no order follows; the kill switch stops the loop within one bar interval; every halt writes a reason-coded record; restart requires an explicit call and is tested.

### 5.9 Execution Layer
Fill simulation (backtest) and Alpaca paper submission (paper mode) behind one interface, **with a pluggable fill model (§3B.5)**.

- **Paper-only:** paper endpoints and credentials only; no live-money code path.
- **Data recency - RESOLVED 2026-09-01.** The Basic tier's restriction applies to SIP (403 recent, 409 streaming). **IEX is genuinely real-time** - latest trade 0.1 min old, latest quote ~0, and the **websocket stream authenticates and delivers trades ~0.1 s old**. No paid tier is required for M3.
- **Bar-lag interpretation.** REST *bar* lag cycles between ~0 and ~5 minutes because it reports the last *completed* 5-minute bar. That is the bar interval, **not feed latency**.
- **No-forward-fill rule (new v3.0).** An absent bar is an interval in which the instrument did not trade. `SparseBarFillModel` returns `NoFill`; it never synthesises a price. Applies to thin options strikes **and** thin IEX intervals.
- **Credential validity (new v3.0).** A check that credentials are *non-empty* is not a check. The layer makes one authenticated call at startup and **aborts on non-200**. *A key rotation on 2026-09-01 would otherwise have produced a full run of 403s that looked like a successful run.*
- **Dependency preflight.** `websockets` is required for the IEX stream and is not a default install. Its absence must **fail**, not warn.

**AC:** results shift monotonically with cost_multiplier; paper mode round-trips an order; **a non-paper endpoint or live credential set is rejected**; **submission is refused while halted**; **a missing bar produces `NoFill`, asserted by test**; startup aborts on an authentication failure; a missing stream dependency raises.

### 5.10 Decision Log
Append-only store of DecisionRecords and halt records. **Publication constraint:** full-history logs are not committed; sample logs bounded to a few trading days. **AC:** every candidate trade has exactly one record; records immutable; queryable by run_id, decision, reason code, regime, **asset_class**, feed and halt event; no credential ever appears in a record; **committed sample logs stay within the configured bound (CI check)**; **the guardrail test matches report/verification filenames anywhere in the name, not only as a prefix** *(a prefix-only match is what let `alpaca_verification_report.json` reach a public repo on 2026-09-01)*.

### 5.11 Explanation Service

**Grounding rule (hard requirement).** The prompt contains only DecisionRecord fields and the reason-code documentation; no market data, no models, no external source. The service has no tools, so this is a property of the architecture rather than an instruction the model is asked to follow.

**Three layers of enforcement**, implemented in `project_beta.grounding`, **built before the service exists**:

1. **Output filter, at generation time.** `enforce_grounding(text, record)` runs before an explanation is stored or displayed. Every numeral and controlled-vocabulary state label must trace to a field in the source record; a failure raises and the explanation is blocked.
2. **Automated claim checking, in the audit.** `check_explanation` does the mechanical part of the ≥50-sample audit - numeric claims (accepting percentage and rounded renderings: `0.72` ↔ `"72%"`) and state labels. **Human judgment is reserved for non-numeric prose.**
3. **Drift canary.** A fixed DecisionRecord passes through the live service in CI; the result must be grounded and must still mention the key state values.

**What the checker deliberately does not do.** It cannot judge prose. Small-integer suppression exists as an option and is **off by default** - a check that quietly ignores things is how a guardrail rots.

**New fields to cover (v3.0).** `asset_class` and the `instrument` block are assertable state: an explanation claiming a contract was tradeable when `tradeable: false` must fail the filter.

**Two surfaces read this section's grounding rule.** **§5.11B**, the decision inspector, is in the guaranteed core and uses this rule unchanged, one record at a time. **§5.11A**, the cross-artifact query layer, is optional and widens it to a hashed manifest.

**Explicitly out of scope: generative what-if.** Counterfactuals have no logged referent. *The permissible form, if ever built, is narration of a **precomputed** parameter sweep from §5.14.*

**AC:**
- **No explanation is stored or displayed without passing `enforce_grounding`;** a test asserts a hallucinated explanation raises.
- The ≥50-sample audit reports **100% grounded**, with the machine-checked/human-read split recorded. **Any hallucinated claim is a release blocker.**
- **Regression test on the label check:** a regime name appearing only as a key in `regime.probs` must **not** count as an asserted state. *This was a real defect, caught by the checker's own hallucination tests - the argument for writing those first.*
- **A false `instrument.tradeable` claim raises.**
- The drift canary passes, or its failure is investigated before results are published.

### 5.11B Decision Inspector (guaranteed core, new v3.2)

**Two interaction surfaces, and they are not the same thing.** This one is
**decision-level** and is in the guaranteed core. §5.11A is **cross-artifact**
analysis and is optional behind the Week 8 gate. Cutting §5.11A does not remove
the user's ability to interrogate the system; it removes the ability to ask
across many runs at once.

**Responsibility.** Let the user select one decision, or one timestamp at which
no decision happened, and ask a bounded question about it. The questions are
about *this* decision only:

- why was this trade sized the way it was
- why was this signal rejected
- why did the risk engine reduce or block the position
- **why did no trade occur at this timestamp**

**Evidence, and nothing else.** The answer is assembled from the stored fields
for that one decision: the `DecisionRecord`, the candidate-trade record, the
risk state at that bar, the deterministic strategy rule state, and the reason
codes. **No manifest, no retrieval across runs, no fold results, no clusters, no
sweeps.** One record in, one answer out, exactly as §5.11 already works.

**This is why it belongs in the core: the guarantee already exists.**
`project_beta.grounding` checks a text against a single record today, is tested,
and shipped before the service it polices. The inspector inherits that checker
unchanged. It needs no manifest and no widened grounding, so **nothing in this
section depends on the §5.11A prerequisite** and nothing here is at risk from
the Week 8 gate.

**The non-decision case, which is the part that needs building.** Today a bar
with no candidate produces no record at all, so there is nothing to answer from.
The inspector requires a **rule-state trace**: at each evaluated bar the
strategy records which rule conditions it checked and which one failed first,
under the same determinism and provenance rules as a `DecisionRecord`. Where
that trace exists, "no trade at 10:35" is answered with the failed condition and
its values. **Where it does not exist, the inspector says so plainly** and does
not infer. A guessed reason for a non-event is a fabricated claim about the
system's own state, which is precisely what §5.11's grounding rule forbids.

**Boundaries, same as everywhere else.** Read-only. No tools, no market access,
no write path. It explains one decision and refuses to recommend a trade,
propose a change to trading logic, or say which strategy family to use.

**AC:**
- Every answer passes `enforce_grounding` against the **single** record it
  describes; a test asserts an answer citing a value absent from that record
  raises.
- **A non-decision at a selected timestamp returns the failed rule condition**
  when the trace exists, and an explicit "not recorded" when it does not. A test
  covers both, and asserts no reason is invented in the second case.
- The rule-state trace is **deterministic and provenance-carrying**: the same
  data and config produce the same trace, for every strategy family (§5.3).
- The inspector answers with **no access to the evidence manifest**, asserted by
  a test, so the §5.11A cut cannot silently disable it.
- The four question types above are answerable for every strategy family.

### 5.11A Evidence Manifest & Grounded Query Layer (optional, Week 8 gate)

**Scope: across artifacts, not within one decision.** Per-decision questions are
§5.11B and are in the guaranteed core. This section is the **broader**
natural-language analysis: asking across fold results, failure clusters,
parameter sweeps and another strategy family's evidence, in one question. It is
the deeper half of the workbench, and it is the half that carries a prerequisite
and a cut line.

**Responsibility.** Answer questions that span a fixed set of precomputed
artifacts, with every claim cited.

**The manifest comes first.** A hashed, versioned `EvidenceManifest` naming
exactly what may be cited: the decision-log slice, the fold table, the
failure-cluster statistics (§5.13), and the parameter-sweep grid (§5.14).
Artifacts are **precomputed**; nothing is computed at query time, so an answer
can never depend on work the user cannot inspect. Each entry carries an id and a
content hash, and the manifest hash travels with every answer.

**Grounding, widened.** `project_beta.grounding` currently checks a text against
one DecisionRecord. §5.11A requires the same check against the manifest: every
numeral and controlled-vocabulary state label must trace to a cited artifact.
**This must be built and tested before the query layer answers anything**, the
same order that put the checker before the explanation service.

**The prose judge is advisory, and never the gate.** A separate
low-temperature LLM judge may be added as a **rubric-assisted verifier** for the
soft prose claims the mechanical checker cannot decide. It is never the source
of truth. The deterministic check against the frozen manifest is the gate, and
the judge sits beside it under one rule: **it may only downgrade.** It can flag a
claim as unsupported or disputed and send it to human review; it can never clear
a claim the deterministic check did not clear, and it can never promote a
blocked answer. Anything unsupported or disputed is blocked or queued for a
person, never published on the judge's say-so.

**Low temperature is not determinism, and the audit must not pretend otherwise.**
A judge verdict stored as audit evidence carries the model id, the prompt hash,
the rubric version and the sampling parameters, and its non-determinism is stated
rather than implied. The judge's own agreement with human labels is measured on a
sample, so its contribution is a reported number rather than an assumption. The
machine-checked, judge-flagged and human-read split is reported as it is for
§5.11.

**The boundary, enforced not requested.** No tools, no market access, no write
path, no multi-turn memory, and **no open-ended chat**: questions are answered
from a fixed taxonomy. The layer explains and compares logged or computed
evidence. **It refuses to recommend a trade or propose a change to trading
logic**, and refusal is a tested code path, not a prompt instruction.

**User text is untrusted input.** This is the first place in the system where
text it did not author reaches a prompt. Until now, prompt injection is
impossible by construction because every prompt is assembled from record fields;
that property ends here. User text is carried in a delimited slot the system
prompt declares to be data, never instruction (§20.2 Harm 4).

**Strategy questions are in scope; strategy advice is not.** The workbench can report what the selected strategy did and what evidence exists for it, including its claim status, and it can show another family's evidence beside it. **It refuses to rank strategies or answer which one to use**, for the same reason it refuses to recommend a trade: a ranking is advice, and the multiple-comparisons rule above means the comparison would not be supportable even if advice were allowed.

**In scope, the question taxonomy:** why a decision came out as it did; where
the strategy loses money, over the cluster statistics; which rung of the ladder
is earning its complexity, over the fold table; what a different threshold would
have produced, over the **precomputed** sweep and never generated; and how the
live paper run compares with the backtest distribution.

**Out of scope, permanently:** generated counterfactuals with no computed
referent (§5.11), recommendations, proposed strategy modifications, and anything
that would require the layer to reach outside the manifest.

**AC:**
- **No answer is returned without passing manifest grounding**; a test asserts an
  answer citing a value absent from the manifest raises.
- **Every claim carries an artifact, record or sweep-cell id**; an answer with an
  uncited claim fails.
- **An adversarial query corpus** is refused or answered from evidence only, with
  no item causing an instruction in user text to be executed.
- **A recommendation-request suite asserts refusal**, including requests phrased
  as questions about evidence.
- **The judge cannot clear.** A test asserts that a claim failing the
  deterministic check stays blocked whatever the judge returns, and that a judge
  verdict alone never marks a claim supported.
- **Judge verdicts are reproducible as records**: model id, prompt hash, rubric
  version and sampling parameters are stored with each verdict.
- The manifest hash and the artifact ids appear in the stored answer record, so
  an answer is reproducible from the artifacts it cites.
- **Week 8 fallback:** if manifest grounding is not merged, this section is cut.
  The §5.11B decision inspector and per-decision explanations remain; what is
  lost is cross-artifact reach, not the product's interaction. The cut is
  recorded, not silent.

### 5.12 Dashboard
Current regime, open positions, equity curve, recent decisions with explanations, strategy-toggle panel, **cross-asset panel**, **halt status and kill switch**. **Requirements:** a persistent, non-dismissible "paper trading only - not investment advice" statement; results views display **asset class, feed, session and fold count**; **live vs. replay unambiguously labeled**; **each cross-asset panel states its tier**, so a viewer cannot mistake a 4-fold crypto figure or an options feasibility rate for a core result. **AC:** measured via Outline §10.2; disclaimer string CI-asserted; halt control reachable without leaving the main screen; tier labels CI-asserted.

### 5.12A Replay Mode

- **Responsibility:** replay a recorded run deterministically at accelerated speed.
- **Why it exists:** the AI role is background automation, the least demonstrable of the three; on 5-minute bars a demo slot may contain **zero trades**, and the Final Presentation is a live demo worth 25%. Replay also makes the §10.2 protocol repeatable.
- **Requirements:** reads stored DecisionRecords only; **no re-computation.** Speed control. `mode: replay`. Unmistakable labeling.
- **AC:** replaying a run twice produces byte-identical displayed sequences; the replay/live indicator is CI-asserted; replay works from a bounded sample log.

### 5.13 Failure Analysis
Statistical clustering of losing trades, then LLM interpretation and targeted-test suggestions. **Order requirement:** statistics first, narrative second. **AC:** top 3 failure modes documented, each with a targeted test merged; **the narrative passes the same grounding check against its computed cluster statistics.**

### 5.14 Evaluation Harness
Runs the ablation ladder under walk-forward validation for the primary strategy, **on equities only** (Outline §7A). Crypto runs the same harness with its own fold scheme; options runs the feasibility study, not the ladder.

**AC:** one command produces the full results table; **every results row records `asset_class`, `feed`, `session`, `fold_scheme`, `n_folds`, `strategy`, `strategy_version` and `strategy_tier` (§3B.3), and required schema coverage rejects a row missing any of them**; **the harness refuses to place SIP- and IEX-derived runs, runs from different asset classes, or different strategy families in the same comparison table**; **it refuses to compute a Sharpe or drawdown for `asset_class: option`.**

### 5.15 Packaging, Cards & Release Engineering
**Model Cards** (Wk 9) - feed provenance, asset class, fold count, the §5.2 transfer result, calibration, limitations. **System Card** (Wk 9) - the composed pipeline, where AI sits and where it deliberately does not, the guardrails, the asset-class tier structure and why each tier claims what it claims. **Container** (Wk 12). **Latency & cost report** (Wk 12). **AC:** `docker build` succeeds from a clean checkout; cards linked from the README; CI green with no test disabled.

## 6. Cross-Cutting Requirements

| Requirement | Verifiable condition |
|---|---|
| Reproducible | Fresh clone + documented commands regenerate headline results; artifacts and datasets hashed |
| Leakage-safe | Feature leakage test, cache-only backtests, walk-forward everywhere, session filter pre-feature, **point-in-time instrument universe** |
| Explainable | 100% of decisions have grounded explanations; every one passes the generation-time filter before storage or display |
| Testable | CI runs unit + property + leakage + grounding tests on every merge; no test disabled to force green |
| Auditable | Any reported number traces to a run_id and its DecisionRecords; every halt traces to a reason code |
| Evaluation rigor protected | Secondary strategies structurally cannot enter the graded harness |
| **Tier-honest** | **Every results row carries `asset_class` and `n_folds`; no cross-asset or cross-feed comparison table; no performance metric computed for options** |
| **Upgradable** | **Each of the six seams (§3B) has at least one test; a stub second data-provider adapter satisfies the Protocol** |
| Safe by construction | No live-money code path; CI-asserted disclaimers; grounding audit at 100% or release blocked |
| Stoppable | Every auto-halt trigger has a test; the kill switch stops the loop within one bar |
| **Credential-honest** | **Startup makes one authenticated call and aborts on non-200; a non-empty check is not a check** |
| **Schedulable** | **The deployed tree is outside macOS TCC-protected folders, and the scheduled path is verified through the scheduler (Outline §9C)** |
| License-compliant | No raw vendor data or unlicensed weights committed; MIT LICENSE present |
| Publication-constrained | Committed decision logs stay within the bounded window; report/verification filenames matched anywhere in the name |
| Feed-honest | Every RunConfig, DecisionRecord, results table, Model Card and dashboard view records `asset_class`, `feed` and `session` |
| Demonstrable | Replay of a recorded run is deterministic and unmistakably labeled |
| Privacy-minimal | No personal data collected; no credential in a log, record, or prompt |
| Portable | `docker build` + documented command runs end-to-end from a clean environment |
| Fairness-disaggregated | Results report per-regime performance with slice counts; regime abstention implemented and tested |
| Provider-policy aligned | The LLM never enters the trade decision path; the dashboard carries an AI-use disclosure |

## 7. Milestones

| Weeks | Internal focus | PRD modules due | Official milestone |
|---|---|---|---|
| 1–2 | Foundation | **§3B.1 provider + 5.2 transfer experiment (the first build task)**, 5.1, schemas §4, **§5.11 grounding checker**, seams §3B.2–3B.6 scaffolded, logs, leakage tests, repo hygiene set, Responsible AI charter, focus areas, Outline §22 design answers, pitch artifact | **Milestone 1 - Fri 9/11, 11:59 p.m. ET** |
| 3–4 | Baselines + harness | 5.3, 5.8, **5.8A halt control**, 5.9 (simulator), 5.10, 5.14 core; B1/B2 over ~14 folds; **Data Card** | - |
| 5 | Regime prototype | 5.4 first-cut, wired end-to-end | **Milestone 2 - end of Wk 5** |
| 6 | Regime intelligence | 5.4 finalized; M1 ablation. *Fallback checkpoint + graded-options gate* | - |
| 7–8 | Signal intelligence | 5.5 (feature set per the §5.2 verdict, incl. abstention); M2 ablation; **§5.11A evidence manifest + widened grounding, with tests**. *Fallback checkpoint, incl. the §5.11A cut decision* | - |
| 9 | **ALPHA** | 5.9 on the paper account via IEX, basic 5.12, **5.11B decision inspector incl. the rule-state trace**, **halt control live**, running unattended from a non-protected folder. **Model Cards + System Card** | **Milestone 3 - end of Wk 9** |
| 9–10 | Cross-asset tracks | Crypto secondary run (~4 folds); **5.6 options execution layer** | - |
| 10 | Gates · safety | **§5.11A query layer wired on top of the merged manifest grounding**; **red-team pass on 5.11 and 5.11A**, incl. the injection corpus and the refusal suite | - |
| 11–12 | Interpretability + robustness + release candidate | 5.11 service wired to the existing filter, 5.13, **5.12A replay mode**, robustness suite, fresh-clone test, container, latency & cost report, user-impact run | **Milestone 4 - end of Wk 12** |
| 13 | Polish for portfolio | Package repo/demo/report | - |
| 14 | Ship | Demo video, final report, live presentation (replay-backed) | **Final Presentation - end of Wk 14** |

## 8. Release Acceptance Criteria

1. End-to-end run in both modes from ingestion through decision, logging, and dashboard.
2. **Ablation B1→M2 complete under walk-forward with costs, on equities.** Crypto reported with its fold count; options reported as feasibility, not performance.
3. The prespecified primary metric comparison reported - improvement **or** a rigorously characterized negative result.
4. **Explanation audit passes at 100% grounded, with the machine-checked/human-read split recorded, and no explanation was ever stored or displayed without passing the generation-time filter.**
5. Every candidate trade is auditable end to end.
6. Top 3 failure modes documented with targeted tests merged.
7. Fresh-clone reproduction succeeds using quick-start plus the documented re-fetch step.
8. Container builds and runs the documented backtest from a clean environment.
9. Model Cards and System Card published and linked from the README, recording feed provenance **and asset class**.
10. Latency & cost report published alongside the results tables.
11. The Outline §10.2 user-impact protocol has been run and reported.
12. Per-regime disaggregated results reported, including any regime where the filtered system underperforms B2.
13. Nothing in the public repo violates Outline §20.5, **and the pre-publication history rewrite is complete**.
14. **Every reported result records its asset class, feed, session filter and fold count.**
15. Every auto-halt trigger is tested; the kill switch stops the loop within one bar interval.
16. Replay mode reproduces a recorded run deterministically and is unmistakably labeled.
17. **The drift canary passes on the shipped model version, or its failure is investigated and explained.**
18. **Each of the six seams (§3B) has at least one passing test.**
19. The strategy-toggle panel functions for at least one secondary strategy and is labeled exploratory (nice-to-have).

## 9. Open Questions

**Resolved:** primary strategy · bar timeframe · multi-strategy architecture · AI usage policy · **team composition (two-person group approved 2026-09-03; expectations do not scale with size)** · redistribution prohibited · Trading API vs Broker API · LLM output rights and provider policy · **data source, tier, feeds, `data.start` per asset class, fold design, session filtering, scale-free volume features** · **AI role, interaction style, platform, pattern tier, task inventory** · **what-if excluded on grounding grounds** · **hallucination enforcement mechanism** · **IEX real-time latency and streaming entitlement (2026-09-01)** · **news gate - dropped** · **asset-class tiers** · **vendor switch for options - rejected on fold arithmetic** · **Week 10 red-team target - the explanation service** · **TCC / scheduled-execution constraint**.

**Still open:**
- **The §5.2 transfer-validation result** - Week 1–2, blocking §5.5. **The only open data-side risk.**
- **Professional vs Non-Professional subscriber classification** - no such document exists in the account.
- **Query layer go/no-go** - Week 10.
- **Signal-quality acceptance threshold default** - after first M2 calibration.
- **Dashboard stack** - Week 3.
- **Compute-budget LLM figure** - needs a real cost-per-decision measurement.
- **Whether the grounding checker needs a prose-claim heuristic** - decide after the first ≥50-sample audit.
- **Options ATM liquidity characterisation** - needed before the §5.6 selection rule can be finalised.
- **Final Technical Report due date** - confirm on Canvas. (M1 settled 2026-09-05: Friday 2026-09-11, 11:59 p.m. Eastern.)
