"""Grounding checker - machine verification that an explanation says nothing
the decision record doesn't support.

The explanation service may reference only fields present in its source
DecisionRecord (PRD §5.11). That rule is worth little if the only thing
enforcing it is a person reading fifty explanations at the end of a long week.
This module does the mechanical part - every number, every state label - and
surfaces the residue for human judgment rather than pretending to settle it.

Two uses:

1. **Output filter, at generation time.** Call `check_explanation` before an
   explanation is stored or displayed. A failure means the model asserted
   something not in the record.
2. **Release audit.** Run over a sample of ≥50 explanations; PRD §5.11 requires
   100% grounded, and treats any hallucinated claim as a release blocker.

What it deliberately does *not* do: judge prose. "The setup looked strong" is
unverifiable by this checker and is exactly the kind of claim a human should be
reading for. The tool exists to make that human's remaining job small enough to
do honestly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Numbers as they appear in prose: 552.31, 0.64, 72, 1,250.00, -180.00
_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")

# State labels the system can legitimately assert. A label outside this
# vocabulary is not necessarily wrong, but a label *inside* it that is not in
# the record is a factual error about the system's own state.
CONTROLLED_VOCABULARY = {
    "uptrend", "downtrend", "choppy",
    "low", "high",
    "approved", "reduced", "delayed", "rejected",
}

# Numbers so common in ordinary prose that flagging them produces noise rather
# than signal ("one of three filters", "the 2 open positions"). Off by default:
# a check that quietly ignores things is how a guardrail rots. Turn it on
# deliberately, and say so in the audit write-up.
SMALL_INTEGER_CEILING = 12


@dataclass
class GroundingReport:
    """The outcome of checking one explanation against one record."""

    grounded: bool
    ungrounded_numbers: list[str] = field(default_factory=list)
    ungrounded_labels: list[str] = field(default_factory=list)
    checked_numbers: int = 0
    checked_labels: int = 0

    def summary(self) -> str:
        if self.grounded:
            return (
                f"GROUNDED - {self.checked_numbers} numeric and "
                f"{self.checked_labels} label claims all trace to the record."
            )
        parts = []
        if self.ungrounded_numbers:
            parts.append(f"numbers not in record: {', '.join(self.ungrounded_numbers)}")
        if self.ungrounded_labels:
            parts.append(f"labels not in record: {', '.join(self.ungrounded_labels)}")
        return "UNGROUNDED - " + "; ".join(parts)


# ------------------------------------------------------------------ extraction


def _walk(obj: Any):
    """Yield every leaf **value** in a nested record.

    Keys are deliberately excluded. An earlier version yielded them too, which
    silently defeated the label check: `regime.probs` has keys "uptrend",
    "downtrend" and "choppy", so every regime name counted as permitted and a
    model could assert the wrong regime unchallenged. Only what the record
    *asserts* - the value of `regime.label` - is a grounded claim; the others are
    just the shape of a probability distribution.
    """
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _walk(item)
    else:
        yield obj


def record_numbers(record: dict) -> set[float]:
    """Every numeric value anywhere in the record, including nested."""
    out: set[float] = set()
    for leaf in _walk(record):
        if isinstance(leaf, bool):
            continue # bool is an int subclass; not a numeric claim
        if isinstance(leaf, (int, float)):
            out.add(float(leaf))
    return out


def record_labels(record: dict) -> set[str]:
    """Every controlled-vocabulary term the record actually contains."""
    out: set[str] = set()
    for leaf in _walk(record):
        if not isinstance(leaf, str):
            continue
        lowered = leaf.lower()
        if lowered in CONTROLLED_VOCABULARY:
            out.add(lowered)
        # Reason codes are asserted verbatim; treat them as labels too.
        if re.fullmatch(r"[A-Z][A-Z0-9_]{2,}", leaf):
            out.add(leaf.lower())
    return out


def _parse(literal: str) -> float | None:
    try:
        return float(literal.replace(",", ""))
    except ValueError:
        return None


def _decimals(literal: str) -> int:
    cleaned = literal.replace(",", "")
    return len(cleaned.split(".")[1]) if "." in cleaned else 0


def _matches(claim: float, precision: int, permitted: set[float]) -> bool:
    """Does `claim` correspond to some value in the record?

    Accepts three legitimate renderings of the same underlying value:
      * the value itself 0.64 → "0.64"
      * the value as a percentage 0.72 → "72%"
      * either, rounded to the stated precision 0.7234 → "72%" / "0.72"
    """
    for value in permitted:
        for candidate in (value, value * 100.0):
            if abs(candidate - claim) < 1e-9:
                return True
            if round(candidate, precision) == round(claim, precision):
                return True
    return False


# -------------------------------------------------------------------- checking


def check_explanation(
    explanation: str,
    record: dict,
    *,
    ignore_small_integers: bool = False,
) -> GroundingReport:
    """Verify every checkable claim in `explanation` against `record`.

    Args:
        explanation: the generated text.
        record: the DecisionRecord it was generated from.
        ignore_small_integers: skip integers at or below SMALL_INTEGER_CEILING.
            Reduces noise from ordinary counting language, at the cost of
            blinding the check to small fabricated values. Default off.

    Returns:
        A GroundingReport. `grounded` is False if anything failed to trace.
    """
    permitted_numbers = record_numbers(record)
    permitted_labels = record_labels(record)

    ungrounded_numbers: list[str] = []
    checked_numbers = 0
    for literal in _NUMBER.findall(explanation):
        value = _parse(literal)
        if value is None:
            continue
        if ignore_small_integers and value.is_integer() and abs(value) <= SMALL_INTEGER_CEILING:
            continue
        checked_numbers += 1
        if not _matches(value, _decimals(literal), permitted_numbers):
            ungrounded_numbers.append(literal)

    ungrounded_labels: list[str] = []
    checked_labels = 0
    lowered = explanation.lower()
    for term in CONTROLLED_VOCABULARY:
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            checked_labels += 1
            if term not in permitted_labels:
                ungrounded_labels.append(term)

    return GroundingReport(
        grounded=not ungrounded_numbers and not ungrounded_labels,
        ungrounded_numbers=ungrounded_numbers,
        ungrounded_labels=ungrounded_labels,
        checked_numbers=checked_numbers,
        checked_labels=checked_labels,
    )


class GroundingError(ValueError):
    """Raised by the output filter when an explanation asserts unsupported facts."""


def enforce_grounding(explanation: str, record: dict, **kwargs: Any) -> str:
    """Output filter: return the explanation, or raise if it is not grounded.

    Wrap the explanation service's return value in this. An explanation that
    fails here must never reach a user or a stored record - by the time a human
    is reading it, over-trust has already had its opportunity.
    """
    report = check_explanation(explanation, record, **kwargs)
    if not report.grounded:
        raise GroundingError(
            f"{report.summary()}\nExplanation: {explanation!r}\n"
            "See PRD §5.11 - a hallucinated claim is a release blocker."
        )
    return explanation
