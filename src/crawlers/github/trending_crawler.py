"""GitHub Trending 크롤러."""

from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import structlog
from bs4 import BeautifulSoup

from ..base import BaseCrawler, CrawlerConfig, CrawlResult

logger = structlog.get_logger()


class GitHubTrendingCrawler(BaseCrawler):
    """
    GitHub Trending 저장소 크롤러.

    Supports:
    - Daily/Weekly/Monthly trending
    - Language filtering (Python, TypeScript, etc.)
    - Topic filtering (AI, ML, etc.)
    """

    BASE_URL = "https://github.com"

    def __init__(
        self,
        source_id: str,
        language: str | None = None,
        since: str = "daily",  # daily, weekly, monthly
        spoken_language: str | None = None,
        **kwargs,
    ):
        # Build trending URL
        url = self._build_url(language, since, spoken_language)
        super().__init__(source_id, url, **kwargs)

        self.language = language
        self.since = since

    def _build_url(
        self,
        language: str | None,
        since: str,
        spoken_language: str | None,
    ) -> str:
        """Build GitHub trending URL."""
        url = f"{self.BASE_URL}/trending"

        if language:
            url += f"/{language.lower()}"

        params = []
        if since != "daily":
            params.append(f"since={since}")
        if spoken_language:
            params.append(f"spoken_language_code={spoken_language}")

        if params:
            url += "?" + "&".join(params)

        return url

    async def parse(self, html: str) -> list[CrawlResult]:
        """Parse GitHub trending page."""
        results: list[CrawlResult] = []
        soup = BeautifulSoup(html, "lxml")

        # Find repository articles
        repo_items = soup.select("article.Box-row")

        for item in repo_items:
            try:
                result = self._parse_repo_item(item)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning("github_item_parse_failed", error=str(e))

        logger.info(
            "github_trending_parse_complete",
            source_id=self.source_id,
            results_count=len(results),
            language=self.language,
            since=self.since,
        )

        return results

    def _parse_repo_item(self, item: BeautifulSoup) -> CrawlResult | None:
        """Parse a single repository item."""
        # Repository name and URL
        repo_link = item.select_one("h2 a, h1 a")
        if not repo_link:
            return None

        href = repo_link.get("href", "")
        if not href:
            return None

        url = urljoin(self.BASE_URL, href)
        repo_name = href.strip("/")  # e.g., "owner/repo"

        # Description
        desc_elem = item.select_one("p.col-9, p.my-1, p.pr-4")
        description = desc_elem.get_text(strip=True) if desc_elem else ""

        # Build title
        title = f"⭐ {repo_name}"
        if description:
            title = f"{repo_name}: {description[:100]}"

        # Metadata
        metadata: dict[str, Any] = {
            "repo_name": repo_name,
            "type": "github_trending",
            "since": self.since,
        }

        # Language
        lang_elem = item.select_one("[itemprop='programmingLanguage'], span.d-inline-block.ml-0")
        if lang_elem:
            metadata["language"] = lang_elem.get_text(strip=True)

        # Stars
        star_elem = item.select_one("a[href$='/stargazers']")
        if star_elem:
            stars_text = star_elem.get_text(strip=True).replace(",", "")
            try:
                metadata["stars"] = int(stars_text)
            except ValueError:
                metadata["stars_text"] = stars_text

        # Forks
        fork_elem = item.select_one("a[href$='/forks']")
        if fork_elem:
            forks_text = fork_elem.get_text(strip=True).replace(",", "")
            try:
                metadata["forks"] = int(forks_text)
            except ValueError:
                pass

        # Stars today/this week
        today_elem = item.select_one("span.d-inline-block.float-sm-right, span.float-sm-right")
        if today_elem:
            today_text = today_elem.get_text(strip=True)
            metadata["trending_stars"] = today_text

        # Built by (contributors)
        contributors = item.select("a[data-hovercard-type='user'] img")
        if contributors:
            metadata["contributors"] = len(contributors)

        # Topics/Tags
        topics = item.select("a.topic-tag")
        if topics:
            metadata["topics"] = [t.get_text(strip=True) for t in topics[:5]]

        return CrawlResult(
            url=url,
            title=title,
            content=description,
            published_at=datetime.utcnow(),  # Trending is always current
            metadata=metadata,
        )


class GitHubSearchCrawler(BaseCrawler):
    """
    GitHub Repository Search 크롤러.

    키워드 기반 저장소 검색.
    """

    BASE_URL = "https://github.com"

    def __init__(
        self,
        source_id: str,
        query: str,
        sort: str = "stars",  # stars, forks, updated
        language: str | None = None,
        **kwargs,
    ):
        url = self._build_search_url(query, sort, language)
        super().__init__(source_id, url, **kwargs)

        self.query = query
        self.sort = sort

    def _build_search_url(
        self,
        query: str,
        sort: str,
        language: str | None,
    ) -> str:
        """Build GitHub search URL."""
        from urllib.parse import quote_plus

        search_query = query
        if language:
            search_query += f" language:{language}"

        return f"{self.BASE_URL}/search?q={quote_plus(search_query)}&type=repositories&s={sort}"

    async def parse(self, html: str) -> list[CrawlResult]:
        """Parse GitHub search results."""
        results: list[CrawlResult] = []
        soup = BeautifulSoup(html, "lxml")

        # Find repository items
        repo_items = soup.select("div.search-title a, li.repo-list-item")

        for item in repo_items:
            try:
                result = self._parse_search_item(item)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning("github_search_item_parse_failed", error=str(e))

        return results

    def _parse_search_item(self, item: BeautifulSoup) -> CrawlResult | None:
        """Parse a single search result item."""
        # For search-title a elements
        if item.name == "a":
            href = item.get("href", "")
            if not href or not href.startswith("/"):
                return None

            url = urljoin(self.BASE_URL, href)
            repo_name = href.strip("/")

            return CrawlResult(
                url=url,
                title=repo_name,
                content=None,
                published_at=datetime.utcnow(),
                metadata={
                    "repo_name": repo_name,
                    "type": "github_search",
                    "query": self.query,
                },
            )

        # For more complex structures, similar to trending parser
        return None


# AI/ML related search queries
AI_GITHUB_QUERIES = [
    "LLM framework",
    "AI agent",
    "RAG retrieval",
    "transformer model",
    "diffusion model",
    "autonomous driving",
    "humanoid robot",
    "computer vision",
    "NLP natural language",
]
