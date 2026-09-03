# Options Trading Bot — Standalone Build Plan

**Written 2026-09-03, revised the same day once the purpose was clear.**
Separate from the CIS 5980 capstone, and deliberately not in the `Project-Beta`
repo. This is an independent personal project.

**Purpose: to understand options trading from a retail trader's seat, not an
institution's.** That is not a softer goal than finding edge; it is a different
one, and it changes what this system should optimise for. §2 says how.

Assumptions: **$80/month is acceptable**, and there is **no schedule pressure**.

---

## 0. Licensing verdict — read this before spending anything

Checked against ThetaData's published Terms and Conditions and Subscriber
Agreement, 2026-09-03. **Good-faith reading, not legal advice.**

| Question | Finding | Consequence |
|---|---|---|
| **Can I subscribe, download the history, and cancel?** | **No.** Subscriber Agreement §8(c): on termination "Licensee shall cease using and delete, destroy, or return all copies of the Data." §8(e): "All data obtained indirectly or directly from Theta Data must be expunged within 30 days of termination." The T&C additionally require written certification of destruction | **$80/month is recurring while you hold the data.** But see §12: for a study rather than a permanent system, a *bounded* subscription is the right shape |
| **Do my computed results survive cancellation?** | Not addressed directly. The obligation attaches to "the Data" | **Ask them in writing.** The natural reading is that aggregate statistics which cannot reconstruct quotes are yours; do not assume it |
| **Is research use permitted?** | Yes. Exhibit A, Section C permits "internal personal use... analysis, and/or research" | Backtesting for your own account is the permitted use |
| **Can I redistribute or publish the data?** | **No.** §1(b) bars disclosing or delivering data to any third party without written consent; §8(e) bars redistribution "before or after the time of termination." OPRA data "shall remain the property of the respective exchange" | **Same posture as Alpaca.** Publish code, hashes and aggregate results. Never quotes, never anything a price series could be rebuilt from |
| **Commercial use?** | **Prohibited.** Limited to "your personal investment activities and the personal investment activities of your immediate family members" | Fine for a personal bot and a portfolio piece. Not fine for managing anyone else's money or selling signals |
| **Do trading strategies count as "derivative works"?** | **Ambiguous.** The T&C bar creating "derivative works of the Services or any Content"; Exhibit A separately permits analysis and research | Same ambiguity as Polygon §5(d). Put it to ThetaData support in writing before publishing anything built on it, and keep the reply |
| **Professional vs non-professional status** | Referenced via OPRA, not defined | Already open with Alpaca. Resolve both in one email |

---

## 1. 🚩 THE STOP GATE — do this first, and be willing to stop

> **Phase 1 is not "write the adapter." Phase 1 is the vendor transfer
> experiment, and it is a gate you must be prepared to fail.**
>
> This bot would **backtest on ThetaData's consolidated OPRA quotes** and
> **fill against Alpaca's paper engine**. Two different vendors describing the
> same market. That is a train/live feed mismatch, vendor edition, and it is the
> same class of problem the capstone already measured between SIP and IEX —
> where the pre-committed test **failed** and an entire feature class was
> dropped.
>
> **Before any strategy work, before any backtest, before any model:** pull the
> overlap where both vendors cover SPY options, compare mid prices, spreads and
> bar presence contract by contract, and **fix the pass/fail threshold before
> running it**.
>
> **If they disagree materially, stop.** A ThetaData backtest that does not
> predict Alpaca fills is a backtest of a system you cannot run. Finding that
> out costs one month's subscription. Finding it out after eight years of
> results exist costs the credibility of every number in them.
>
> This is the step most people skip, and skipping it is how a bot that
> backtests beautifully loses money for reasons nobody can locate.

---

## 2. What this project is for, and what that changes

**The goal is understanding, not edge.** The question is not "can I beat the
market" but "**what actually determines a retail options trader's outcome, and
where does the money go?**"

Five consequences, and they run through the rest of this document:

1. **A negative result is a complete success.** If the bot loses money and the
   attribution shows exactly why, the project has done its job. That removes the
   pressure that makes people quietly move thresholds.
2. **P&L attribution is the headline deliverable, not a measurement layer.**
   The single most valuable thing this can teach you is the answer to *"I was
   right about direction and still lost money — where did it go?"* That is §10a,
   and everything else exists to make it computable.
3. **Statistical ceremony relaxes; honesty guards do not.** Drop the bootstrap
   confidence intervals and the locked-protocol formality — you are not
   convincing a reviewer. **Keep every leakage guard**: point-in-time universe,
   no forward fill, no look-ahead. Those exist to stop you fooling *yourself*,
   which is the entire risk in a project with no external referee.
4. **Fold count matters less; quote data matters more.** Ten walk-forward folds
   serve a claim you are no longer making. The NBBO history serves the lesson
   directly, because the spread is the dominant retail cost and you cannot see
   it without quotes. That reshapes the budget in §12.
5. **Long-only stops being a compromise and becomes the correct scope.** §6
   noted that most documented options edge lives in *selling* premium, and that
   a long-only rule trades that away for safety. For a project about the retail
   experience, long premium is also **what most retail options activity actually
   is**. The constraint now matches the subject.

---

## 3. What the $80 buys

| | Alpaca alone | With ThetaData Standard |
|---|---|---|
| Options history | 31 months | **8 years** |
| Walk-forward folds at 30/6/6 | 0 | 10 |
| **Quotes (NBBO)** | **none** | **every OPRA quote, tick level** |
| Spread cost | unmeasurable | **measured** |
| Greek attribution | crude, from thin trade bars | **clean, from quote mids** |

Given §2, read that table bottom-up. The last three rows are why you would pay;
the fold count is a bonus.

## 4. Architecture

```
ThetaData (research)          Alpaca (execution)
      |                              |
      +---- MarketDataProvider ------+        <- already built
                    |
      SPY bars, features, regime + signal-quality models   <- reused unchanged
                    |
            Trade Decision Engine  + IV gate               <- one new rule, §6
                    |
            Contract selection (deterministic)             <- new
                    |
            Options risk engine                            <- new
                    |
      NBBO fill model (backtest) | Alpaca paper (live)     <- new
                    |
      Decision log -> P&L attribution -> metrics           <- new, the deliverable
```

**The design decision that makes it work: the signal comes from the underlying,
the option is the execution instrument.** SPY 5-minute bars drive the features
and both models. Only after a trade is approved does the system choose a
contract. Nothing is trained on options data, so the models keep the full SPY
history rather than being truncated to the options window.

## 5. Phase 1 — the data layer, and the gate

Write `data/thetadata.py` against the existing `MarketDataProvider` Protocol.
This is the payoff for seam 1: a new adapter file, not a rewrite. It implements
`get_bars`, `list_contracts` and — unlike the Alpaca adapter — `get_quotes`,
which currently raises `NotSupported`.

Then run the §1 gate and honour its result. Reuse `transfer_check.py`'s pattern:
pre-committed thresholds, a logged artifact, a verdict the code computes rather
than you.

## 6. Strategy design — are options strategies the same as equity strategies?

**Partly, and the part that differs is the part that matters.**

A momentum signal expresses a *directional* view. Options can carry a
directional view, but they can also carry views with no equity analogue: that
implied volatility is too high, that skew is mispriced, that the term structure
is wrong. Running momentum alone means **you are trading equities with a
different instrument, and taking an unmeasured volatility position on the side.**

### Why buying a call is not buying stock with leverage

When you buy a call to express bullish momentum, you unavoidably also **buy
volatility and sell time**. If SPY rises exactly as your signal predicted, but
slowly, you can still lose money. The equity version of that trade cannot lose.
That is not a detail; it is a second bet you did not consciously place — and per
§2, understanding that bet is most of the point of this project.

### Three levels of response, cheapest first

**Level 1 — gate on IV rank. Do this one.** Keep momentum as the only signal,
and add one condition to the Trade Decision Engine: take long-premium trades
only when IV rank is low, meaning options are cheap relative to their own recent
history. The volatility exposure becomes deliberate rather than accidental. One
rule, fits the existing gate architecture exactly, highest value per line in
this document.

**Level 2 — let the structure match the view.**

| Conviction | IV rank | Structure | Why |
|---|---|---|---|
| Strong | Low | Long call or put | Maximum convexity, premium is cheap |
| Moderate | High | Vertical debit spread | Caps the volatility exposure and the cost |
| Weak | Any | No trade | The risk engine already handles this |

**Level 3 — an options-native strategy.** Signals from options-market quantities
rather than price: IV rank and percentile, the **IV minus realized-vol spread**,
term-structure slope, put-call skew, open-interest concentration. These predict
*volatility*, not direction, and they are the only place options-specific edge
actually lives.

### Do you need to capture alphas?

**Not to build the bot.** Momentum plus an IV gate is coherent and, for §2's
purpose, sufficient.

**Yes, if you want edge that comes *from options*** rather than equity edge
merely expressed through options:

- **Time-series alphas on one underlying** — IV rank, IV-RV spread, term slope,
  skew. Computable from ThetaData for SPY alone, and they drop into the feature
  registry as ordinary features.
- **Cross-sectional alphas across a universe** — rank hundreds of underlyings by
  IV percentile or skew steepness and trade the extremes. Closer to the
  WorldQuant formulation. Available at the same $80 since ThetaData covers OPRA,
  but it multiplies data volume, survivorship care and liquidity screening by
  the size of the universe. **Not a v1.**

### Sequence, and let the data choose

1. Build **momentum + IV-rank gate** (Level 1).
2. Run the **greek attribution** in §10a. If most P&L traces to **delta**, your
   equity signal is doing the work and options are just leverage. If most traces
   to **vega**, the volatility dimension is where the action is.
3. Build **Level 3** only if step 2 says so.

---

## 7. The retail reality layer — the part institutions never feel

This section exists because of §2, and it is what separates this from a toy
institutional system.

### 7.1 The spread is the dominant cost, by an order of magnitude

A $2.00 option quoted 1.95 / 2.05 costs **5% round trip** to cross. Commissions
are noise beside that. Institutions get price improvement, midpoint fills and
size; retail crosses the spread. **Quantifying this, by moneyness and by DTE and
by time of day, is arguably the single most useful output of the whole project**,
and it is exactly what the NBBO data is for.

Deliverable: a spread-cost table, and a chart of realised cost against the
strategy's gross edge. If the spread eats the edge, that is the finding.

### 7.2 Commissions — model them even though Alpaca's are zero

**Alpaca charges no commission on options** through the Trading API, and
per-contract regulatory and exchange fees (OCC, ORF, SEC, TAF) still apply and
are not itemised on their support page; pull the current brokerage fee schedule.

**That makes Alpaca unrepresentative of typical retail**, where $0.50 to $0.65
per contract is normal. Since the goal is to understand the retail seat rather
than to flatter the result, **run the cost model at $0, at $0.65/contract, and at
$1.00/contract** and report all three. On a $200 premium, $0.65 each way is 0.65%
round trip — small against the spread, large against a thin edge.

### 7.3 Position sizing does not divide evenly

You cannot buy 0.4 contracts. With a $10,000 account and a 2%-of-equity premium
cap, the budget is $200, which buys roughly **one** contract of anything liquid.
That has three consequences a large account never meets:

- **granularity**: sizing is quantised, so risk per trade jumps in steps
- **diversification is unavailable**: one or two positions, not twenty
- **a single bad fill is a meaningful fraction of the month**

Model it honestly: floor the contract count, and skip the trade when the floor
is zero rather than silently rounding up.

### 7.4 The $25,000 day-trading rule is gone, and that is new

FINRA Regulatory Notice 26-10 eliminated the pattern-day-trader designation and
the **$25,000 minimum equity requirement entirely**, replacing them with an
intraday margin standard, **effective 4 June 2026**, with an 18-month phase-in to
20 October 2027 for firms needing time.

This matters a lot for a 5-minute-bar strategy, which until three months ago
would have been capped at three day trades per five business days below $25k.

- **Confirm Alpaca has actually implemented it** rather than assuming; the
  phase-in runs to late 2027.
- The replacement rule attaches to **intraday margin deficits**. A long-only
  options bot that pays premium in full has no margin requirement beyond the
  premium, so it should not bind. **Verify rather than assume**, and record the
  answer.

### 7.5 Expiry mechanics, even long-only

An in-the-money long option is **auto-exercised at expiry** unless you close it,
which can hand you 100 shares of SPY you did not budget for and cannot afford in
a small account. This is why §8's expiry-day flatten by 15:30 ET is a hard rule
rather than a nicety.

### 7.6 Taxes, noted rather than modelled

Options gains are short-term for a strategy holding days, and the wash-sale rule
applies. Not worth modelling in the backtest; worth knowing before reading any
result as take-home money.

---

## 8. Contract selection and risk

```
select(direction, spot, t) -> contract | NO_CONTRACT(reason)
  universe = universe_as_of(t)                  # point-in-time, non-negotiable
  filter   = right matches direction
           & DTE in [min_dte, max_dte]
           & |strike/spot - 1| <= moneyness_band
           & NBBO spread <= max_spread_pct      # §7.1, now measurable
           & quoted size >= min_size
  rank     = closest to target moneyness, then tightest spread
```

`universe_as_of(t)` is the single most important line. Selecting a contract
because it turns out to have traded is look-ahead bias in its purest form, and
it is the guard §2 says never relaxes.

| Control | Rule |
|---|---|
| Sizing | Max premium per trade as a fraction of equity. **Premium at risk, never notional.** Floor the contract count; skip at zero (§7.3) |
| Daily theta budget | Cap total premium outlay per session |
| **Long only in v1** | The system may never construct a short-option order. Removes assignment, margin calls and undefined loss in one rule — and matches what retail actually does (§2.5) |
| No opens near expiry | DTE floor |
| Expiry-day flatten | Close everything by 15:30 ET (§7.5) |
| Max concurrent contracts | Bounds correlated exposure across strikes |

One test per control, asserting the order is refused.

## 9. The fill model, which is the point of paying

- **Entry**: limit at mid plus a fraction of the spread, filled only if the
  quote supports it at that timestamp, with a stated size assumption
- **Never market orders.** A wide options spread makes a market order an
  unpriced commitment
- **Spread cost is measured, not assumed** (§7.1)
- **Queue position and market impact are not simulated.** Fills stay optimistic;
  say so in every result

## 10. Measurement

**a. P&L attribution by greek — the headline deliverable.** Back implied vol out
of the NBBO mid, compute greeks at entry and exit, then decompose:

```
dP  ~=  delta*dS  +  0.5*gamma*dS^2  +  vega*dIV  +  theta*dt  +  residual
```

Report what fraction of P&L came from **direction**, from **volatility**, and
from **decay**. This answers the retail question directly, and it is also the
test that decides whether Level 3 is worth building. `py_vollib` or QuantLib do
the pricing; the Treasury curve is free from FRED and SPY's dividend yield is
public. Document the assumptions: SPY options are American, so Black-Scholes is
an approximation.

**b. Cost decomposition.** Gross P&L, then spread cost, then commissions at
three levels (§7.2), then net. **Show what fraction of gross edge each layer
eats.** For a retail-perspective project this is as important as the attribution.

**c. Skew-aware performance metrics.** Sortino, Calmar, profit factor, tail
ratio, maximum drawdown, win rate, average win against average loss, and the
full return distribution rather than its first two moments. Report Sharpe, never
alone.

**d. Walk-forward, 30/6/6, 10 folds.** Keep the structure for honesty, drop the
significance machinery per §2.3. Report per-fold results and let the spread
across folds speak for itself.

## 11. Paper-forward

Run it live on Alpaca paper (Level 2: buy calls, buy puts) for 12 to 18 months.
Limit and market orders only, day time-in-force only, no extended hours, no
fractional contracts.

Free, and for §2's purpose the most instructive phase of all: it is the only way
to measure the gap between your NBBO backtest fills and what a broker actually
does, and watching it run is where the retail intuition actually forms.

## 12. Budget — bounded, not open-ended

Given §2.4, the subscription is for a **study period**, not forever:

| Phase | Data | Cost |
|---|---|---|
| Gate (§1) | ThetaData Standard, 1 month | $80 |
| Study: backtest, attribution, cost decomposition | ThetaData Standard, 3 to 5 more months | $240 to $400 |
| Paper-forward (§11), 12 to 18 months | Alpaca free tier | **$0** |
| **Total** | | **$320 to $480** |

Then cancel and delete the raw data per §0, keeping your computed results if
ThetaData confirms in writing that aggregates survive termination. **Ask before
you subscribe, not after.**

If the §1 gate fails, you stop at $80.

## 13. Sequence

| Phase | Work | Gate |
|---|---|---|
| 1 | ThetaData adapter, **vendor transfer experiment** | 🚩 **The transfer result. If the vendors disagree, stop** |
| 2 | Momentum + IV-rank gate (§6 Level 1) | The gate is a config parameter, not a hard-coded rule |
| 3 | Contract selection, `universe_as_of`, options risk controls | Every control refuses its order in a test |
| 4 | NBBO fill model, retail cost model (§7) | No-forward-fill and point-in-time assertions pass |
| 5 | **Attribution and cost decomposition** (§10a, §10b) | This is the deliverable. Everything before it is plumbing |
| 6 | Level 3 vol strategy — **only if attribution says vega dominates** | §6's step 2 |
| 7 | Paper-forward, 12 to 18 months | — |

Phases 1 to 5 are perhaps six to ten weekends. Phase 7 is calendar time.

## 14. What success looks like

Not a Sharpe ratio. Success is being able to answer these, with numbers you
produced and can defend:

- **Where does a retail options trader's money actually go?** Split gross P&L
  into direction, volatility, decay, spread and commission.
- **How much of the edge does the spread eat**, by moneyness, DTE and time of
  day?
- **Was I right about direction and still wrong about the trade?** How often, and
  by how much.
- **Does gating on IV rank change the answer?** That is a clean, isolated
  experiment.
- **How far apart are backtest fills and paper fills?** The honest measure of
  every backtest anyone shows you, including yours.

**A losing bot that answers all five is a success.** A profitable bot that
answers none is a coincidence you cannot repeat.

### Still true, and worth keeping in view

- Eight years holds a handful of genuine volatility regimes, and options P&L is
  fat-tailed, so tail behaviour stays under-sampled however many folds you count.
- Paper fills are optimistic; a paper-forward record is evidence, not a track
  record.
- The largest documented options edge is out of scope by design (§6), so a null
  result is evidence about the half you chose to trade.
- Commercial use is barred by the data licence.

---

**Sources:** [ThetaData pricing](https://www.thetadata.net/pricing) ·
[ThetaData Terms and Conditions](https://www.thetadata.net/terms-and-conditions) ·
[ThetaData Subscriber Agreement](https://www.thetadata.net/subscriber-agreement) ·
[Alpaca options trading overview](https://docs.alpaca.markets/us/docs/options-trading-overview) ·
[Alpaca options commissions](https://alpaca.markets/support/what-are-the-commission-fees-per-option-contract) ·
[FINRA Regulatory Notice 26-10](https://www.finra.org/rules-guidance/notices/26-10)
