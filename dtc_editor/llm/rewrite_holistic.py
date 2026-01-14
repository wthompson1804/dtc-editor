"""
Prototype: LLM-First Holistic Rewrite

This module implements the inverted approach:
1. LLM rewrites paragraph holistically for vigor and clarity
2. Vale rules validate the output hasn't broken constraints
3. Invariant checks ensure technical accuracy preserved
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple
import subprocess
import tempfile
import json
import re
import os

# The holistic rewrite prompt - very different from issue-specific prompts
HOLISTIC_SYSTEM_PROMPT = """You are an expert technical editor specializing in clear, vigorous prose.
Your task is to rewrite paragraphs to be more engaging and readable while preserving technical accuracy.

STYLE GOALS (apply all):
- Use active voice and strong verbs
- Eliminate nominalizations (use "implement" not "implementation of")
- Break up noun stacks (unpack dense noun phrases)
- Vary sentence length and rhythm
- Lead with concrete subjects, not abstractions
- Cut throat-clearing and filler phrases
- Be direct and confident, not hedging

ABSOLUTE CONSTRAINTS (never violate):
- Preserve ALL technical terms exactly as written
- Preserve ALL numbers, statistics, and measurements
- Preserve ALL proper nouns and organization names
- Preserve ALL citations and references (Figure X-Y, Table X-Y)
- Do NOT add information not present in the original
- Do NOT remove key technical claims or facts
- Maintain the same overall meaning and intent"""

HOLISTIC_USER_TEMPLATE = """Rewrite this paragraph for clarity and vigor while preserving technical accuracy:

---
{paragraph}
---

Return ONLY the rewritten paragraph, no explanations or commentary."""


@dataclass
class ValidationResult:
    """Result of post-rewrite validation."""
    passed: bool
    issues: List[str]
    preserved_terms_ok: bool
    numbers_ok: bool
    vale_issues: List[str]


@dataclass
class HolisticRewriteResult:
    """Result of a holistic rewrite attempt."""
    original: str
    rewritten: str
    validation: ValidationResult
    accepted: bool
    rejection_reason: Optional[str] = None


def extract_numbers(text: str) -> Set[str]:
    """Extract all numbers and numeric patterns from text."""
    patterns = [
        r'\d+\.?\d*%?',  # Basic numbers and percentages
        r'Figure\s+\d+-\d+',  # Figure references
        r'Table\s+\d+-\d+',  # Table references
        r'\$[\d,]+\.?\d*',  # Currency
    ]
    numbers = set()
    for p in patterns:
        numbers.update(re.findall(p, text, re.IGNORECASE))
    return numbers


def extract_proper_nouns(text: str, protected_terms: Set[str]) -> Set[str]:
    """Extract proper nouns and protected terms present in text."""
    found = set()
    text_lower = text.lower()
    for term in protected_terms:
        if term.lower() in text_lower:
            found.add(term)
    return found


def run_vale_on_text(text: str, vale_config: str) -> List[str]:
    """Run Vale on text and return list of issues found."""
    issues = []

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(text)
        f.flush()
        temp_path = f.name

    try:
        result = subprocess.run(
            ['vale', '--config', vale_config, '--output', 'JSON', temp_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.stdout.strip():
            data = json.loads(result.stdout)
            for filepath, file_issues in data.items():
                for issue in file_issues:
                    issues.append(f"{issue.get('Check', 'unknown')}: {issue.get('Message', '')}")
    except Exception as e:
        issues.append(f"Vale error: {e}")
    finally:
        os.unlink(temp_path)

    return issues


def validate_rewrite(
    original: str,
    rewritten: str,
    protected_terms: Set[str],
    vale_config: Optional[str] = None,
) -> ValidationResult:
    """
    Validate that a rewrite hasn't broken constraints.

    This is the KEY difference from current approach:
    Vale rules are used as POST-VALIDATORS, not detectors.
    """
    issues = []

    # 1. Check numbers preserved
    orig_numbers = extract_numbers(original)
    new_numbers = extract_numbers(rewritten)
    missing_numbers = orig_numbers - new_numbers
    numbers_ok = len(missing_numbers) == 0
    if not numbers_ok:
        issues.append(f"Missing numbers: {missing_numbers}")

    # 2. Check protected terms preserved
    orig_terms = extract_proper_nouns(original, protected_terms)
    new_terms = extract_proper_nouns(rewritten, protected_terms)
    missing_terms = orig_terms - new_terms
    preserved_terms_ok = len(missing_terms) == 0
    if not preserved_terms_ok:
        issues.append(f"Missing protected terms: {missing_terms}")

    # 3. Check length isn't drastically different (might indicate content loss)
    orig_words = len(original.split())
    new_words = len(rewritten.split())
    if new_words < orig_words * 0.5:
        issues.append(f"Content may be lost: {orig_words} words → {new_words} words")

    # 4. Run Vale as validator (check for remaining issues, but also check nothing broke)
    vale_issues = []
    if vale_config and os.path.exists(vale_config):
        vale_issues = run_vale_on_text(rewritten, vale_config)

    passed = numbers_ok and preserved_terms_ok and len(issues) == 0

    return ValidationResult(
        passed=passed,
        issues=issues,
        preserved_terms_ok=preserved_terms_ok,
        numbers_ok=numbers_ok,
        vale_issues=vale_issues,
    )


def rewrite_paragraph_holistically(
    paragraph: str,
    api_key: str,
    protected_terms: Set[str],
    vale_config: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514",
) -> HolisticRewriteResult:
    """
    Rewrite a paragraph holistically using LLM, then validate.

    This is the INVERTED approach:
    1. LLM rewrites for vigor (not fixing specific issues)
    2. Validators check constraints weren't violated
    3. Accept or reject based on validation
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    # Step 1: Get holistic rewrite from LLM
    message = client.messages.create(
        model=model,
        max_tokens=2048,
        temperature=0.4,  # Slightly higher for more creative rewrites
        system=HOLISTIC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": HOLISTIC_USER_TEMPLATE.format(paragraph=paragraph)}],
    )

    rewritten = ""
    for block in message.content:
        if hasattr(block, "text"):
            rewritten += block.text
    rewritten = rewritten.strip()

    # Step 2: Validate the rewrite
    validation = validate_rewrite(
        original=paragraph,
        rewritten=rewritten,
        protected_terms=protected_terms,
        vale_config=vale_config,
    )

    # Step 3: Accept or reject
    if validation.passed:
        return HolisticRewriteResult(
            original=paragraph,
            rewritten=rewritten,
            validation=validation,
            accepted=True,
        )
    else:
        return HolisticRewriteResult(
            original=paragraph,
            rewritten=rewritten,
            validation=validation,
            accepted=False,
            rejection_reason="; ".join(validation.issues),
        )


def demo_comparison(paragraph: str, api_key: str):
    """
    Demo: Show the difference between current and proposed approach.
    """
    # Protected terms for MEC paper
    protected_terms = {
        "Digital Twin Consortium", "DTC", "MEC", "ETSI", "IoT",
        "Internet of Things", "Kubernetes", "DePIN", "OT", "IT",
        "Multi-access Edge Computing", "Edge Computing",
    }

    vale_config = "/Users/williamthompson/Downloads/dtc_editor_pilot_final/.vale.ini"

    print("=" * 70)
    print("ORIGINAL PARAGRAPH")
    print("=" * 70)
    print(paragraph)
    print(f"\nWord count: {len(paragraph.split())}")

    # Run Vale on original to show detected issues
    print("\n" + "=" * 70)
    print("VALE ISSUES IN ORIGINAL (current approach: these trigger LLM fixes)")
    print("=" * 70)
    orig_issues = run_vale_on_text(paragraph, vale_config)
    for issue in orig_issues[:10]:
        print(f"  - {issue}")
    if len(orig_issues) > 10:
        print(f"  ... and {len(orig_issues) - 10} more")

    # Now do holistic rewrite
    print("\n" + "=" * 70)
    print("HOLISTIC LLM REWRITE (proposed approach)")
    print("=" * 70)

    result = rewrite_paragraph_holistically(
        paragraph=paragraph,
        api_key=api_key,
        protected_terms=protected_terms,
        vale_config=vale_config,
    )

    print(result.rewritten)
    print(f"\nWord count: {len(result.rewritten.split())}")

    # Validation results
    print("\n" + "=" * 70)
    print("VALIDATION (Vale as post-validator)")
    print("=" * 70)
    print(f"Passed: {result.validation.passed}")
    print(f"Numbers preserved: {result.validation.numbers_ok}")
    print(f"Protected terms preserved: {result.validation.preserved_terms_ok}")

    if result.validation.issues:
        print("Constraint violations:")
        for issue in result.validation.issues:
            print(f"  - {issue}")

    if result.validation.vale_issues:
        print(f"\nRemaining Vale issues in rewrite ({len(result.validation.vale_issues)}):")
        for issue in result.validation.vale_issues[:5]:
            print(f"  - {issue}")

    print("\n" + "=" * 70)
    print("COMPARISON")
    print("=" * 70)
    print(f"Original Vale issues: {len(orig_issues)}")
    print(f"Rewrite Vale issues:  {len(result.validation.vale_issues)}")
    print(f"Accepted: {result.accepted}")
    if result.rejection_reason:
        print(f"Rejection reason: {result.rejection_reason}")

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m dtc_editor.llm.rewrite_holistic <api_key>")
        sys.exit(1)

    api_key = sys.argv[1]

    # The problematic first paragraph
    paragraph = """As the need for expansion of the human experience and real-time capability continues to expand, many of the world's standards organizations are focusing on the need to distribute intelligence services more ubiquitously from the cloud down to the edge environments.  This migration of content and services closer to the agents that need to access and consume them is best supported via a migration to a more distributed intelligent network infrastructure.  The key needs for expanding the capabilities of the intelligent networking infrastructure are the following:"""

    demo_comparison(paragraph, api_key)
