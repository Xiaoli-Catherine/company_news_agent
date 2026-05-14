from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from .config import STOCK_KEYWORDS
from .types import Company, NewsItem


class GoogleNewsRssClient:
    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds

    def search_company_news(
        self,
        company: Company,
        *,
        max_items: int | None,
        lookback_days: int,
        published_dates: set[date] | None = None,
        timezone_name: str = "America/Los_Angeles",
    ) -> list[NewsItem]:
        query_lookback_days = max(1, len(published_dates)) if published_dates else lookback_days
        query = self._build_query(company, query_lookback_days)
        url = (
            "https://news.google.com/rss/search?"
            f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        )
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 CompanyNewsAgent/0.1"
                )
            },
        )

        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = response.read()

        root = ElementTree.fromstring(payload)
        items = root.findall("./channel/item")
        print(f"{company.ticker} RSS 返回后：{len(items)} 条新闻来源", flush=True)
        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
        local_timezone = ZoneInfo(timezone_name)

        with_required_fields: list[ElementTree.Element] = []
        for item in items:
            title = _text(item, "title")
            link = _text(item, "link")
            if not title or not link:
                continue
            with_required_fields.append(item)
        print(f"{company.ticker} 去掉缺失标题/链接后：{len(with_required_fields)} 条新闻来源", flush=True)

        date_filtered_items: list[ElementTree.Element] = []
        for item in with_required_fields:
            published_at = _parse_datetime(_text(item, "pubDate"))
            if published_dates and not _is_published_on_any(
                published_at,
                published_dates,
                local_timezone,
            ):
                continue
            if not published_dates and published_at and published_at < cutoff:
                continue
            date_filtered_items.append(item)
        print(f"{company.ticker} 日期筛选后：{len(date_filtered_items)} 条新闻来源", flush=True)

        event_date_filtered_items: list[ElementTree.Element] = []
        for item in date_filtered_items:
            if published_dates and _appears_to_report_event_outside_window(
                title=_text(item, "title"),
                summary=_text(item, "description"),
                published_at=_parse_datetime(_text(item, "pubDate")),
                target_dates=published_dates,
                local_timezone=local_timezone,
            ):
                continue
            event_date_filtered_items.append(item)
        print(f"{company.ticker} 事件日期筛选后：{len(event_date_filtered_items)} 条新闻来源", flush=True)

        company_event_items: list[ElementTree.Element] = []
        for item in event_date_filtered_items:
            if _appears_to_be_non_event_noise(
                title=_text(item, "title"),
                summary=_text(item, "description"),
            ):
                continue
            company_event_items.append(item)
        print(f"{company.ticker} 公司事件规则筛选后：{len(company_event_items)} 条新闻来源", flush=True)

        parsed: list[NewsItem] = []
        for item in company_event_items:
            title = _text(item, "title")
            link = _text(item, "link")
            source = _source(item)
            published_at = _parse_datetime(_text(item, "pubDate"))
            parsed.append(
                NewsItem(
                    company=company,
                    title=unescape(title),
                    source=source or "Unknown source",
                    url=link,
                    published_at=published_at,
                    summary=_text(item, "description") or None,
                )
            )

        deduped = dedupe_news(parsed)
        print(f"{company.ticker} URL/标题去重后：{len(deduped)} 条新闻来源", flush=True)
        final_items = deduped[:max_items] if max_items is not None else deduped
        if max_items is not None:
            print(f"{company.ticker} 数量限制后：{len(final_items)} 条新闻来源", flush=True)
        return final_items

    @staticmethod
    def _build_query(company: Company, lookback_days: int) -> str:
        names = " OR ".join((company.name, company.ticker, *company.aliases))
        keywords = " OR ".join(STOCK_KEYWORDS)
        return f"({names}) ({keywords}) when:{lookback_days}d"


def dedupe_news(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    deduped: list[NewsItem] = []

    for item in sorted(
        items,
        key=lambda news: news.published_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    ):
        key = item.url.split("&url=")[-1] if "&url=" in item.url else item.url
        title_key = item.title.lower().strip()
        if key in seen or title_key in seen:
            continue
        seen.add(key)
        seen.add(title_key)
        deduped.append(item)

    return deduped


def _text(item: ElementTree.Element, tag: str) -> str:
    node = item.find(tag)
    return (node.text or "").strip() if node is not None else ""


def _source(item: ElementTree.Element) -> str:
    source = item.find("source")
    return (source.text or "").strip() if source is not None else ""


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _is_published_on_any(
    published_at: datetime | None,
    target_dates: set[date],
    local_timezone: ZoneInfo,
) -> bool:
    if published_at is None:
        return False
    return published_at.astimezone(local_timezone).date() in target_dates


MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


STALE_EVENT_PATTERNS = (
    r"\blast\s+(week|month|quarter|year)\b",
    r"\bprevious\s+(week|month|quarter|year)\b",
    r"\b\d+\s+(weeks|months|years)\s+ago\b",
    r"\bearlier\s+this\s+(month|quarter|year)\b",
)

MARKET_NOISE_PATTERNS = (
    r"\bstock\s+(rises|falls|jumps|drops|slips|slides|gains|climbs|surges|sinks)\b",
    r"\bshares?\s+(rise|rises|fall|falls|jump|jumps|drop|drops|slip|slips|slide|slides|gain|gains|climb|climbs|surge|surges|sink|sinks)\b",
    r"\b(pre[- ]market|after[- ]hours)\b",
    r"\b(price target|analyst rating|buy rating|sell rating|hold rating)\b",
    r"\b(upgrade|downgrade|initiates coverage|raises target|lowers target)\b",
    r"\b(technical analysis|chart pattern|moving average|relative strength)\b",
    r"\b(why .* stock|is .* stock a buy|should you buy|best stocks?)\b",
)

CULTURE_NOISE_PATTERNS = (
    r"\b(company culture|workplace culture|office culture)\b",
    r"\b(best place to work|best places to work|great place to work)\b",
    r"\b(employee benefits|office perks|workplace ranking)\b",
    r"\b(diversity ranking|dei ranking)\b",
)

EMPLOYEE_EVENT_ALLOW_PATTERNS = (
    r"\b(layoffs?|job cuts?|union|strike|walkout|employee lawsuit|workers sue|labor complaint)\b",
)


def _appears_to_report_event_outside_window(
    *,
    title: str,
    summary: str,
    published_at: datetime | None,
    target_dates: set[date],
    local_timezone: ZoneInfo,
) -> bool:
    text = f"{unescape(title)} {unescape(summary or '')}".lower()
    if any(re.search(pattern, text) for pattern in STALE_EVENT_PATTERNS):
        return True

    event_dates = _extract_explicit_event_dates(text, published_at, local_timezone)
    if event_dates:
        return not any(event_date in target_dates for event_date in event_dates)

    return False


def _appears_to_be_non_event_noise(*, title: str, summary: str) -> bool:
    text = f"{unescape(title)} {unescape(summary or '')}".lower()
    if any(re.search(pattern, text) for pattern in EMPLOYEE_EVENT_ALLOW_PATTERNS):
        return False
    return any(re.search(pattern, text) for pattern in MARKET_NOISE_PATTERNS + CULTURE_NOISE_PATTERNS)


def _extract_explicit_event_dates(
    text: str,
    published_at: datetime | None,
    local_timezone: ZoneInfo,
) -> set[date]:
    if published_at is None:
        reference_year = datetime.now(local_timezone).year
    else:
        reference_year = published_at.astimezone(local_timezone).year

    dates: set[date] = set()
    dates.update(_extract_iso_dates(text))
    dates.update(_extract_month_name_dates(text, reference_year))
    return dates


def _extract_iso_dates(text: str) -> set[date]:
    dates: set[date] = set()
    for match in re.finditer(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text):
        year, month, day = (int(value) for value in match.groups())
        try:
            dates.add(date(year, month, day))
        except ValueError:
            continue
    return dates


def _extract_month_name_dates(text: str, reference_year: int) -> set[date]:
    dates: set[date] = set()
    month_names = "|".join(MONTHS)
    patterns = (
        rf"\b({month_names})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,\s*(20\d{{2}}))?\b",
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_names})\.?(?:,\s*(20\d{{2}}))?\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            first, second, year_value = match.groups()
            if first.isdigit():
                day = int(first)
                month = MONTHS[second]
            else:
                month = MONTHS[first]
                day = int(second)
            year = int(year_value) if year_value else reference_year
            try:
                dates.add(date(year, month, day))
            except ValueError:
                continue
    return dates
