"""Tests for the grounding checker — including deliberate hallucinations.

A grounding checker that only sees correct explanations is worthless. Most of
these tests feed it fabricated claims and assert it catches them.

The explanation service doesn't exist yet. Building the guardrail first means it
is waiting for the feature rather than trailing it — and the synthetic cases
below are a specification of what the service may and may not say.
"""

from __future__ import annotations

import pytest

from project_beta.grounding import (
    GroundingError,
    check_explanation,
    enforce_grounding,
    record_labels,
    record_numbers,
)

RECORD = {
    "decision_id": "d-1",
    "trade_id": "t-1",
    "mode": "backtest",
    "feed": "sip",
    "regime": {
        "label": "uptrend",
        "probs": {"uptrend": 0.72, "downtrend": 0.08, "choppy": 0.20},
        "vol_flag": "low",
        "model_version": "regime_xgb_v0.4",
    },
    "signal_quality": {"p_profit": 0.64, "p_target_before_stop": 0.58},
    "decision": "approved",
    "decision_reason_codes": ["REGIME_PERMITS", "SQ_ABOVE_THRESHOLD"],
    "risk": {"position_size": 100, "active_constraints": [], "drawdown_state": 0.031},
    "execution": {"fill_price": 552.35, "slippage_bps": 0.7},
}


# ------------------------------------------------------------------ extraction


def test_record_numbers_reaches_nested_values() -> None:
    numbers = record_numbers(RECORD)
    assert 0.72 in numbers  # regime.probs.uptrend
    assert 552.35 in numbers  # execution.fill_price
    assert 0.031 in numbers  # risk.drawdown_state


def test_record_labels_collects_states_and_reason_codes() -> None:
    labels = record_labels(RECORD)
    assert "uptrend" in labels
    assert "approved" in labels
    assert "low" in labels
    assert "regime_permits" in labels
    assert "downtrend" not in labels  # a probability key, not an asserted state


# ------------------------------------------------------------- grounded cases


def test_a_faithful_explanation_passes() -> None:
    text = (
        "Approved — uptrend regime (72%), signal quality 0.64, "
        "no active risk constraints. Filled at 552.35."
    )
    report = check_explanation(text, RECORD)
    assert report.grounded, report.summary()
    assert report.checked_numbers >= 3


def test_probability_rendered_as_a_percentage_is_accepted() -> None:
    """0.72 in the record and "72%" in the prose are the same claim."""
    assert check_explanation("Uptrend at 72%.", RECORD).grounded


def test_rounding_to_displayed_precision_is_accepted() -> None:
    """3.1% is a fair rendering of drawdown_state 0.031."""
    assert check_explanation("Drawdown is 3.1%.", RECORD).grounded


def test_summary_reports_what_was_checked() -> None:
    report = check_explanation("Uptrend at 72%, quality 0.64.", RECORD)
    assert "GROUNDED" in report.summary()


# --------------------------------------------------------- hallucination cases


def test_a_fabricated_price_is_caught() -> None:
    """The model invents a fill price that never happened."""
    report = check_explanation("Approved — filled at 561.90.", RECORD)
    assert not report.grounded
    assert "561.90" in report.ungrounded_numbers


def test_a_wrong_regime_label_is_caught() -> None:
    """The record says uptrend; the explanation says choppy."""
    report = check_explanation("Rejected — choppy regime.", RECORD)
    assert not report.grounded
    assert "choppy" in report.ungrounded_labels


def test_a_wrong_decision_label_is_caught() -> None:
    report = check_explanation("This trade was rejected.", RECORD)
    assert not report.grounded
    assert "rejected" in report.ungrounded_labels


def test_a_plausible_but_invented_confidence_is_caught() -> None:
    """The dangerous case: a number in the right shape and the right place,
    which simply isn't what the model computed."""
    report = check_explanation("Signal quality 0.81 cleared the threshold.", RECORD)
    assert not report.grounded
    assert "0.81" in report.ungrounded_numbers


def test_multiple_hallucinations_are_all_reported() -> None:
    report = check_explanation("Choppy regime at 45%, filled at 600.00.", RECORD)
    assert not report.grounded
    assert len(report.ungrounded_numbers) == 2
    assert "choppy" in report.ungrounded_labels
    assert "UNGROUNDED" in report.summary()


# --------------------------------------------------------------- output filter


def test_enforce_grounding_returns_a_faithful_explanation() -> None:
    text = "Approved — uptrend regime (72%), signal quality 0.64."
    assert enforce_grounding(text, RECORD) == text


def test_enforce_grounding_blocks_a_hallucination() -> None:
    """This is the guardrail that matters: a bad explanation must not reach a
    user or a stored record. By the time a human reads it, over-trust has
    already had its chance."""
    with pytest.raises(GroundingError, match="UNGROUNDED"):
        enforce_grounding("Uptrend at 99%.", RECORD)


# ------------------------------------------------------------- knobs and edges


def test_small_integer_suppression_is_off_by_default() -> None:
    """A check that quietly ignores things is how a guardrail rots. Ordinary
    counting language is flagged unless suppression is turned on deliberately."""
    strict = check_explanation("Three filters agreed.", RECORD)
    relaxed = check_explanation("Three filters agreed.", RECORD, ignore_small_integers=True)
    assert relaxed.grounded
    # "Three" is a word, not a numeral, so nothing is flagged either way here —
    # the meaningful case is numerals:
    assert not check_explanation("2 filters agreed.", RECORD).grounded
    assert check_explanation("2 filters agreed.", RECORD, ignore_small_integers=True).grounded
    assert strict.grounded  # no numerals present


def test_unverifiable_prose_is_not_flagged() -> None:
    """The checker handles the mechanical part. Judging whether "a solid setup"
    is a fair characterisation is a human's job, and the audit should say so
    rather than pretending this tool settled it."""
    report = check_explanation("The setup looked solid and the entry was clean.", RECORD)
    assert report.grounded
    assert report.checked_numbers == 0


def test_booleans_are_not_treated_as_numeric_claims() -> None:
    record = {"decision": "approved", "auto_halt_enabled": True}
    assert check_explanation("Approved.", record).grounded


# ------------------------------------------------------------------- canary


CANARY_RECORD = dict(RECORD)
CANARY_EXPECTED_VALUES = ["72", "0.64", "uptrend", "approved"]


@pytest.mark.canary
def test_canary_explanation_still_mentions_the_key_state() -> None:
    """Drift detector for the live explanation service.

    The model version is pinned, but a provider can change behaviour behind a
    pinned name, or deprecate it mid-semester. Explanations would degrade with
    nothing failing. Once the service exists, replace the stub below with a real
    call and this test catches drift on the next CI run.
    """
    pytest.skip("enable once the explanation service exists (PRD §5.11)")

    # generated = explanation_service.explain(CANARY_RECORD)   # noqa: ERA001
    # assert enforce_grounding(generated, CANARY_RECORD)       # noqa: ERA001
    # for value in CANARY_EXPECTED_VALUES:                     # noqa: ERA001
    #     assert value in generated.lower()                    # noqa: ERA001
