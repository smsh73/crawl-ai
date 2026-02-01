"""AI-powered report generator."""

from datetime import datetime, timedelta
from typing import Any

import structlog

from src.core.ai_orchestrator import AIOrchestrator, AITaskType
from src.core.database import get_db_context
from src.core.models import Content, ContentStatus

logger = structlog.get_logger()


class ReportGenerator:
    """
    Generate intelligence reports from collected content.

    Report types:
    - Daily Brief: Top news and trends from the past 24 hours
    - Weekly Report: Comprehensive analysis of the week's developments
    - Custom Report: On-demand reports for specific topics/timeframes
    """

    def __init__(self, orchestrator: AIOrchestrator | None = None):
        self.ai = orchestrator or AIOrchestrator()

    async def generate_daily(self) -> dict[str, Any]:
        """Generate daily intelligence brief."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=1)

        contents = await self._get_contents(start_date, end_date)

        if not contents:
            return self._empty_report("daily", start_date, end_date)

        report = await self._generate_report(
            contents=contents,
            report_type="daily",
            start_date=start_date,
            end_date=end_date,
        )

        logger.info(
            "daily_report_generated",
            content_count=len(contents),
            start_date=start_date.isoformat(),
        )

        return report

    async def generate_weekly(self) -> dict[str, Any]:
        """Generate weekly intelligence report."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)

        contents = await self._get_contents(start_date, end_date)

        if not contents:
            return self._empty_report("weekly", start_date, end_date)

        report = await self._generate_report(
            contents=contents,
            report_type="weekly",
            start_date=start_date,
            end_date=end_date,
        )

        logger.info(
            "weekly_report_generated",
            content_count=len(contents),
            start_date=start_date.isoformat(),
        )

        return report

    async def generate_custom(
        self,
        topic: str,
        days: int = 30,
    ) -> dict[str, Any]:
        """Generate custom report for a specific topic."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        contents = await self._get_contents(start_date, end_date, topic=topic)

        if not contents:
            return self._empty_report("custom", start_date, end_date, topic=topic)

        report = await self._generate_report(
            contents=contents,
            report_type="custom",
            start_date=start_date,
            end_date=end_date,
            topic=topic,
        )

        return report

    async def _get_contents(
        self,
        start_date: datetime,
        end_date: datetime,
        topic: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get relevant contents from database."""
        from sqlalchemy import select, desc

        async with get_db_context() as db:
            query = (
                select(Content)
                .where(
                    Content.status.in_([ContentStatus.PROCESSED, ContentStatus.NOTIFIED]),
                    Content.collected_at >= start_date,
                    Content.collected_at <= end_date,
                )
                .order_by(desc(Content.importance_score))
                .limit(limit)
            )

            result = await db.execute(query)
            contents = result.scalars().all()

            return [
                {
                    "id": str(c.id),
                    "title": c.title,
                    "summary": c.summary,
                    "url": c.url,
                    "categories": c.categories,
                    "entities": c.entities,
                    "importance_score": c.importance_score,
                    "published_at": c.published_at.isoformat() if c.published_at else None,
                    "matched_keywords": c.matched_keywords,
                }
                for c in contents
            ]

    async def _generate_report(
        self,
        contents: list[dict[str, Any]],
        report_type: str,
        start_date: datetime,
        end_date: datetime,
        topic: str | None = None,
    ) -> dict[str, Any]:
        """Generate report using AI."""
        # Prepare content summaries for AI
        content_text = self._format_contents_for_ai(contents[:50])  # Limit for context

        # Generate report based on type
        if report_type == "daily":
            prompt = self._get_daily_prompt(content_text, start_date)
        elif report_type == "weekly":
            prompt = self._get_weekly_prompt(content_text, start_date, end_date)
        else:
            prompt = self._get_custom_prompt(content_text, topic or "", start_date, end_date)

        response = await self.ai.request(prompt, task_type=AITaskType.ANALYZE)

        # Parse AI response
        import json
        try:
            report_content = json.loads(response.content)
        except json.JSONDecodeError:
            report_content = {"raw_analysis": response.content}

        return {
            "id": f"{report_type}_{end_date.strftime('%Y%m%d')}",
            "type": report_type,
            "topic": topic,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "generated_at": datetime.utcnow().isoformat(),
            "content_count": len(contents),
            "report": report_content,
            "sources": [{"title": c["title"], "url": c["url"]} for c in contents[:10]],
        }

    def _format_contents_for_ai(self, contents: list[dict[str, Any]]) -> str:
        """Format contents for AI analysis."""
        lines = []
        for i, content in enumerate(contents, 1):
            lines.append(f"{i}. {content['title']}")
            if content.get("summary"):
                lines.append(f"   Summary: {content['summary']}")
            if content.get("categories"):
                lines.append(f"   Categories: {', '.join(content['categories'])}")
            lines.append("")
        return "\n".join(lines)

    def _get_daily_prompt(self, content_text: str, date: datetime) -> str:
        """Get prompt for daily report."""
        return f"""Generate a daily AI industry intelligence brief for {date.strftime('%Y-%m-%d')}.

Based on these news items:
{content_text}

Create a JSON report with:
1. "headline": One-sentence overview of the day's most important development
2. "top_stories": Array of 3-5 most important stories with:
   - "title": Story title
   - "summary": 2-3 sentence summary
   - "impact": Why this matters (1 sentence)
   - "importance": "high", "medium", or "low"
3. "trends": Array of 2-3 emerging trends observed
4. "keyword_stats": Object with keyword categories and their mention counts
5. "notable_companies": Array of companies that were prominently mentioned
6. "outlook": Brief outlook for tomorrow based on today's developments

Return ONLY valid JSON."""

    def _get_weekly_prompt(
        self, content_text: str, start_date: datetime, end_date: datetime
    ) -> str:
        """Get prompt for weekly report."""
        return f"""Generate a weekly AI industry intelligence report for {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}.

Based on these news items:
{content_text}

Create a comprehensive JSON report with:
1. "executive_summary": 3-4 sentence overview of the week
2. "key_developments": Array of 5-7 major developments with:
   - "title": Development title
   - "description": Detailed description (3-4 sentences)
   - "implications": Business/industry implications
   - "category": Category (e.g., "Product Launch", "Funding", "Partnership")
3. "trend_analysis": Array of 3-5 trends with:
   - "trend": Trend name
   - "evidence": Supporting evidence from the week's news
   - "trajectory": "rising", "stable", or "declining"
4. "company_spotlight": Analysis of 3-5 most active companies
5. "technology_focus": Deep dive on 2-3 key technologies mentioned
6. "market_signals": Any market-relevant signals observed
7. "next_week_watchlist": 3-5 things to watch next week

Return ONLY valid JSON."""

    def _get_custom_prompt(
        self,
        content_text: str,
        topic: str,
        start_date: datetime,
        end_date: datetime,
    ) -> str:
        """Get prompt for custom topic report."""
        return f"""Generate a focused intelligence report on "{topic}" covering {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}.

Based on these relevant news items:
{content_text}

Create a focused JSON report with:
1. "overview": Executive summary of {topic} developments
2. "timeline": Chronological array of key events
3. "key_players": Companies and people involved
4. "technical_details": Any technical information mentioned
5. "market_impact": Market and business implications
6. "competitive_landscape": How different players are positioned
7. "future_outlook": Predictions and expected developments
8. "recommendations": Actionable insights

Return ONLY valid JSON."""

    def _empty_report(
        self,
        report_type: str,
        start_date: datetime,
        end_date: datetime,
        topic: str | None = None,
    ) -> dict[str, Any]:
        """Return empty report when no content available."""
        return {
            "id": f"{report_type}_{end_date.strftime('%Y%m%d')}",
            "type": report_type,
            "topic": topic,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "generated_at": datetime.utcnow().isoformat(),
            "content_count": 0,
            "report": {
                "message": "No content available for the specified period.",
            },
            "sources": [],
        }
