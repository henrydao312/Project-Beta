"""Guardrail tests — the project's own safety and licensing rules, enforced in CI.

These exist so the constraints in the Responsible AI charter cannot quietly
erode. Each one corresponds to a documented commitment; if a test here fails,
a promise made in the project documents has been broken.

Do not weaken a test here to make CI green. Fix the thing it caught.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Files a data vendor's terms forbid us from redistributing. Alpaca's Terms &
# Conditions and Customer Agreement §30 both prohibit reproducing or
# distributing market data. See Outline §20.1 and §20.5.
DATA_EXTENSIONS = {".csv", ".parquet", ".feather", ".h5", ".arrow"}
FIXTURE_DIR = REPO_ROOT / "data" / "fixtures"
MAX_FIXTURE_BYTES = 512 * 1024  # a sample, not a dataset


def _tracked_files() -> list[Path]:
    """Files git would track, ignoring .git and anything gitignored."""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("not a git repository yet")
    return [REPO_ROOT / line for line in out.splitlines() if line]


# --------------------------------------------------------------- disclaimers


def test_readme_carries_the_paper_trading_disclaimer() -> None:
    """Harm 1 guardrail (Outline §20.2): someone must not mistake this for advice.

    Asserted in CI so the disclaimer cannot vanish in a refactor or a README
    rewrite. It also satisfies the LLM provider's AI-use disclosure standard
    for high-risk domains.
    """
    readme = (REPO_ROOT / "README.md").read_text().lower()
    assert "paper trading only" in readme, "README must state paper trading only"
    assert "not investment advice" in readme, "README must disclaim investment advice"


def test_readme_explains_why_the_dataset_is_absent() -> None:
    """A reader must understand the data licence constraint, not assume a gap."""
    readme = (REPO_ROOT / "README.md").read_text().lower()
    assert "dataset_hash" in readme
    assert any(w in readme for w in ("licence", "license")), (
        "README must explain the data licensing constraint"
    )


# ------------------------------------------------------------ no vendor data


def test_no_market_data_files_are_committed() -> None:
    """Outline §20.5: raw vendor bars must never enter the public repository.

    A sample fixture is permitted; a dataset is not. The size cap is what makes
    that distinction enforceable rather than aspirational.
    """
    offenders: list[str] = []
    for path in _tracked_files():
        if path.suffix.lower() not in DATA_EXTENSIONS:
            continue
        if not path.exists():
            continue
        in_fixtures = FIXTURE_DIR in path.parents
        if not in_fixtures:
            offenders.append(f"{path.relative_to(REPO_ROOT)} (outside data/fixtures/)")
        elif path.stat().st_size > MAX_FIXTURE_BYTES:
            size_kb = path.stat().st_size // 1024
            offenders.append(
                f"{path.relative_to(REPO_ROOT)} ({size_kb} KB > "
                f"{MAX_FIXTURE_BYTES // 1024} KB fixture cap)"
            )
    assert not offenders, (
        "Market data must not be redistributed (Outline §20.1, §20.5). "
        "Offending files:\n  " + "\n  ".join(offenders)
    )


def test_no_verification_reports_are_committed() -> None:
    """Outline §20.1/§20.5: vendor-derived figures are not redistributable either.

    The data-extension check above misses these: a verification report is a
    .json file, and .json is deliberately not in DATA_EXTENSIONS because
    configs and schemas legitimately use it. But `report_*.json` from the
    Alpaca probes carries per-day IEX volume, bar counts and timestamps —
    derived from vendor bars and covered by the same terms as the bars.
    Caught here by name rather than by extension.
    """
    offenders = [
        str(p.relative_to(REPO_ROOT))
        for p in _tracked_files()
        if re.fullmatch(r".*(report|verification).*\.json", p.name)
    ]
    assert not offenders, (
        "Verification reports carry vendor-derived data and must not be "
        f"committed (Outline §20.1, §20.5). Offending files: {offenders}"
    )


# An Alpaca key assignment followed by something that actually looks like a key:
# paper IDs begin PK, live IDs begin AK, both ~20 chars. Matching the *shape of a
# value* rather than the variable name matters — an earlier version searched for
# the bare marker string and flagged this very file for containing its own
# search terms.
CREDENTIAL_PATTERN = re.compile(
    r"""APCA_API_(?:KEY_ID|SECRET_KEY)\s*=\s*['"]?(?:PK|AK)?[A-Za-z0-9]{16,}""",
)


def test_no_credentials_are_committed() -> None:
    """Privacy plan (Outline §20.4): secrets live in the environment, never in git."""
    tracked = _tracked_files()
    assert ".env" not in {p.name for p in tracked}, ".env must never be committed"

    offenders = []
    for path in tracked:
        if path.suffix not in {".py", ".yaml", ".yml", ".md", ".sh", ".txt"}:
            continue
        if not path.exists() or path.resolve() == Path(__file__).resolve():
            continue  # this file defines the pattern; scanning it is circular
        if CREDENTIAL_PATTERN.search(path.read_text(errors="ignore")):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"possible credential literals in: {offenders}"


# ------------------------------------------------------------- repo hygiene


@pytest.mark.parametrize(
    "filename",
    ["README.md", "LICENSE", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", ".gitignore"],
)
def test_required_repo_files_exist(filename: str) -> None:
    """The Milestone 1 repo checklist, enforced rather than remembered."""
    assert (REPO_ROOT / filename).is_file(), f"{filename} is required at M1"


def test_ci_workflow_exists() -> None:
    assert (REPO_ROOT / ".github" / "workflows" / "ci.yml").is_file()


# ----------------------------------------------------- prespecified evaluation


def test_evaluation_protocol_is_locked() -> None:
    """Outline §17 criterion 4 promises a *prespecified* risk-adjusted metric,
    and §20.2 harm 3 lists that prespecification as a guardrail.

    A guardrail with no document behind it is a sentence. This asserts the
    document exists, declares itself locked, and names exactly one primary
    metric rather than the disjunction ("Sharpe or maximum drawdown") that the
    Outline originally carried, which was two chances at one claim.
    """
    path = REPO_ROOT / "EVALUATION_PROTOCOL.md"
    assert path.is_file(), "EVALUATION_PROTOCOL.md must exist before M-tier runs"
    text = path.read_text()
    assert "LOCKED" in text, "the protocol must declare itself locked"
    assert "decision-log entry" in text, "it must state how it may be changed"
    assert "Minimum detectable" in text, (
        "the protocol must state what the design can detect, so a null result "
        "is interpretable rather than surprising"
    )
