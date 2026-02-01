#!/usr/bin/env python3
"""Initialize database with default data."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import init_db, get_db_context
from src.core.models import KeywordGroup, Keyword, Source, SourceType, Schedule
from src.crawlers.news.rss_crawler import AI_NEWS_RSS_SOURCES
from src.processors.keyword_matcher import DEFAULT_AI_KEYWORDS


async def init_keywords():
    """Initialize default AI keyword groups."""
    async with get_db_context() as db:
        for group_name, keywords in DEFAULT_AI_KEYWORDS.items():
            # Check if group exists
            from sqlalchemy import select

            existing = await db.execute(
                select(KeywordGroup).where(KeywordGroup.name == group_name)
            )
            if existing.scalar_one_or_none():
                print(f"  Keyword group '{group_name}' already exists, skipping...")
                continue

            # Create group
            group = KeywordGroup(name=group_name, description=f"Default {group_name} keywords")
            db.add(group)
            await db.flush()

            # Add keywords
            for keyword, synonyms in keywords.items():
                kw = Keyword(
                    group_id=group.id,
                    keyword=keyword,
                    synonyms=synonyms if synonyms else None,
                )
                db.add(kw)

            print(f"  Created keyword group: {group_name} ({len(keywords)} keywords)")


async def init_sources():
    """Initialize default RSS sources."""
    async with get_db_context() as db:
        for source_data in AI_NEWS_RSS_SOURCES:
            # Check if source exists
            from sqlalchemy import select

            existing = await db.execute(
                select(Source).where(Source.url == source_data["url"])
            )
            if existing.scalar_one_or_none():
                print(f"  Source '{source_data['name']}' already exists, skipping...")
                continue

            source = Source(
                name=source_data["name"],
                url=source_data["url"],
                source_type=SourceType.RSS,
                crawl_interval_minutes=60,
            )
            db.add(source)
            print(f"  Created source: {source_data['name']}")


async def init_schedules():
    """Initialize default schedules."""
    async with get_db_context() as db:
        from sqlalchemy import select

        # Check if any schedule exists
        existing = await db.execute(select(Schedule).limit(1))
        if existing.scalar_one_or_none():
            print("  Schedules already exist, skipping...")
            return

        # Get all sources
        sources_result = await db.execute(select(Source))
        sources = sources_result.scalars().all()

        # Create hourly news crawl schedule
        schedule = Schedule(
            name="Hourly News Crawl",
            description="Crawl all RSS news sources every hour",
            cron_expression="0 * * * *",
            timezone="Asia/Seoul",
            task_type="crawl",
        )
        db.add(schedule)
        await db.flush()

        # Link all RSS sources
        for source in sources:
            if source.source_type == SourceType.RSS:
                schedule.sources.append(source)

        print(f"  Created schedule: Hourly News Crawl ({len(schedule.sources)} sources)")


async def main():
    """Run database initialization."""
    print("=" * 60)
    print("Crawl AI - Database Initialization")
    print("=" * 60)

    print("\n1. Creating database tables...")
    await init_db()
    print("   Done!")

    print("\n2. Initializing keyword groups...")
    await init_keywords()

    print("\n3. Initializing RSS sources...")
    await init_sources()

    print("\n4. Initializing schedules...")
    await init_schedules()

    print("\n" + "=" * 60)
    print("Database initialization complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
