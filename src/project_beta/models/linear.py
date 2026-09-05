"""Regularised logistic regression, multinomial and binary. The documented baseline.

Outline §5.1 specifies "logistic regression (baseline), random forest, XGBoost".
This is that baseline, written out rather than imported, for three reasons that
are worth stating because the obvious move is `pip install scikit-learn`:

  - **It is exactly reproducible.** Full-batch gradient descent with a fixed
    iteration count and a fixed initialisation produces the same weights on any
    machine, in any version, forever. Every published number in this project
    has to be reproducible from a config hash, and a solver whose default
    changes between library versions quietly breaks that.
  - **It has no hidden preprocessing.** Standardisation happens here, on the
    training window only, and the test asserting that is the difference between
    a walk-forward result and a leaked one. Library conveniences that fit a
    scaler on everything you hand them are the usual way this goes wrong.
  - **It keeps the dependency surface honest.** A tree ensemble is a genuine
    upgrade and belongs behind the same interface; a linear baseline is sixty
    lines and a dependency is forever.

`Classifier` is the interface the ladder's models use. Adding an XGBoost
backend later means implementing `fit` and `predict_proba`, and nothing else in
the project changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

import numpy as np


class Classifier(Protocol):
    classes_: list
    def fit(self, X: np.ndarray, y: Sequence) -> "Classifier": ...
    def predict_proba(self, X: np.ndarray) -> np.ndarray: ...


@dataclass
class StandardScaler:
    """Mean and scale, fitted on the training window and never refitted.

    This tiny class exists to make one leakage route impossible to take by
    accident. Fitting a scaler on train and test together leaks the test
    window's location and spread into every training row - a leak that improves
    results, leaves no trace, and is the single most common defect in
    walk-forward code.
    """

    mean: np.ndarray | None = None
    scale: np.ndarray | None = None

    def fit(self, X: np.ndarray) -> "StandardScaler":
        X = np.asarray(X, dtype=float)
        self.mean = X.mean(axis=0)
        sd = X.std(axis=0)
        # A constant column carries no information; dividing by its zero spread
        # would produce NaN and poison every weight update after it.
        self.scale = np.where(sd > 1e-12, sd, 1.0)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.mean is None or self.scale is None:
            raise RuntimeError("scaler used before fit")
        return (np.asarray(X, dtype=float) - self.mean) / self.scale


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


class LogisticRegression:
    """Multinomial (or binary) logistic regression with L2, by gradient descent.

    Deterministic by construction: zero initialisation, full-batch updates, a
    fixed step count. No seed is needed because nothing is drawn.
    """

    def __init__(
        self,
        *,
        l2: float = 1.0,
        learning_rate: float = 0.5,
        max_iter: int = 400,
        tol: float = 1e-7,
    ) -> None:
        self.l2 = l2
        self.learning_rate = learning_rate
        self.max_iter = max_iter
        self.tol = tol
        self.classes_: list = []
        self.weights_: np.ndarray | None = None
        self.bias_: np.ndarray | None = None
        self.scaler = StandardScaler()
        self.n_iter_ = 0

    def fit(self, X: np.ndarray, y: Sequence) -> "LogisticRegression":
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[0] == 0:
            raise ValueError("fit needs a non-empty 2-D feature matrix")
        if len(y) != X.shape[0]:
            raise ValueError(f"{len(y)} labels for {X.shape[0]} rows")

        self.classes_ = sorted(set(y), key=str)
        if len(self.classes_) < 2:
            # One class in the training window is a real and reportable state -
            # a fold that saw only one regime. Predicting it with certainty is
            # the honest answer, and it is better than a crash mid-fold.
            self.weights_ = np.zeros((X.shape[1], 1))
            self.bias_ = np.zeros(1)
            self.scaler.fit(X)
            return self

        index = {c: i for i, c in enumerate(self.classes_)}
        Y = np.zeros((X.shape[0], len(self.classes_)))
        for row, label in enumerate(y):
            Y[row, index[label]] = 1.0

        Z = self.scaler.fit(X).transform(X)
        n, d = Z.shape
        k = len(self.classes_)
        W = np.zeros((d, k))
        b = np.zeros(k)

        previous = np.inf
        for step in range(self.max_iter):
            P = _softmax(Z @ W + b)
            error = P - Y
            grad_w = Z.T @ error / n + self.l2 * W / n
            grad_b = error.mean(axis=0)
            W -= self.learning_rate * grad_w
            b -= self.learning_rate * grad_b
            loss = -np.log(np.clip((P * Y).sum(axis=1), 1e-12, None)).mean()
            self.n_iter_ = step + 1
            if abs(previous - loss) < self.tol:
                break
            previous = loss

        self.weights_, self.bias_ = W, b
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.weights_ is None or self.bias_ is None:
            raise RuntimeError("predict_proba used before fit")
        if len(self.classes_) < 2:
            return np.ones((len(X), 1))
        Z = self.scaler.transform(X)
        return _softmax(Z @ self.weights_ + self.bias_)

    def predict(self, X: np.ndarray) -> list:
        proba = self.predict_proba(X)
        return [self.classes_[i] for i in proba.argmax(axis=1)]

    def proba_dict(self, X: np.ndarray) -> list[dict]:
        """Probabilities keyed by class name, as the DecisionRecord carries them.

        PRD §4.2 flags a subtlety the grounding checker depends on: this dict
        contains every class *name* as a key, but the record only asserts the
        one in `label`. Keys are not claims; values are.
        """
        proba = self.predict_proba(X)
        return [
            {c: float(row[i]) for i, c in enumerate(self.classes_)} for row in proba
        ]
