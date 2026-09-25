from __future__ import annotations

import json
from pathlib import Path

from .types import Company


COMPANIES_PATH = Path(__file__).with_name("companies.json")


def load_companies(path: Path = COMPANIES_PATH) -> tuple[Company, ...]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Companies file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in companies file {path}: {exc}") from exc

    if not isinstance(data, list) or not data:
        raise ValueError(f"Companies file must contain a non-empty JSON list: {path}")

    companies: list[Company] = []
    seen_tickers: set[str] = set()
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Company #{index} must be a JSON object.")

        name = item.get("name")
        ticker = item.get("ticker")
        aliases = item.get("aliases", [])
        icon = item.get("icon", "🏢")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Company #{index} must have a non-empty name.")
        if not isinstance(ticker, str) or not ticker.strip():
            raise ValueError(f"Company #{index} must have a non-empty ticker.")
        if not isinstance(aliases, list) or not all(
            isinstance(alias, str) and alias.strip() for alias in aliases
        ):
            raise ValueError(f"Company #{index} aliases must be a list of non-empty strings.")
        if not isinstance(icon, str) or not icon.strip():
            raise ValueError(f"Company #{index} must have a non-empty icon.")

        normalized_ticker = ticker.strip().upper()
        if normalized_ticker in seen_tickers:
            raise ValueError(f"Duplicate company ticker: {normalized_ticker}")
        seen_tickers.add(normalized_ticker)
        companies.append(
            Company(
                name=name.strip(),
                ticker=normalized_ticker,
                aliases=tuple(alias.strip() for alias in aliases),
                icon=icon.strip(),
            )
        )

    return tuple(companies)


COMPANIES = load_companies()

STOCK_KEYWORDS: tuple[str, ...] = (
    "earnings",
    "revenue",
    "guidance",
    "acquisition",
    "lawsuit",
    "antitrust",
    "product launch",
    "partnership",
    "layoffs",
    "executive",
    "regulation",
    "investigation",
    "contract",
    "investment",
)

DEFAULT_MAX_ITEMS_PER_COMPANY = None
DEFAULT_LOOKBACK_DAYS = 3
DEFAULT_DATE_WINDOW_DAYS = 1
DEFAULT_TIMEZONE = "America/Los_Angeles"
DEFAULT_OUTPUT_PATH = Path("reports/company-stock-news.pdf")
DEFAULT_HTML_OUTPUT_PATH = Path("reports/company-stock-news.html")
