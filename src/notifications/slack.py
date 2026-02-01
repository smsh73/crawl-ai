"""Slack notification integration."""

from typing import Any

import structlog
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from src.core.config import settings
from src.core.models import Content

logger = structlog.get_logger()


class SlackNotifier:
    """
    Slack notification sender.

    Features:
    - Rich message formatting with blocks
    - Importance-based styling
    - Batch summaries
    """

    def __init__(self):
        self.client: AsyncWebClient | None = None

    async def _get_client(self) -> AsyncWebClient:
        """Get or create Slack client."""
        if self.client is None:
            if not settings.slack_bot_token:
                raise ValueError("Slack bot token not configured")

            self.client = AsyncWebClient(
                token=settings.slack_bot_token.get_secret_value()
            )
        return self.client

    async def send(
        self, content: Content, config: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Send notification to Slack.

        Args:
            content: Content to notify about
            config: Channel configuration

        Returns:
            Dict with send result
        """
        client = await self._get_client()
        channel = config.get("channel", settings.slack_default_channel)

        # Build message blocks
        blocks = self._build_message_blocks(content)

        try:
            response = await client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text=f"📰 {content.title}",  # Fallback text
            )

            logger.info(
                "slack_message_sent",
                channel=channel,
                content_id=str(content.id),
                ts=response.get("ts"),
            )

            return {
                "status": "sent",
                "channel": channel,
                "ts": response.get("ts"),
            }

        except SlackApiError as e:
            logger.error(
                "slack_api_error",
                channel=channel,
                error=str(e),
            )
            raise

    async def send_batch(
        self, contents: list[Content], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Send batch summary to Slack."""
        client = await self._get_client()
        channel = config.get("channel", settings.slack_default_channel)

        blocks = self._build_batch_blocks(contents)

        try:
            response = await client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text=f"📊 AI 뉴스 요약 ({len(contents)}건)",
            )

            return {
                "status": "sent",
                "channel": channel,
                "count": len(contents),
                "ts": response.get("ts"),
            }

        except SlackApiError as e:
            logger.error("slack_batch_error", error=str(e))
            raise

    def _build_message_blocks(self, content: Content) -> list[dict[str, Any]]:
        """Build Slack message blocks for a single content."""
        # Determine importance emoji
        importance = content.importance_score or 0.5
        if importance >= 0.8:
            emoji = "🔴"
            importance_text = "높음"
        elif importance >= 0.6:
            emoji = "🟡"
            importance_text = "중간"
        else:
            emoji = "🟢"
            importance_text = "낮음"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {content.title[:100]}",
                    "emoji": True,
                },
            },
        ]

        # Add summary if available
        if content.summary:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": content.summary[:500],
                },
            })

        # Add metadata
        fields = []

        if content.categories:
            fields.append({
                "type": "mrkdwn",
                "text": f"*카테고리:* {', '.join(content.categories[:3])}",
            })

        if content.matched_keywords:
            fields.append({
                "type": "mrkdwn",
                "text": f"*키워드:* {', '.join(content.matched_keywords[:5])}",
            })

        fields.append({
            "type": "mrkdwn",
            "text": f"*중요도:* {importance_text} ({importance:.1%})",
        })

        if fields:
            blocks.append({
                "type": "section",
                "fields": fields,
            })

        # Add link button
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "원문 보기",
                        "emoji": True,
                    },
                    "url": content.url,
                    "action_id": f"view_article_{content.id}",
                },
            ],
        })

        # Add divider
        blocks.append({"type": "divider"})

        return blocks

    def _build_batch_blocks(self, contents: list[Content]) -> list[dict[str, Any]]:
        """Build Slack message blocks for batch summary."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📊 AI 뉴스 요약 ({len(contents)}건)",
                    "emoji": True,
                },
            },
            {"type": "divider"},
        ]

        # Group by importance
        high_importance = [c for c in contents if (c.importance_score or 0) >= 0.8]
        medium_importance = [c for c in contents if 0.6 <= (c.importance_score or 0) < 0.8]

        if high_importance:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🔴 주요 뉴스*",
                },
            })

            for content in high_importance[:5]:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"• <{content.url}|{content.title[:80]}>",
                    },
                })

        if medium_importance:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🟡 일반 뉴스*",
                },
            })

            for content in medium_importance[:5]:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"• <{content.url}|{content.title[:80]}>",
                    },
                })

        blocks.append({"type": "divider"})

        return blocks
