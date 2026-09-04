# Decisions that constrain implementation

Rules already settled, with the reason for each. Most are enforced in code and
will fail a test or a config load if broken. **If a rule looks wrong or gets in
the way, raise it rather than working around it.** Reversing one is a normal
conversation; routing around one silently is not.

| # | Rule | Why | Enforced by |
|---|---|---|---|
| 1 | Walk-forward is **30/6/6, step 6** (42 months per fold): 14 equity folds, 4 crypto, 0 options | The validation window exists so thresholds are never chosen on the test window. 30 months still spans several regimes | `WalkForwardConfig` defaults |
| 2 | **No volume-derived features**, in the models or in B2's strategy rules | Backtests run on SIP, live runs on IEX at ~3% of the volume. The 2026-09-02 transfer test measured Spearman 0.57 against a pre-committed 0.70 bar and failed | Review. Do not reintroduce |
| 3 | An `asset_class: option` config **may not carry a `walk_forward` block** | Options history begins 2024-01-18. 31 months, and one fold needs 42. Zero folds | `RunConfig.validate()` |
| 4 | **No options result row carries a Sharpe or drawdown** | Options makes a fill-feasibility claim, never a performance claim | Harness schema test |
| 5 | Options require `fill_model: sparse_bar`. **A missing bar is a no-trade interval, never a forward-filled price** | Filling an absent bar invents a fill that could not have happened | `RunConfig.validate()`, execution simulator test |
| 6 | The options universe is **point-in-time**: `universe_as_of(t)` | Selecting a contract because it turns out to have traded is look-ahead bias, and the most likely correctness bug here | `AlpacaProvider.list_contracts` |
| 7 | **RTH filter runs before any feature is computed.** Crypto uses `continuous` instead | 60% of SIP bars fall outside regular hours and behave differently. Options carry extended-hours bars too | `RunConfig.validate()`, pipeline |
| 8 | `feed` is **equities only** (`sip` or `iex`). Crypto and options must not set one | Alpaca versions its data APIs per asset class; sip/iex is an equities concept | `RunConfig.validate()` |
| 9 | Per-asset-class history floors: SIP 2016-06-10, IEX 2021-06-10, crypto 2021-06-10, options 2024-01-18 | Measured by API probe. Earlier dates return no bars | `DataConfig.history_floor()` |
| 10 | **Backtest on SIP, live paper on IEX** | Recent SIP is not entitled on the free tier (403) and SIP streaming returns 409 | `RunConfig.validate()` |
| 11 | **Paper endpoints only.** No live-money code path exists | Safety guardrail from the Responsible AI charter | `AlpacaProvider.__init__` rejects a non-paper host |
| 12 | Credentials come from the environment, never source. **Startup makes one authenticated call and aborts on non-200** | A check that credentials are non-empty is not a check. A key rotation once produced a full run of 403s that looked successful | `authenticate()`, guardrail test |
| 13 | **Every results row records** `asset_class`, `feed`, `fold_scheme`, `n_folds`, `config_hash` | The comparability caveat belongs in the data, not in prose around it | `RunConfig.provenance()`, schema test |
| 14 | The LLM reads the **decision log only** and never enters the trade decision path | It narrates decisions the deterministic engine already made. This is what keeps the system outside the provider's high-risk category | Grounding checker, ≥50-sample audit |
| 15 | **No market data, verification reports, or full decision logs in the repo.** Bounded sample fixtures only | Vendor terms prohibit redistribution, and a multi-year decision log approximates a price series | `tests/test_guardrails.py`, CI |
| 16 | Coverage validation: **do not assert exactly 78 bars/day**, flag days below 90%, exclude the first and last day of any fetch window | Post-filter counts legitimately fall short on a thin feed, and a window edge is not an outage | Pipeline validation |
| 17 | The primary metric is **locked**: annualised Sharpe, M2 versus B2, equities only | Prespecified before any model was trained. See `EVALUATION_PROTOCOL.md` | Guardrail test |

The full decision history, including options considered and declined, is
maintained separately. If the reason above is not enough to act on, ask.
