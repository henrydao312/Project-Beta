# PROJECT BETA - Project Outline (Revision 12)

**AI Capstone (CIS 5980) - AI Engineering Track - Two-person team: Henry Dao and Jacky**

Revisions 2–7 established scope, the multi-strategy architecture, the Product One-Pager (§1A) and the Demo Walkthrough (§19). **Revision 8** aligned to the Phase 1 deck. **Revision 8.1–8.2** verified the licensing audit and added publication constraints (§20.5). **Revision 9** recorded the verified data architecture (§9). **Revision 10 (2026-08-30)** completed the Phase 1 deck read, adding §22, §8A halt control, §20.3 step 3, and §19.5 replay mode.

**Revision 11 (2026-09-01) - the news gate is out, multiple asset classes are in, and Week 1 data verification is complete.** Every change here rests on a measurement, not a preference:

1. **Plan A / Plan B news gate DROPPED** (§5.6–5.7 and §6 deleted). Replaced by an options track. This removes M3/M4 from the ablation ladder, retires the Week 2 feasibility gate, and closes the FinBERT licensing problem by removal rather than substitution.
2. **New §7A - asset-class tiers.** "Multiple assets" leaves the permanent-exclusions list. Equities is the **graded core**; crypto is a **graded secondary**; options is a **validated execution layer**. The tiers are set by measured fold counts, not by preference.
3. **§9 data architecture completed.** All eight verification questions closed at **$0**. The decisive one: the IEX free tier is **genuinely real-time** and its **streaming is entitled**, so Milestone 3 needs no paid data tier.
4. **New §9C - the scheduled-execution constraint.** macOS TCC blocks launchd agents from privacy-protected folders. This is an M3 architecture requirement, discovered by a failed scheduled run.
5. **New §7B - the post-course upgrade path.** Options cannot be graded on 31 months of history; the architecture is built so that lifting the constraint later is a bounded job rather than a rewrite.

**Revision 12 (2026-09-05) - three corrections after the first graded run.** The
build is ahead of this document in three places. In each one the code is right
and the text was wrong, so the text moves:

1. **§5.1 labels are forward-looking, not contemporaneous.** Read literally, the
   old wording described a label computed from the same bar's features, which
   would have made M1 a model trained to reproduce an `if` statement. The
   implemented rule is still transparent but looks forward one session, and it
   carries a mandatory training-window embargo.
2. **§5.1 model roster corrected.** Logistic regression exists and is
   hand-written. Random forest, XGBoost and the HMM comparison do not exist.
3. **§5.2 volume verdict closed.** The feed-transfer experiment ran 2026-09-02,
   measured Spearman 0.57 against a pre-committed 0.70 bar, and resolved to
   DROP. It was the last open data-side risk and it is no longer open.

---

## 1. Project Statement (Course Step 1)

> **PROJECT BETA is an AI-assisted paper-trading system for a single liquid ETF (SPY) that uses a market-regime classifier and a signal-quality filter to gate a transparent rule-based strategy, enforces deterministic risk controls, and produces grounded LLM explanations for every trade decision - with the same system extended to crypto as a secondary validated track and to single-leg options as an execution layer.**

- **Track declaration:** **AI Engineering Track.**
- **User / stakeholder:** A discretionary retail trader or junior quantitative researcher who wants systematic, interpretable, risk-controlled filtering of trading signals.
- **Main workflow:** Market data → validation → features → rule-based signal → regime classification → signal-quality scoring → risk engine → simulated/paper execution → decision log → explanation → dashboard.
- **Expected value:** Improved risk-adjusted performance and reduced drawdown versus the identical unfiltered strategy, with a transparent, auditable rationale for every decision.
- **User-relevant success criteria:**
  1. The AI-filtered strategy improves at least one prespecified risk-adjusted metric (Sharpe or maximum drawdown) versus the identical rule-based strategy in walk-forward testing, net of costs - **or** produces a rigorously supported negative result.
  2. Every accepted, reduced, delayed, or rejected trade has a structured explanation that accurately reflects the true model and risk state.
  3. A reader of the dashboard can correctly state why the system took (or refused) a given trade, unaided - measured, not asserted (§10.2).

## 1A. Product One-Pager

**The issue.** Retail traders and junior quant researchers routinely act on trading signals they can't fully trust - noisy, unfiltered, and impossible to audit after the fact when a trade goes wrong.

**The audience.** Discretionary retail traders and junior quantitative researchers who want systematic, explainable, risk-controlled signal filtering - not a black box.

**The proposed idea.** An AI-assisted paper-trading system: a market-regime classifier and signal-quality model filter a transparent, rule-based momentum-breakout strategy on 5-minute SPY bars, a deterministic risk engine enforces limits, and every trade decision gets a grounded, plain-English explanation. The same pipeline extends to BTC/USD as a secondary track and to single-leg SPY options as an execution layer.

**What makes it stand out.** Most public "AI trading bots" let an LLM make the trade call directly and show one cherry-picked backtest. PROJECT BETA never lets AI touch trading logic - it only gates a transparent rule-based strategy - and every explanation is grounded in a logged decision (audited: ≥50-sample grounding check). Success is measured with an ablation ladder (§7) isolating what each AI component adds, under walk-forward validation, and a rigorous negative result counts as a legitimate outcome (§18). **And each asset class makes only the claim its data can support (§7A)** - a discipline most student projects skip. The differentiation is AI-engineering discipline - auditability, grounding, honest ablation - not a claim to have found a better trading strategy.

**Success criteria.**
- *Primary (offline):* the filters improve Sharpe or maximum drawdown over the unfiltered baseline (B2), net of costs, in walk-forward testing - or the negative result is rigorously characterized.
- *Primary (user-impact):* an unaided reader identifies the current regime, open positions, and the reason for the most recent decision (§10.2).
- *Secondary:* 100% of sampled explanations audit as grounded; the system runs live, unattended, on an Alpaca paper account.

**Biggest single risk + fallback.** The data-availability risk is **closed** - ten years of consolidated 5-minute history at zero cost, and as of 2026-09-01 every remaining data question is answered (§9). The largest remaining technical risk is the **train/live feed mismatch** (§5.2), with a designed mitigation and a pre-committed validation experiment. The largest schedule risk is unchanged: a working paper loop is due at Week 9.

## 2. Research Questions

**Primary:** Can an ML-based market-regime classifier and signal-quality model improve the risk-adjusted performance or reduce the drawdown of a transparent rule-based trading strategy on out-of-sample data, net of transaction costs?

**Secondary:** Does the same filtering approach generalize beyond a single equity instrument - and where the data cannot support a validated performance claim, can the system's decisions nonetheless be shown to be *executable* on that instrument? *(§7A: crypto answers the first half with ~4 folds; options answers the second.)*

## 3. Scope Tiers - the guaranteed core is the MVP

| Tier | Components | Status |
|---|---|---|
| **Guaranteed core = the MVP feature set** | Data pipeline, feature engineering, rule-based strategy (momentum breakout), regime classifier (M1), signal-quality model (M2), risk engine **incl. halt control (§8A)**, execution simulator, paper trading, evaluation harness, explanation agent, failure-analysis assistant, dashboard **incl. replay mode (§19.5)** | Committed - this alone is a complete capstone |
| **Graded secondary** | **Crypto (BTC/USD)** - same pipeline, ~4 walk-forward folds, fold count reported with every number (§7A) | Confirmed 2026-09-01 |
| **Validated execution layer** | **Single-leg SPY options** - contract selection, liquidity screen, fill-feasibility study with a held-out test (§7A, §5.6) | Confirmed 2026-09-01 |
| **Confirmed design, lightweight scope** | Multi-strategy toggle - MA trend and mean reversion behind the same interface (§5.3), backtest-only exploratory | Confirmed 2026-08-26 |
| **Optional** | HMM regime comparison, **read-only trade query layer (§22.1)**, daily AI summary | Week 10 decision |
| **Excluded** | Live-money trading, RL, autonomous LLM trading, tick data, SEC-filing RAG, AI-controlled risk rules, **news/sentiment gate (dropped 2026-08-31)**, **generative what-if scenarios (§22.1 - rejected on grounding grounds, not scope)** | Out of scope permanently |

**Named fallback checkpoints:**

- Regime classifier not calibrated and ablated against B2 by **end of Week 6** → the options overlay is reduced to a live paper-forward demonstration.
- **Week 6, graded-options gate:** if the equity core is running end-to-end - B1→B2→M1→M2 across 14 folds, with the risk engine and execution simulator - graded options *may* be revisited (§7B). If not, options stays a validated execution layer and moves to the post-course phase.
- Paper loop not running end-to-end by **end of Week 8** → the secondary-strategy toggle is dropped; Week 8 goes to the alpha.
- Release candidate not containerized and reproducible by **end of Week 11** → the query layer is off the table.

## 4. Core Pipeline

```text
Market data - SIP consolidated (backtest) | IEX (live paper), §9
→ data validation (gaps, duplicates, outliers, timestamps, RTH filter)
→ feature engineering (returns, realized vol, MA slopes, ADX, scale-free volume, VWAP distance, range expansion)
→ transparent rule-based signal
→ market-regime classifier
→ signal-quality model
→ combined trade gate
→ deterministic risk engine ⟵ halt control (§8A)
→ instrument selection ⟵ options execution layer (§5.6), equities pass through
→ execution simulator / Alpaca paper broker
→ structured decision log
→ LLM trade explanation (grounded in logged state only)
→ dashboard (live | replay, §19.5)
→ failure-analysis assistant
```

For the frontend / backend / AI-layer view the M1 Design Checklist asks for, see **§22.4**.

## 5. AI Components

### 5.1 Market-Regime Classifier (required - M1)

**Labeling scheme:** 3 trend states - uptrend / downtrend / choppy - from a transparent rule, plus a separate binary volatility flag. Rationale: crossed classes on a short-bar history produce thin, noisy labels; 3+1 keeps classes populated and interpretable.

**The rule is transparent but forward-looking** (amended Rev 12; earlier text implied it read the current bar). The label at bar `t` describes what the next `horizon` bars actually did, scaled by the volatility known at `t`: `uptrend` when the forward log return exceeds `trend_k * rv_78[t] * sqrt(horizon)`, `downtrend` below the negative of that, `choppy` otherwise, with the volatility flag set when realized vol over the same window exceeds `vol_k * rv_78[t]`. Defaults: `horizon = 78` bars (one session), `trend_k = 0.5`, `vol_k = 1.15`. A rule evaluated on the current bar's own features would make the label a deterministic function of the classifier's inputs: M1 would fit almost perfectly, add nothing over B2, and the ablation rung would measure nothing.

**The embargo is the cost, and it is not optional.** A label at `t` reads prices to `t + horizon`, so the last `horizon` bars of every training window are dropped. `EMBARGO_BARS` is that count, the fold runner drops those rows, and `test_models.py` asserts it. Skipping it leaks the opening hours of the validation window into training, which improves results and leaves no trace. See §11.

**Models:** logistic regression, and it is the only one built (corrected Rev 12). It is a hand-written multinomial implementation in `models/linear.py` rather than scikit-learn, which buys exact reproducibility across library versions and no hidden preprocessing. **Random forest, XGBoost and the optional HMM comparison do not exist.** `models/linear.py` defines a `Classifier` protocol so adding one is a bounded job, but the first graded run found the binding constraint to be statistical power rather than model capacity (§10), so building them is a scope decision and not a fix for the null.
**Outputs:** regime probabilities per bar, used to permit, restrict, or size participation.
**Documentation (Wk 9):** a **Model Card**, recording feed provenance and asset class.

### 5.2 Signal-Quality Model (required - M2)

Scores each candidate trade.

**Features:** regime probabilities, signal strength, realized volatility, trend strength. **Volume confirmation was removed** (corrected Rev 12) by the feed-transfer verdict below.
**Outputs:** probability of profitable outcome, probability target hit before stop, confidence.
**Training data:** candidate-trade outcomes from the SIP backtest.

**Scope note:** this model scores the *underlying*. Contract selection for the options layer is deterministic and downstream (§5.6), so the options track adds **no new model** - which is why it needs no folds of its own (§7A).

#### The train/live feed mismatch - RESOLVED 2026-09-02 (Rev 12)

Verified 2026-08-30: **IEX carries a median 3.16% of consolidated volume** (2.79–3.78% across six sessions - structural, not noise). Backtests run on SIP, live on IEX (§9), so a feature on *absolute* volume would train on values ~30× larger than it meets at inference, and would fail silently on deployment.

The transfer assumption was **pre-committed and then tested**, so the outcome rested on evidence rather than on convenience at the time: compute the scale-free volume features from IEX and SIP over the overlapping 2021–2026 period, correlate bar-by-bar, keep them on strong agreement and **drop them entirely on weak agreement**.

**Verdict: DROP.** The experiment ran 2026-09-02 and measured Spearman **0.57** against the pre-committed bar of **0.70**. The rule resolves that to DROP and the rule was honoured. **The project has no active volume-derived feature.** The earlier design decision that volume features merely be *scale-free* is superseded: scale-free was not enough, because IEX's ~3% share is a different execution mix rather than a smaller random sample of the same one.

**VWAP distance goes too, by extension of the rule** (design call, 2026-09-04). It was never one of the four features the experiment tested. VWAP is a price, so a distance to it looks scale-free, but its weights are volumes. Extending the rule rather than re-running the experiment was a judgment call and is recorded as one.

Dropped features stay in the registry with `status="dropped"` rather than being deleted, so the finding survives as an artifact rather than as an absence that looks like an oversight. `test_features.py::test_no_active_feature_is_volume_derived` fails if one goes active again, and reinstating one takes a decision-log entry, not an edit. See `DECISIONS.md` rule 2.

### 5.3 Strategy Engine

`generate_candidates(features, bars) -> list[CandidateTrade]` from a transparent rule set. **Primary - momentum breakout:** the only strategy with full evaluation rigor. **Secondary - MA trend, mean reversion:** same interface, backtest-only, labeled exploratory. Parameters in RunConfig, not code. **AC:** same data + config ⇒ byte-identical candidate list; the primary/secondary distinction enforced in the harness.

### 5.4 LLM Trade-Explanation Agent (required)

Converts the decision log into readable rationales. **Grounding rule:** only fields present in the decision log; never alters trading logic, never makes buy/sell decisions. *This is also what keeps the project outside the LLM provider's high-risk "financial decisions" category (§20.1).* The optional read-only query layer extends this agent - see §22.1.

### 5.5 Failure-Analysis Assistant (required)

Statistical clustering of losing trades first, then LLM interpretation and targeted-test suggestions.

### 5.6 Options Execution Layer (new, Rev 11 - replaces the deleted news gate)

**Not an AI component.** Listed here because it occupies the slot the news gate vacated, and because its constraints shape the execution simulator (§8).

Given an approved CandidateTrade on the underlying, the layer deterministically selects a single-leg SPY contract and reports whether that contract was actually tradeable.

- **Contract discovery.** Alpaca's `/v2/options/contracts` with `status=inactive` enumerates expired contracts (verified 2026-09-01, `HTTP 200`). Hand-built OCC symbology is a fallback, not a requirement.
- **Selection rule.** Deterministic and documented: expiry window, moneyness or delta band, minimum measured liquidity. Parameters in RunConfig.
- **Liquidity screen.** Bar presence measured by moneyness bucket, fitted on the first ~25 months and tested on the last ~6 - a genuine held-out split validating the *selection rule*.
- **No-forward-fill rule.** An absent options bar is a **no-trade interval, not missing data**. A backtest that fills on missing bars invents prices that never existed. Enforced in the execution simulator and asserted by test.
- **Point-in-time correctness.** Selecting contracts *because they turn out to have bars* is look-ahead bias. The universe must be correct as of decision time (§11).

**What it reports:** fill-feasibility rate with confidence intervals, execution-cost characterisation by moneyness and regime, and the limitation that Alpaca provides no historical options *quotes* - so spread and slippage are bar-derived proxies, stated as such.

## 6. *(deleted - Week 2 News Feasibility Gate)*

The news/sentiment gate was dropped on 2026-08-31 in favour of the options track. The gate was retired **by removal, not by evaluation**: it was never run. This also closes the FinBERT undeclared-weights problem (§20.1 row 4) without needing a substitute model, which is the cleaner outcome for a public portfolio repo.

## 7. Baseline & Ablation Ladder

| # | System | Regime AI | Signal AI | Status |
|---|---|---:|---:|---|
| B1 | Buy & hold | – | – | Guaranteed |
| B2 | Momentum-breakout strategy + risk layer | – | – | Guaranteed |
| M1 | B2 + regime classifier | ✓ | – | Guaranteed |
| M2 | M1 + signal-quality model | ✓ | ✓ | Guaranteed |

Four rungs, not six. **The ablation ladder is equities-only**, on the SIP backtest feed, for the primary strategy. Crypto and options appear in a separate cross-asset generalisation section (§7A) - they are not additional rungs.

## 7A. Asset-Class Tiers (new, Rev 11)

Three asset classes, three *kinds of claim*. The tier is set by measured history, not by preference.

| Track | History | Folds at 30/6/6 | Tier | What it claims |
|---|---|---|---|---|
| **Equities (SPY, SIP)** | 122 months | **~14** | **Graded core** | Full walk-forward, full ablation B1→B2→M1→M2. The primary claim rests here |
| **Crypto (BTC/USD)** | ~63 months | **~4** | **Graded secondary** | A real validated result, explicitly underpowered. **The fold count travels with every reported number.** Tests generalisation; never supports a claim alone |
| **Options (SPY)** | **31 months** | **0** | **Validated execution layer** | Quantitative, with a genuine train/test split, making **no strategy-performance claim** (§5.6) |

**Definitions, so the labels are not decorative.** A *graded* tier makes a **performance** claim backed by walk-forward validation. A *validated execution layer* makes a **capability and feasibility** claim - quantitatively and out-of-sample - about whether the system's decisions could actually be executed. The dividing line is the kind of claim, not the quality of the work.

**Why options cannot be graded.** One fold at 30/6/6 requires 42 months. Options history begins **2024-01-18** - measured 2026-09-01, and the evidence is the *shape*: eighteen contracts across six different expiries all clip their first bar into a two-day window, including a June expiry that had been trading for months by January. Eighteen contracts cannot coincidentally begin trading at once; it is a hard data floor of the same class as the 2016-06-10 SIP floor. 31 months cannot become 42.

**Two further reasons, beyond the arithmetic.** Options trains no model (§5.2), so there is nothing to validate on it. And 2024-01 → 2026-09 is close to a single market regime - a regime classifier trained or tested only there would have almost no regime variety, defeating the purpose of M1. Short history is not just fewer folds; it is fewer *regimes*.

**Explicitly rejected: shortening the protocol for one asset class.** A 12/3/3 scheme would yield ~5 options folds, at the cost of cross-asset comparability - which is the project's central claim. Recorded so the option is visibly declined rather than silently unavailable.

## 7B. Post-Course Upgrade Path (new, Rev 11)

Ship the tiers above for the course; build the seams so lifting the options constraint later is bounded work. The six seams are listed below; the post-course roadmap is maintained separately.

**The six seams**, built during the course at roughly 10% overhead, versus 4–6 weeks retrofitted:

1. **Vendor-agnostic `MarketDataProvider`** - `get_bars`, `list_contracts`, `get_quotes`, `get_chain_snapshot`. **Define the full interface including what Alpaca cannot do**; the Alpaca adapter raises `NotSupported` and the pipeline degrades loudly. Shape the interface around one vendor's limits and those limits become architectural.
2. **Asset-class-parameterised RunConfig** - `data_start`, session calendar, fold scheme, feature set per asset class. If the fold scheme is configuration, adding a graded options track later is a YAML file plus data.
3. **Results schema carrying provenance** - every row stamped with `asset_class`, `vendor`, `feed`, `data_start`, `fold_scheme`, `n_folds`, `config_hash`. This puts the comparability caveat *in the data* rather than in prose.
4. **Point-in-time universe** - `universe_as_of(t)`, returning `["SPY"]` today. Guards the project's most likely correctness bug (§5.6).
5. **Pluggable fill model** - bar-based, sparse-bar, and later quote-based.
6. **Feature registry with declared data requirements** - options-native features (IV, skew, term structure) are *added* later, not wired in by hand.

**Why no vendor switch now.** Massive (formerly Polygon) options plans top out at "5+ years" for $199/mo - about **3 folds**, fewer than crypto already provides free; their $0 and $29 tiers offer *less* than Alpaca's 31 months. Massive is also a data vendor, not a broker, so execution would stay on Alpaca and a *second* train/live feed mismatch would be introduced on the track with the least evidence behind it. Vendors with genuinely deep intraday options history are priced for institutions. See §9B.

## 8. Risk & Execution Layer (deterministic, auditable)

**Risk controls:** maximum position size, volatility-adjusted sizing, stop-loss rules, maximum drawdown limit, daily loss limit, post-event cooldown, maximum exposure, defined no-trade periods.

**Execution simulator / paper broker:** commissions, spread, slippage, delayed fills, market-hour constraints. Live path on an Alpaca paper account, primary strategy only.

**No-trade-interval rule (new, Rev 11).** A missing bar is an interval in which the instrument did not trade - never a forward-filled price. This applies to **thin options strikes and to thin IEX intervals alike**: IEX bars/day range 74–87 against a 78-bar regular-session maximum, so intervals with no IEX trades genuinely occur. Asserted by test.

**Paper-only enforcement:** paper endpoints and paper credentials only; no live-money code path, and a unit test asserts a non-paper endpoint is rejected.

**Credential validity (new, Rev 11).** A check that credentials are *non-empty* is not a check. The loop makes one authenticated call at startup and aborts on non-200. *Learned the hard way: a key rotation on 2026-09-01 would otherwise have produced a full run of 403s that looked like a successful run.*

## 8A. Halt Control - kill switch, rollback, postmortem (Rev 10)

The Accountability slide requires *"plan for failures: rollback plan, kill switch, postmortems"* and an escalation path. The design had per-decision limits but **no way to stop the loop mid-session** - a genuine omission for a system placing orders unattended.

- **Kill switch.** A single command, and a control in the dashboard, that halts the trading loop immediately. Open positions are left as-is rather than liquidated - an automatic unwind is itself a risky action, and the honest default is to stop acting and hand control back. The halt reason and timestamp are written to the decision log.
- **Auto-halt triggers.** The loop halts itself on: the daily loss limit being hit, a drawdown-limit breach, repeated broker API errors, a data-staleness threshold, a failed pre-trade sanity check, **or a credential/authentication failure (§8)**. Each writes a distinct reason code.
- **Restart is deliberate, never automatic.**
- **Rollback.** Model artifacts and RunConfigs are versioned and hashed.
- **Postmortem.** Any auto-halt gets a short written entry in the experiment log - trigger, state, cause, fix.
- **Escalation path.** Single-user system, so escalation is a notification to the operator on halt rather than a support queue. Stated explicitly so the absence of a support path reads as a considered decision.

**AC:** a test triggers each auto-halt condition and asserts no order is submitted afterwards; the manual kill switch stops the loop within one bar interval; every halt appears in the decision log with its reason code.

## 9. Data Architecture - COMPLETE 2026-09-01

**Decision: Alpaca free (Basic) tier, dual-feed. Semester data cost: $0.** All eight verification questions closed by direct API measurement.

| Probe | Result |
|---|---|
| SIP historical depth, 5-min | **2016-06-10 onward - 10.2 years** (2015 empty on both feeds) |
| IEX historical depth | 2021-06-10 onward - 5.2 years |
| SIP historical entitlement | ✅ Entitled |
| SIP recent data | ❌ **Not entitled** - `403` |
| SIP streaming | ❌ **Not entitled** - `409` |
| **IEX recency** | **Real-time - latest trade 0.1 min old, latest quote ~0** *(2026-09-01, market open)* |
| **IEX streaming** | ✅ **Entitled** - authenticates, subscribes, delivers trades **~0.1 s old** |
| IEX volume vs. consolidated | **3.16% median** (2.79–3.78% across six sessions) |
| **Coverage, 42 sessions** | **40/42 full regular sessions · 0 duplicates · 74–87 bars/day** |
| SIP bars/day | 192 = 04:00–20:00 ET |
| **BTC/USD 5-min depth** | 2021-06-10 or earlier → now; 865 bars per 3-day window vs 864 expected for true 24/7 |
| **Options 5-min bars (SPY)** | **From 2024-01-18 - 31 months.** Contract discovery works for expired contracts with `status=inactive` |

| | Feed | Why |
|---|---|---|
| **Backtest / walk-forward / ablation** | **SIP consolidated** | Ten years of history and true volume. The graded evaluation runs here |
| **Live paper trading (M3)** | **IEX** | The only real-time feed entitled on this tier - and it *is* genuinely real-time |

Every RunConfig, results table and Model Card records its feed **and its asset class**.

**Consequences.** `data.start` is now **asset-class-specific**: `2016-06-10` for equities, `2024-01-18` for options. 30/6/6 walk-forward gives ~14 equity folds, ~4 crypto folds, 0 options folds (§7A). The feed mismatch remains a first-class constraint (§5.2).

**RTH filtering is mandatory** - 192 SIP bars/day means ~60% fall outside 09:30–16:00 ET. **IEX returns 74–87 bars/day against a 78-bar regular-session maximum, and options bars show the same pattern**, so the filter is load-bearing on all three feeds, not cosmetic.

**Coverage validation rules (corrected 2026-09-01).** An earlier run reported "42/42 full sessions, zero gaps." A later sample of 42 sessions showed 40/42:

- **Do not assert exactly 78 bars/day** as a completeness test. Post-RTH-filter counts legitimately fall short when 5-minute intervals contain no trades on a feed carrying ~3% of volume.
- **Flag days below ~90% coverage for review**, do not auto-reject.
- **Exclude the first and last day of any fetch window from coverage statistics.** A 9-bar session observed at a window edge was a boundary artifact, not an outage - a real outage appears mid-window.
- **"Zero gaps" was a property of one sample window, not of the feed.** The durable statement: no duplicates ever observed; near-complete coverage; occasional no-trade intervals.

## 9A. Tech Stack and Compute Budget

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Data / broker | **Alpaca Trading API, Basic (free), dual-feed (§9)** - $0 |
| Data handling | pandas, pyarrow (Parquet), hashed datasets |
| Classical ML | scikit-learn, XGBoost |
| LLM | Hosted API (Claude), pinned version - explanation + failure narrative only |
| Frontend | Browser UI served locally (Streamlit or equivalent) - §22.3 |
| Testing / CI | pytest, GitHub Actions |
| Packaging | Docker (Wk 12) |

| Cost item | Amount |
|---|---|
| Model training | **CPU only, no GPU** |
| Backtests | **$0 by construction** - cache-only |
| **Market data** | **$0 - confirmed by measurement, all asset classes** |
| LLM API | ~**$10–30/month** |
| CI | Free tier |

**Total expected semester spend: the LLM API line only.**

**Dependency note.** `websockets` is required for the IEX stream and is not a default install. Its absence causes the stream check to **skip itself with a warning rather than fail**, which is a silent-failure class the M3 loop must not inherit: verify the import at startup and abort, do not warn.

## 9B. Upgrade Paths - recorded, not needed

| Option | Price | Verdict |
|---|---|---|
| **Alpaca Algo Trader Plus** | $99/mo | ❌ **Trigger did not fire.** Its case was collapsing the dual feed if IEX proved delayed. **IEX is real-time with an entitled stream (§9)**, so the only remaining benefit is full SIP volume live - which the §5.2 transfer experiment decides, not latency |
| **Massive (Polygon) Options Advanced** | $199/mo | ❌ 5+ years → **~3 folds**; crypto already gives 4 free. Data vendor, not a broker - execution stays on Alpaca, adding a second feed mismatch |
| Massive Options Developer / Starter / Basic | $79 / $29 / $0 | ❌ 4 / 2 / 2 years. The lower tiers offer **less** than Alpaca's 31 months |
| Databento | Usage-based | Depth unconfirmed (quote-based pricing) |

**Buy an upgrade to remove a methodological problem, not to buy history.** Trigger: only if the §5.2 transfer experiment fails *and* losing volume features materially degrades the signal-quality model. **Half of that trigger has now fired** (Rev 12): the experiment failed on 2026-09-02. The second half is unmet and currently unmeasurable, since the first graded run could not detect an effect of this size either way (§10), so the upgrade stays unbought. **No vendor fixes options history length at a student budget** (§7A, §7B).

**Going live** (permanently excluded, §3) would require: real-time data as a hard prerequisite; re-examining Professional vs Non-Professional subscriber status; deliberately removing the paper-only guardrail a test enforces; and an actual track record - walk-forward results are evidence about a hypothesis, not a track record.

## 9C. Scheduled Execution - the TCC constraint (new, Rev 11)

**Milestone 3 requires the system to run unattended through market hours on an always-on desktop (§22.3).** A scheduled run on 2026-09-01 failed before executing a single line:

```
shell-init: error retrieving current directory: getcwd: cannot access parent directories: Operation not permitted
/bin/bash: .../Desktop/Project-Beta/run_market_open.sh: Operation not permitted
```

**`~/Desktop`, `~/Documents` and `~/Downloads` are macOS TCC privacy-protected locations. A launchd agent has no access to them and cannot even exec a script that lives there.** An interactive Terminal *does* have that access, which is why every manual run succeeded and the scheduled one did not.

**Consequences, which are architectural rather than incidental:**

- **The project must not live under a protected folder.** Resolved 2026-09-01 by moving to `~/dev/Project-Beta`. Not `~/projects/Project-Beta` - macOS filesystems are case-insensitive by default, so that would have collided with the existing `~/projects/project-beta`.
- **Granting Full Disk Access to `/bin/bash` is the wrong fix.** It hands every script the shell ever runs unrestricted access to the user's files, to work around a folder choice.
- **A scheduled job must be verified through its scheduler** (`launchctl kickstart`), never only by hand. **Testing interactively does not test the scheduled path** - the two contexts have different permissions, and this failure is exactly what that gap looks like.

## 10. Evaluation Framework (Course Step 2)

Two layers, both necessary.

### 10.1 Offline metrics (primary results layer)

**Trading metrics - the headline.** Total and annualized return, Sharpe, Sortino, maximum drawdown, Calmar, profit factor, win rate, average win/loss, turnover, exposure, trade count, cost sensitivity. Prespecified primary comparison: **M-tier vs. B2 on Sharpe or maximum drawdown, net of costs, walk-forward, on equities.**

**ML metrics - supporting.** Precision, recall, F1, ROC-AUC, PR curves, per-regime confusion matrices, calibration, Brier score.

**Cross-asset metrics (§7A).** Crypto: the same trading and ML metrics, **with the fold count (~4) attached to every figure**. Options: fill-feasibility rate with confidence intervals, liquidity-screen performance on the held-out window, and execution-cost distribution by moneyness and regime - **never a Sharpe or drawdown claim**.

### 10.2 User-impact metrics (required second layer)

| Measure | Protocol | Target |
|---|---|---|
| **Decision comprehension** | 3 readers unfamiliar with the project, 5 minutes with the dashboard (live or replay, §19.5), unaided. Each states (a) current regime, (b) open positions, (c) why the most recent decision came out as it did | **≥ 8 of 9 correct**, none failing (c) |
| **Time to audit a decision** | Timed: from clicking a decision row to naming the filter that caused the outcome | **Median under 60 s** |
| **Explanation trust check** | 10 sampled explanations; reader marks each claim traceable or not | **100% traceable**; any untraceable claim is a release blocker |

**Why these, not "time saved."** Conventional user-impact metrics assume the user was doing the task manually. The honest analogue is *auditability under time pressure*. **Limitation:** n=3 is a usability smoke test, not a study.

### 10.3 Robustness tests

Walk-forward only; bull/bear/sideways subperiods; 2–3× cost stress; delayed execution; missing-data handling; out-of-distribution volatility; confidence threshold sweeps; **the §5.2 feed-transfer check**; **the options no-forward-fill assertion (§8)**.

### 10.4 Reproducibility rubric

Results regenerate from a clean clone using documented config and the documented data-acquisition step (§17.7).

## 11. Leakage Prevention

- Walk-forward only; no future information at any stage.
- All AI/LLM outputs cached; backtests never call live APIs.
- Feature code self-reviewed for lookahead bias before merge.
- **RTH filtering applied before any feature computation** (§9).
- **Label embargo (new, Rev 12).** M1's regime labels are forward-looking by design (§5.1), so a label at bar `t` reads prices to `t + horizon`. The last `horizon` bars of every training window are therefore dropped: `EMBARGO_BARS` in `models/labels.py`, applied by the fold runner and asserted by `test_models.py`. Without it the opening hours of each validation window leak into training, which improves results and leaves no trace.
- **Point-in-time instrument universe (new, Rev 11).** Selecting an options contract *because it turns out to have bars* uses knowledge that it traded - look-ahead bias in its purest form. The universe must be constructed as of decision time, via `universe_as_of(t)` (§7B seam 4). This is the project's most likely correctness bug and the one a methodology reviewer probes first.

## 12. Timeline (14 weeks)

| Weeks | Internal focus | Deliverables | Official due date |
|---|---|---|---|
| 1–2 | Foundations | Repo checklist (six items); **vendor-agnostic data provider (§7B seam 1)**; data pipeline + validation (§9 architecture, RTH filter, coverage rules, hashing); feature pipeline; **§5.2 feed-transfer experiment - the first build task**; leakage checklist; four logs; **§20 Responsible AI charter**; **§21 focus areas**; **§22 AI application design**; pitch artifact | **Milestone 1 - end of Wk 2** |
| 3–4 | Baselines + harness | B1/B2 running, walk-forward framework (~14 folds), cost model, metrics suite, B1/B2 results, **Data Card**, **halt control (§8A)** built with the risk engine | - |
| 5 | Regime prototype | Regime classifier (M1) first-cut wired end-to-end | **Milestone 2 - end of Wk 5** |
| 6 | Regime intelligence | Labeling finalized, calibrated, M1 vs. B2 ablation. **Fallback checkpoint + graded-options gate (§7A)** | - |
| 7–8 | Signal-quality intelligence | Candidate-trade dataset, quality model (features per the §5.2 verdict), calibration, M2 ablation. **Fallback checkpoint** | - |
| 9 | **ALPHA - Milestone 3** | End-to-end on the paper account via IEX, **halt control live**, running unattended from a non-protected folder (§9C). **Model Cards + System Card** | **Milestone 3 - end of Wk 9** |
| 9–10 | Cross-asset tracks | Crypto secondary run (~4 folds, §7A); **options execution layer** - contract selection, liquidity screen, fill-feasibility study (§5.6) | - |
| 10 | Gates · safety | Go/no-go on the query layer. **Red-team pass (§20.2), targeting the explanation service** | - |
| 11–12 | Interpretability + robustness + release candidate | Explanation agent, failure clustering, targeted tests, robustness suite, final results, architecture diagram, quick-start docs, fresh-clone test, **replay mode (§19.5)**, demo script, **demo video draft**, **container**, **latency & cost report**, **user-impact run**. **Fallback checkpoint** | **Milestone 4 - end of Wk 12** |
| 13 | Polish for portfolio | Package repo/demo/report; no new features | - |
| 14 | Ship | Final demo video, report, live presentation. **Second user-impact run** | **Final Presentation - end of Wk 14** |

## 13. Work Breakdown and Ownership

Two people. Faculty confirmed on 2026-09-03 that scope expectations do not
scale with team size. The additional capacity is applied to depth and to
workstreams that previously had no owner, not to new scope.

| # | Stream | Contents | Owner |
|---|---|---|---|
| 1 | **Data & pipeline** | Provider interface, ingestion, validation, RTH filtering, coverage rules, features, leakage prevention | Henry |
| 2 | **ML** | Regime + signal-quality models, calibration, ablations, feed-transfer validation | Henry |
| 3 | **Systems - core** | Risk engine, halt control, execution simulator, Alpaca integration, containerization | Henry |
| 4 | **Evaluation & research** | Harness, robustness tests, failure analysis, experiment log, latency/cost profiling | Henry |
| 5 | **Systems - surface** | Dashboard, replay mode | **Jacky** (candidate) |
| 6 | **Secondary tracks** | Crypto run, options execution layer | **Jacky** (candidate) |
| 7 | **Adversarial** | Red-team pass, grounding audit | **Jacky** (candidate) |
| 8 | **Docs & demo** | Documentation, model/system cards, architecture diagram, demo video, report | Shared |

Streams 5 to 7 are the candidate areas described in `Jacky_Onboarding.md`; one
is selected after an initial skills discussion. Streams 1 to 4 remain with
Henry: they are the critical path in Weeks 3 to 8 and require full project
context. Henry reviews all changes and is accountable for what ships,
regardless of authorship (§16).

## 14. Logs (all started Week 1)

Decision log · Experiment log (incl. halt postmortems, §8A) · AI usage log with provenance · Risk register (§15).

## 15. Risk Register

| Risk | Mitigation |
|---|---|
| Data leakage inflating results | Leakage checklist; walk-forward only; feature-code self-review; cached AI outputs; RTH filter pre-feature |
| ~~Intraday data availability/cost~~ | **CLOSED 2026-08-30** - ten years of consolidated 5-minute history at $0 (§9) |
| ~~Real-time data may be 15-minute delayed~~ | **CLOSED 2026-09-01** - IEX measured real-time, streaming entitled (§9) |
| **Train/live feed mismatch** | ✅ **CLOSED 2026-09-02 (Rev 12).** The transfer experiment measured Spearman 0.57 against a pre-committed 0.70 bar and the rule resolved to DROP. No volume-derived feature is active, so the mismatch can no longer reach a model. The residual risk moved to §5.2's other side: whether losing those features costs signal quality, which the ablation ladder now measures rather than assumes |
| **Look-ahead via options contract selection** | **New (§11).** Point-in-time universe; contracts chosen as of decision time, never because they are known to have traded |
| **Extended-hours bars contaminating features** | RTH filtering at ingestion, enforced in code - necessary on SIP, IEX **and options** (§9) |
| **Sparse options bars overstating fillability** | **New (§8).** No-forward-fill rule, asserted by test; fill feasibility reported as a measured rate, not assumed |
| **Autonomous loop cannot be stopped mid-session** | **(§8A).** Kill switch, auto-halt triggers, deliberate restart, rollback via versioned artifacts |
| **Scheduled job silently fails to run** | **New (§9C).** Project outside TCC-protected folders; scheduled jobs verified through the scheduler, never only by hand |
| **Invalid credentials producing a plausible-looking failed run** | **New (§8).** Startup authentication check that aborts on non-200; a non-empty check is not a check |
| **Showcase demo has nothing to show** | **(§19.5).** Deterministic replay mode, built Wk 11–12, also serving the §10.2 protocol |
| ~~Historical news unavailable~~ · ~~sentiment model licensing~~ | **CLOSED 2026-08-31 - news gate dropped** (§6) |
| Regime labels ambiguous | 3+1 scheme; documented; revised only with logged evidence |
| Signal-quality model overfits | Ten years of 5-minute bars; regularization; calibration + Brier reported |
| **Secondary tracks over-claimed** | **New (§7A).** Tiers fixed by measured fold counts; crypto's fold count travels with every number; options makes no performance claim |
| Market-data licensing blocks reproducibility | Sample fixture + re-fetch script + `dataset_hash` (§17.7) |
| Published decision logs may constitute redistributable data | §20.5 - sample logs bounded, CI-enforced |
| Transaction-cost sensitivity at 5-minute bars | Cost-stress tests reported prominently |
| Multi-strategy toggle dilutes evaluation rigor | Secondaries never enter the graded ladder; harness-enforced |
| LLM cost / API changes | Cached outputs; pinned versions |
| Team bandwidth and coordination | Two contributors. Onboarding costs one to two weeks, review adds latency, and a single-owner workstream stalls if that owner does. Mitigations: interface contracts keep each stream separable (§13); branch-and-pull-request with Henry reviewing all changes; no critical-path work is assigned to the second owner, so a stall reduces scope rather than blocking the core; weekly journal, four logs, conditional tiers and named checkpoints as before |
| Overfitting via repeated backtest iteration | Prespecify the primary metric before M1 experiments; log every experiment |
| Milestone timing mismatch | Re-verify against Canvas each phase |

## 16. Generative AI Usage Policy - CONFIRMED (2026-08-24)

Coding agents are explicitly allowed course-wide. In-system LLM use is limited to the explanation agent and failure-analysis assistant; LLMs never generate or modify trading logic. Written deliverables follow the conservative default - AI assists thinking and structure, Henry writes the submitted prose, kept AI text is cited. **Two agreements apply:** the desktop app (consumer terms) for development assistance, the API (commercial terms) for the explanation service. All usage recorded with provenance detail. **Anti-vibecoding:** the PRD is the spec and stays current; nothing merges without a test that would fail if the behavior were wrong; CI stays green with no test disabled.

## 17. Success Criteria

1. End-to-end run from ingestion through paper-trade decision, logging, and monitoring.
2. Each AI component evaluated independently with §10 metrics.
3. **Full ablation through M2 for the primary strategy on equities**; crypto reported as a graded secondary with its fold count; options reported as a validated execution layer (§7A).
4. At least one **prespecified** risk-adjusted metric improves versus B2 after costs - or the negative result is rigorously characterized.
5. Every trade decision has a grounded explanation auditing correctly against the log.
6. Top failure modes identified, tested, documented.
7. **A fresh clone reproduces headline results** *(licensing prohibits redistributing bars, so the repo ships a sample fixture, re-fetch script, and hash)*.
8. Container builds and runs; latency & cost report published with the results.
9. The §10.2 user-impact protocol is run and reported, whatever the outcome.
10. Nothing in the public repo violates §20.5.
11. **Every reported result records its feed and asset class**; the §5.2 transfer result is published with the Model Cards.
12. **Halt control works: every auto-halt trigger is tested, and the kill switch stops the loop within one bar interval (§8A).**
13. **The six architecture seams (§7B) exist and are exercised by at least one test each**, so the post-course upgrade is demonstrably a configuration and adapter job.

## 18. Framing the Outcome

The prespecified hypothesis is that regime and quality filtering improve risk-adjusted performance. **A rigorous negative result is an acceptable and defensible outcome** - the deliverable is judged on coherence, evaluation quality, and honest failure analysis, not on beating the market.

**This extends to the tier structure.** Discovering that options history supports zero folds, and restructuring the claim rather than shortening the protocol to fit, is a result in the same sense: it is evidence about what the data can support, arrived at by measurement and recorded with its arithmetic.

## 19. Demo Walkthrough & Sample UI

### 19.1 How the trading works - plain-language pipeline

Not an interactive advisor - a closed-loop paper-trading system a user watches, then reviews.

1. **Data pipeline** pulls SPY 5-minute bars, validates, filters to regular hours. No AI.
2. **Feature engineering** computes indicators. No AI - deterministic math.
3. **Strategy Engine** checks fixed rules; proposes a candidate trade. No AI.
4. **Regime classifier (AI)** outputs trend probabilities and a volatility flag - describes the environment, doesn't propose trades.
5. **Signal-quality model (AI)** scores the candidate.
6. **Trade Decision Engine** combines these into one of four fixed outcomes via documented logic, not an LLM's judgment.
7. **Risk Engine** (no AI, ever) enforces sizing, stops, drawdown limits - and can halt the loop entirely (§8A).
8. **Instrument selection** - equities pass straight through; the options layer deterministically picks a contract and checks it was tradeable (§5.6). No AI.
9. **Execution** - if approved, placed on the paper account.
10. **Decision log** records every input, output, and reason code.
11. **Explanation agent (AI)** reads that log and writes a rationale limited to what's in it.
12. **Dashboard** - live or replay (§19.5).
13. **Failure-analysis assistant (AI)** clusters losing trades statistically, then narrates the clusters.

*Steps 6, 7 and 8 are load-bearing for §20.1: the trade decision and the instrument choice are both deterministic, and no AI output reaches them as an instruction.*

### 19.2 What the end user sees

**Main dashboard:** header (regime label + probability, volatility flag, equity, today's P&L, **halt status**); equity curve vs. B1; open positions with active risk constraints; **decision feed** - most-recent-first rows with timestamp, decision badge, quality score, and a one-line grounded explanation, expanding to the full DecisionRecord. Persistent disclaimer: paper trading only; not investment advice. **Halt control** is on this screen.

**Strategy toggle panel** (backtest-only): momentum breakout (primary, live), MA trend, or mean reversion. Labeled exploratory.

**Cross-asset panel:** equities (graded), crypto (graded secondary, fold count shown), options (execution layer, feasibility metrics only). **Each panel states its tier**, so a viewer cannot mistake one claim for another.

**Failure analysis view:** clustered failure modes with LLM interpretation and links to targeted tests.

### 19.3 Sample demo script

1. Open on the dashboard mid-session (or replay) - current regime and equity curve vs. baseline.
2. Click into 2-3 decisions - read the grounded explanation, show it matches the DecisionRecord exactly.
3. Show the results table: Sharpe/drawdown for B1→M2, the primary comparison.
4. Show the cross-asset panel - and say plainly why crypto carries a fold count and options carries no Sharpe.
5. Open the strategy toggle briefly - note these are exploratory by design.
6. Open the failure-analysis view - one real failure cluster and its targeted test.

### 19.4 Pitch artifact - 6-slide structure (Week 2)

Problem · the system in one diagram · what makes it different · how success is measured · scope and risk · where it stands. *Built: `PROJECT_BETA_Product_Demo.pptx` with speaker notes. Updated to Rev 11 on 2026-09-03.*

### 19.5 Replay mode (Rev 10 - Weeks 11–12)

**The problem it solves.** The product's AI role is background automation (§22.2), the least demonstrable of the three roles the course names. On 5-minute bars a momentum strategy may produce **zero trades during a ten-minute demo slot**. The Final Presentation is 25% of the grade and is a live demo.

**What it is.** A deterministic replay of a recorded session - the dashboard reads a stored run and advances through it at accelerated speed. No re-computation, no simulation of new data: it replays logged records, so what the audience sees is exactly what the system did.

**Why this and not a chat interface.** Adding conversational AI to make the demo feel interactive would be decoration bolted on to satisfy a rubric. Replay solves a presentation problem as a presentation problem, and leaves the product honest.

**Second use.** The §10.2 user-impact protocol needs decisions on screen for three readers, which can't be scheduled around market volatility either. Replay makes the measurement repeatable.

**AC:** replay of a given run is byte-identical across runs; the dashboard clearly labels replay vs. live.

## 20. Responsible AI Charter (required Milestone 1 material)

Covers **system-behavior risk** - what this thing could do to someone - as distinct from §15's project-execution risk.

### 20.1 Licensing audit - VERIFIED 2026-08-30

Read against published terms. **Good-faith reading, not legal advice.**

| # | Asset | Verified finding | Constraint |
|---|---|---|---|
| **1** | **Alpaca market data** - two governing documents | Terms & Conditions: *"No part of the Service or Content may be copied, reproduced, republished... or distributed in any way (including 'mirroring')... without Alpaca's express prior written consent"*; Content *"provided exclusively for personal and noncommercial access and use."* **Customer Agreement §30:** *"I agree not to reproduce, distribute, sell or commercially exploit the market data in any manner without written consent"* | **The repo cannot contain the dataset.** Sample fixture + re-fetch script + `dataset_hash`; constraint stated in the README. Personal, non-commercial academic use is exactly this project - only redistribution is blocked. **Applies equally to equity, crypto and options bars** |
| **2** | **NASDAQ OMX / NYSE Display Services** - conditional | *"the Information is licensed only for personal use."* §1: *"Subscriber may not sell, lease, furnish or otherwise permit or provide access to the Information to any other Person."* **§12** defines Information to include *"any element of Information as used or processed in such a way that the Information can be identified, recalculated or re-engineered."* | (a) Personal-use posture. (b) **§12's derived-data reach** drives §20.5 - and rules out publicly hosting the dashboard (§22.3). (c) **Non-Professional status must be affirmatively qualified** |
| **3** | **Polygon / Massive (not subscribed)** | §1 personal, non-business, non-commercial. §2: *"you may not use the Market Data to build an application intended for use by end users other than you."* **§5(d)** bars derivative works *"including... any investment strategy."* | Not currently relevant. **If the post-course options upgrade proceeds (§7B), this becomes a required second-vendor audit before any public release** |
| **4** | **FinBERT** | No license declared on the model card; upstream repo Apache-2.0 covers **code**, not weights | ✅ **MOOT as of 2026-08-31** - no sentiment model is in scope. Closed by removal, not substitution |
| **5** | **Hosted LLM - outputs** | Consumer terms: *"we assign to you all of our right, title, and interest - if any - in Outputs."* Commercial §B: *"Customer... owns its Outputs"*; *"Anthropic may not train models on Customer Content from Services"* | Explanations can be published. **Both agreements apply.** Pin the model version |
| **6** | **Hosted LLM - usage policy** | Finance is a High-Risk Use Case: *"financial decisions, including investment advice..."* | **Compliant by design.** The LLM never makes or influences a trade decision (§19.1 steps 6–8); it narrates a logged decision. No external consumers. **The strongest point in the charter:** the constraint chosen for evaluation integrity is what keeps the system outside the high-risk category |
| *(7)* | scikit-learn, XGBoost, pandas, pyarrow | Permissive OSS (BSD-3 / Apache-2.0 family) | Record resolved licenses in the dependency manifest |

**Own-repo license: MIT.** **Still open:** Professional / Non-Professional status - no such document exists in the account (checked 2026-08-31); resolve by asking Alpaca support in writing.

**Sources:** [Alpaca T&C](https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf) · [Alpaca Customer Agreement](https://files.alpaca.markets/disclosures/library/AcctAppMarginAndCustAgmt.pdf) · [NASDAQ OMX Subscriber Agreement](https://files.alpaca.markets/disclosures/library/NASDAQ+OMX+Global+Subscriber+Agreement.pdf) · [NYSE Display Services](https://files.alpaca.markets/disclosures/library/NYSE+Market+Data+Display+Services+Agreement.pdf) · [Massive/Polygon options pricing](https://massive.com/options) · [Anthropic Consumer Terms](https://www.anthropic.com/legal/consumer-terms) · [Anthropic Commercial Terms](https://www.anthropic.com/legal/commercial-terms) · [Anthropic Usage Policy](https://www.anthropic.com/legal/aup)

### 20.2 Safety plan - top 3 harms, each with a guardrail and a test

| # | Harm | Guardrail | Test |
|---|---|---|---|
| **1** | **Financial harm through misuse.** Someone clones the repo, points it at a live account, and loses real money - or reads the dashboard as investment advice | No live-money code path; paper endpoints and credentials only (§8). **Halt control (§8A)**. README and dashboard carry "paper trading only; not investment advice." No performance claim without its cost model and walk-forward caveat | Unit test: the execution layer **rejects** a non-paper endpoint or live credentials. CI-asserted disclaimer strings. **Halt tests per §8A** |
| **2** | **Over-trust in a wrong or invented explanation** - the failure mode that makes an "explainable" system worse than an opaque one | Hard grounding rule: prompt contains only DecisionRecord fields plus reason-code documentation. Reason codes from a fixed enum. **The optional query layer inherits this rule unchanged** | Grounding audit on ≥50 random explanations. Target 100%; **any hallucinated claim is a release blocker.** Plus the §10.2 trust check |
| **3** | **Misleading performance claims.** Leakage, overfitting, an under-modelled cost assumption, an unstated feed limitation, **or a secondary track's result read as if it carried the core's evidentiary weight** | Walk-forward only, point-in-time features and instrument universe (§11), cached AI outputs, prespecified primary metric fixed before M1 experiments, negative results framed as legitimate (§18). **Feed, asset class and fold count recorded wherever results appear (§7A)** | Leakage test (shift-forward invariance); backtest cache-only enforcement; 2–3× cost-stress runs reported *alongside* headline numbers; **schema test asserting every results row carries `asset_class` and `n_folds`** |

**The Week 10 red-team target is the explanation service.** The news gate was the planned prompt-injection surface; with it dropped, the pass targets the explanation service, exercising the grounding rule against adversarial log content. *If the query layer ships, user-typed text becomes a second injection surface and joins this pass.*

### 20.3 Fairness note - three steps (Rev 10)

**Framing, stated openly.** The slide's examples are human groups. A single-instrument paper-trading system has no human demographic groups in its data, and inventing one would be dishonest. The real analogue is **market conditions**, and this adaptation is deliberate. The substance the fairness requirement protects - *does this work as well for everyone it will be applied to, or only on average* - maps exactly onto regimes.

**Step 1 - the groups.** Market regimes (uptrend / downtrend / choppy), volatility states (high / low), and calendar subperiods. A filter trained mostly on trending data can look excellent in aggregate while being actively harmful in choppy conditions - and a user who happens to start during that regime gets the bad version of the system.

**Step 2 - the check.** A per-regime and per-volatility-state breakdown for the M-tier system versus B2 - accept/reject rates, realized risk-adjusted performance, and calibration, sliced by regime. **Any regime in which the filtered system underperforms the unfiltered baseline is reported explicitly**, not averaged away.

**Step 3 - one concrete mitigation.** *If a regime is identified where the filtered system underperforms B2:* the signal-quality threshold becomes **regime-conditional** - the model abstains rather than participates in regimes where it demonstrably adds no value. Implemented in the Trade Decision Engine and expressed as a RunConfig parameter, not a note in the report.

**Honest limits of that mitigation:**

- Abstention **reduces harm without fixing the model.** That is mitigation, not repair.
- It **costs trade count** in the abstaining regime, weakening the statistical power of exactly the slice already least understood.
- It **depends on regime classification being correct**, so it inherits the classifier's own errors.
- With a single asset and finite history, **some regimes will have thin sample support.** Where a slice is too thin to support a claim, the report gives the count rather than the ratio. **The same discipline governs the secondary tracks (§7A):** crypto's ~4 folds and options' zero are reported as counts, not smoothed into ratios.

### 20.4 Privacy plan

| Data | Why | Retention | Minimization |
|---|---|---|---|
| Alpaca API key / secret, paper account ID | Fetch data, place paper orders | Life of project; **rotated if exposed - rotated 2026-09-01** | **Environment variables only - never committed.** `.gitignore` covers `.env` and `.env.*`. *Alpaca displays the secret once and does not retain it - a lost secret can only be replaced, and replacement invalidates every stored copy* |
| Decision log (DecisionRecords) | Single source of truth | Semester + final report | Market state, model outputs, reason codes. **No personal data.** *Contains prices - see §20.5* |
| Cached LLM prompts/responses | Reproducibility and cost control | Semester | Assembled from DecisionRecord fields only |
| Usability-check notes (§10.2) | Evidence for the user-impact metric | Until the final report | Responses only, not participant identity |

**Minimization principle:** the system collects nothing about anyone. Single-user, single-account, observational - the correct posture is **"never start collecting it."**

**Data-subject rights.** **Not applicable here, and stated rather than silently omitted:** there are no external users and no personal data. If the query layer ships, user-typed queries become the first genuinely new data class and this row needs a retention line before it does.

**Third-party API data policies.** The LLM provider's commercial terms state *"Anthropic may not train models on Customer Content from Services"*, and prompts carry only market and model state.

### 20.5 Publication constraints - what may and may not go in the public repo

| Artifact | Publishable? | Reasoning |
|---|---|---|
| Raw OHLCV bars - **equities, crypto or options** | **No** | Alpaca T&C and Customer Agreement §30 |
| Small sample fixture (bounded window) | **Yes, minimally** | Enough to run tests; not a usable dataset |
| Re-fetch script + `dataset_hash` | **Yes** | Code and a hash - reproduction verifiable without redistribution |
| **Full multi-year decision logs** | **No** | DecisionRecords carry entry/stop/target/fill prices; across years of 5-minute bars this approximates a price series that *"can be identified, recalculated or re-engineered"* |
| **Sample decision logs - bounded window** | **Yes** | A few trading days. CI-enforced |
| **Verification reports (`report_*.json`)** | **No** | They carry per-session IEX volume - vendor-derived, same terms as the bars. In `.gitignore` **and** `tests/test_guardrails.py`, which matches the word anywhere in the filename rather than as a prefix |
| Aggregate results tables, equity curves, metrics | **Yes** | Statistics over the data, not reconstructable to bars |
| Trained model artifacts | **Yes** | Parameters learned from the data; hash them |
| Generated explanations | **Yes** | Outputs assigned to the user |

**Rule of thumb:** if someone could rebuild a usable price series from it, it doesn't go in the repo. State the constraint in the README so a reader understands *why* the dataset is absent.

**Incident on record (2026-09-01).** Two verification reports carrying per-session IEX volume were committed and briefly pushed to a public repo. Contained by making the repository private within ~30 minutes; the files remain in history at two commits and a history rewrite is required before the repo goes public in Week 12. The guardrail gap that allowed it - a prefix-only filename match - is fixed. Recorded here rather than quietly repaired, because §20.5 is only credible if its failures are logged too.

## 21. Optional Focus Areas - Declared

**Evaluation & Responsible AI (primary) + Model & System (secondary).**

| Area | Declared | Why |
|---|---|---|
| **Evaluation & Responsible AI** | ✅ **Primary** | The ablation ladder (§7), walk-forward-only validation, cost-stress and subperiod robustness (§10.3), per-regime fairness disaggregation and mitigation (§20.3), the feed-transfer experiment (§5.2), **the asset-class tier discipline (§7A)**, latency/cost profiling, the ≥50-sample grounding audit, failure analysis with targeted tests |
| **Model & System** | ✅ Secondary | Two trained classical models with calibration; a composed multi-stage gating pipeline; grounded LLM services under a hard structural constraint; **a vendor-agnostic data layer designed for a documented upgrade path (§7B)** |
| Data | ❌ Not declared | Careful work, but standard market-data hygiene |
| Application & Deployment | ❌ Not declared | Dashboard and container ship, but they serve the evaluation story rather than being the contribution |

**Why not claim all four.** A proposal claiming everything reads as unfocused. Two declared areas with explicit reasons for declining the other two is a stronger signal.

---

## 22. AI Application Design - the course's Parts I–III (Rev 10)

### 22.1 Part I - Interaction model and the role of AI

**Interaction style: a static dashboard.** **Access surface: browser, served locally.**

**Role of AI: background automation.** The AI runs unattended inside a closed loop: it classifies the market, scores candidate trades, and afterwards writes explanations. The user watches and reviews; they never converse with it to get a trade decision.

**Optional third mode: on-demand helper.** The Week-10-gated query layer would add an "Ask AI" affordance over a selected logged decision. Read-only, same grounding rule, same audit.

**What is deliberately excluded.** **Generative what-if scenarios** are permanently out of scope. A counterfactual has **no logged referent**, so the LLM would either speculate - which this system is built not to do - or the grounding rule would have to be weakened. That rule is the project's central claim and the basis of a release-blocking audit (§20.2 Harm 2).

*If a what-if capability is ever wanted, the honest form is computed, not generated:* narration of a **precomputed** parameter sweep.

### 22.2 Part I - Why this role, and the demo consequence

Background automation is the right role: the user's problem is that signals fire faster than they can be judged, and the value is in the loop running without them. But it is the **least demonstrable** of the three roles, and the Final Presentation (25%) is a live demo. §19.5's replay mode is the mitigation.

### 22.3 Part I - Platform and support model

**Self-contained, single-user, local - containerized.**

- **Self-contained is chosen.** The Docker container (Wk 12) is the packaging story.
- **Serverless is rejected on shape, not cost.** The trading loop is long-running and stateful.
- **Public cloud hosting is rejected on licensing.** The data licence grants personal, non-commercial use, and the subscriber agreement bars furnishing the Information to another Person (§20.1 rows 1–2). **A publicly hosted dashboard serving live market data to visitors would breach the licence the project depends on.**
- **A private cloud VM would be permissible** - still one user - but adds cost for no benefit.
- **Mobile is rejected.** The user is at a desk auditing decisions.

**Uptime.** Milestone 3 requires the system to run *unattended*, so the host must stay awake through market hours. An always-on desktop covers this with no cloud spend. **And per §9C, the project must not live in a TCC-protected folder, or the scheduler cannot start it at all** - confirmed by a failed scheduled run, not assumed.

### 22.4 Part I - High-level architecture (frontend / backend / AI layer)

| Layer | Components | Notes |
|---|---|---|
| **Frontend** | Browser dashboard served locally - decision feed, equity curve, open positions, halt control, strategy-toggle panel, cross-asset panel, failure-analysis view, replay controls | Streamlit or equivalent; single user, no auth surface, no public exposure (§22.3) |
| **Backend** | **MarketDataProvider (vendor-agnostic, §7B)**, data pipeline, feature engineering, Strategy Engine, Trade Decision Engine, Risk Engine + halt control, **instrument selection / options execution layer**, Execution Layer, Decision Log, Evaluation Harness | All deterministic. Python; Parquet bar store; append-only decision log. **No AI in the trade decision path** |
| **AI layer** | Regime classifier, signal-quality model (both local classical ML); Explanation Service and Failure-Analysis narrative (hosted LLM API) | Reads from the backend; the explanation services read the decision log **only**. Model versions pinned in RunConfig |

The boundary that matters: **the AI layer never writes into the trade decision path.**

### 22.5 Part II - AI architecture pattern and the decision-tree walk

Of the six patterns the course orders by cost, PROJECT BETA is **Tier 1 - Prompt-Centric**, for both LLM services. Walking the decision tree as given:

> **"Could a prompt-centric solution meet your quality and safety needs?" → Yes.** The tree terminates here.

Confirmed against the later branches: no need to read or write external systems (the Explanation Service is *forbidden* from touching anything but the decision log, which is stricter than merely not needing tools) → not Tool-Augmented; no question-answering over document collections → no RAG; no multi-step planning across tools → nothing agentic; no fine-tuning or pretraining.

**Where the classical models sit.** The regime classifier and signal-quality model are **not on this spectrum at all** - it orders *LLM application* patterns, and these are conventional supervised learning on tabular features.

**Why the lowest tier is the right answer, not a limitation.** The lowest tier is also the *safest*: the reason the explanation service is prompt-centric is the grounding constraint, and a higher tier would mean giving the LLM access to more than the log - which would weaken the property the whole project is built on. Cost discipline and safety discipline point the same way.

### 22.6 Part III - AI task inventory and technology selection

**Four tasks** - the news gate's conditional extraction is gone as of Rev 11.

| # | Step in the user flow | AI task | Technology | Build or buy |
|---|---|---|---|---|
| 1 | Classify current market conditions | **Classification** (tabular, not text) | Logistic regression → RF / XGBoost, local | **Build** |
| 2 | Score a candidate trade's quality | **Classification** (tabular) | XGBoost, local | **Build** |
| 3 | Explain each trade decision in plain English | **Text generation** | Hosted LLM API, pinned version | **Buy** |
| 4 | Narrate computed failure clusters | **Text generation** over precomputed statistics | Hosted LLM API | **Buy** |

**Not used, and stated deliberately:** information retrieval / RAG (no document corpus), speech recognition, text-to-speech, vision/OCR, **and text classification / structured extraction - removed with the news gate.** The task inventory is short by design and got shorter by decision.

**Build-vs-buy rationale.** *Buy* the language model: text generation is mature, commoditized, and not where this project's differentiation lives. *Build* the classifiers: they are core to the differentiation, the task is tabular market-regime classification for which no managed service exists, and their calibration and per-fold evaluation are the substance of the graded ablation.

**And the course's own conclusion applies directly:** *"your unique value can come from the pipeline that combines multiple services, not from any single model."* No component here is novel in isolation. The contribution is the composition: AI that gates rather than decides, every decision logged, every explanation checkable against its log, each component's value isolated by ablation - **and each asset class making only the claim its data can support.**
