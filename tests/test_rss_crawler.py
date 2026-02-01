"""Test RSS crawler functionality."""

import pytest
from src.crawlers.news.rss_crawler import RSSCrawler, AI_NEWS_RSS_SOURCES


@pytest.mark.asyncio
async def test_rss_crawler_techcrunch():
    """Test crawling TechCrunch AI RSS feed."""
    url = "https://techcrunch.com/category/artificial-intelligence/feed/"
    crawler = RSSCrawler("test-tc", url)

    try:
        results = await crawler.crawl()

        assert len(results) > 0, "Should return at least one result"

        # Check first result structure
        first = results[0]
        assert first.url, "Should have URL"
        assert first.title, "Should have title"
        assert first.content_hash, "Should have content hash"

        print(f"\n✅ TechCrunch: Found {len(results)} articles")
        for r in results[:3]:
            print(f"   - {r.title[:60]}...")

    finally:
        await crawler.close()


@pytest.mark.asyncio
async def test_rss_crawler_multiple_sources():
    """Test crawling multiple RSS sources."""
    results_summary = []

    for source in AI_NEWS_RSS_SOURCES[:5]:  # Test first 5 sources
        crawler = RSSCrawler(f"test-{source['name']}", source["url"])

        try:
            results = await crawler.crawl()
            results_summary.append({
                "name": source["name"],
                "count": len(results),
                "status": "✅" if len(results) > 0 else "⚠️",
            })
        except Exception as e:
            results_summary.append({
                "name": source["name"],
                "count": 0,
                "status": f"❌ {str(e)[:30]}",
            })
        finally:
            await crawler.close()

    print("\n" + "=" * 60)
    print("RSS Crawler Test Results")
    print("=" * 60)
    for r in results_summary:
        print(f"{r['status']} {r['name']}: {r['count']} articles")


@pytest.mark.asyncio
async def test_rss_content_hash_uniqueness():
    """Test that content hashes are unique."""
    url = "https://techcrunch.com/category/artificial-intelligence/feed/"
    crawler = RSSCrawler("test-hash", url)

    try:
        results = await crawler.crawl()

        hashes = [r.content_hash for r in results]
        unique_hashes = set(hashes)

        assert len(hashes) == len(unique_hashes), "All content hashes should be unique"

    finally:
        await crawler.close()
