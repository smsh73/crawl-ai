"""YouTube Channel/Search 크롤러."""

import re
from datetime import datetime
from typing import Any

import structlog

from ..base import BaseCrawler, CrawlResult

logger = structlog.get_logger()


class YouTubeCrawler(BaseCrawler):
    """
    YouTube 크롤러.

    Note: YouTube는 API 사용을 권장합니다.
    이 크롤러는 RSS 피드 기반으로 동작합니다.
    """

    # YouTube channel RSS feed format
    CHANNEL_RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    PLAYLIST_RSS_URL = "https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"

    def __init__(
        self,
        source_id: str,
        channel_id: str | None = None,
        playlist_id: str | None = None,
        **kwargs,
    ):
        if channel_id:
            url = self.CHANNEL_RSS_URL.format(channel_id=channel_id)
        elif playlist_id:
            url = self.PLAYLIST_RSS_URL.format(playlist_id=playlist_id)
        else:
            raise ValueError("Either channel_id or playlist_id must be provided")

        super().__init__(source_id, url, **kwargs)

        self.channel_id = channel_id
        self.playlist_id = playlist_id

    async def parse(self, html: str) -> list[CrawlResult]:
        """Parse YouTube RSS feed."""
        import feedparser

        results: list[CrawlResult] = []
        feed = feedparser.parse(html)

        for entry in feed.entries:
            try:
                result = self._parse_entry(entry)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning("youtube_entry_parse_failed", error=str(e))

        logger.info(
            "youtube_parse_complete",
            source_id=self.source_id,
            results_count=len(results),
        )

        return results

    def _parse_entry(self, entry: Any) -> CrawlResult | None:
        """Parse a single YouTube feed entry."""
        video_id = getattr(entry, "yt_videoid", None)
        if not video_id:
            # Try to extract from link
            link = getattr(entry, "link", "")
            match = re.search(r"v=([a-zA-Z0-9_-]+)", link)
            if match:
                video_id = match.group(1)

        if not video_id:
            return None

        url = f"https://www.youtube.com/watch?v={video_id}"
        title = getattr(entry, "title", "")

        # Get description/summary
        content = None
        if hasattr(entry, "media_group"):
            media = entry.media_group
            if hasattr(media, "media_description"):
                content = media.media_description

        if not content and hasattr(entry, "summary"):
            content = entry.summary

        # Published date
        published_at = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_at = datetime(*entry.published_parsed[:6])
            except Exception:
                pass

        # Metadata
        metadata: dict[str, Any] = {
            "video_id": video_id,
            "type": "youtube_video",
        }

        # Channel info
        if hasattr(entry, "author"):
            metadata["channel_name"] = entry.author

        if hasattr(entry, "yt_channelid"):
            metadata["channel_id"] = entry.yt_channelid

        # Thumbnail
        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            metadata["thumbnail"] = entry.media_thumbnail[0].get("url")

        # Views (if available)
        if hasattr(entry, "media_statistics"):
            stats = entry.media_statistics
            if hasattr(stats, "views"):
                metadata["views"] = stats.views

        return CrawlResult(
            url=url,
            title=title,
            content=content,
            published_at=published_at,
            metadata=metadata,
        )


# AI/Tech YouTube channels
AI_YOUTUBE_CHANNELS = [
    {
        "name": "Two Minute Papers",
        "channel_id": "UCbfYPyITQ-7l4upoX8nvctg",
    },
    {
        "name": "Yannic Kilcher",
        "channel_id": "UCZHmQk67mSJgfCCTn7xBfew",
    },
    {
        "name": "AI Explained",
        "channel_id": "UCNJ1Ymd5yFuUPtn21xtRbbw",
    },
    {
        "name": "Fireship",
        "channel_id": "UCsBjURrPoezykLs9EqgamOA",
    },
    {
        "name": "Lex Fridman",
        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",
    },
    {
        "name": "sentdex",
        "channel_id": "UCfzlCWGWYyIQ0aLC5w48gBQ",
    },
    {
        "name": "3Blue1Brown",
        "channel_id": "UCYO_jab_esuFRV4b17AJtAw",
    },
    {
        "name": "Andrej Karpathy",
        "channel_id": "UCXUPKJO5MZQN11PqgIvyuvQ",
    },
]
