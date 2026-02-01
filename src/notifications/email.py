"""Email notification integration."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import aiosmtplib
import structlog

from src.core.config import settings
from src.core.models import Content

logger = structlog.get_logger()


class EmailNotifier:
    """Email notification sender."""

    async def send(
        self, content: Content, config: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Send email notification.

        Args:
            content: Content to notify about
            config: Email configuration (to, cc, bcc)

        Returns:
            Dict with send result
        """
        if not settings.smtp_user or not settings.smtp_password:
            raise ValueError("SMTP credentials not configured")

        to_email = config.get("to")
        if not to_email:
            raise ValueError("Email recipient not specified")

        # Build email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[AI Alert] {content.title[:80]}"
        msg["From"] = settings.email_from
        msg["To"] = to_email

        # Plain text version
        text_content = self._build_text_content(content)
        msg.attach(MIMEText(text_content, "plain"))

        # HTML version
        html_content = self._build_html_content(content)
        msg.attach(MIMEText(html_content, "html"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.smtp_password.get_secret_value(),
                start_tls=True,
            )

            logger.info(
                "email_sent",
                to=to_email,
                content_id=str(content.id),
            )

            return {
                "status": "sent",
                "to": to_email,
            }

        except Exception as e:
            logger.error("email_send_failed", error=str(e))
            raise

    def _build_text_content(self, content: Content) -> str:
        """Build plain text email content."""
        lines = [
            f"제목: {content.title}",
            "",
        ]

        if content.summary:
            lines.extend([
                "요약:",
                content.summary,
                "",
            ])

        if content.categories:
            lines.append(f"카테고리: {', '.join(content.categories)}")

        if content.matched_keywords:
            lines.append(f"키워드: {', '.join(content.matched_keywords)}")

        if content.importance_score:
            lines.append(f"중요도: {content.importance_score:.1%}")

        lines.extend([
            "",
            f"원문: {content.url}",
        ])

        return "\n".join(lines)

    def _build_html_content(self, content: Content) -> str:
        """Build HTML email content."""
        importance = content.importance_score or 0.5
        if importance >= 0.8:
            badge_color = "#dc3545"
            badge_text = "높음"
        elif importance >= 0.6:
            badge_color = "#ffc107"
            badge_text = "중간"
        else:
            badge_color = "#28a745"
            badge_text = "낮음"

        categories_html = ""
        if content.categories:
            categories_html = f"""
            <p><strong>카테고리:</strong> {', '.join(content.categories)}</p>
            """

        keywords_html = ""
        if content.matched_keywords:
            keywords_html = f"""
            <p><strong>키워드:</strong> {', '.join(content.matched_keywords)}</p>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #1a1a2e; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
                .badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px; color: white; font-size: 12px; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2 style="margin: 0;">{content.title}</h2>
                    <span class="badge" style="background: {badge_color};">중요도: {badge_text}</span>
                </div>
                <div class="content">
                    {f'<p>{content.summary}</p>' if content.summary else ''}
                    {categories_html}
                    {keywords_html}
                    <p style="margin-top: 20px;">
                        <a href="{content.url}" class="button">원문 보기</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
