"""Feature engineering: the registry (seam 6) and its price-derived feature set.

Importing this package populates the registry. `REGISTRY` is the single source
for what exists, what was dropped and why, and what each feature needs from the
provider.
"""

from project_beta.features import core as _core  # noqa: F401  (registration)
from project_beta.features.registry import (
    PROVIDER_CAPABILITIES,
    REGISTRY,
    FeatureFrame,
    FeatureRegistry,
    FeatureSpec,
    FeatureUnavailable,
)

__all__ = [
    "PROVIDER_CAPABILITIES",
    "REGISTRY",
    "FeatureFrame",
    "FeatureRegistry",
    "FeatureSpec",
    "FeatureUnavailable",
]
