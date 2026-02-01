#!/usr/bin/env python3
"""Live crawling test script - no database required."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_rss_crawlers():
    """Test RSS crawlers with live feeds."""
    from src.crawlers.news.rss_crawler import RSSCrawler, AI_NEWS_RSS_SOURCES

    print("=" * 70)
    print("🔍 RSS Crawler Live Test")
    print("=" * 70)

    total_articles = 0
    successful = 0
    failed = 0

    for source in AI_NEWS_RSS_SOURCES:
        print(f"\n📰 {source['name']}")
        print(f"   URL: {source['url']}")

        crawler = RSSCrawler(f"test-{source['name']}", source["url"])

        try:
            results = await crawler.crawl()
            total_articles += len(results)
            successful += 1

            print(f"   ✅ Found {len(results)} articles")

            # Show first 2 articles
            for r in results[:2]:
                title = r.title[:55] + "..." if len(r.title) > 55 else r.title
                print(f"      • {title}")
                if r.published_at:
                    print(f"        📅 {r.published_at.strftime('%Y-%m-%d %H:%M')}")

        except Exception as e:
            failed += 1
            print(f"   ❌ Error: {str(e)[:50]}")

        finally:
            await crawler.close()

    print("\n" + "=" * 70)
    print(f"📊 Summary: {successful} sources OK, {failed} failed, {total_articles} total articles")
    print("=" * 70)


async def test_keyword_matching():
    """Test keyword matching with sample articles."""
    from src.processors.keyword_matcher import KeywordMatcher, DEFAULT_AI_KEYWORDS

    print("\n" + "=" * 70)
    print("🔑 Keyword Matcher Test")
    print("=" * 70)

    matcher = KeywordMatcher(DEFAULT_AI_KEYWORDS, enable_semantic=False)

    test_texts = [
        "OpenAI releases GPT-5 with enhanced reasoning capabilities",
        "Tesla's FSD v13 shows significant improvements in autonomous driving",
        "Figure AI raises $675M for humanoid robot development",
        "NVIDIA announces new AI chips for data centers",
        "Microsoft integrates Copilot across all Office products",
        "Boston Dynamics showcases new Atlas robot capabilities",
        "Anthropic's Claude demonstrates improved coding abilities",
        "Google DeepMind achieves breakthrough in protein folding",
    ]

    for text in test_texts:
        results = await matcher.match(text)
        keywords = [f"{r.keyword}({r.keyword_group})" for r in results]

        print(f"\n📝 \"{text[:50]}...\"")
        if keywords:
            print(f"   🏷️  Matched: {', '.join(keywords)}")
        else:
            print("   ⚠️  No matches")


async def test_ai_processor_mock():
    """Test AI processor structure (without actual API calls)."""
    print("\n" + "=" * 70)
    print("🤖 AI Processor Structure Test")
    print("=" * 70)

    from src.processors.ai_processor import AIContentProcessor
    from src.core.ai_orchestrator import AIOrchestrator, AITaskType, TASK_PROVIDER_MAP

    # Test orchestrator configuration
    orchestrator = AIOrchestrator()
    available = orchestrator.get_available_providers()

    print(f"\n📡 Available AI Providers: {[p.value for p in available] if available else 'None configured'}")

    print("\n📋 Task-Provider Mapping:")
    for task, providers in TASK_PROVIDER_MAP.items():
        print(f"   {task.value}: {' → '.join([p.value for p in providers])}")

    # Test processor initialization
    processor = AIContentProcessor()
    print("\n✅ AIContentProcessor initialized successfully")


async def main():
    """Run all tests."""
    print("\n" + "🚀" * 35)
    print("       CRAWL AI - Live Integration Test")
    print("🚀" * 35 + "\n")

    await test_rss_crawlers()
    await test_keyword_matching()
    await test_ai_processor_mock()

    print("\n" + "✨" * 35)
    print("       All Tests Completed!")
    print("✨" * 35 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
