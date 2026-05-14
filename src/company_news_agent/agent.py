from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import (
    COMPANIES,
    DEFAULT_DATE_WINDOW_DAYS,
    DEFAULT_HTML_OUTPUT_PATH,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MAX_ITEMS_PER_COMPANY,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_TIMEZONE,
)
from .llm import NewsSynthesizer
from .news import GoogleNewsRssClient
from .types import Company, CompanyReport


def run_agent(
    *,
    companies: tuple[Company, ...] = COMPANIES,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    html_output_path: Path = DEFAULT_HTML_OUTPUT_PATH,
    max_items: int | None = DEFAULT_MAX_ITEMS_PER_COMPANY,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    published_dates: set[date] | None = None,
    timezone_name: str = DEFAULT_TIMEZONE,
) -> tuple[Path, Path]:
    news_client = GoogleNewsRssClient()
    synthesizer = NewsSynthesizer(target_dates=published_dates)
    reports: list[CompanyReport] = []

    for company in companies:
        if published_dates:
            date_range = ", ".join(day.isoformat() for day in sorted(published_dates))
            print(
                f"Searching news for {company.name} ({company.ticker}) "
                f"published on {date_range} ({timezone_name})...",
                flush=True,
            )
        else:
            print(f"Searching news for {company.name} ({company.ticker})...", flush=True)
        items = news_client.search_company_news(
            company,
            max_items=max_items,
            lookback_days=lookback_days,
            published_dates=published_dates,
            timezone_name=timezone_name,
        )
        print(f"Found {len(items)} items for {company.ticker}.", flush=True)
        print(f"Synthesizing {company.ticker} report...", flush=True)
        reports.append(synthesizer.synthesize(company, items))
        print(f"Finished {company.ticker}.", flush=True)

    from .html_report import build_html_report
    from .pdf_report import build_pdf_report

    html_path = build_html_report(reports, html_output_path, timezone_name=timezone_name)
    pdf_path = build_pdf_report(reports, output_path, timezone_name=timezone_name)
    return html_path, pdf_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search stock-related company news, synthesize it, and generate a PDF report."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"PDF output path. Default: {DEFAULT_OUTPUT_PATH}",
    )
    parser.add_argument(
        "--html-output",
        type=Path,
        default=DEFAULT_HTML_OUTPUT_PATH,
        help=f"HTML output path. Default: {DEFAULT_HTML_OUTPUT_PATH}",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=DEFAULT_MAX_ITEMS_PER_COMPANY,
        help="Optional maximum news items to keep per company. Default: no limit.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="Lookback window in days when --all-recent is used.",
    )
    parser.add_argument(
        "--all-recent",
        action="store_true",
        help="Use --days instead of filtering to today's local date.",
    )
    parser.add_argument(
        "--today-date",
        type=_parse_date,
        default=None,
        help="Center date for the default date window in YYYY-MM-DD format. Default: current local date.",
    )
    parser.add_argument(
        "--date-window-days",
        type=int,
        default=DEFAULT_DATE_WINDOW_DAYS,
        help=(
            "Number of days before and after the center date to include. "
            "Default: 1, meaning yesterday, today, and tomorrow."
        ),
    )
    parser.add_argument(
        "--timezone",
        default=DEFAULT_TIMEZONE,
        help=f"Timezone used for today's-news filtering. Default: {DEFAULT_TIMEZONE}",
    )
    parser.add_argument(
        "--tickers",
        nargs="*",
        default=None,
        help="Optional subset of tickers, for example: --tickers GOOG AAPL",
    )
    return parser.parse_args()


def main() -> None:
    _load_env()
    args = parse_args()
    selected = _select_companies(args.tickers)
    published_dates = None
    if not args.all_recent:
        center_date = args.today_date or datetime.now(ZoneInfo(args.timezone)).date()
        published_dates = _date_window(center_date, args.date_window_days)
    html_path, pdf_path = run_agent(
        companies=selected,
        output_path=args.output,
        html_output_path=args.html_output,
        max_items=args.max_items,
        lookback_days=args.days,
        published_dates=published_dates,
        timezone_name=args.timezone,
    )
    print(f"HTML report written to: {html_path}")
    print(f"PDF report written to: {pdf_path}")


def _select_companies(tickers: list[str] | None) -> tuple[Company, ...]:
    if not tickers:
        return COMPANIES

    requested = {ticker.upper() for ticker in tickers}
    selected = tuple(company for company in COMPANIES if company.ticker.upper() in requested)
    missing = requested - {company.ticker.upper() for company in selected}
    if missing:
        raise ValueError(f"Unknown ticker(s): {', '.join(sorted(missing))}")
    return selected


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected date in YYYY-MM-DD format.") from exc


def _date_window(center_date: date, window_days: int) -> set[date]:
    if window_days < 0:
        raise ValueError("--date-window-days must be >= 0")
    return {
        center_date + timedelta(days=offset)
        for offset in range(-window_days, window_days + 1)
    }


if __name__ == "__main__":
    main()
