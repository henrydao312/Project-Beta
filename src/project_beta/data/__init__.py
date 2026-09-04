"""Data layer: the vendor-agnostic provider interface, its adapters, and the
ingestion and validation pipeline that turns vendor bars into a dataset."""

from project_beta.data.pipeline import (
    IngestResult,
    SessionCoverage,
    ValidationError,
    ValidationReport,
    dataset_hash,
    filter_session,
    ingest,
    validate_bars,
)
from project_beta.data.provider import (
    Bar,
    MarketDataProvider,
    NotSupported,
    OptionContract,
    ProviderAuthError,
    Quote,
)

__all__ = [
    "Bar",
    "IngestResult",
    "MarketDataProvider",
    "NotSupported",
    "OptionContract",
    "ProviderAuthError",
    "Quote",
    "SessionCoverage",
    "ValidationError",
    "ValidationReport",
    "dataset_hash",
    "filter_session",
    "ingest",
    "validate_bars",
]
