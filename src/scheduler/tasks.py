"""Celery tasks for crawling, processing, and notifications."""

import asyncio
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from celery import shared_task

from src.core.database import get_db_context
from src.core.models import Content, ContentStatus, JobExecution, JobStatus, Source, SourceStatus

logger = structlog.get_logger()


def run_async(coro):
    """Helper to run async code in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# -----------------------------------------------------------------------------
# Crawling Tasks
# -----------------------------------------------------------------------------


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_source(self, source_id: str) -> dict[str, Any]:
    """
    Crawl a single source.

    Args:
        source_id: UUID of the source to crawl

    Returns:
        Dict with crawl results
    """
    return run_async(_crawl_source_async(self, source_id))


async def _crawl_source_async(task, source_id: str) -> dict[str, Any]:
    """Async implementation of crawl_source."""
    from src.crawlers.news import RSSCrawler, WebNewsCrawler
    from src.core.models import SourceType

    job_id = None
    items_collected = 0
    items_saved = 0

    async with get_db_context() as db:
        # Get source
        source = await db.get(Source, UUID(source_id))
        if not source:
            logger.error("crawl_source_not_found", source_id=source_id)
            return {"error": "Source not found"}

        # Create job execution record
        job = JobExecution(
            job_type="crawl",
            status=JobStatus.RUNNING,
            started_at=datetime.utcnow(),
            metadata={"source_id": source_id, "source_name": source.name},
        )
        db.add(job)
        await db.flush()
        job_id = str(job.id)

        try:
            # Select appropriate crawler
            if source.source_type == SourceType.RSS:
                crawler = RSSCrawler(source_id, source.url)
            else:
                from src.crawlers.base import CrawlerConfig
                config = CrawlerConfig(**(source.config or {}))
                crawler = WebNewsCrawler(source_id, source.url, config)

            # Execute crawl
            results = await crawler.crawl()
            items_collected = len(results)

            # Save results
            for result in results:
                # Check for duplicate
                existing = await db.execute(
                    Content.__table__.select().where(
                        Content.content_hash == result.content_hash
                    )
                )
                if existing.first():
                    continue

                content = Content(
                    source_id=source.id,
                    url=result.url,
                    title=result.title,
                    content=result.content,
                    content_hash=result.content_hash,
                    published_at=result.published_at,
                    status=ContentStatus.NEW,
                )
                db.add(content)
                items_saved += 1

            # Update source status
            source.last_crawled_at = datetime.utcnow()
            source.last_success_at = datetime.utcnow()
            source.error_count = 0
            source.status = SourceStatus.ACTIVE

            # Update job
            job.status = JobStatus.COMPLETED
            job.finished_at = datetime.utcnow()
            job.items_collected = items_collected
            job.items_saved = items_saved

            await crawler.close()

            logger.info(
                "crawl_source_success",
                source_id=source_id,
                items_collected=items_collected,
                items_saved=items_saved,
            )

            return {
                "job_id": job_id,
                "source_id": source_id,
                "items_collected": items_collected,
                "items_saved": items_saved,
                "status": "completed",
            }

        except Exception as e:
            logger.error(
                "crawl_source_failed",
                source_id=source_id,
                error=str(e),
            )

            # Update source error status
            source.error_count += 1
            source.last_error = str(e)
            if source.error_count >= 3:
                source.status = SourceStatus.ERROR

            # Update job
            job.status = JobStatus.FAILED
            job.finished_at = datetime.utcnow()
            job.error_message = str(e)

            # Retry if not max retries
            raise task.retry(exc=e)


@shared_task
def crawl_all_sources(source_types: list[str] | None = None) -> dict[str, Any]:
    """
    Crawl all active sources of specified types.

    Args:
        source_types: List of source types to crawl (e.g., ["rss", "web"])

    Returns:
        Dict with task IDs for each source
    """
    return run_async(_crawl_all_sources_async(source_types))


async def _crawl_all_sources_async(source_types: list[str] | None) -> dict[str, Any]:
    """Async implementation of crawl_all_sources."""
    from sqlalchemy import select

    async with get_db_context() as db:
        query = select(Source).where(Source.status == SourceStatus.ACTIVE)

        if source_types:
            query = query.where(Source.source_type.in_(source_types))

        result = await db.execute(query)
        sources = result.scalars().all()

        tasks = {}
        for source in sources:
            task = crawl_source.delay(str(source.id))
            tasks[str(source.id)] = task.id

        logger.info(
            "crawl_all_sources_dispatched",
            source_count=len(sources),
            source_types=source_types,
        )

        return {
            "dispatched": len(tasks),
            "tasks": tasks,
        }


# -----------------------------------------------------------------------------
# Processing Tasks
# -----------------------------------------------------------------------------


@shared_task
def process_content(content_id: str) -> dict[str, Any]:
    """
    Process a single content item with AI.

    Args:
        content_id: UUID of the content to process

    Returns:
        Dict with processing results
    """
    return run_async(_process_content_async(content_id))


async def _process_content_async(content_id: str) -> dict[str, Any]:
    """Async implementation of process_content."""
    from src.processors.ai_processor import AIContentProcessor

    async with get_db_context() as db:
        content = await db.get(Content, UUID(content_id))
        if not content:
            return {"error": "Content not found"}

        processor = AIContentProcessor()
        result = await processor.process(content)

        # Update content with AI results
        content.summary = result.get("summary")
        content.categories = result.get("categories")
        content.entities = result.get("entities")
        content.sentiment = result.get("sentiment")
        content.relevance_score = result.get("relevance_score")
        content.importance_score = result.get("importance_score")
        content.matched_keywords = result.get("matched_keywords")
        content.status = ContentStatus.PROCESSED
        content.processed_at = datetime.utcnow()

        logger.info("process_content_success", content_id=content_id)

        return {
            "content_id": content_id,
            "status": "processed",
            **result,
        }


@shared_task
def process_pending_content() -> dict[str, Any]:
    """Process all pending content items."""
    return run_async(_process_pending_content_async())


async def _process_pending_content_async() -> dict[str, Any]:
    """Async implementation of process_pending_content."""
    from sqlalchemy import select

    async with get_db_context() as db:
        query = select(Content).where(
            Content.status == ContentStatus.NEW
        ).limit(100)  # Process in batches

        result = await db.execute(query)
        contents = result.scalars().all()

        tasks = {}
        for content in contents:
            task = process_content.delay(str(content.id))
            tasks[str(content.id)] = task.id

        return {
            "dispatched": len(tasks),
            "tasks": tasks,
        }


# -----------------------------------------------------------------------------
# Notification Tasks
# -----------------------------------------------------------------------------


@shared_task
def send_notifications(content_id: str) -> dict[str, Any]:
    """Send notifications for a content item."""
    return run_async(_send_notifications_async(content_id))


async def _send_notifications_async(content_id: str) -> dict[str, Any]:
    """Async implementation of send_notifications."""
    from src.notifications.manager import NotificationManager

    async with get_db_context() as db:
        content = await db.get(Content, UUID(content_id))
        if not content:
            return {"error": "Content not found"}

        manager = NotificationManager()
        results = await manager.notify(content)

        content.status = ContentStatus.NOTIFIED
        content.notified_at = datetime.utcnow()

        return {
            "content_id": content_id,
            "notifications_sent": len(results),
        }


@shared_task
def send_pending_notifications() -> dict[str, Any]:
    """Send notifications for all processed content."""
    return run_async(_send_pending_notifications_async())


async def _send_pending_notifications_async() -> dict[str, Any]:
    """Async implementation of send_pending_notifications."""
    from sqlalchemy import select

    async with get_db_context() as db:
        # Find high-importance processed content
        query = select(Content).where(
            Content.status == ContentStatus.PROCESSED,
            Content.importance_score >= 0.7,  # Only important items
        ).limit(50)

        result = await db.execute(query)
        contents = result.scalars().all()

        tasks = {}
        for content in contents:
            task = send_notifications.delay(str(content.id))
            tasks[str(content.id)] = task.id

        return {
            "dispatched": len(tasks),
            "tasks": tasks,
        }


# -----------------------------------------------------------------------------
# Report Tasks
# -----------------------------------------------------------------------------


@shared_task
def generate_daily_report() -> dict[str, Any]:
    """Generate daily intelligence report."""
    return run_async(_generate_daily_report_async())


async def _generate_daily_report_async() -> dict[str, Any]:
    """Async implementation of generate_daily_report."""
    from src.processors.report_generator import ReportGenerator

    generator = ReportGenerator()
    report = await generator.generate_daily()

    logger.info("daily_report_generated", report_id=report.get("id"))

    return report


@shared_task
def generate_weekly_report() -> dict[str, Any]:
    """Generate weekly intelligence report."""
    return run_async(_generate_weekly_report_async())


async def _generate_weekly_report_async() -> dict[str, Any]:
    """Async implementation of generate_weekly_report."""
    from src.processors.report_generator import ReportGenerator

    generator = ReportGenerator()
    report = await generator.generate_weekly()

    logger.info("weekly_report_generated", report_id=report.get("id"))

    return report


# -----------------------------------------------------------------------------
# Utility Tasks
# -----------------------------------------------------------------------------


@shared_task
def health_check() -> dict[str, Any]:
    """Periodic health check task."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }
