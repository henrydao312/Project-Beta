# PROJECT BETA — Architecture Seams & Post-Course Upgrade Path

**Written 2026-09-01.** Companion to `Decision_Tracker.md`. The tracker records *what was decided*; this records *how the code must be shaped so the deferred decisions stay cheap to reverse*.

**The decision this document serves:** ship **Shape A** for the course — equities as graded core, crypto as graded secondary, options as a validated execution layer — while building the seams that make **Shape B** (options-forward, and ultimately graded options) a bounded post-course upgrade rather than a rewrite.

**The economics.** Building these seams at design time costs roughly 10% overhead. Retrofitting them costs 4–6 weeks. They are not speculative generality — every one has a named second implementation that is already on the roadmap below.

---

## 1. Why options cannot be graded during the course

| Requirement to grade a track | Equities | Options today |
|---|---|---|
| Walk-forward folds at 36/6/6 (48 months each) | 122 months → **~14 folds** | 31 months → **0 folds** |
| A model trained on that asset class | Regime + signal-quality, SIP-trained | **None** — models score the underlying; contract selection is deterministic |
| Features native to the asset class | Price/volume, available | **IV, skew, term structure, open interest — not in OHLCV bars** |
| Fill realism | Deep liquidity, near-complete bars | Sparse (5–1,458 bars/contract), **no quote history** |

To match equities' 14 folds you would need roughly **126 months — 10.5 years** of intraday options data. That does not exist at a student budget (see §5).

---

## 2. The six seams

Build these during the course. Each is small now and load-bearing later.

### 2.1 Vendor-agnostic market-data provider

```
MarketDataProvider
  get_bars(symbol, timeframe, start, end, feed)      -> DataFrame
  list_contracts(underlying, as_of, filters)          -> list[Contract]
  get_quotes(symbol, start, end)                      -> DataFrame
  get_chain_snapshot(underlying, as_of)               -> Chain
```

**Define the full interface, including what Alpaca cannot do.** The Alpaca adapter raises `NotSupported` for `get_quotes` and `get_chain_snapshot`; the pipeline degrades explicitly and loudly, never silently.

> **This is the critical detail.** If the interface is shaped around Alpaca's limits, those limits become architectural. A capability the current vendor lacks must still appear in the contract.

Second implementation on the roadmap: a Massive (Polygon) adapter in Phase 2.

### 2.2 Asset-class-parameterised RunConfig

| Parameter | Equities | Crypto | Options |
|---|---|---|---|
| `data_start` | 2016-06-10 | ≥2021-06-10 | 2024-01-18 |
| `session_calendar` | RTH 09:30–16:00 ET | 24/7, no filter | 09:30–16:15 ET |
| `fold_scheme` | 36/6/6, step 6 | 36/6/6, step 6 | *n/a — no folds* |
| `n_folds` | ~14 | ~4 | 0 |
| `feature_set` | price/volume | price/volume | *(Phase 2: + IV/skew)* |

**If the fold scheme is configuration rather than a constant, adding a graded options track post-course is a YAML file plus data.**

### 2.3 Results schema carrying provenance

Every result row stamped with `asset_class`, `vendor`, `feed`, `data_start`, `fold_scheme`, `n_folds`, `config_hash`.

**Highest-leverage item on this list.** It puts the comparability caveat *in the data* rather than in prose — a reader cannot accidentally compare a 14-fold equity result against a 4-fold crypto result without the difference being visible in the row. A Phase 2 options run then drops into the same tables with no analysis rewritten.

### 2.4 Point-in-time universe

`universe_as_of(t) -> list[symbol]`. Today it returns `["SPY"]`. That is fine — the point is that `"SPY"` is never hardcoded across the codebase, so options contract selection later becomes an implementation of an existing concept rather than surgery on every call site.

**This also guards the project's most likely correctness bug.** Selecting options contracts *because they turn out to have bars* is look-ahead bias: it uses knowledge that they traded. A universe that is correct as of decision time is the defence, and it is what a quant interviewer probes first.

### 2.5 Pluggable fill model

```
FillModel.fill(candidate, bar_context, quote_context|None) -> Fill | NoFill
```

- `BarFillModel` — equities, deep liquidity.
- `SparseBarFillModel` — options today. **An absent bar is an untradeable interval, never a forward-filled price.** A backtest that fills on missing bars invents prices that never existed.
- `QuoteFillModel` — Phase 3, once NBBO history is available.

### 2.6 Feature registry with declared data requirements

Each feature declares what it needs (`requires: bars` / `requires: chain_snapshots`). The pipeline refuses to run a feature whose requirements the active provider cannot satisfy. Phase 2 options features are then *added*, not wired in by hand.

### What NOT to build now

No options models, no IV pipeline, no second vendor adapter, no abstraction whose second implementation you cannot name. Six seams, not fifteen.

---

## 3. What options delivers during the course

"Validated execution layer" — quantitative, with a genuine train/test split, making **no strategy-performance claim**.

1. **Contract-selection rule** — deterministic and documented: expiry window, moneyness or delta band, minimum liquidity. Built on `status=inactive` discovery, proven working 2026-09-01.
2. **Measured liquidity screen** — bar presence by moneyness bucket. Replaces the mid-range-strike sampling that produced the misleading 5-bar counts.
3. **Fill-feasibility study** — for every signal the equity system generated from 2024-01-18 onward, was a tradeable contract available at decision time? Report the hit rate with confidence intervals.
4. **Held-out validation** — fit the liquidity screen on the first ~25 months, test on the last ~6. A legitimate out-of-sample split that validates the *selection rule*.
5. **Execution-cost characterisation** by moneyness and regime, with the missing-quote limitation stated outright.
6. **Live paper-forward evidence** through M3.

None of this needs a single walk-forward fold.

---

## 4. Post-course roadmap

### Phase 1 — the course (Shape A)
Equity core, 14 folds, full ablation B1→B2→M1→M2. Crypto graded secondary at 4 folds, fold count attached to every reported number. Options as §3 above. **All six seams in place and unexercised.**

### Phase 2 — Shape B, options-forward (post-course, ~$199–400)
1. Verify **before paying** whether the plan includes historical options *quotes* or only aggregates and trades. Without quotes, slippage stays unfalsifiable and much of the value evaporates.
2. Second-vendor licensing audit — Massive's terms are stricter than Alpaca's, and the repo is public from Week 12.
3. Write the Massive adapter against the §2.1 interface.
4. Backfill ~5 years of options data.
5. Add options-native features via the §2.6 registry: IV, term structure, skew. Requires a risk-free curve and a dividend assumption — both are modelling choices that must be documented and defended.
6. Train options-specific models; run walk-forward at an **explicitly labelled** shorter scheme (~3 folds on 60 months).
7. Tag **v2** with a written diff against v1.

**The version story is itself a portfolio asset:** v1 shipped under a measured data constraint; v2 lifted the constraint and reported what changed. That is a stronger narrative than having done it all at once, because it demonstrates the constraint was understood rather than stumbled over.

### Phase 3 — optional
Quote-based fill model; live paper options; additional underlyings via `universe_as_of`.

---

## 5. Vendor comparison — recorded 2026-09-01

Massive (formerly Polygon) options plans:

| Plan | Price | History | Folds at 36/6/6 |
|---|---|---|---|
| Basic | $0 | 2 years | 0 |
| Starter | $29/mo | 2 years | 0 |
| Developer | $79/mo | 4 years | ~1 |
| **Advanced** | **$199/mo** | **5+ years** | **~3** |

**The decisive comparison: $199/mo buys ~3 options folds. Crypto already gives 4, free.** The free and $29 tiers offer *less* history than Alpaca's 31 months.

Also note: **Massive is a data vendor, not a broker.** Execution stays on Alpaca regardless, so adopting it introduces a second train/live feed mismatch — the same class of problem as SIP/IEX, on the track with the least evidence behind it.

Databento OPRA depth could not be confirmed (quote-based pricing, $125 free credits). Vendors with genuinely deep intraday options history — CBOE DataShop, ORATS — are priced for institutions.

**Conclusion: no vendor switch is justified for the course.** Today's result weakened rather than strengthened the case for Alpaca Algo Trader Plus, since IEX proved real-time with an entitled stream.

---

## 6. The Week 6 gate

> **If the equity core is running end-to-end — B1→B2→M1→M2 across 14 folds, with the risk engine and execution simulator — by the Week 6 checkpoint, graded options may be revisited. If not, options remains a validated execution layer for the course and moves to Phase 2.**

Costs nothing now, keeps the option genuinely open, and makes the call on evidence rather than Week 1 optimism.

---

## 7. Why this ordering is the stronger portfolio

The measurement story is the asset, not the missing feature: *31 months measured, 48 needed for one fold, protocol kept and claim restructured rather than the protocol bent to fit.* Very few student projects contain that reasoning; most contain a backtest with an impressive Sharpe and no discussion of whether the data could support it.

Two others already on the timeline that interviewers probe hard:

- **The SIP/IEX transfer experiment** — training on consolidated volume, executing on a feed carrying ~3% of it, with a pre-committed falsifiable test and a pre-committed decision to drop volume features if it fails. A real production problem with a real experimental design.
- **Point-in-time correctness** — see §2.4.

A purchased 3-fold options table displaces neither and adds little. The seams give you the upgrade *and* the account of why it was deferred.
