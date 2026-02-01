"""AI-powered content processor."""

import json
from typing import Any

import structlog

from src.core.ai_orchestrator import AIOrchestrator, AITaskType
from src.core.models import Content

logger = structlog.get_logger()


class AIContentProcessor:
    """
    Process content using AI for:
    - Summarization
    - Classification
    - Entity extraction
    - Sentiment analysis
    - Relevance/Importance scoring
    """

    def __init__(self, orchestrator: AIOrchestrator | None = None):
        self.ai = orchestrator or AIOrchestrator()

    async def process(self, content: Content) -> dict[str, Any]:
        """
        Process content through AI pipeline.

        Args:
            content: Content model to process

        Returns:
            Dict with all processing results
        """
        text = f"{content.title}\n\n{content.content or ''}"

        # Run AI analysis
        try:
            result = await self._analyze_content(text)
            logger.info(
                "ai_processor_success",
                content_id=str(content.id),
                categories=result.get("categories"),
                importance=result.get("importance_score"),
            )
            return result
        except Exception as e:
            logger.error(
                "ai_processor_failed",
                content_id=str(content.id),
                error=str(e),
            )
            return self._get_default_result()

    async def _analyze_content(self, text: str) -> dict[str, Any]:
        """Run comprehensive AI analysis on content."""
        prompt = f"""Analyze the following content and provide a structured analysis.

Content:
{text[:4000]}

Provide your analysis as a JSON object with these fields:
1. "summary": A 2-3 sentence summary of the key points
2. "categories": Array of relevant categories from: ["AI Research", "Product Launch", "Funding/Investment", "Partnership", "Regulation/Policy", "Technical", "Business", "Opinion"]
3. "entities": Object with:
   - "companies": Array of company names mentioned
   - "people": Array of people mentioned
   - "technologies": Array of technologies/products mentioned
4. "sentiment": One of "positive", "negative", "neutral"
5. "relevance_score": Float 0-1, how relevant this is to AI/tech industry
6. "importance_score": Float 0-1, how significant/impactful this news is
7. "key_topics": Array of main topics (e.g., "LLM", "Robotics", "Autonomous Vehicles")

Return ONLY valid JSON, no explanation or markdown."""

        response = await self.ai.request(prompt, task_type=AITaskType.ANALYZE)

        try:
            # Parse JSON response
            result = json.loads(response.content)
            return self._validate_result(result)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return self._validate_result(result)
            raise

    def _validate_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize AI result."""
        return {
            "summary": result.get("summary", ""),
            "categories": result.get("categories", []),
            "entities": result.get("entities", {}),
            "sentiment": result.get("sentiment", "neutral"),
            "relevance_score": min(1.0, max(0.0, float(result.get("relevance_score", 0.5)))),
            "importance_score": min(1.0, max(0.0, float(result.get("importance_score", 0.5)))),
            "key_topics": result.get("key_topics", []),
        }

    def _get_default_result(self) -> dict[str, Any]:
        """Return default result when AI processing fails."""
        return {
            "summary": None,
            "categories": [],
            "entities": {},
            "sentiment": "neutral",
            "relevance_score": 0.5,
            "importance_score": 0.5,
            "key_topics": [],
        }

    async def summarize(self, text: str, max_length: int = 200) -> str:
        """Generate a summary of the text."""
        prompt = f"""Summarize the following in {max_length} characters or less.
Be concise and capture the key point.

Text:
{text[:3000]}

Summary:"""

        response = await self.ai.request(prompt, task_type=AITaskType.SUMMARIZE)
        return response.content.strip()

    async def extract_entities(self, text: str) -> dict[str, list[str]]:
        """Extract named entities from text."""
        prompt = f"""Extract named entities from the following text.

Text:
{text[:3000]}

Return as JSON with keys: "companies", "people", "technologies", "locations"
Only return valid JSON."""

        response = await self.ai.request(prompt, task_type=AITaskType.EXTRACT)

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"companies": [], "people": [], "technologies": [], "locations": []}

    async def classify(self, text: str, categories: list[str]) -> list[str]:
        """Classify text into one or more categories."""
        prompt = f"""Classify the following text into one or more of these categories:
{', '.join(categories)}

Text:
{text[:3000]}

Return only the matching category names as a JSON array."""

        response = await self.ai.request(prompt, task_type=AITaskType.CLASSIFY)

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return []
