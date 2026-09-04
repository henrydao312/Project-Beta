# Contributing to PROJECT BETA

Thanks for your interest. This is an academic capstone project, so the primary
audience is reviewers and anyone reproducing the results - but the setup below
works for contributors too.

## Setup

```bash
git clone <repo-url> && cd project-beta
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests

```bash
pytest # full suite; should be green before any push
ruff check . # lint
```

Tests must pass before a pull request is opened. If a test fails, fix the cause
 - **never disable or weaken a test to get a green check.** The guardrail tests
in `tests/test_guardrails.py` enforce commitments made in the project's safety
and licensing documents; a failure there means a promise was broken, not that
the test is inconvenient.

## Getting data

Market data is **not** in this repository and cannot be redistributed - see the
README's data section. You will need your own Alpaca API keys:

```bash
cp .env.example .env # .env is gitignored
chmod 600 .env
source .env
```

Use **paper** keys (the key ID begins with `PK`). There is no live-money code
path in this project and there should never be one.

## Pull request process

1. Branch: `git checkout -b feature/short-description`
2. Make the change, with a test that would fail without it
3. Run `pytest` and `ruff check .`
4. Commit and push, then open a pull request describing what changed and why
5. CI must be green

## Things that will be rejected

- **Committed market data or credentials.** Both are caught by tests, but please
  don't rely on that.
- **Full-history decision logs.** Only bounded sample logs belong in the repo;
  a complete log approximates a redistributable price series.
- **AI in the trade decision path.** The separation between "AI classifies and
  explains" and "deterministic logic decides" is the point of this project, not
  an implementation detail.
- **A weakened grounding rule.** The explanation service may reference only
  fields present in the decision log. Features that would require it to
  speculate - counterfactuals, for instance - are out of scope by design.

## AI-assisted contributions

AI assistance is welcome and used in this project. Please note in the pull
request which parts were AI-assisted, and satisfy yourself that the code is
correct before submitting it - you own what you ship regardless of what wrote
it.

## Questions

Open an issue.
