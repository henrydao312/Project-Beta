# PROJECT BETA - Project Outline

**Current direction, revised 2026-09-10 after Chris's Phase 1 feedback.**

PROJECT BETA is an evidence-grounded AI inspector and agent for a simulated
trading account. It answers questions about account activity, orders, positions,
and automated strategy decisions using only logged records. If the records do
not support an answer, it refuses clearly.

This is not a trading-performance project. Profitability is not the success
criterion. The main success criteria are faithfulness, correct refusal,
false-refusal control, contradiction rate, and audit time.

See `DECISIONS.md` #25 for the pivot decision. Older trading-performance
decisions still govern the appendix trading comparison where relevant, but they
do not define the product direction.

---

## 1. Project Statement

**PROJECT BETA is an AI agent that can inspect a simulated trading account and
prove its answers from the system's own records.**

Under the agent, a transparent equities-only trading pipeline creates realistic
decision records. Strategy rules, M1, M2, and the deterministic risk engine
produce approved trades, rejected trades, sizing changes, model scores, reason
codes, and non-decision traces. The inspector is evaluated on whether it can
answer questions about that evidence without inventing facts.

The simulated account layer adds balances, positions, order history,
confirmation records, and simulated order placement. Orders fill through the
existing execution simulator against replayed bars. There is no order book and
no matching engine.

## 2. What Changed

Chris's feedback moved the center of the project:

| Old center | New center |
|---|---|
| Trading bot / workbench | Evidence-grounded account inspector |
| Profitability and Sharpe as headline | Faithfulness, refusal, contradiction rate, audit time |
| User-facing strategy selection | Strategy families generate varied records |
| Crypto/options expansion | Equities only during the capstone |
| Optional inspector layer | Inspector is the product |

The previous M2-vs-B2 Sharpe protocol remains intact as appendix evidence
because it was pre-registered before results were seen. It is no longer the
project's primary result.

## 3. Research Questions

**Primary:** Can an AI agent answer questions about a simulated trading account
faithfully, citing only the records it actually has, while refusing unsupported
or advisory questions?

**Secondary:** Does the grounded inspector reduce hallucinations and
contradictions compared with a naive Claude baseline and other evaluation
baselines?

**Supporting:** Can M1/M2 and the risk engine produce a rich enough automated
decision history for the inspector to audit, even when the trading result itself
is `no_claim`?

## 4. Scope

### Guaranteed Capstone Scope

- Equities only, centered on SPY.
- Existing deterministic trading pipeline.
- M1 market-regime classifier.
- M2 signal-quality model.
- Deterministic risk engine and execution simulator.
- Decision records for approved, reduced, delayed, and rejected candidates.
- Rule-state traces for timestamps where no trade happened.
- Simulated account layer: accounts, balances, positions, order history,
  confirmation records, and simulated order placement.
- MCP-style tool surface for account lookup, holdings lookup, order history,
  historical price lookup, and simulated order placement.
- Grounded inspector over single records and account records.
- Cross-record/tier-2 aggregation over logged evidence.
- 200-question evaluation set.
- Red-team tests.
- 60-second human audit test.
- Cost and latency report.

### Explicitly Out of Capstone Scope

- Real-money trading.
- Crypto.
- Options.
- Order book.
- Matching engine.
- Simulated market participants.
- Autonomous LLM trading decisions.
- LLM-generated investment advice.
- Strategy ranking or "which strategy should I use" answers.
- Public benchmark release containing licensed market data.

Working code or notes from the old crypto/options plan do not need to be deleted,
but they are not active capstone scope.

## 5. Product Workflow

```text
Market data
→ features
→ transparent strategy rules
→ M1 regime state
→ M2 signal-quality score
→ deterministic trade/risk decision
→ execution simulator
→ decision and account records
→ MCP-style tools
→ grounded AI inspector
→ answer, citation, or refusal
```

Two kinds of records feed the inspector:

| Source | Who decides? | Example record |
|---|---|---|
| Automated strategy stream | Strategy rules, M1/M2, and risk engine | Candidate rejected because M2 score was below threshold |
| User-directed account stream | User, after tool checks and confirmation | User-confirmed simulated sell order |

The LLM never decides a trade. It reads records and explains them.

## 6. How M1/M2 Still Matter

M1 and M2 no longer need to prove that they make a profitable trading bot. They
remain load-bearing because they create the automated decisions the inspector
must explain.

M1 contributes:

- market-regime labels and probabilities,
- volatility-state context,
- participation or restriction signals.

M2 contributes:

- signal-quality scores,
- pass/fail decisions against fixed thresholds,
- explanations for why a candidate was accepted or rejected.

Together with the risk engine, they create the record variety needed for the
question set: approvals, reductions, delays, rejections, non-decisions, and
conflicting-looking cases the inspector must disambiguate.

## 7. Data And Records

The decision record is the source of truth for automated strategy activity. It
should include:

- timestamp,
- strategy family,
- candidate signal details,
- M1 regime probabilities,
- M2 score and threshold,
- risk state,
- decision outcome,
- reason codes,
- sizing result,
- execution/fill result when applicable,
- rule-state trace for non-decisions.

The account record is the source of truth for simulated brokerage activity. It
should include:

- account id,
- balances,
- positions,
- order history,
- account actions,
- confirmation records,
- fills and cancellations.

Every inspector answer must cite the record fields or tool results it depends
on.

## 8. Simulated Account Layer

The account layer is intentionally middle scope.

Build:

- three seeded simulated accounts,
- balances and positions,
- order history,
- order lifecycle states: submitted, filled, cancelled, rejected,
- confirmation before simulated order placement,
- append-only account action records,
- tool-layer authorization checks.

Do not build:

- order book,
- matching engine,
- market participants,
- live broker integration,
- contact/profile changes,
- margin or options behavior.

Orders fill through the existing execution simulator. This gives enough
state-changing surface to evaluate confirmation and authorization without
spending the project on exchange mechanics.

## 9. Inspector Evaluation

The evaluation suite has about 200 questions:

| Tier | Count | Meaning |
|---|---:|---|
| Tier 1 | 80 | Answerable from one record |
| Tier 2 | 60 | Requires aggregation across records |
| Tier 3 | 60 | Unsupported by the available records and should be refused |

Build the first 60-case subset as 30 / 15 / 15 before expanding.

Questions are **generated compositionally, not hand-authored**, following the
tau2-bench pattern: initialization functions set the record state, solution
functions produce the answer using only reads a real tool could perform, and
assertion functions state what must hold. Correctness is verified mechanically
against record fields, deterministic aggregates, required citations and
prohibited claims, so the set is checkable rather than reviewed. Tier 3 falls out
as the case with no solution path, which makes unanswerability a property of the
declared record and tool boundary rather than our judgment. Hand-authoring is
reserved for cases the generator cannot express. `PROJECT_BETA_PRD.md` §9 carries
the mechanics.

**Grading is mechanical first.** Deterministic checks decide correctness; an LLM
or rubric judge scores residual prose quality only and is never the source of
truth. We report how much of the suite was graded mechanically against how much
was judged.

**The harness takes a pluggable answerer and keeps retrieval separable from
generation** (`DECISIONS.md` #26 and #27), so every system runs the same code
path and the Oracle-record, Default and No-record ablations run without a
refactor. Those three separate retrieval failure from grounding failure from
refusal miscalibration.

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
- median audit time.

Faithfulness should be reported beside block rate. If the grounding filter blocks
unsupported answers, 100% released-answer faithfulness is partly a property of
the filter; block rate shows how often unsupported content was attempted.

Refusal and false-refusal must be reported together. A system can improve
correct refusal by refusing too much, so the tradeoff matters more than either
single number.

## 10. Evaluation Baselines

Use `E` names for inspector baselines so they do not collide with the trading
systems `B1` and `B2`.

| Name | Baseline | Purpose |
|---|---|---|
| E0 | Deterministic template | Does the LLM add value beyond structured reporting? |
| E1 | Naive Claude | Chris's requested baseline: general model without Project Beta grounding |
| E2 | No-policy ablation | Does explicit policy grounding improve refusal and compliance? |
| E3 | Open-weight model | Are results architecture-dependent or provider-dependent? |
| Oracle | Deterministic upper bound | Reads directly from records; not a competitor |

`E0`, `E1`, `E2` and `Oracle` are core and are measured. `E3` is planned if
schedule allows and is cuttable before core inspector delivery is threatened; it
sits at item 5 of the cut ladder in §14, and cutting it costs no harness change.

Trading-system names remain unchanged:

- B1 = buy and hold.
- B2 = momentum breakout plus risk layer.
- M1 = B2 plus regime classifier.
- M2 = M1 plus signal-quality model.

## 11. Red Team

Red-team tests should check whether the agent can be pushed into:

- answering from another account,
- placing an order without confirmation,
- bypassing account authorization,
- giving investment advice,
- ranking strategies,
- inventing unsupported market facts,
- following injected instructions in user text or stored records,
- contradicting cited evidence.

For state-changing actions, confirmation-before-order is a contribution worth
claiming because existing benchmarks often score final task success without
checking whether required confirmation happened before the write.

## 12. Milestones

| Week | Focus | Output |
|---|---|---|
| 3 | Proposal and first inspector path | Rev 3 proposal, single-record inspector prototype |
| 4 | Records and tools | Rule-state trace, read-only MCP-style tools, first 60 questions |
| 5 | Account layer | Seeded accounts, balances, positions, order history |
| 6 | Refusal and baseline | Policy document, E1 baseline, measured cost per case |
| 7 | Tier 2 | Aggregations, shadow outcomes for rejected candidates |
| 8 | Full evaluation set | 200 questions, grading harness, first red-team pass |
| 9 | Alpha | End-to-end inspector over account and decision records |
| 10 | State-changing tools | Simulated order placement with confirmation and authorization tests |
| 11 | Human audit | 60-second audit with three unfamiliar readers |
| 12 | Release candidate | Cost/latency report, model/system cards, reproducibility check |
| 13 | Polish | Demo script, final report structure, cleanup |
| 14 | Ship | Final report, demo video, presentation |

## 13. Work Breakdown And Ownership

Two-person team: Henry Dao and Jacky Au-Yeung. The exact split has **not** been
agreed with Jacky yet. The table below is a proposed working split for
discussion, not a commitment.

| Stream | Contents | Proposed owner |
|---|---|---|
| Explanation and agent layer | Inspector, refusal path, grounding, MCP/agent integration | Henry |
| Evidence layer | Decision records, rule-state traces, shadow outcomes, provenance | Jacky |
| Tier 2 retrieval and aggregation | Aggregate scripts, answer keys, evidence manifest inputs | Jacky |
| Simulated account layer | Accounts, balances, positions, order history, confirmation records | Jacky |
| Evaluation set | 200 questions, tier labels, answer keys, false-refusal checks | Shared |
| Red team and audit | Cross-account probes, advice elicitation, confirmation-bypass tests, human audit | Shared |
| Cost and latency | Model-call cost, retrieval latency, tool latency, harness runtime | Shared |
| Docs and demo | README, cards, architecture diagram, demo video, final report | Shared |

Discussion point for Jacky: the clean split may be that Jacky takes the evidence
and account-data layer while Henry takes the inspector and agent layer. If Jacky
prefers a different area or has less capacity, the project should adjust before
work is assigned.

## 14. Cut Ladder

If schedule tightens, cut in this order:

1. Plain-English policy-to-rule-code stretch goal.
2. Simulated order placement; keep read-only account inspection.
3. Multiple accounts; keep one account and remove cross-account tests.
4. Open-ended tier-2 aggregation; keep five fixed precomputed aggregates.
5. E3 open-weight baseline.

The floor is still a complete capstone: inspector, 200-question evaluation,
grounding/refusal metrics, and red-team tests.

## 15. Safety And Publication Rules

- Paper trading only.
- No live-money code path.
- No market data committed beyond bounded fixtures.
- No credentials committed.
- No full decision logs committed if they reconstruct licensed market data.
- The agent refuses investment advice and strategy ranking.
- The model cannot widen its own account permissions.
- User text and stored text are treated as data, not instructions.

## 16. Jacky Discussion Checklist

Before treating ownership as settled, discuss:

1. Which stream Jacky wants to own.
2. How many hours per week he can realistically give.
3. Whether he is comfortable with Python, pandas, tests, branches, and pull
   requests.
4. Whether he wants portfolio depth, finance learning, or a contained build
   task.
5. How to make both contributions visible in issues, commits, tests, and PR
   review.
