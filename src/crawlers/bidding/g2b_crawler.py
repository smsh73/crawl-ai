"""나라장터(G2B) 입찰공고 크롤러."""

import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlencode

import structlog
from bs4 import BeautifulSoup

from ..base import BaseCrawler, CrawlerConfig, CrawlResult

logger = structlog.get_logger()


class G2BCrawler(BaseCrawler):
    """
    나라장터(G2B) 입찰공고 크롤러.

    Supports:
    - 물품/용역/공사 입찰공고 검색
    - 키워드 기반 필터링
    - AI, 인공지능 등 관련 공고 수집
    """

    BASE_URL = "https://www.g2b.go.kr"
    SEARCH_URL = "https://www.g2b.go.kr/pt/menu/selectSubFrame.do"

    def __init__(
        self,
        source_id: str,
        keywords: list[str] | None = None,
        bid_type: str = "all",  # all, goods, service, construction
        **kwargs,
    ):
        # 나라장터 검색 URL 구성
        url = self._build_search_url(keywords, bid_type)
        super().__init__(source_id, url, **kwargs)

        self.keywords = keywords or ["AI", "인공지능", "빅데이터", "클라우드"]
        self.bid_type = bid_type

    def _build_search_url(self, keywords: list[str] | None, bid_type: str) -> str:
        """Build G2B search URL."""
        # 나라장터 기본 검색 URL
        base = "https://www.g2b.go.kr/pt/menu/selectSubFrame.do"

        params = {
            "framesrc": "/pt/menu/frameSubSearchByKeyword.do",
        }

        if keywords:
            params["searchKeyword"] = " ".join(keywords)

        return f"{base}?{urlencode(params)}"

    async def parse(self, html: str) -> list[CrawlResult]:
        """Parse G2B search results."""
        results: list[CrawlResult] = []
        soup = BeautifulSoup(html, "lxml")

        # 나라장터 검색 결과 테이블 파싱
        # Note: 실제 나라장터는 iframe과 복잡한 구조를 가지므로
        # 실제 구현 시 Playwright 사용 권장

        # 공고 목록 찾기 (일반적인 패턴)
        rows = soup.select("table.list_table tbody tr, table.tb_list tbody tr")

        if not rows:
            # 대안 셀렉터 시도
            rows = soup.select("tr[onclick], tr.bg_color1, tr.bg_color2")

        for row in rows:
            try:
                result = self._parse_bid_row(row)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning("g2b_row_parse_failed", error=str(e))

        logger.info(
            "g2b_parse_complete",
            source_id=self.source_id,
            results_count=len(results),
        )

        return results

    def _parse_bid_row(self, row: BeautifulSoup) -> CrawlResult | None:
        """Parse a single bid row."""
        cells = row.select("td")
        if len(cells) < 4:
            return None

        # 공고명 (제목)
        title_cell = row.select_one("td a, td.title a")
        if not title_cell:
            # 다른 패턴 시도
            for cell in cells:
                link = cell.select_one("a")
                if link and len(link.get_text(strip=True)) > 10:
                    title_cell = link
                    break

        if not title_cell:
            return None

        title = title_cell.get_text(strip=True)
        href = title_cell.get("href", "")

        # URL 구성
        if href.startswith("javascript:"):
            # JavaScript 링크에서 공고번호 추출
            match = re.search(r"'(\d+)'", href)
            if match:
                bid_no = match.group(1)
                url = f"{self.BASE_URL}/pt/menu/selectSubFrame.do?bidNo={bid_no}"
            else:
                url = self.BASE_URL
        elif href.startswith("/"):
            url = urljoin(self.BASE_URL, href)
        else:
            url = href or self.BASE_URL

        # 메타데이터 추출
        metadata: dict[str, Any] = {}

        # 공고번호
        bid_no_cell = row.select_one("td:first-child")
        if bid_no_cell:
            metadata["bid_number"] = bid_no_cell.get_text(strip=True)

        # 수요기관
        org_patterns = ["td:nth-child(3)", "td.org", "td:contains('기관')"]
        for pattern in org_patterns:
            org_cell = row.select_one(pattern)
            if org_cell:
                metadata["organization"] = org_cell.get_text(strip=True)
                break

        # 마감일
        date_text = ""
        for cell in cells:
            text = cell.get_text(strip=True)
            if re.search(r"\d{4}[-/]\d{2}[-/]\d{2}", text):
                date_text = text
                break

        published_at = None
        if date_text:
            try:
                # 다양한 날짜 형식 처리
                date_match = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", date_text)
                if date_match:
                    published_at = datetime(
                        int(date_match.group(1)),
                        int(date_match.group(2)),
                        int(date_match.group(3)),
                    )
                    metadata["deadline"] = date_text
            except Exception:
                pass

        # 추정가
        for cell in cells:
            text = cell.get_text(strip=True)
            if "원" in text or re.search(r"[\d,]+원?$", text):
                metadata["estimated_price"] = text
                break

        return CrawlResult(
            url=url,
            title=title,
            content=None,  # 상세 내용은 별도 크롤링 필요
            published_at=published_at,
            metadata=metadata,
        )

    async def crawl_with_keywords(self, keywords: list[str]) -> list[CrawlResult]:
        """Crawl G2B with specific keywords."""
        all_results = []

        for keyword in keywords:
            self.url = self._build_search_url([keyword], self.bid_type)
            logger.info("g2b_crawl_keyword", keyword=keyword)

            try:
                results = await self.crawl()
                all_results.extend(results)
            except Exception as e:
                logger.warning("g2b_keyword_crawl_failed", keyword=keyword, error=str(e))

        # 중복 제거
        seen = set()
        unique_results = []
        for r in all_results:
            if r.content_hash not in seen:
                seen.add(r.content_hash)
                unique_results.append(r)

        return unique_results


# AI 관련 입찰 키워드
AI_BID_KEYWORDS = [
    "인공지능",
    "AI",
    "머신러닝",
    "딥러닝",
    "빅데이터",
    "데이터분석",
    "클라우드",
    "챗봇",
    "자연어처리",
    "영상분석",
    "음성인식",
    "자율주행",
    "로봇",
    "RPA",
    "자동화",
]
