# PROJECT BETA

**An AI agent that answers questions about a simulated trading account, proves every answer from the system's own records, and refuses clearly when the records cannot support one.**

> ⚠️ **Paper trading only. Not investment advice.** No real money is at risk at any point. There is no live-money code path in this repository, and a test enforces its absence.

AI Capstone (CIS 5980), Penn Engineering - Fall 2026. Two-person team: Henry Dao and Jacky Au-Yeung.

---

## What it does

Underneath the agent, a fixed, readable momentum-breakout rule proposes candidate trades on 5-minute SPY bars. Two machine-learning models judge the *context* - what market regime we're in, and how likely this particular signal is to work out - and a deterministic risk engine enforces hard limits. Every decision, and every decision declined, is written to an append-only log.

That pipeline is the substrate, not the product. **The product is the agent on top of it**: ask why a trade was sized the way it was, which rule condition failed at 10:32, whether a rejection came from the filter or the risk engine, or what an account holds. Every numeral and state label in an answer must trace to a field in a cited record before the answer is released, and questions the records cannot settle get a clean refusal rather than a plausible guess. **Whether the strategy makes money is not a success criterion.** Equities only.

**The AI never decides a trade.** It classifies and scores; a documented rule combines those into approve / reduce / delay / reject; the risk engine can override all of it. That constraint is the point of the project, not a limitation of it.

## Quick start

```bash
git clone <repo-url> && cd project-beta
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest # should be green
python -m project_beta.config configs/example_backtest.yaml # validate a run config
```

Five minutes, no API keys needed. Keys are only required once you fetch data - see below.

## Installation and usage

**Requirements:** Python 3.11+.

**Credentials.** Market data and paper trading need Alpaca API keys. Never commit them.

```bash
cp .env.example .env # then edit; .env is gitignored
chmod 600 .env
source .env
```

**Getting the data.** See the licensing note below - the dataset is deliberately not in this repository.

## Data: why the dataset isn't here

Alpaca's Terms & Conditions and Customer Agreement §30 both prohibit reproducing or redistributing market data. This repository therefore ships:

- a **small sample fixture** under `data/fixtures/` - enough to run the tests and demonstrate the pipeline,
- a **documented re-fetch script** that rebuilds the full dataset from your own Alpaca account,
- the **`dataset_hash`** for each published result, so a reproduction can be *verified* without the data ever being redistributed.

A fresh clone plus a legitimately-obtained dataset matching the recorded hash reproduces the published tables. This is a licence constraint, stated rather than worked around.

**Two feeds, deliberately.** Backtests use the SIP consolidated feed (2016-06-10 onward, ~10 years, true market volume). Live paper trading uses IEX, the only real-time feed available on the free tier. IEX carries roughly **3.16%** of consolidated volume, so all volume-derived features are scale-free by construction. Every result records which feed produced it, and results from different feeds are never compared.

## Guardrails already enforced

Two of the project's safety commitments are enforced in code from week one, before the
features they protect exist:

- **Grounding** (`src/project_beta/grounding.py`) - every number and state label in a
  generated explanation must trace to a field in its source decision record. Used as an
  output filter at generation time and as the mechanical half of the release audit.
  Prose is left to human review, deliberately.
- **Repo hygiene** (`tests/test_guardrails.py`) - no market data outside a size-capped
  fixture directory, no credentials, and the paper-trading disclaimer must be present.

## Architecture

| Layer | What's in it |
|---|---|
| **Frontend** | Local browser dashboard - decision feed, equity curve, positions, halt control, replay mode |
| **Backend** | Data pipeline · features · strategy engine · trade decision engine · risk engine + halt control · execution · decision log · evaluation harness. **Fully deterministic; no AI in the trade decision path** |
| **AI layer** | Regime classifier and signal-quality model (local, classical ML) · explanation service and failure-analysis narrative (hosted LLM, reads the decision log only) |

The load-bearing property: the AI layer's outputs enter the backend as **data, never as instructions**.

## Status

Week 1 of 14. Scope, evaluation design, licensing audit and safety plan are complete; the data architecture is verified. The pipeline is under construction. See the project documents for the full specification.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Participation is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE). Note that the licence covers **this code only** - market data obtained through it remains subject to your data provider's terms, and is not redistributable.
