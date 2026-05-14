from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from difflib import SequenceMatcher
import json
import os
import re

from .types import Company, CompanyReport, NewsCluster, NewsItem


TRANSLATION_BATCH_SIZE = 20
CLUSTER_BATCH_SIZE = 30


class NewsSynthesizer:
    def __init__(self, model: str | None = None, target_dates: set[date] | None = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.target_dates = target_dates
        self._client = self._build_client()

    def synthesize(self, company: Company, items: list[NewsItem]) -> CompanyReport:
        if not items:
            return CompanyReport(
                company=company,
                overview="未找到该公司近期与股票相关的新闻。",
                stock_relevance="没有可用于分析的新闻来源。",
                key_points=(),
                news=(),
            )

        if self._client is None:
            return self._fallback_report(company, items)

        translated_items = self.translate_items(items)
        news_clusters = self.cluster_items(translated_items)
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a financial news analyst. Summarize only the supplied "
                        "news items. Do not invent facts. Return valid JSON with keys "
                        "overview, stock_relevance, and key_points. Keep overview and "
                        "stock_relevance concise."
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_prompt(company, news_clusters),
                },
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        key_points = data.get("key_points", [])
        if isinstance(key_points, str):
            key_points = [key_points]

        return CompanyReport(
            company=company,
            overview=str(data.get("overview", "")).strip(),
            stock_relevance=str(data.get("stock_relevance", "")).strip(),
            key_points=tuple(str(point).strip() for point in key_points if str(point).strip()),
            news=tuple(news_clusters),
        )

    def translate_items(self, items: list[NewsItem]) -> list[NewsItem]:
        if self._client is None:
            return items

        translated_items: list[NewsItem] = []
        total_filtered = 0
        batches = _chunks(items, TRANSLATION_BATCH_SIZE)
        for batch_index, batch in enumerate(batches, start=1):
            translated_batch, filtered_count = self._translate_items_batch(batch)
            translated_items.extend(translated_batch)
            total_filtered += filtered_count
        print(
            f"LLM 日期/公司事件筛选后：{len(translated_items)} 条新闻来源",
            flush=True,
        )
        return translated_items

    def _translate_items_batch(self, items: list[NewsItem]) -> tuple[list[NewsItem], int]:
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You translate financial news metadata into Simplified Chinese. "
                        "Also write a useful Chinese summary for each news item. "
                        "You also filter for concrete company events only. "
                        "Preserve company names, tickers, numbers, and URLs exactly. "
                        "Return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_translation_prompt(items),
                },
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        translated = data.get("items", [])
        by_index = {
            int(item.get("index")): item
            for item in translated
            if isinstance(item, dict) and str(item.get("index", "")).isdigit()
        }

        translated_items_batch: list[NewsItem] = []
        filtered_count = 0
        for index, item in enumerate(items, start=1):
            result = by_index.get(index, {})
            if result and not _as_bool(result.get("keep"), default=True):
                filtered_count += 1
                continue
            translated_items_batch.append(
                replace(
                    item,
                    title_zh=str(result.get("title_zh") or "").strip() or None,
                    summary_zh=_limit_sentences(str(result.get("summary_zh") or "").strip(), 10) or None,
                )
            )
        return translated_items_batch, filtered_count

    def cluster_items(self, items: list[NewsItem]) -> list[NewsCluster]:
        if self._client is None:
            return _heuristic_clusters(items)

        if len(items) <= CLUSTER_BATCH_SIZE:
            clusters = self._cluster_items_batch(items)
            print(f"LLM 同事件整合后：{len(clusters)} 条整合新闻", flush=True)
            return clusters

        clusters: list[NewsCluster] = []
        batches = _chunks(items, CLUSTER_BATCH_SIZE)
        for batch_index, batch in enumerate(batches, start=1):
            batch_clusters = self._cluster_items_batch(batch)
            clusters.extend(batch_clusters)
        merged_clusters = _merge_similar_clusters(clusters)
        print(
            f"LLM 同事件整合后：{len(merged_clusters)} 条整合新闻",
            flush=True,
        )
        return merged_clusters

    def _cluster_items_batch(self, items: list[NewsItem]) -> list[NewsCluster]:
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You group news items that report the same underlying event. "
                        "Return valid JSON only. Do not drop any item indexes."
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_clustering_prompt(items),
                },
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        groups = data.get("groups", [])
        clusters: list[NewsCluster] = []
        used_indexes: set[int] = set()

        for group in groups:
            if not isinstance(group, dict):
                continue
            indexes = _parse_indexes(group.get("item_indexes"))
            grouped_items = tuple(
                items[index - 1]
                for index in indexes
                if 1 <= index <= len(items) and index not in used_indexes
            )
            if not grouped_items:
                continue
            used_indexes.update(indexes)
            title = str(group.get("title_zh") or grouped_items[0].title_zh or grouped_items[0].title).strip()
            summary = str(group.get("summary_zh") or grouped_items[0].summary_zh or "").strip()
            clusters.append(
                NewsCluster(
                    title_zh=title,
                    summary_zh=_limit_sentences(summary, 10) or "该新闻主题暂无可用总结。",
                    items=_dedupe_cluster_items_by_source(grouped_items),
                )
            )

        for index, item in enumerate(items, start=1):
            if index not in used_indexes:
                clusters.append(
                    NewsCluster(
                        title_zh=item.title_zh or item.title,
                        summary_zh=_limit_sentences(item.summary_zh or "", 10) or "该新闻主题暂无可用总结。",
                        items=(item,),
                    )
                )

        return clusters

    @staticmethod
    def _build_prompt(company: Company, clusters: list[NewsCluster]) -> str:
        lines = [
            f"Company: {company.name}",
            f"Ticker: {company.ticker}",
            "",
            "Deduplicated news topics:",
        ]
        for index, cluster in enumerate(clusters, start=1):
            sources = ", ".join(item.source for item in cluster.items)
            lines.extend(
                [
                    f"{index}. Topic: {cluster.title_zh}",
                    f"   Summary: {cluster.summary_zh}",
                    f"   Reported by: {sources}",
                ]
            )
        lines.append("")
        lines.append(
            "Write Chinese output. Be specific about the business, financial, regulatory, "
            "competitive, or market implications for the stock. Mention uncertainty when "
            "the supplied news does not provide enough evidence."
        )
        return "\n".join(lines)

    def _build_translation_prompt(self, items: list[NewsItem]) -> str:
        payload = {
            "items": [
                {
                    "index": index,
                    "title": item.title,
                    "summary": item.summary or "",
                    "source": item.source,
                    "published_at": item.published_at.isoformat() if item.published_at else "",
                    "url": item.url,
                }
                for index, item in enumerate(items, start=1)
            ]
        }
        return (
            "Translate every news title into Simplified Chinese. For summary_zh, write "
            "2-3 Chinese sentences, never more than 10 sentences. Cover: what happened, the main company/business line "
            "or stakeholder involved, why it may matter to the stock, and any uncertainty "
            "or limitation in the supplied item. If the original summary is empty or low "
            "quality, infer cautiously from the title and do not invent specific facts. "
            "If there is a lot of information, keep only the most important points. "
            f"{self._date_filter_instruction(items)} "
            f"{self._company_event_filter_instruction()} "
            "Return JSON in this exact shape: "
            '{"items":[{"index":1,"keep":true,"filter_reason":"","title_zh":"...","summary_zh":"..."}]}\n\n'
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

    def _date_filter_instruction(self, items: list[NewsItem]) -> str:
        if not items:
            return ""
        dates = sorted(date_value.isoformat() for date_value in self.target_dates or set())
        if not dates:
            return (
                "Also decide keep=true only if the item appears to describe an event in "
                "the report date window; set keep=false if it clearly describes an older "
                "or future event outside the window."
            )
        return (
            "Also decide whether to keep each item before it goes into the report. "
            f"The allowed event-date window is: {', '.join(dates)}. Set keep=true only "
            "if the news appears to describe an event happening in that window, or if "
            "the event date is not explicit but likely current. Set keep=false if the "
            "title/summary indicates the event happened outside that window, for example "
            "last week, last month, several days ago, or an explicit date outside the "
            "window. If unsure, keep=true and mention uncertainty in summary_zh."
        )

    @staticmethod
    def _company_event_filter_instruction() -> str:
        return (
            "Also set keep=true only for concrete company events. Keep news about earnings, "
            "revenue, guidance, acquisitions, partnerships, product launches, lawsuits, "
            "antitrust/regulatory actions, investigations, executive changes, layoffs, "
            "business expansion or contraction, major contracts, capital investment, "
            "or major operational events. Set keep=false for items that are only about "
            "stock price movement, market commentary, analyst ratings, price targets, "
            "technical analysis, generic stock recommendations, company culture, workplace "
            "rankings, office perks, or non-event interviews/commentary. If an employee "
            "topic is a concrete event such as layoffs, strike, union action, or lawsuit, "
            "keep=true."
        )

    @staticmethod
    def _build_clustering_prompt(items: list[NewsItem]) -> str:
        payload = {
            "items": [
                {
                    "index": index,
                    "title_zh": item.title_zh or item.title,
                    "summary_zh": item.summary_zh or "",
                    "original_title": item.title,
                    "source": item.source,
                    "published_at": item.published_at.isoformat() if item.published_at else "",
                    "url": item.url,
                }
                for index, item in enumerate(items, start=1)
            ]
        }
        return (
            "Group items that are about the same concrete news event, even if different "
            "media outlets used different wording. Do not group broad market commentary "
            "unless the underlying event is the same. For each group, write one Chinese "
            "topic title and a detailed Chinese summary of 3-5 sentences, never more than "
            "10 sentences. The summary "
            "should synthesize all grouped sources and explain: what happened, who is "
            "involved, the potential stock relevance, whether multiple outlets are "
            "confirming the same point, and what investors may need to watch next. Do not "
            "invent facts beyond the supplied titles/summaries. If there is a lot of "
            "information, keep only the most important points. Return JSON in this exact shape: "
            '{"groups":[{"title_zh":"...","summary_zh":"...","item_indexes":[1,2]}]}\n\n'
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

    @staticmethod
    def _build_client():
        if not os.getenv("OPENAI_API_KEY"):
            return None
        try:
            from openai import OpenAI
        except ImportError:
            return None
        return OpenAI(timeout=180, max_retries=1)

    @staticmethod
    def _fallback_report(company: Company, items: list[NewsItem]) -> CompanyReport:
        news_clusters = _heuristic_clusters(items)
        key_points = tuple(cluster.title_zh for cluster in news_clusters[:5])
        return CompanyReport(
            company=company,
            overview=(
                f"已找到 {len(news_clusters)} 条整合后新闻，来自 {len(items)} 条原始报道。"
            ),
            stock_relevance=(
                "由于未设置 OPENAI_API_KEY，当前未启用 LLM 翻译和整合。"
                "请先安装依赖并配置 API key，以生成完整中文报告。"
            ),
            key_points=key_points,
            news=tuple(news_clusters),
        )


def _parse_indexes(value) -> list[int]:
    if not isinstance(value, list):
        return []
    indexes: list[int] = []
    for item in value:
        try:
            indexes.append(int(item))
        except (TypeError, ValueError):
            continue
    return indexes


def _as_bool(value, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return default


def _chunks(items: list[NewsItem], size: int) -> list[list[NewsItem]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _merge_similar_clusters(clusters: list[NewsCluster]) -> list[NewsCluster]:
    merged: list[NewsCluster] = []
    for cluster in clusters:
        normalized = _normalize_title(cluster.title_zh)
        match_index = None
        for index, candidate in enumerate(merged):
            score = SequenceMatcher(None, normalized, _normalize_title(candidate.title_zh)).ratio()
            if score >= 0.82:
                match_index = index
                break

        if match_index is None:
            merged.append(cluster)
            continue

        existing = merged[match_index]
        merged[match_index] = NewsCluster(
            title_zh=existing.title_zh,
            summary_zh=_combine_summaries(existing.summary_zh, cluster.summary_zh),
            items=_dedupe_cluster_items_by_source(existing.items + cluster.items),
        )
    return merged


def _combine_summaries(first: str, second: str) -> str:
    if not second or second in first:
        return first
    if not first or first in second:
        return second
    return _limit_sentences(f"{first} {second}", 10)


def _heuristic_clusters(items: list[NewsItem]) -> list[NewsCluster]:
    clusters: list[list[NewsItem]] = []
    for item in items:
        normalized = _normalize_title(item.title)
        match: list[NewsItem] | None = None
        for cluster in clusters:
            score = SequenceMatcher(None, normalized, _normalize_title(cluster[0].title)).ratio()
            if score >= 0.72:
                match = cluster
                break
        if match is None:
            clusters.append([item])
        else:
            match.append(item)

    return [
        NewsCluster(
            title_zh=cluster[0].title_zh or cluster[0].title,
            summary_zh=_limit_sentences(cluster[0].summary_zh or "", 10) or "该新闻主题暂无可用总结。",
            items=_dedupe_cluster_items_by_source(tuple(cluster)),
        )
        for cluster in clusters
    ]


def _normalize_title(title: str) -> str:
    value = title.lower()
    value = re.sub(r"\s+-\s+[^-]+$", "", value)
    value = re.sub(r"\b(google|alphabet|amazon|apple|goog|amzn|aapl|stock|shares?)\b", "", value)
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    return " ".join(value.split())


def _limit_sentences(text: str, max_sentences: int) -> str:
    if not text:
        return ""
    sentences = re.findall(r"[^。！？!?]+[。！？!?]?", text)
    if len(sentences) <= max_sentences:
        return text
    trimmed = "".join(sentence.strip() for sentence in sentences[:max_sentences]).strip()
    return trimmed if trimmed.endswith(("。", "！", "？", ".", "!", "?")) else f"{trimmed}。"


def _dedupe_cluster_items_by_source(items: tuple[NewsItem, ...]) -> tuple[NewsItem, ...]:
    seen_sources: set[str] = set()
    deduped: list[NewsItem] = []
    for item in sorted(
        items,
        key=lambda news: news.published_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    ):
        source_key = _normalize_source(item.source)
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        deduped.append(item)
    return tuple(deduped)


def _normalize_source(source: str) -> str:
    return " ".join(source.lower().replace("&amp;", "&").split())
