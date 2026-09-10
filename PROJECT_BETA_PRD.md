# PROJECT BETA - Product Requirements Document

**Version:** 4.0 draft, revised 2026-09-10 after Chris's Phase 1 feedback.

**Governing direction:** PROJECT BETA is an evidence-grounded inspector and
agent over a simulated trading account. It is not a trading-performance product.
Profitability is not a success criterion. The project is equities-only during
the capstone.

See `Project_Outline.md` for the readable project plan and `DECISIONS.md` #25
for the pivot decision.

---

## 1. Product Vision

PROJECT BETA lets a user ask bounded questions about a simulated trading account
and the automated trading decisions behind it.

The agent can answer questions such as:

- "Why was this trade rejected?"
- "Was this position reduced by the risk engine?"
- "What did the account hold after this order?"
- "Which rejection reason was most common this week?"
- "Why did nothing happen at this timestamp?"

The agent must answer only from cited records or tool results. If the evidence
is absent, ambiguous, outside the account scope, or advisory, it refuses.

The trading pipeline still matters, but as evidence generation. Strategy rules,
M1, M2, and the risk engine create the decisions, rejections, scores, reason
codes, and records the inspector explains.

## 2. Goals

Required product goals:

- Inspect account records, order records, and decision records.
- Explain approved, reduced, delayed, rejected, and absent trade decisions.
- Refuse unsupported questions.
- Refuse investment advice and strategy-ranking requests.
- Cite every factual answer to records or tool results.
- Support tier-1 single-record questions.
- Support tier-2 cross-record aggregate questions.
- Correctly refuse tier-3 unsupported questions.
- Provide a small simulated account layer with safe state-changing actions.
- Require confirmation before simulated order placement.
- Measure cost, latency, refusal, false refusal, contradiction, and audit time.

## 3. Non-Goals

The capstone does not build:

- live-money trading,
- crypto,
- options,
- an order book,
- a matching engine,
- simulated market participants,
- autonomous LLM trade selection,
- LLM-generated investment advice,
- strategy ranking,
- public redistribution of licensed market data.

## 4. Architecture

```text
Market data
→ deterministic trading pipeline
→ M1 regime classifier
→ M2 signal-quality model
→ deterministic risk and trade decision
→ execution simulator
→ append-only decision/account records
→ MCP-style tool surface
→ grounded AI inspector
→ answer, citation, or refusal
```

### Layers

| Layer | Responsibility |
|---|---|
| Data and strategy layer | Builds features and produces candidate decisions on equities data |
| M1/M2 layer | Produces regime context and signal-quality scores |
| Risk/execution layer | Applies deterministic rules, simulates fills, records outcomes |
| Simulated account layer | Maintains fake accounts, balances, positions, orders, confirmations |
| Tool layer | Exposes bounded read/write actions with authorization checks |
| Inspector layer | Uses tools and records to answer, cite, or refuse |

The LLM never enters the trade decision path. It cannot widen account scope or
authorize its own actions.

## 5. Core Data Contracts

### DecisionRecord

A decision record should capture:

- `decision_id`
- `timestamp`
- `symbol`
- `strategy_family`
- `candidate_signal`
- `m1_regime_state`
- `m1_regime_probabilities`
- `m2_score`
- `m2_threshold`
- `m2_threshold_fold`
- `m2_threshold_window`
- `risk_state`
- `decision_outcome`
- `reason_codes`
- `position_size`
- `fill_result`
- `evidence_refs`

Any record carrying a fitted threshold also carries the fold and validation
window that selected it (`DECISIONS.md` #28). The signal-quality threshold is
chosen per validation window, so it varies across folds. An answer citing a
threshold without naming its window is ungrounded.

### RuleStateTrace

A rule-state trace should capture why no candidate or order existed at a
timestamp:

- `timestamp`
- `strategy_family`
- checked rule conditions,
- pass/fail state for each condition,
- final non-decision reason,
- evidence refs.

### AccountRecord

The simulated account model should capture:

- `account_id`
- cash balance,
- buying power,
- positions,
- order history,
- account actions,
- confirmation records,
- fills,
- cancellations and rejections.

## 6. Simulated Account Layer

Minimum account features:

- three seeded accounts,
- account lookup,
- balance lookup,
- holdings lookup,
- order history lookup,
- simulated order placement,
- confirmation before order placement,
- append-only records for every account action.

Order lifecycle:

```text
requested → confirmation_required → submitted → filled | cancelled | rejected
```

Orders fill through the existing execution simulator against replayed historical
bars. There is no order book and no matching engine.

Authorization requirements:

- A principal can inspect only accounts assigned to that principal.
- The model cannot change principal identity.
- The model cannot place an order without explicit confirmation.
- The model cannot alter account permissions or contact details.

## 7. Tool Surface

The first tool surface should be small and typed.

Read tools:

- `get_account(account_id)`
- `get_balances(account_id)`
- `get_positions(account_id)`
- `get_order_history(account_id, filters)`
- `get_decision(decision_id)`
- `get_rule_state(timestamp, strategy_family)`
- `get_historical_price(symbol, timestamp)`
- `get_aggregate(metric, filters)`

State-changing tool:

- `place_simulated_order(account_id, symbol, side, quantity, confirmation_id)`

The order tool must fail without a valid confirmation record.

## 8. Inspector Behavior

The inspector must:

- answer from records and tool results only,
- cite evidence for every numeral and controlled state label,
- refuse unsupported questions,
- refuse advisory questions,
- refuse strategy-ranking questions,
- state when a required record does not exist,
- never infer a cause for a non-decision unless a rule-state trace records it.

Generated answers pass through the grounding filter before release. Any answer
with an untraceable factual claim is blocked or sent to review.

## 9. Evaluation

The inspector evaluation set has about 200 cases:

| Tier | Count | Expected behavior |
|---|---:|---|
| Tier 1 | 80 | Answer from one cited record |
| Tier 2 | 60 | Answer from aggregate evidence across records |
| Tier 3 | 60 | Refuse because available evidence cannot support the answer |

Build and measure an initial 60-case subset first: 30 tier 1, 15 tier 2, 15
tier 3.

### Case generation

Cases are generated compositionally rather than hand-authored, following the
tau2-bench pattern. A case is three ordered lists:

- **initialization functions** that select or construct the record state,
- **solution functions**, restricted to reads a real tool could perform, that
  produce the answer,
- **assertion functions** that must hold: required values, the reason code, the
  cited record id, and prohibited claims.

Groups are mutually exclusive by gate outcome (regime gate, signal-quality gate,
risk gate, and the single-valued final decision), and a case combines at most one
outcome per gate. Correctness is verified mechanically: apply the initializations,
apply the solutions, confirm every assertion holds, and separately confirm the
case was not already satisfied beforehand.

Tier 3 is the case where the solution list is empty. That is a property of the
record schema and the permitted tool set rather than a judgment, which is what
makes the refusal metric defensible. **Unanswerability is relative to the
declared record and tool boundary, not absolute.**

Hand-authoring is the exception, not the rule: it is for cases the generator
cannot express, and each one is recorded as such.

### Harness

The harness takes a pluggable answerer (`DECISIONS.md` #26). `E0`, `E1`, `E2`,
`Oracle` and `Full` run through the same interface and the same code path, and
`E3` plugs in unchanged.

Retrieval is separable from generation (`DECISIONS.md` #27), so the harness can
run three modes against the same case:

| Mode | Evidence supplied | Isolates |
|---|---|---|
| Oracle-record | Exactly the records the case needs | Grounded generation, retrieval removed |
| Default | The system retrieves | The whole pipeline |
| No-record | Withheld; the answer is not recoverable | Refusal calibration |

### Grading order

Mechanical checks first. An LLM or rubric judge scores only residual prose
quality and is **never the source of truth** (`DECISIONS.md` #22).

| Check | Used for |
|---|---|
| `exact_match` | Scalars: reason codes, record ids, scores, thresholds, dates |
| `must_include` | Multi-part answers: reason plus value plus threshold plus record id |
| `must_not_include` | Prohibited claims, advice, fabricated ids, values absent from the cited record |
| Deterministic aggregation | Tier 2 counts, rates and grouped summaries |
| Judge | Readability and completeness, after the above |

Report the share of the suite graded mechanically against the share judged, and
the judge's agreement with human labels on a sample.

Metrics:

- evidence faithfulness,
- citation accuracy,
- unsupported-claim rate,
- grounding block rate,
- tier-1 correctness,
- tier-2 correctness,
- correct refusal rate,
- false-refusal rate,
- contradiction rate,
- confirmation-before-order compliance,
- cross-account violation rate,
- median audit time.

Refusal and false-refusal are reported together. Faithfulness is reported beside
block rate.

## 10. Baselines

Inspector baselines use `E` names to avoid collision with trading-system `B`
names.

| Name | Description |
|---|---|
| E0 | Deterministic template, no LLM |
| E1 | Naive Claude with code/data/record context but no Project Beta grounding |
| E2 | Project Beta with the policy document removed |
| E3 | Open-weight model in the same harness |
| Oracle | Deterministic upper bound reading directly from records |

`E0`, `E1`, `E2` and `Oracle` are **core measured systems**. `E3` is **planned if
schedule allows** and is cuttable before core inspector delivery is threatened
(`Project_Outline.md` §14, cut ladder item 5). Cutting `E3` requires no harness
change, because every system runs through the same answerer interface.

Trading names remain:

- B1 = buy and hold.
- B2 = momentum breakout plus risk layer.
- M1 = B2 plus regime classifier.
- M2 = M1 plus signal-quality model.

## 11. Red-Team Requirements

The red-team suite should include:

- cross-account access attempts,
- order placement without confirmation,
- attempts to trade from another account,
- prompt injection through user text,
- prompt injection through stored record text,
- investment-advice requests,
- strategy-ranking requests,
- unsupported market-fact questions,
- hallucination before/after tests with and without the historical-price tool.

Expected result: either a cited answer from permitted evidence or a clear
refusal.

## 12. User Experience

The first usable interface should prioritize inspection, not trading.

Required views:

- account summary,
- positions,
- order history,
- decision feed,
- decision detail with evidence,
- inspector question box,
- refusal/citation display,
- audit-friendly record view.

Nice-to-have views:

- replay mode,
- aggregate evaluation dashboard,
- red-team result summary.

The UI must display the paper-trading-only disclaimer and must never present
outputs as investment advice.

## 13. Acceptance Criteria

The project is release-ready when:

1. A user can inspect at least one seeded account end to end.
2. A user can ask tier-1 questions over single records and receive cited answers
   or refusals.
3. Tier-2 aggregate questions are answered from deterministic aggregate outputs.
4. Tier-3 unsupported questions are refused.
5. Simulated order placement requires confirmation.
6. Cross-account attempts are refused or blocked.
7. The evaluation harness runs the 60-case subset, then the full 200-case suite.
8. E0, E1, E2, and Oracle are measured; E3 is measured if schedule allows.
9. Faithfulness, block rate, refusal, false refusal, contradiction rate, cost,
   latency, and audit time are reported.
10. No live-money path exists.
11. No market data, credentials, or full reconstructive decision logs are
    committed.

## 14. Proposed Work Split

This split is a planning assumption until Henry and Jacky agree.

| Stream | Proposed owner |
|---|---|
| Inspector, refusal policy, grounding, MCP/agent integration | Henry |
| Decision records, rule-state traces, account data, tier-2 aggregates | Jacky |
| Evaluation set, red-team suite, audit test, cost/latency report | Shared |

If Jacky prefers a different stream or has different capacity, adjust this plan
before creating owned issues.
