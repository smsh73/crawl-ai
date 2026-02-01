#!/usr/bin/env python3
"""Manual crawl script for testing."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import get_db_context
from src.core.models import Source, SourceType
from src.crawlers.news import RSSCrawler, WebNewsCrawler
from src.crawlers.base import CrawlerConfig


async def crawl_single_source(source_url: str, source_type: str = "rss"):
    """Crawl a single source for testing."""
    print(f"Crawling: {source_url}")
    print("-" * 60)

    if source_type == "rss":
        crawler = RSSCrawler("test", source_url)
    else:
        crawler = WebNewsCrawler("test", source_url)

    try:
        results = await crawler.crawl()
        print(f"\nFound {len(results)} items:\n")

        for i, result in enumerate(results[:10], 1):
            print(f"{i}. {result.title}")
            print(f"   URL: {result.url}")
            if result.published_at:
                print(f"   Date: {result.published_at}")
            print()

    except Exception as e:
        print(f"Error: {e}")

    finally:
        await crawler.close()


async def crawl_all_sources():
    """Crawl all configured sources."""
    from sqlalchemy import select

    async with get_db_context() as db:
        result = await db.execute(select(Source).where(Source.status == "active"))
        sources = result.scalars().all()

        print(f"Found {len(sources)} active sources\n")

        for source in sources:
            print(f"\n{'=' * 60}")
            print(f"Crawling: {source.name}")
            print(f"URL: {source.url}")
            print(f"Type: {source.source_type}")
            print("=" * 60)

            if source.source_type == SourceType.RSS:
                crawler = RSSCrawler(str(source.id), source.url)
            else:
                config = CrawlerConfig(**(source.config or {}))
                crawler = WebNewsCrawler(str(source.id), source.url, config)

            try:
                results = await crawler.crawl()
                print(f"Found {len(results)} items")

                for result in results[:3]:
                    print(f"  - {result.title[:60]}...")

            except Exception as e:
                print(f"Error: {e}")

            finally:
                await crawler.close()


async def main():
    """Run crawl based on command line args."""
    if len(sys.argv) > 1:
        url = sys.argv[1]
        source_type = sys.argv[2] if len(sys.argv) > 2 else "rss"
        await crawl_single_source(url, source_type)
    else:
        await crawl_all_sources()


if __name__ == "__main__":
    asyncio.run(main())
