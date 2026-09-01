# Fixtures

A handful of bars, for tests and for demonstrating the pipeline shape.

**This is not a dataset and must never become one.** The data provider's terms
prohibit redistributing market data (Outline §20.1, §20.5), so this directory is
capped: `tests/test_guardrails.py` fails if any file here exceeds 512 KB, or if a
data file appears anywhere else in the repository.

To obtain the real dataset, use the re-fetch script with your own API keys and
verify it against the `dataset_hash` recorded with each published result.
