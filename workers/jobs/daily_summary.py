"""Build and email a daily Partifi usage / error summary via Amazon SES."""

from __future__ import annotations

import argparse
import html
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import boto3
import redis

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import db_conn
from config import get_settings
from queue_ops import PROCESSING_KEY, QUEUE_KEY

logger = logging.getLogger("partifi.daily_summary")

SAMPLE_LIMIT = 5
DOWNLOAD_TOP_LIMIT = 5
MAX_ERROR_PARTSETS = 25
MAX_LOG_LINES = 20


@dataclass
class PartsetLink:
    public_id: str
    title: str | None
    composer: str | None
    extra: str | None = None  # e.g. download count or error label


@dataclass
class DailyReport:
    generated_at: datetime
    hours: int
    user_total: int
    new_user_names: list[str]
    partsets_total: int
    partsets_imslp: int
    partsets_upload: int
    parts_total: int
    parts_imslp: int
    parts_upload: int
    ready_created: int
    sample_partsets: list[PartsetLink]
    download_events: int
    download_partsets: int
    top_downloads: list[PartsetLink]
    error_partsets: list[PartsetLink]
    stuck_partsets: list[PartsetLink]
    log_lines: list[str] = field(default_factory=list)
    queue_pending: int | None = None
    queue_processing: int | None = None


def _public_base_url() -> str:
    settings = get_settings()
    base = (settings.partifi_public_base_url or "https://partifi.org").rstrip("/")
    return base


def public_partset_url(public_id: str) -> str:
    return f"{_public_base_url()}/{public_id}"


def _display_name(title: str | None, composer: str | None, public_id: str) -> str:
    title = (title or "").strip()
    composer = (composer or "").strip()
    if title and composer:
        return f"{title} — {composer}"
    if title:
        return title
    if composer:
        return composer
    return public_id


def _user_label(name: str | None, given_name: str | None) -> str:
    for candidate in ((name or "").strip(), (given_name or "").strip()):
        if candidate:
            return candidate
    return "(unnamed)"


def _queue_depths() -> tuple[int | None, int | None]:
    try:
        client = redis.from_url(get_settings().redis_url, decode_responses=True)
        return int(client.llen(QUEUE_KEY)), int(client.llen(PROCESSING_KEY))
    except Exception:
        logger.exception("Failed to read Redis queue depths")
        return None, None


def gather_report(hours: int = 24, log_lines: list[str] | None = None) -> DailyReport:
    params = {"hours": hours}

    user_total = int(db_conn.fetchone("SELECT COUNT(*) FROM users")[0])
    new_users = db_conn.fetchall(
        """
        SELECT name, given_name
        FROM users
        WHERE ts >= NOW() - INTERVAL :hours HOUR
        ORDER BY ts ASC
        """,
        params,
    )
    new_user_names = [_user_label(row[0], row[1]) for row in new_users]

    created = db_conn.fetchone(
        """
        SELECT
          COUNT(*),
          SUM(imslp_id IS NOT NULL),
          SUM(imslp_id IS NULL)
        FROM partsets
        WHERE create_ts >= NOW() - INTERVAL :hours HOUR
        """,
        params,
    )
    partsets_total = int(created[0] or 0)
    partsets_imslp = int(created[1] or 0)
    partsets_upload = int(created[2] or 0)

    parts = db_conn.fetchone(
        """
        SELECT
          COUNT(*),
          SUM(ps.imslp_id IS NOT NULL),
          SUM(ps.imslp_id IS NULL)
        FROM parts p
        JOIN partsets ps ON ps.id = p.partset_id
        WHERE ps.create_ts >= NOW() - INTERVAL :hours HOUR
        """,
        params,
    )
    parts_total = int(parts[0] or 0)
    parts_imslp = int(parts[1] or 0)
    parts_upload = int(parts[2] or 0)

    ready_created = int(
        db_conn.fetchone(
            """
            SELECT COUNT(*)
            FROM partsets
            WHERE create_ts >= NOW() - INTERVAL :hours HOUR
              AND parts_ready = 1
            """,
            params,
        )[0]
        or 0
    )

    sample_rows = db_conn.fetchall(
        """
        SELECT id, title, composer
        FROM partsets
        WHERE create_ts >= NOW() - INTERVAL :hours HOUR
          AND parts_ready = 1
        ORDER BY RAND()
        LIMIT :limit
        """,
        {**params, "limit": SAMPLE_LIMIT},
    )
    sample_partsets = [
        PartsetLink(public_id=row[0], title=row[1], composer=row[2]) for row in sample_rows
    ]

    download_events = int(
        db_conn.fetchone(
            """
            SELECT COUNT(*)
            FROM downloads
            WHERE ts >= NOW() - INTERVAL :hours HOUR
            """,
            params,
        )[0]
        or 0
    )
    download_partsets = int(
        db_conn.fetchone(
            """
            SELECT COUNT(DISTINCT partset_id)
            FROM downloads
            WHERE ts >= NOW() - INTERVAL :hours HOUR
            """,
            params,
        )[0]
        or 0
    )
    top_rows = db_conn.fetchall(
        """
        SELECT d.partset_id, ps.title, ps.composer, COUNT(*) AS cnt
        FROM downloads d
        JOIN partsets ps ON ps.id = d.partset_id
        WHERE d.ts >= NOW() - INTERVAL :hours HOUR
        GROUP BY d.partset_id, ps.title, ps.composer
        ORDER BY cnt DESC, d.partset_id ASC
        LIMIT :limit
        """,
        {**params, "limit": DOWNLOAD_TOP_LIMIT},
    )
    top_downloads = [
        PartsetLink(
            public_id=row[0],
            title=row[1],
            composer=row[2],
            extra=str(row[3]),
        )
        for row in top_rows
    ]

    error_rows = db_conn.fetchall(
        """
        SELECT id, title, composer, error, error_message
        FROM partsets
        WHERE error IS NOT NULL
          AND COALESCE(error_ts, create_ts) >= NOW() - INTERVAL :hours HOUR
        ORDER BY COALESCE(error_ts, create_ts) DESC
        LIMIT :limit
        """,
        {**params, "limit": MAX_ERROR_PARTSETS},
    )
    error_partsets = [
        PartsetLink(
            public_id=row[0],
            title=row[1],
            composer=row[2],
            extra=_error_extra(row[3], row[4]),
        )
        for row in error_rows
    ]

    stuck_rows = db_conn.fetchall(
        """
        SELECT id, title, composer, status, error_message
        FROM partsets
        WHERE COALESCE(error_ts, paste_start, mod_ts, last_access, create_ts)
                >= NOW() - INTERVAL :hours HOUR
          AND error IS NULL
          AND (
            (import_complete IS NULL AND create_ts < NOW() - INTERVAL 1 HOUR)
            OR (
              paste_start IS NOT NULL
              AND paste_complete IS NULL
              AND parts_ready = 0
              AND paste_start < NOW() - INTERVAL 1 HOUR
            )
          )
        ORDER BY COALESCE(paste_start, mod_ts, last_access, create_ts) DESC
        LIMIT :limit
        """,
        {**params, "limit": MAX_ERROR_PARTSETS},
    )
    stuck_partsets = [
        PartsetLink(
            public_id=row[0],
            title=row[1],
            composer=row[2],
            extra=_stuck_extra(row[3], row[4]),
        )
        for row in stuck_rows
    ]

    pending, processing = _queue_depths()
    cleaned_logs = [line.strip() for line in (log_lines or []) if line.strip()][:MAX_LOG_LINES]

    return DailyReport(
        generated_at=datetime.now(timezone.utc),
        hours=hours,
        user_total=user_total,
        new_user_names=new_user_names,
        partsets_total=partsets_total,
        partsets_imslp=partsets_imslp,
        partsets_upload=partsets_upload,
        parts_total=parts_total,
        parts_imslp=parts_imslp,
        parts_upload=parts_upload,
        ready_created=ready_created,
        sample_partsets=sample_partsets,
        download_events=download_events,
        download_partsets=download_partsets,
        top_downloads=top_downloads,
        error_partsets=error_partsets,
        stuck_partsets=stuck_partsets,
        log_lines=cleaned_logs,
        queue_pending=pending,
        queue_processing=processing,
    )


def _error_extra(error: str | None, message: str | None) -> str:
    label = (error or "error").strip()
    msg = (message or "").strip()
    if msg:
        if len(msg) > 160:
            msg = msg[:157] + "..."
        return f"{label}: {msg}"
    return label


def _stuck_extra(status: str | None, message: str | None) -> str:
    bits = ["stuck"]
    if status:
        bits.append(f"status={status}")
    msg = (message or "").strip()
    if msg:
        if len(msg) > 120:
            msg = msg[:117] + "..."
        bits.append(msg)
    return " — ".join(bits) if len(bits) > 1 else bits[0]


def subject_line(report: DailyReport) -> str:
    day = f"{report.generated_at:%b} {report.generated_at.day}"
    err_n = len(report.error_partsets) + len(report.stuck_partsets) + len(report.log_lines)
    err_bit = f"{err_n} error{'s' if err_n != 1 else ''}" if err_n else "no errors"
    return (
        f"Partifi daily: {len(report.new_user_names)} new users, "
        f"{report.partsets_total} partsets, {err_bit} — {day}"
    )


def render_text(report: DailyReport) -> str:
    lines: list[str] = []
    lines.append("Partifi Daily Summary")
    lines.append(f"Last {report.hours} hours (generated {report.generated_at:%Y-%m-%d %H:%M UTC})")
    lines.append("")

    lines.append("Users")
    lines.append(
        f"{report.user_total} total · {len(report.new_user_names)} new"
    )
    if report.new_user_names:
        lines.append(" · ".join(report.new_user_names))
    lines.append("")

    lines.append("Partsets")
    lines.append(
        f"{report.partsets_total} created "
        f"({report.partsets_imslp} IMSLP, {report.partsets_upload} upload) · "
        f"{report.parts_total} parts "
        f"({report.parts_imslp} IMSLP, {report.parts_upload} upload)"
    )
    if report.sample_partsets:
        lines.append(
            f"Sample ({len(report.sample_partsets)} of {report.ready_created} ready):"
        )
        for item in report.sample_partsets:
            label = _display_name(item.title, item.composer, item.public_id)
            lines.append(f"  - {label}: {public_partset_url(item.public_id)}")
    elif report.partsets_total:
        lines.append(f"No ready partsets to sample ({report.ready_created} ready).")
    lines.append("")

    lines.append("Downloads")
    lines.append(
        f"{report.download_events} parts downloaded across {report.download_partsets} partsets"
    )
    if report.top_downloads:
        lines.append("Most downloaded:")
        for item in report.top_downloads:
            label = _display_name(item.title, item.composer, item.public_id)
            lines.append(
                f"  - {label} — {item.extra} parts: {public_partset_url(item.public_id)}"
            )
    lines.append("")

    lines.append("Errors")
    if not (report.error_partsets or report.stuck_partsets or report.log_lines):
        lines.append("None.")
    else:
        if report.queue_pending is not None:
            lines.append(
                f"Queue: {report.queue_pending} pending / "
                f"{report.queue_processing} processing"
            )
        for item in report.error_partsets:
            label = _display_name(item.title, item.composer, item.public_id)
            lines.append(f"  - {label}: {item.extra} — {public_partset_url(item.public_id)}")
        for item in report.stuck_partsets:
            label = _display_name(item.title, item.composer, item.public_id)
            lines.append(f"  - {label}: {item.extra} — {public_partset_url(item.public_id)}")
        for line in report.log_lines:
            lines.append(f"  - log: {line}")

    lines.append("")
    return "\n".join(lines)


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _html_link(item: PartsetLink, suffix: str = "") -> str:
    label = _esc(_display_name(item.title, item.composer, item.public_id))
    url = _esc(public_partset_url(item.public_id))
    extra = f" {_esc(suffix)}" if suffix else ""
    return f'<a href="{url}" style="color:#b00000;text-decoration:none;">{label}</a>{extra}'


def render_html(report: DailyReport) -> str:
    sections: list[str] = []
    sections.append(
        f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;font-size:15px;line-height:1.45;color:#222;max-width:640px;">
  <h1 style="font-size:22px;margin:0 0 4px;font-weight:650;">Partifi Daily Summary</h1>
  <p style="margin:0 0 24px;color:#666;font-size:13px;">Last {report.hours} hours · generated {report.generated_at:%Y-%m-%d %H:%M UTC}</p>
""".strip()
    )

    new_n = len(report.new_user_names)
    sections.append('<h2 style="font-size:16px;margin:0 0 8px;border-bottom:1px solid #e6e6e6;padding-bottom:4px;">Users</h2>')
    sections.append(
        f'<p style="margin:0 0 8px;"><strong>{report.user_total}</strong> total · '
        f"<strong>{new_n}</strong> new</p>"
    )
    if report.new_user_names:
        names = " · ".join(_esc(n) for n in report.new_user_names)
        sections.append(f'<p style="margin:0 0 24px;">{names}</p>')
    else:
        sections.append('<p style="margin:0 0 24px;color:#666;">No new users.</p>')

    sections.append('<h2 style="font-size:16px;margin:0 0 8px;border-bottom:1px solid #e6e6e6;padding-bottom:4px;">Partsets</h2>')
    sections.append(
        f'<p style="margin:0 0 8px;"><strong>{report.partsets_total}</strong> created '
        f"({report.partsets_imslp} IMSLP, {report.partsets_upload} upload) · "
        f"<strong>{report.parts_total}</strong> parts "
        f"({report.parts_imslp} IMSLP, {report.parts_upload} upload)</p>"
    )
    if report.sample_partsets:
        sections.append(
            f'<p style="margin:0 0 6px;color:#666;font-size:13px;">'
            f"Random sample ({len(report.sample_partsets)} of {report.ready_created} ready)</p>"
        )
        items = "".join(
            f'<li style="margin:0 0 4px;">{_html_link(item)}</li>'
            for item in report.sample_partsets
        )
        sections.append(f'<ul style="margin:0 0 24px;padding-left:18px;">{items}</ul>')
    elif report.partsets_total:
        sections.append(
            f'<p style="margin:0 0 24px;color:#666;">No ready partsets to sample '
            f"({report.ready_created} ready).</p>"
        )
    else:
        sections.append('<p style="margin:0 0 24px;color:#666;">No partsets created.</p>')

    sections.append('<h2 style="font-size:16px;margin:0 0 8px;border-bottom:1px solid #e6e6e6;padding-bottom:4px;">Downloads</h2>')
    sections.append(
        f'<p style="margin:0 0 8px;"><strong>{report.download_events}</strong> parts downloaded '
        f"across <strong>{report.download_partsets}</strong> partsets</p>"
    )
    if report.top_downloads:
        sections.append('<p style="margin:0 0 6px;color:#666;font-size:13px;">Most downloaded</p>')
        items = "".join(
            f'<li style="margin:0 0 4px;">{_html_link(item, suffix=f"— {item.extra} parts")}</li>'
            for item in report.top_downloads
        )
        sections.append(f'<ul style="margin:0 0 24px;padding-left:18px;">{items}</ul>')
    else:
        sections.append('<p style="margin:0 0 24px;color:#666;">No downloads.</p>')

    err_n = len(report.error_partsets) + len(report.stuck_partsets) + len(report.log_lines)
    sections.append('<h2 style="font-size:16px;margin:0 0 8px;border-bottom:1px solid #e6e6e6;padding-bottom:4px;">Errors</h2>')
    if err_n == 0:
        sections.append(
            '<p style="margin:0;padding:10px 12px;background:#f3faf3;border-radius:6px;color:#1b5e20;">'
            "No errors warranting attention.</p>"
        )
    else:
        bits = []
        if report.error_partsets:
            bits.append(f"{len(report.error_partsets)} partset error(s)")
        if report.stuck_partsets:
            bits.append(f"{len(report.stuck_partsets)} stuck")
        if report.log_lines:
            bits.append(f"{len(report.log_lines)} log alert(s)")
        summary = " · ".join(bits)
        if report.queue_pending is not None:
            summary += (
                f" · queue {report.queue_pending} pending / "
                f"{report.queue_processing} processing"
            )
        sections.append(f'<p style="margin:0 0 8px;"><strong>{summary}</strong></p>')
        items: list[str] = []
        for item in report.error_partsets:
            items.append(
                f'<li style="margin:0 0 6px;">{_html_link(item)}'
                f'<div style="color:#666;font-size:13px;">{_esc(item.extra or "")}</div></li>'
            )
        for item in report.stuck_partsets:
            items.append(
                f'<li style="margin:0 0 6px;">{_html_link(item)}'
                f'<div style="color:#666;font-size:13px;">{_esc(item.extra or "")}</div></li>'
            )
        for line in report.log_lines:
            items.append(
                f'<li style="margin:0 0 6px;font-family:ui-monospace,Menlo,Consolas,monospace;'
                f'font-size:12px;color:#444;">{_esc(line)}</li>'
            )
        sections.append(
            f'<ul style="margin:0;padding-left:18px;">{"".join(items)}</ul>'
        )

    sections.append("</div>")
    return "\n".join(sections)


def send_email(*, subject: str, text_body: str, html_body: str) -> str:
    settings = get_settings()
    if not settings.ses_from or not settings.ses_to:
        raise RuntimeError("SES_FROM and SES_TO must be set")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.ses_from
    msg["To"] = settings.ses_to
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    client = boto3.client(
        "ses",
        region_name=settings.ses_region or settings.s3_region,
        aws_access_key_id=settings.s3_access_key or None,
        aws_secret_access_key=settings.s3_secret_key or None,
    )
    response = client.send_raw_email(
        Source=settings.ses_from,
        Destinations=[addr.strip() for addr in settings.ses_to.split(",") if addr.strip()],
        RawMessage={"Data": msg.as_string()},
    )
    return str(response.get("MessageId") or "")


def _parse_log_lines(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [line.rstrip("\n") for line in raw.splitlines() if line.strip()]


def run_daily_summary(
    *,
    hours: int = 24,
    dry_run: bool = False,
    log_text: str | None = None,
) -> DailyReport:
    report = gather_report(hours=hours, log_lines=_parse_log_lines(log_text))
    subject = subject_line(report)
    text_body = render_text(report)
    html_body = render_html(report)

    if dry_run:
        print(subject)
        print("---")
        print(text_body)
        return report

    message_id = send_email(subject=subject, text_body=text_body, html_body=html_body)
    logger.info("Daily summary sent message_id=%s subject=%r", message_id, subject)
    print(f"sent message_id={message_id}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the text body instead of sending email",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Optional file of filtered journal/log lines to include",
    )
    args = parser.parse_args(argv)

    log_text = os.environ.get("DAILY_SUMMARY_LOG_TEXT")
    if args.log_file is not None:
        log_text = args.log_file.read_text(encoding="utf-8", errors="replace")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_daily_summary(hours=args.hours, dry_run=args.dry_run, log_text=log_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
