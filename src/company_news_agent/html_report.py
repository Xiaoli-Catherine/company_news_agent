from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from .types import CompanyReport, NewsCluster, NewsItem


def build_html_report(
    reports: list[CompanyReport],
    output_path: Path,
    timezone_name: str = "America/Los_Angeles",
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M %Z")
    html = "\n".join(
        [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>公司股票相关新闻报告</title>",
            f"<style>{_css()}</style>",
            "</head>",
            "<body>",
            '<main class="report">',
            '<section class="cover">',
            "<h1>公司股票相关新闻报告</h1>",
            f'<p class="meta">生成时间：{escape(generated_at)}</p>',
            '<h2>新闻数量汇总</h2>',
            '<div class="summary-grid">',
            *[_summary_card(report) for report in reports],
            "</div>",
            "</section>",
            *[_company_section(report) for report in reports],
            "</main>",
            "</body>",
            "</html>",
        ]
    )
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _summary_card(report: CompanyReport) -> str:
    raw_count = sum(len(cluster.items) for cluster in report.news)
    anchor = _company_anchor(report)
    return (
        '<article class="summary-card">'
        f'<div class="company-mark">{escape(report.company.icon)}</div>'
        f'<h3><a href="#{anchor}">{escape(report.company.name)} '
        f"<span>{escape(report.company.ticker)}</span></a></h3>"
        f"<p>{len(report.news)} 条整合新闻，{raw_count} 条原始报道</p>"
        "</article>"
    )


def _company_section(report: CompanyReport) -> str:
    clusters = "\n".join(
        _cluster_block(index, cluster)
        for index, cluster in enumerate(report.news, start=1)
    )
    key_points = ""
    if report.key_points:
        points = "\n".join(f"<li>{escape(point)}</li>" for point in report.key_points)
        key_points = f"<h3>关键要点</h3><ul>{points}</ul>"

    return (
        f'<section class="company page-break" id="{_company_anchor(report)}">'
        '<header class="company-header">'
        f'<div class="company-emoji">{escape(report.company.icon)}</div>'
        "<div>"
        f"<h2>{escape(report.company.name)} <span>{escape(report.company.ticker)}</span></h2>"
        "</div>"
        "</header>"
        "<h3>新闻概况</h3>"
        f"<p>{escape(report.overview)}</p>"
        "<h3>股票相关性</h3>"
        f"<p>{escape(report.stock_relevance)}</p>"
        f"{key_points}"
        "<h3>整合新闻与报道媒体</h3>"
        f"{clusters}"
        "</section>"
    )


def _cluster_block(index: int, cluster: NewsCluster) -> str:
    sources = "\n".join(
        _source_block(source_index, item)
        for source_index, item in enumerate(cluster.items, start=1)
    )
    return (
        '<article class="news-cluster">'
        '<div class="cluster-title">'
        f"<h4>{index}. {escape(cluster.title_zh)}</h4>"
        "</div>"
        f'<p class="cluster-summary">新闻总结：{escape(cluster.summary_zh)}</p>'
        f'<p class="source-count">报道媒体：{len(cluster.items)} 家/条</p>'
        f'<div class="sources">{sources}</div>'
        "</article>"
    )


def _source_block(index: int, item: NewsItem) -> str:
    date = item.published_at.strftime("%Y-%m-%d %H:%M UTC") if item.published_at else "Unknown date"
    return (
        '<div class="source-item">'
        f'<p><strong>{index}. {escape(item.source)}</strong> | {escape(date)}</p>'
        f'<p><a href="{escape(item.url)}">{escape(item.url)}</a></p>'
        f'<p class="original-title">原文标题：{escape(item.title)}</p>'
        "</div>"
    )


def _company_anchor(report: CompanyReport) -> str:
    return f"company-{escape(report.company.ticker.lower())}"


def _css() -> str:
    return """
@page {
  size: Letter;
  margin: 0.55in;
}
* {
  box-sizing: border-box;
}
body {
  margin: 0;
  color: #202124;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Hiragino Sans GB", "Microsoft YaHei", "Apple Color Emoji",
    "Segoe UI Emoji", sans-serif;
  font-size: 13px;
  line-height: 1.5;
  background: #fff;
}
.report {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
}
h1, h2, h3, h4, p {
  margin-top: 0;
}
h1 {
  font-size: 28px;
  margin-bottom: 6px;
}
h2 {
  font-size: 22px;
  margin-bottom: 10px;
}
h2 span, h3 span {
  color: #5f6368;
  font-weight: 600;
}
h3 {
  font-size: 15px;
  margin: 18px 0 6px;
}
h4 {
  font-size: 14px;
  margin: 0;
}
.meta, .source-count, .original-title {
  color: #5f6368;
}
.cover {
  margin-bottom: 24px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.summary-card {
  border: 1px solid #dadce0;
  border-radius: 8px;
  padding: 10px;
}
.company-mark, .company-emoji {
  font-size: 24px;
}
.summary-card h3 {
  margin: 4px 0;
}
.page-break {
  break-before: page;
  page-break-before: always;
}
.company-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.company {
  border-top: 1px solid #dadce0;
  padding-top: 18px;
  margin-top: 18px;
}
.company-header h2 {
  margin: 0;
}
.news-cluster {
  border-top: 1px solid #dadce0;
  padding-top: 10px;
  margin-top: 12px;
  break-inside: avoid;
  page-break-inside: avoid;
}
.cluster-title {
  display: block;
}
.cluster-title h4 {
  display: inline;
}
.cluster-summary {
  margin: 6px 0;
}
.sources {
  margin-top: 4px;
}
.source-item {
  margin: 6px 0 8px 18px;
  break-inside: avoid;
  page-break-inside: avoid;
}
.source-item p {
  margin-bottom: 2px;
}
a {
  color: #1a73e8;
  text-decoration: none;
  word-break: break-all;
  overflow-wrap: anywhere;
}
.summary-card h3 a {
  color: inherit;
}
.summary-card h3 a:hover {
  text-decoration: underline;
}
ul {
  margin-top: 4px;
  padding-left: 18px;
}
@media print {
  html, body {
    width: 100%;
  }
  .report {
    max-width: none;
  }
  .cover {
    break-after: page;
    page-break-after: always;
  }
  .summary-grid {
    display: block;
  }
  .summary-card {
    display: block;
    margin-bottom: 8px;
    border: 1px solid #dadce0;
  }
  .company-header {
    display: block;
  }
  .company-emoji {
    display: inline-block;
    margin-right: 6px;
  }
  .company-header h2 {
    display: inline;
  }
  .news-cluster {
    margin-top: 10px;
    padding-top: 8px;
  }
  h1 {
    font-size: 24px;
  }
  h2 {
    font-size: 18px;
  }
  h3 {
    font-size: 13px;
  }
  h4 {
    font-size: 12px;
  }
  body {
    font-size: 11px;
    line-height: 1.42;
  }
}
"""
