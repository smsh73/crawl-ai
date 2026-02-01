"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from src.core.config import settings

# Create Celery app
celery_app = Celery(
    "crawl_ai",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.scheduler.tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.scheduler_timezone,
    enable_utc=True,

    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=600,  # 10 minutes max
    task_soft_time_limit=540,  # 9 minutes soft limit

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=4,

    # Result backend settings
    result_expires=3600,  # 1 hour

    # Task routing
    task_routes={
        "src.scheduler.tasks.crawl_*": {"queue": "crawl"},
        "src.scheduler.tasks.process_*": {"queue": "process"},
        "src.scheduler.tasks.send_*": {"queue": "notify"},
        "src.scheduler.tasks.generate_*": {"queue": "report"},
    },

    # Default queue
    task_default_queue="default",
)

# Beat schedule (default schedules)
# These can be overridden by database-driven schedules
celery_app.conf.beat_schedule = {
    # News crawling - every hour
    "crawl-news-hourly": {
        "task": "src.scheduler.tasks.crawl_all_sources",
        "schedule": crontab(minute=0),  # Every hour at :00
        "args": (["rss", "web"],),
        "options": {"queue": "crawl"},
    },

    # Process new content - every 30 minutes
    "process-content": {
        "task": "src.scheduler.tasks.process_pending_content",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "process"},
    },

    # Send notifications - every 15 minutes
    "send-notifications": {
        "task": "src.scheduler.tasks.send_pending_notifications",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "notify"},
    },

    # Daily report - weekdays at 8:00 AM
    "daily-report": {
        "task": "src.scheduler.tasks.generate_daily_report",
        "schedule": crontab(hour=8, minute=0, day_of_week="1-5"),
        "options": {"queue": "report"},
    },

    # Weekly report - Monday at 9:00 AM
    "weekly-report": {
        "task": "src.scheduler.tasks.generate_weekly_report",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),
        "options": {"queue": "report"},
    },

    # Health check - every 5 minutes
    "health-check": {
        "task": "src.scheduler.tasks.health_check",
        "schedule": crontab(minute="*/5"),
    },
}

# Database-driven dynamic schedules will be loaded separately
# using celery-redbeat or django-celery-beat pattern
