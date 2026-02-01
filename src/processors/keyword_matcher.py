"""Keyword matching engine with semantic similarity support."""

import re
from dataclasses import dataclass
from typing import Any

import structlog

from src.core.ai_orchestrator import AIOrchestrator, AITaskType

logger = structlog.get_logger()


@dataclass
class MatchResult:
    """Result of keyword matching."""

    keyword: str
    keyword_group: str
    match_type: str  # exact, synonym, semantic
    score: float
    matched_text: str | None = None


class KeywordMatcher:
    """
    Keyword matching engine with multiple matching strategies:
    1. Exact match - Direct string matching
    2. Synonym match - Match against predefined synonyms
    3. Semantic match - AI-powered semantic similarity
    """

    def __init__(
        self,
        keywords: dict[str, dict[str, Any]] | None = None,
        ai_orchestrator: AIOrchestrator | None = None,
        enable_semantic: bool = True,
    ):
        """
        Initialize matcher.

        Args:
            keywords: Dict of {group_name: {keyword: [synonyms]}}
            ai_orchestrator: AI orchestrator for semantic matching
            enable_semantic: Enable AI-powered semantic matching
        """
        self.keywords = keywords or {}
        self.ai = ai_orchestrator or AIOrchestrator()
        self.enable_semantic = enable_semantic

        # Build lookup structures
        self._build_lookups()

    def _build_lookups(self) -> None:
        """Build efficient lookup structures."""
        # Exact match lookup: keyword -> (group, original_keyword)
        self.exact_lookup: dict[str, tuple[str, str]] = {}

        # Synonym lookup: synonym -> (group, original_keyword)
        self.synonym_lookup: dict[str, tuple[str, str]] = {}

        for group_name, group_keywords in self.keywords.items():
            for keyword, synonyms in group_keywords.items():
                # Add keyword itself
                key = keyword.lower()
                self.exact_lookup[key] = (group_name, keyword)

                # Add synonyms
                if synonyms:
                    for synonym in synonyms:
                        syn_key = synonym.lower()
                        self.synonym_lookup[syn_key] = (group_name, keyword)

    def add_keyword_group(
        self, group_name: str, keywords: dict[str, list[str] | None]
    ) -> None:
        """Add a keyword group."""
        self.keywords[group_name] = keywords
        self._build_lookups()

    async def match(
        self,
        text: str,
        min_score: float = 0.5,
        use_semantic: bool | None = None,
    ) -> list[MatchResult]:
        """
        Match text against all keywords.

        Args:
            text: Text to match
            min_score: Minimum score threshold
            use_semantic: Override semantic matching setting

        Returns:
            List of MatchResult objects
        """
        results: list[MatchResult] = []
        text_lower = text.lower()

        # 1. Exact matching
        exact_results = self._match_exact(text_lower)
        results.extend(exact_results)

        # 2. Synonym matching
        synonym_results = self._match_synonyms(text_lower)
        results.extend(synonym_results)

        # 3. Semantic matching (if enabled and no exact matches)
        should_use_semantic = (
            use_semantic if use_semantic is not None else self.enable_semantic
        )

        if should_use_semantic and len(results) == 0:
            semantic_results = await self._match_semantic(text)
            results.extend([r for r in semantic_results if r.score >= min_score])

        # Deduplicate (keep highest score per keyword)
        seen: dict[str, MatchResult] = {}
        for result in results:
            key = f"{result.keyword_group}:{result.keyword}"
            if key not in seen or result.score > seen[key].score:
                seen[key] = result

        final_results = list(seen.values())
        final_results.sort(key=lambda x: x.score, reverse=True)

        logger.debug(
            "keyword_match_complete",
            text_length=len(text),
            matches=len(final_results),
        )

        return final_results

    def _match_exact(self, text_lower: str) -> list[MatchResult]:
        """Perform exact keyword matching."""
        results = []

        for keyword_lower, (group_name, original_keyword) in self.exact_lookup.items():
            # Use word boundary matching
            pattern = rf'\b{re.escape(keyword_lower)}\b'
            if re.search(pattern, text_lower):
                results.append(
                    MatchResult(
                        keyword=original_keyword,
                        keyword_group=group_name,
                        match_type="exact",
                        score=1.0,
                        matched_text=original_keyword,
                    )
                )

        return results

    def _match_synonyms(self, text_lower: str) -> list[MatchResult]:
        """Perform synonym matching."""
        results = []

        for synonym_lower, (group_name, original_keyword) in self.synonym_lookup.items():
            pattern = rf'\b{re.escape(synonym_lower)}\b'
            if re.search(pattern, text_lower):
                results.append(
                    MatchResult(
                        keyword=original_keyword,
                        keyword_group=group_name,
                        match_type="synonym",
                        score=0.9,  # Slightly lower than exact match
                        matched_text=synonym_lower,
                    )
                )

        return results

    async def _match_semantic(self, text: str) -> list[MatchResult]:
        """Perform AI-powered semantic matching."""
        if not self.keywords:
            return []

        # Build keyword list for AI
        all_keywords = []
        for group_name, group_keywords in self.keywords.items():
            for keyword in group_keywords.keys():
                all_keywords.append(f"{group_name}:{keyword}")

        prompt = f"""Given the following text and keyword list, identify which keywords are semantically relevant to the text.
Even if the exact keyword doesn't appear, check if the content is about that topic.

Text:
{text[:2000]}

Keywords:
{', '.join(all_keywords)}

Return a JSON array of objects with:
- "keyword": the matched keyword (format: "group:keyword")
- "score": relevance score from 0.0 to 1.0
- "reason": brief explanation

Only include keywords with score >= 0.5. Return empty array if no matches.
Return ONLY valid JSON."""

        try:
            response = await self.ai.request(prompt, task_type=AITaskType.CLASSIFY)

            import json
            matches = json.loads(response.content)

            results = []
            for match in matches:
                keyword_full = match.get("keyword", "")
                if ":" in keyword_full:
                    group_name, keyword = keyword_full.split(":", 1)
                    results.append(
                        MatchResult(
                            keyword=keyword,
                            keyword_group=group_name,
                            match_type="semantic",
                            score=float(match.get("score", 0.5)),
                            matched_text=match.get("reason"),
                        )
                    )

            return results

        except Exception as e:
            logger.warning("semantic_match_failed", error=str(e))
            return []


# Default AI keyword configuration
DEFAULT_AI_KEYWORDS = {
    "AI Core": {
        "AI": ["인공지능", "Artificial Intelligence", "A.I."],
        "LLM": ["Large Language Model", "대규모 언어 모델", "거대 언어 모델"],
        "GPT": ["GPT-4", "GPT-5", "ChatGPT"],
        "Claude": ["Anthropic Claude", "Claude AI"],
        "Gemini": ["Google Gemini", "Gemini Pro", "Gemini Ultra"],
    },
    "Physical AI": {
        "Physical AI": ["Embodied AI", "실체화된 AI"],
        "Humanoid": ["휴머노이드", "인간형 로봇", "Humanoid Robot"],
        "Auto Pilot": ["자율주행", "Autonomous Driving", "FSD", "Full Self-Driving"],
        "Robotics": ["로봇공학", "로보틱스"],
    },
    "AI Business": {
        "AI Agent": ["AI 에이전트", "Autonomous Agent", "자율 에이전트"],
        "Vertical AI": ["버티컬 AI", "Industry AI", "산업 특화 AI"],
        "AI Automation": ["AI 자동화", "Intelligent Automation", "지능형 자동화"],
    },
    "Big Tech": {
        "OpenAI": ["오픈AI", "Open AI"],
        "Google": ["구글", "Google AI", "DeepMind"],
        "Meta": ["메타", "Meta AI", "Facebook AI"],
        "NVIDIA": ["엔비디아", "NVIDIA AI"],
        "Tesla": ["테슬라", "Tesla AI", "Tesla Bot"],
        "Microsoft": ["마이크로소프트", "MS", "Microsoft AI"],
        "Amazon": ["아마존", "Amazon AI", "AWS AI"],
        "Apple": ["애플", "Apple AI", "Apple Intelligence"],
    },
}
