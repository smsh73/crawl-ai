"""Webhook notification integration."""

from typing import Any

import httpx
import structlog

from src.core.models import Content

logger = structlog.get_logger()


class WebhookNotifier:
    """
    Generic webhook notification sender.

    Supports custom payloads and headers for integration
    with various services.
    """

    async def send(
        self, content: Content, config: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Send webhook notification.

        Args:
            content: Content to notify about
            config: Webhook configuration (url, headers, template)

        Returns:
            Dict with send result
        """
        url = config.get("url")
        if not url:
            raise ValueError("Webhook URL not specified")

        headers = config.get("headers", {})
        headers.setdefault("Content-Type", "application/json")

        # Build payload
        payload = self._build_payload(content, config.get("template"))

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )
                response.raise_for_status()

                logger.info(
                    "webhook_sent",
                    url=url,
                    content_id=str(content.id),
                    status_code=response.status_code,
                )

                return {
                    "status": "sent",
                    "url": url,
                    "response_code": response.status_code,
                }

            except httpx.HTTPError as e:
                logger.error(
                    "webhook_failed",
                    url=url,
                    error=str(e),
                )
                raise

    def _build_payload(
        self, content: Content, template: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Build webhook payload."""
        # Default payload structure
        payload = {
            "event": "new_content",
            "timestamp": content.collected_at.isoformat() if content.collected_at else None,
            "data": {
                "id": str(content.id),
                "url": content.url,
                "title": content.title,
                "summary": content.summary,
                "categories": content.categories,
                "matched_keywords": content.matched_keywords,
                "importance_score": content.importance_score,
                "relevance_score": content.relevance_score,
                "published_at": content.published_at.isoformat() if content.published_at else None,
            },
        }

        # Apply custom template if provided
        if template:
            payload = self._apply_template(payload, template, content)

        return payload

    def _apply_template(
        self,
        payload: dict[str, Any],
        template: dict[str, Any],
        content: Content,
    ) -> dict[str, Any]:
        """Apply custom template to payload."""
        # Simple template substitution
        # Template can reference content fields with {field_name}
        import re

        def substitute(value: Any) -> Any:
            if isinstance(value, str):
                # Find all {field} patterns
                pattern = r'\{(\w+)\}'
                matches = re.findall(pattern, value)
                for match in matches:
                    if hasattr(content, match):
                        attr = getattr(content, match)
                        value = value.replace(f"{{{match}}}", str(attr) if attr else "")
                return value
            elif isinstance(value, dict):
                return {k: substitute(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [substitute(v) for v in value]
            return value

        return substitute(template)
