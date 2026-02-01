"""Database models for Crawl AI."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def generate_uuid() -> str:
    """Generate UUID as string for SQLite compatibility."""
    return str(uuid4())


class SourceType(str, Enum):
    """Types of crawling sources."""

    RSS = "rss"
    WEB = "web"
    API = "api"
    YOUTUBE = "youtube"
    GITHUB = "github"


class SourceStatus(str, Enum):
    """Status of a source."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending"


class JobStatus(str, Enum):
    """Status of a job execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ContentStatus(str, Enum):
    """Status of collected content."""

    NEW = "new"
    PROCESSED = "processed"
    NOTIFIED = "notified"
    ARCHIVED = "archived"


# -----------------------------------------------------------------------------
# Keyword Management
# -----------------------------------------------------------------------------


class KeywordGroup(Base):
    """Group of related keywords."""

    __tablename__ = "keyword_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    keywords: Mapped[list["Keyword"]] = relationship(back_populates="group", cascade="all, delete")


class Keyword(Base):
    """Individual keyword for matching."""

    __tablename__ = "keywords"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    group_id: Mapped[str] = mapped_column(ForeignKey("keyword_groups.id", ondelete="CASCADE"))
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    synonyms: Mapped[list[str] | None] = mapped_column(JSON)  # Alternative spellings
    weight: Mapped[float] = mapped_column(Float, default=1.0)  # Importance weight
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    group: Mapped["KeywordGroup"] = relationship(back_populates="keywords")


# -----------------------------------------------------------------------------
# Source Management
# -----------------------------------------------------------------------------


class Source(Base):
    """Crawling source configuration."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=SourceStatus.ACTIVE.value)

    # Crawling configuration
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # Selectors, headers, etc.
    crawl_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)

    # Metadata
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)

    # AI-generated config (for self-healing)
    ai_generated_config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    config_version: Mapped[int] = mapped_column(Integer, default=1)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    contents: Mapped[list["Content"]] = relationship(back_populates="source")
    schedules: Mapped[list["Schedule"]] = relationship(
        secondary="schedule_sources", back_populates="sources"
    )


# -----------------------------------------------------------------------------
# Schedule Management
# -----------------------------------------------------------------------------


class Schedule(Base):
    """Crawling schedule configuration."""

    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Schedule configuration
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "0 * * * *"
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Seoul")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Task configuration
    task_type: Mapped[str] = mapped_column(String(50), default="crawl")  # crawl, process, report
    keyword_group_ids: Mapped[list[str] | None] = mapped_column(JSON)

    # Timestamps
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    sources: Mapped[list["Source"]] = relationship(
        secondary="schedule_sources", back_populates="schedules"
    )
    executions: Mapped[list["JobExecution"]] = relationship(back_populates="schedule")


class ScheduleSource(Base):
    """Many-to-many relationship between schedules and sources."""

    __tablename__ = "schedule_sources"

    schedule_id: Mapped[str] = mapped_column(
        ForeignKey("schedules.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True
    )


# -----------------------------------------------------------------------------
# Job Execution
# -----------------------------------------------------------------------------


class JobExecution(Base):
    """Record of a job execution."""

    __tablename__ = "job_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    schedule_id: Mapped[str | None] = mapped_column(ForeignKey("schedules.id", ondelete="SET NULL"))
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=JobStatus.PENDING.value)

    # Execution details
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    items_collected: Mapped[int] = mapped_column(Integer, default=0)
    items_saved: Mapped[int] = mapped_column(Integer, default=0)
    items_notified: Mapped[int] = mapped_column(Integer, default=0)

    # Error handling
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Job Metadata
    job_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    schedule: Mapped["Schedule | None"] = relationship(back_populates="executions")


# -----------------------------------------------------------------------------
# Content
# -----------------------------------------------------------------------------


class Content(Base):
    """Collected content from sources."""

    __tablename__ = "contents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))

    # Content data
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)  # For deduplication

    # AI-processed data
    summary: Mapped[str | None] = mapped_column(Text)
    categories: Mapped[list[str] | None] = mapped_column(JSON)
    entities: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # Extracted entities
    sentiment: Mapped[str | None] = mapped_column(String(50))
    relevance_score: Mapped[float | None] = mapped_column(Float)
    importance_score: Mapped[float | None] = mapped_column(Float)

    # Keyword matching
    matched_keywords: Mapped[list[str] | None] = mapped_column(JSON)
    matched_keyword_groups: Mapped[list[str] | None] = mapped_column(JSON)

    # Status
    status: Mapped[str] = mapped_column(String(50), default=ContentStatus.NEW.value)

    # Timestamps
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    collected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    source: Mapped["Source"] = relationship(back_populates="contents")


# -----------------------------------------------------------------------------
# Notifications
# -----------------------------------------------------------------------------


class NotificationConfig(Base):
    """Notification configuration."""

    __tablename__ = "notification_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(50), nullable=False)  # slack, email, webhook
    channel_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Filtering
    keyword_group_ids: Mapped[list[str] | None] = mapped_column(JSON)
    min_importance_score: Mapped[float] = mapped_column(Float, default=0.0)
    min_relevance_score: Mapped[float] = mapped_column(Float, default=0.0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class NotificationLog(Base):
    """Log of sent notifications."""

    __tablename__ = "notification_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    config_id: Mapped[str] = mapped_column(
        ForeignKey("notification_configs.id", ondelete="CASCADE")
    )
    content_id: Mapped[str] = mapped_column(ForeignKey("contents.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # sent, failed
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())