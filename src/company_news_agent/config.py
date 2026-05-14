from __future__ import annotations

from pathlib import Path

from .types import Company


COMPANIES: tuple[Company, ...] = (
    Company(
        name="Alphabet / Google",
        ticker="GOOG",
        aliases=("Google", "Alphabet"),
        icon="🔎",
    ),
    Company(
        name="Amazon",
        ticker="AMZN",
        aliases=("Amazon.com",),
        icon="📦",
    ),
    Company(
        name="Apple",
        ticker="AAPL",
        aliases=("Apple Inc",),
        icon="🍎",
    ),
    Company(
        name="Robinhood",
        ticker="HOOD",
        aliases=("Robinhood Markets", "Robinhood Markets Inc"),
        icon="🏹",
    ),
)

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
