import asyncio
import email.mime.multipart
import email.mime.text
from pathlib import Path
from typing import Any

import aiosmtplib
import structlog
from jinja2 import Environment, FileSystemLoader
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import Settings

log = structlog.get_logger()

_TEMPLATE_DIR = Path(__file__).parent / "templates"

_SUBJECT_MAP = {
    "invite": "Bạn được mời tham gia {enterprise_name} trên Kaori AI",
    "reset-password": "Kaori — Đặt lại mật khẩu / Reset your password",
    "quota-alert": "Kaori — Cảnh báo hạn mức: {usage_pct}% quota đã dùng",
    "report-ready": "Kaori — Báo cáo \"{report_title}\" đã sẵn sàng",
    "workflow-freeform": "{subject}",  # subject + body from workflow send_email node
}


class SmtpClient:
    def __init__(self, settings: Settings):
        self._s = settings
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )

    def _render(self, template: str, context: dict[str, Any]) -> str:
        tpl = self._env.get_template(f"{template.replace('-', '_')}.html")
        return tpl.render(**context, frontend_url=self._s.frontend_url)

    def _subject(self, template: str, context: dict[str, Any]) -> str:
        raw = _SUBJECT_MAP.get(template, "Thông báo từ Kaori AI")
        try:
            return raw.format(**context)
        except KeyError:
            return raw

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiosmtplib.SMTPException, OSError, ConnectionError)),
        reraise=True,
    )
    async def _send_once(self, to: str, subject: str, html: str) -> str:
        msg = email.mime.multipart.MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self._s.smtp_from_name} <{self._s.smtp_user}>"
        msg["To"] = to
        msg["Message-ID"] = f"<{asyncio.get_event_loop().time():.6f}@kaori.ai>"
        msg.attach(email.mime.text.MIMEText(html, "html", "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname=self._s.smtp_host,
            port=self._s.smtp_port,
            username=self._s.smtp_user,
            password=self._s.smtp_password,
            start_tls=self._s.smtp_tls,
            timeout=15,
        )
        return msg["Message-ID"]

    async def send(self, to: str, template: str, context: dict[str, Any]) -> str:
        html = self._render(template, context)
        subject = self._subject(template, context)
        log.info("notification.send.attempt", to=to, template=template)
        msg_id = await self._send_once(to, subject, html)
        log.info("notification.send.ok", to=to, template=template, message_id=msg_id)
        return msg_id
