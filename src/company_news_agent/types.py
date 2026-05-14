from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Company:
    name: str
    ticker: str
    aliases: tuple[str, ...] = ()
    icon: str = "🏢"


@dataclass(frozen=True)
class NewsItem:
    company: Company
    title: str
    source: str
    url: str
    published_at: datetime | None
    summary: str | None = None
    title_zh: str | None = None
    summary_zh: str | None = None


@dataclass(frozen=True)
class NewsCluster:
    title_zh: str
    summary_zh: str
    items: tuple[NewsItem, ...]


@dataclass(frozen=True)
class CompanyReport:
    company: Company
    overview: str
    stock_relevance: str
    key_points: tuple[str, ...]
    news: tuple[NewsCluster, ...]
