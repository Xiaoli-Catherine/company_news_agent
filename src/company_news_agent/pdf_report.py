from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from .types import CompanyReport, NewsCluster, NewsItem


MAX_PDF_SOURCES_PER_CLUSTER = 5


def build_pdf_report(
    reports: list[CompanyReport],
    output_path: Path,
    timezone_name: str = "America/Los_Angeles",
) -> Path:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Image,
            ListFlowable,
            ListItem,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Missing PDF dependency. Install dependencies with: pip install -r requirements.txt"
        ) from exc

    _register_fonts()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title="Company Stock News Report",
    )
    styles = _styles()
    story: list = []

    generated_at = datetime.now(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M %Z")
    story.append(Paragraph("公司股票相关新闻报告", styles["Title"]))
    story.append(Paragraph(_mixed_text(f"生成时间：{generated_at}"), styles["Meta"]))
    story.append(Spacer(1, 0.18 * inch))
    story.append(Paragraph("新闻数量汇总", styles["Heading2"]))
    story.extend(_summary_table(reports, styles, inch))
    story.append(Spacer(1, 0.2 * inch))

    for report_index, report in enumerate(reports):
        if report_index:
            story.append(PageBreak())
            story.extend(_section_divider(inch))

        story.extend(_company_heading(report, styles, inch))
        story.append(Paragraph("新闻概况", styles["Heading2"]))
        story.append(Paragraph(_mixed_text(report.overview), styles["Body"]))
        story.append(Spacer(1, 0.1 * inch))

        story.append(Paragraph("股票相关性", styles["Heading2"]))
        story.append(Paragraph(_mixed_text(report.stock_relevance), styles["Body"]))
        story.append(Spacer(1, 0.1 * inch))

        if report.key_points:
            story.append(Paragraph("关键要点", styles["Heading2"]))
            story.append(
                ListFlowable(
                    [
                        ListItem(Paragraph(_mixed_text(point), styles["Body"]))
                        for point in report.key_points
                    ],
                    bulletType="bullet",
                    leftIndent=18,
                )
            )
            story.append(Spacer(1, 0.1 * inch))

        story.append(Paragraph("整合新闻与报道媒体", styles["Heading2"]))
        for index, cluster in enumerate(report.news, start=1):
            story.extend(_cluster_block(index, cluster, styles, inch))

    doc.build(story)
    return output_path


def _styles() -> dict[str, ParagraphStyle]:
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    styles = getSampleStyleSheet()
    for style_name in ("Title", "Heading1", "Heading2", "Normal", "BodyText"):
        styles[style_name].fontName = "STSong-Light"
    styles.add(
        ParagraphStyle(
            name="Meta",
            parent=styles["Normal"],
            fontName="STSong-Light",
            fontSize=9,
            textColor=colors.HexColor("#5f6368"),
            leading=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontName="STSong-Light",
            fontSize=10,
            leading=15,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Summary",
            parent=styles["BodyText"],
            fontName="STSong-Light",
            fontSize=9.5,
            leading=14.5,
            leftIndent=8,
            rightIndent=4,
            spaceBefore=2,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Source",
            parent=styles["BodyText"],
            fontName="STSong-Light",
            fontSize=8.2,
            leading=12,
            textColor=colors.HexColor("#3c4043"),
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SourceMeta",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#3c4043"),
            spaceAfter=3,
            splitLongWords=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="OriginalTitle",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#3c4043"),
            spaceAfter=6,
            splitLongWords=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Label",
            parent=styles["Normal"],
            fontName="STSong-Light",
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#202124"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="CompanyHeading",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CompanySummary",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#202124"),
        )
    )
    return styles


def _register_fonts() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    except KeyError:
        pass


def _company_heading(report: CompanyReport, styles: dict[str, ParagraphStyle], inch: float) -> list:
    from reportlab.platypus import Paragraph, Spacer, Table

    icon = _emoji_image(report.company.icon, 0.24 * inch)
    heading = Paragraph(
        _escape(f"{report.company.name} ({report.company.ticker})"),
        styles["CompanyHeading"],
    )
    table = Table(
        [[icon, heading]],
        colWidths=[0.34 * inch, 6.1 * inch],
        hAlign="LEFT",
        style=[
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ],
    )
    return [table, Spacer(1, 0.06 * inch)]


def _section_divider(inch: float) -> list:
    from reportlab.platypus import Spacer, Table

    line = Table(
        [[""]],
        colWidths=[6.45 * inch],
        style=[
            ("LINEABOVE", (0, 0), (-1, 0), 0.6, "#dadce0"),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ],
    )
    return [line, Spacer(1, 0.12 * inch)]


def _summary_table(reports: list[CompanyReport], styles: dict[str, ParagraphStyle], inch: float) -> list:
    from reportlab.platypus import Paragraph, Spacer, Table

    rows = []
    for report in reports:
        raw_count = sum(len(cluster.items) for cluster in report.news)
        rows.append(
            [
                _emoji_image(report.company.icon, 0.18 * inch),
                Paragraph(
                    _latin_text(f"{report.company.name} ({report.company.ticker})"),
                    styles["CompanySummary"],
                ),
                Paragraph(
                    _mixed_text(f"{len(report.news)} 条整合新闻，{raw_count} 条原始报道"),
                    styles["Body"],
                ),
            ]
        )

    table = Table(
        rows,
        colWidths=[0.3 * inch, 2.75 * inch, 3.35 * inch],
        hAlign="LEFT",
        style=[
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, "#e8eaed"),
        ],
    )
    return [table, Spacer(1, 0.06 * inch)]


def _cluster_block(
    index: int,
    cluster: NewsCluster,
    styles: dict[str, ParagraphStyle],
    inch: float,
) -> list:
    from reportlab.platypus import Paragraph, Spacer, Table

    title = Paragraph(_mixed_text(f"{index}. {cluster.title_zh}"), styles["Body"])
    header = Table(
        [[title]],
        colWidths=[6.45 * inch],
        hAlign="LEFT",
        style=[
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LINEABOVE", (0, 0), (-1, 0), 0.4, "#dadce0"),
        ],
    )
    block = [
        Spacer(1, 0.06 * inch),
        header,
        Paragraph(_mixed_text(f"新闻总结：{cluster.summary_zh}"), styles["Summary"]),
        Paragraph(_mixed_text(f"报道媒体：{len(cluster.items)} 家/条"), styles["Source"]),
    ]
    visible_items = cluster.items[:MAX_PDF_SOURCES_PER_CLUSTER]
    for source_index, item in enumerate(visible_items, start=1):
        block.extend(_source_block(source_index, item, styles))
    hidden_count = len(cluster.items) - len(visible_items)
    if hidden_count > 0:
        block.append(
            Paragraph(
                _mixed_text(f"另有 {hidden_count} 个来源未在 PDF 中展开，HTML 版本保留完整来源列表。"),
                styles["Source"],
            )
        )
    return block


def _source_block(index: int, item: NewsItem, styles: dict[str, ParagraphStyle]) -> list:
    from reportlab.platypus import Paragraph, Spacer, Table
    from reportlab.lib.units import inch

    date = item.published_at.strftime("%Y-%m-%d %H:%M UTC") if item.published_at else "Unknown date"
    source = _escape(item.source)
    url = _attr_escape(item.url)
    title = _escape(item.title)
    meta = Paragraph(
        f'{index}. {source} | {date} | <a href="{url}">Open source</a>',
        styles["SourceMeta"],
    )
    title_table = Table(
        [[Paragraph("原文标题：", styles["Source"]), Paragraph(title, styles["OriginalTitle"])]],
        colWidths=[0.72 * inch, 5.7 * inch],
        hAlign="LEFT",
        style=[
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ],
    )
    return [
        meta,
        title_table,
        Spacer(1, 0.03 * inch),
    ]


def _emoji_image(emoji: str, size: float):
    from reportlab.platypus import Image, Paragraph

    path = _ensure_emoji_png(emoji)
    if path is None:
        return Paragraph(_escape(emoji), _styles()["Label"])
    return Image(str(path), width=size, height=size)


def _ensure_emoji_png(emoji: str) -> Path | None:
    icon_dir = Path("assets/emoji")
    icon_dir.mkdir(parents=True, exist_ok=True)
    filename = _twemoji_filename(emoji)
    path = icon_dir / f"{filename}.png"
    if path.exists() and path.stat().st_size > 0:
        return path

    url = f"https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/{filename}.png"
    request = Request(url, headers={"User-Agent": "CompanyNewsAgent/0.1"})
    try:
        with urlopen(request, timeout=15) as response:
            path.write_bytes(response.read())
    except OSError:
        return None
    return path if path.exists() and path.stat().st_size > 0 else None


def _twemoji_filename(emoji: str) -> str:
    codepoints = [f"{ord(char):x}" for char in emoji if ord(char) != 0xFE0F]
    return "-".join(codepoints)


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _attr_escape(value: str) -> str:
    return _escape(value).replace('"', "&quot;")


_LATIN_RUN = re.compile(r"([A-Za-z0-9][A-Za-z0-9\s.,;:!?&/()'\"%+\-–—$#@]*[A-Za-z0-9%)]|[A-Za-z0-9])")


def _mixed_text(value: str) -> str:
    parts: list[str] = []
    last_end = 0

    for match in _LATIN_RUN.finditer(value):
        parts.append(_escape(value[last_end:match.start()]))
        text = match.group(0)
        if not text.strip():
            parts.append(_escape(text))
        else:
            parts.append(f'<font name="Helvetica">{_escape(text)}</font>')
        last_end = match.end()

    parts.append(_escape(value[last_end:]))
    return "".join(parts)


def _latin_text(value: str) -> str:
    return f'<font name="Helvetica">{_escape(value)}</font>'
