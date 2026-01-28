"""
LLM-based Capitalization Context Checker

Per AP style, generic terms of art are NOT capitalized. However, formal names
(companies, programs, publications) ARE capitalized.

This module uses LLM to determine context when a capitalized technical term
is detected, deciding whether to lowercase it or keep it capitalized.

Examples:
- "Virtual Power Plant" (generic) → "virtual power plant"
- "Virtual Power Plant Association" (formal name) → keep capitalized
- "The company's Virtual Power Plant system" (generic) → lowercase
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Tuple
import logging
import os

logger = logging.getLogger(__name__)

# Formal name indicators - if these follow the term, it's likely a formal name
FORMAL_NAME_INDICATORS = {
    "association", "consortium", "corporation", "company", "inc", "inc.",
    "llc", "ltd", "limited", "foundation", "institute", "organization",
    "program", "project", "initiative", "alliance", "coalition", "group",
    "committee", "council", "board", "agency", "authority", "commission",
}

# Technical terms that are commonly over-capitalized
TECHNICAL_TERMS = {
    "virtual power plant", "distributed energy resource", "demand response",
    "energy management system", "building management system", "energy storage system",
    "electric vehicle", "machine learning", "artificial intelligence",
    "cloud computing", "edge computing", "digital twin",
}


@dataclass
class CapitalizationDecision:
    """Result of capitalization check."""
    original: str
    corrected: str
    is_formal_name: bool
    confidence: float
    reasoning: str


def is_likely_formal_name(text: str, context: str) -> Tuple[bool, str]:
    """
    Quick heuristic check if a term is likely a formal name.

    Returns:
        (is_formal, reasoning)
    """
    text_lower = text.lower()
    context_lower = context.lower()

    # Find position of term in context
    pos = context_lower.find(text_lower)
    if pos == -1:
        return False, "Term not found in context"

    # Check what follows the term
    after_term = context_lower[pos + len(text_lower):].strip()
    first_word_after = after_term.split()[0] if after_term.split() else ""

    # Check for formal name indicators
    for indicator in FORMAL_NAME_INDICATORS:
        if first_word_after == indicator or after_term.startswith(indicator):
            return True, f"Followed by formal name indicator: '{indicator}'"

    # Check if it's in quotes (often indicates a proper name)
    before_term = context[max(0, pos-2):pos]
    after_end = context[pos + len(text):pos + len(text) + 2]
    if ('"' in before_term or '"' in before_term) and ('"' in after_end or '"' in after_end):
        return True, "Term is in quotes (likely a proper name)"

    return False, "No formal name indicators found"


def check_capitalization_with_llm(
    term: str,
    context: str,
    api_key: Optional[str] = None,
) -> CapitalizationDecision:
    """
    Use LLM to determine if a capitalized term should be lowercased.

    Args:
        term: The capitalized term (e.g., "Virtual Power Plant")
        context: Surrounding text for context
        api_key: Anthropic API key (uses env var if not provided)

    Returns:
        CapitalizationDecision with correction and reasoning
    """
    # First try heuristic check
    is_formal, heuristic_reason = is_likely_formal_name(term, context)

    if is_formal:
        return CapitalizationDecision(
            original=term,
            corrected=term,  # Keep as-is
            is_formal_name=True,
            confidence=0.8,
            reasoning=f"Heuristic: {heuristic_reason}",
        )

    # Try LLM if available
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # No API key - use heuristic only, default to lowercase
        term_lower = term.lower()
        return CapitalizationDecision(
            original=term,
            corrected=term_lower,
            is_formal_name=False,
            confidence=0.6,
            reasoning="No LLM available; defaulting to lowercase per AP style",
        )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""You are an AP style editor. Determine if this technical term should be capitalized.

TERM: "{term}"
CONTEXT: "...{context[:500]}..."

AP STYLE RULES:
- Generic terms of art (virtual power plant, demand response) are NOT capitalized
- Formal names of organizations, programs, publications ARE capitalized
- Example: "virtual power plant" (generic) vs "Virtual Power Plant Association" (formal name)

Is this term being used as:
A) A generic technical term (should be lowercase)
B) A formal name of an organization/program/publication (should be capitalized)

Respond with ONLY "A" or "B" followed by a brief reason."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )

        response = message.content[0].text.strip()
        is_formal = response.upper().startswith("B")

        if is_formal:
            return CapitalizationDecision(
                original=term,
                corrected=term,
                is_formal_name=True,
                confidence=0.9,
                reasoning=f"LLM: {response}",
            )
        else:
            return CapitalizationDecision(
                original=term,
                corrected=term.lower(),
                is_formal_name=False,
                confidence=0.9,
                reasoning=f"LLM: {response}",
            )

    except Exception as e:
        logger.warning(f"LLM check failed: {e}")
        # Fall back to lowercase
        return CapitalizationDecision(
            original=term,
            corrected=term.lower(),
            is_formal_name=False,
            confidence=0.5,
            reasoning=f"LLM error, defaulting to lowercase: {e}",
        )


def batch_check_capitalizations(
    terms_with_context: List[Tuple[str, str]],
    api_key: Optional[str] = None,
) -> List[CapitalizationDecision]:
    """
    Check multiple terms for capitalization.

    Args:
        terms_with_context: List of (term, context) tuples
        api_key: Anthropic API key

    Returns:
        List of CapitalizationDecision objects
    """
    results = []
    for term, context in terms_with_context:
        result = check_capitalization_with_llm(term, context, api_key)
        results.append(result)
    return results
