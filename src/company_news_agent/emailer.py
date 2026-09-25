from __future__ import annotations

import mimetypes
import os
import smtplib
from collections.abc import Sequence
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

from .types import CompanyReport


@dataclass(frozen=True)
class EmailConfig:
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    email_from: str
    email_to: tuple[str, ...]
    subject: str = "公司股票新闻"
    use_tls: bool = True

    @classmethod
    def from_env(cls) -> "EmailConfig":
        missing = [
            name
            for name in (
                "SMTP_HOST",
                "SMTP_USERNAME",
                "SMTP_PASSWORD",
                "EMAIL_FROM",
                "EMAIL_TO",
            )
            if not os.getenv(name)
        ]
        if missing:
            raise ValueError(
                "Missing email environment variable(s): " + ", ".join(missing)
            )

        recipients = tuple(
            email.strip()
            for email in os.environ["EMAIL_TO"].split(",")
            if email.strip()
        )
        if not recipients:
            raise ValueError("EMAIL_TO must contain at least one recipient.")

        return cls(
            smtp_host=os.environ["SMTP_HOST"],
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=os.environ["SMTP_USERNAME"],
            smtp_password=os.environ["SMTP_PASSWORD"],
            email_from=os.environ["EMAIL_FROM"],
            email_to=recipients,
            subject=os.getenv("EMAIL_SUBJECT", "公司股票新闻"),
            use_tls=os.getenv("SMTP_USE_TLS", "true").lower()
            not in {"0", "false", "no"},
        )


def send_report_email(
    *,
    html_path: Path,
    pdf_path: Path,
    reports: Sequence[CompanyReport] = (),
    config: EmailConfig | None = None,
) -> None:
    email_config = config or EmailConfig.from_env()
    attachments = (html_path, pdf_path)
    for path in attachments:
        if not path.exists():
            raise FileNotFoundError(f"Report attachment not found: {path}")

    message = EmailMessage()
    message["From"] = email_config.email_from
    message["To"] = ", ".join(email_config.email_to)
    message["Subject"] = email_config.subject
    message.set_content(_build_email_body(reports))

    for path in attachments:
        content_type, _ = mimetypes.guess_type(path.name)
        maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
        message.add_attachment(
            path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=path.name,
        )

    with smtplib.SMTP(email_config.smtp_host, email_config.smtp_port) as smtp:
        if email_config.use_tls:
            smtp.starttls()
        smtp.login(email_config.smtp_username, email_config.smtp_password)
        smtp.send_message(message)


def _build_email_body(reports: Sequence[CompanyReport]) -> str:
    sections = [
        "您好，\n\n"
        "附件为最新的《公司股票新闻》报告。本报告汇集近期公司事件，"
        "整合相关媒体报道，并总结这些事件对各公司股票的潜在影响。"
    ]

    reports_with_points = [
        report for report in reports if report.news and report.key_points
    ]
    if reports_with_points:
        key_point_lines = ["重点摘要："]
        for report in reports_with_points:
            key_point_lines.append(f"\n{report.company.name} ({report.company.ticker})")
            key_point_lines.extend(f"- {point}" for point in report.key_points)
        sections.append("\n".join(key_point_lines))

    sections.extend(
        [
            "随信附上 HTML 和 PDF 两种版本，方便您阅读。",
            "祝好，\n公司股票新闻助手",
        ]
    )
    return "\n\n".join(sections)
