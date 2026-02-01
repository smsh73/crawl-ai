"""Test keyword matcher functionality."""

import pytest
from src.processors.keyword_matcher import KeywordMatcher, DEFAULT_AI_KEYWORDS


@pytest.mark.asyncio
async def test_exact_match():
    """Test exact keyword matching."""
    matcher = KeywordMatcher(DEFAULT_AI_KEYWORDS, enable_semantic=False)

    text = "OpenAI has released GPT-5 with improved capabilities for AI Agent development."

    results = await matcher.match(text)

    matched_keywords = [r.keyword for r in results]

    assert "OpenAI" in matched_keywords, "Should match OpenAI"
    assert "GPT" in matched_keywords or any("GPT" in kw for kw in matched_keywords), "Should match GPT"
    assert "AI Agent" in matched_keywords, "Should match AI Agent"

    print("\n✅ Exact Match Results:")
    for r in results:
        print(f"   - {r.keyword} ({r.keyword_group}): {r.match_type} [{r.score}]")


@pytest.mark.asyncio
async def test_synonym_match():
    """Test synonym matching."""
    matcher = KeywordMatcher(DEFAULT_AI_KEYWORDS, enable_semantic=False)

    # Use Korean synonym
    text = "테슬라가 새로운 자율주행 기술을 발표했습니다."

    results = await matcher.match(text)

    matched_keywords = [r.keyword for r in results]

    # Should match via synonyms
    assert "Tesla" in matched_keywords or "Auto Pilot" in matched_keywords, \
        "Should match Tesla or Auto Pilot via Korean synonyms"

    print("\n✅ Synonym Match Results:")
    for r in results:
        print(f"   - {r.keyword} ({r.keyword_group}): {r.match_type} [{r.score}]")


@pytest.mark.asyncio
async def test_no_match():
    """Test text with no keyword matches."""
    matcher = KeywordMatcher(DEFAULT_AI_KEYWORDS, enable_semantic=False)

    text = "The weather today is sunny with clear skies."

    results = await matcher.match(text)

    assert len(results) == 0, "Should not match any keywords"

    print("\n✅ No Match Test: Correctly returned 0 matches")


@pytest.mark.asyncio
async def test_case_insensitive():
    """Test case-insensitive matching."""
    matcher = KeywordMatcher(DEFAULT_AI_KEYWORDS, enable_semantic=False)

    text = "OPENAI and NVIDIA are leading the AI revolution."

    results = await matcher.match(text)

    matched_keywords = [r.keyword for r in results]

    assert "OpenAI" in matched_keywords, "Should match OpenAI (case-insensitive)"
    assert "NVIDIA" in matched_keywords, "Should match NVIDIA (case-insensitive)"

    print("\n✅ Case Insensitive Match Results:")
    for r in results:
        print(f"   - {r.keyword}: {r.match_type}")


def test_keyword_group_structure():
    """Test DEFAULT_AI_KEYWORDS structure."""
    assert "AI Core" in DEFAULT_AI_KEYWORDS
    assert "Physical AI" in DEFAULT_AI_KEYWORDS
    assert "AI Business" in DEFAULT_AI_KEYWORDS
    assert "Big Tech" in DEFAULT_AI_KEYWORDS

    # Check AI Core keywords
    ai_core = DEFAULT_AI_KEYWORDS["AI Core"]
    assert "AI" in ai_core
    assert "LLM" in ai_core
    assert "GPT" in ai_core

    # Check synonyms exist
    assert ai_core["AI"] is not None, "AI should have synonyms"
    assert "인공지능" in ai_core["AI"], "AI should have Korean synonym"

    print("\n✅ Keyword Group Structure: Valid")
    for group, keywords in DEFAULT_AI_KEYWORDS.items():
        print(f"   - {group}: {len(keywords)} keywords")
