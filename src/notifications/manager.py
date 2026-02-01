"""Notification management with smart filtering."""

from typing import Any

import structlog

from src.core.config import settings
from src.core.database import get_db_context
from src.core.models import Content, NotificationConfig, NotificationLog

logger = structlog.get_logger()


class NotificationManager:
    """
    Manages notifications with AI-powered filtering.

    Features:
    - Multiple channels (Slack, Email, Webhook)
    - Importance-based filtering
    - Smart batching to avoid notification fatigue
    - Deduplication
    """

    def __init__(self):
        from .slack import SlackNotifier
        from .email import EmailNotifier
        from .webhook import WebhookNotifier

        self.notifiers = {
            "slack": SlackNotifier(),
            "email": EmailNotifier(),
            "webhook": WebhookNotifier(),
        }

    async def notify(self, content: Content) -> list[dict[str, Any]]:
        """
        Send notifications for content based on configured rules.

        Args:
            content: Content to notify about

        Returns:
            List of notification results
        """
        results = []

        # Get applicable notification configs
        configs = await self._get_applicable_configs(content)

        for config in configs:
            try:
                result = await self._send_notification(config, content)
                results.append(result)

                # Log notification
                await self._log_notification(config, content, "sent")

                logger.info(
                    "notification_sent",
                    content_id=str(content.id),
                    channel=config.channel_type,
                )

            except Exception as e:
                logger.error(
                    "notification_failed",
                    content_id=str(content.id),
                    channel=config.channel_type,
                    error=str(e),
                )

                await self._log_notification(config, content, "failed", str(e))

                results.append({
                    "config_id": str(config.id),
                    "status": "failed",
                    "error": str(e),
                })

        return results

    async def _get_applicable_configs(
        self, content: Content
    ) -> list[NotificationConfig]:
        """Get notification configs that match the content."""
        from sqlalchemy import select

        async with get_db_context() as db:
            query = select(NotificationConfig).where(
                NotificationConfig.is_active == True
            )
            result = await db.execute(query)
            configs = result.scalars().all()

            applicable = []
            for config in configs:
                if self._matches_config(content, config):
                    applicable.append(config)

            return applicable

    def _matches_config(
        self, content: Content, config: NotificationConfig
    ) -> bool:
        """Check if content matches notification config criteria."""
        # Check importance threshold
        if content.importance_score and content.importance_score < config.min_importance_score:
            return False

        # Check relevance threshold
        if content.relevance_score and content.relevance_score < config.min_relevance_score:
            return False

        # Check keyword group match
        if config.keyword_group_ids and content.matched_keyword_groups:
            matching_groups = set(config.keyword_group_ids) & set(content.matched_keyword_groups)
            if not matching_groups:
                return False

        return True

    async def _send_notification(
        self, config: NotificationConfig, content: Content
    ) -> dict[str, Any]:
        """Send notification through appropriate channel."""
        notifier = self.notifiers.get(config.channel_type)
        if not notifier:
            raise ValueError(f"Unknown channel type: {config.channel_type}")

        return await notifier.send(content, config.channel_config)

    async def _log_notification(
        self,
        config: NotificationConfig,
        content: Content,
        status: str,
        error: str | None = None,
    ) -> None:
        """Log notification to database."""
        async with get_db_context() as db:
            log = NotificationLog(
                config_id=config.id,
                content_id=content.id,
                status=status,
                error_message=error,
            )
            db.add(log)

    async def send_immediate(
        self,
        content: Content,
        channel: str = "slack",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send immediate notification bypassing config rules."""
        notifier = self.notifiers.get(channel)
        if not notifier:
            raise ValueError(f"Unknown channel: {channel}")

        # Use default config
        config = {
            "channel": kwargs.get("channel", settings.slack_default_channel),
            **kwargs,
        }

        return await notifier.send(content, config)

    async def send_batch_summary(
        self,
        contents: list[Content],
        channel: str = "slack",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a batch summary of multiple contents."""
        notifier = self.notifiers.get(channel)
        if not notifier:
            raise ValueError(f"Unknown channel: {channel}")

        if hasattr(notifier, "send_batch"):
            return await notifier.send_batch(contents, kwargs)
        else:
            # Fallback: send individual notifications
            results = []
            for content in contents:
                result = await notifier.send(content, kwargs)
                results.append(result)
            return {"results": results}
