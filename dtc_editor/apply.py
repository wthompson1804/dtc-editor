from __future__ import annotations
from typing import List, Dict, Tuple
import re
from dtc_editor.ir import DocumentIR
from dtc_editor.editops import EditOp


def _normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text:
    - Replace multiple spaces with single space
    - Preserve paragraph structure (don't collapse newlines)
    """
    # Replace multiple spaces (but not newlines) with single space
    text = re.sub(r'[^\S\n]+', ' ', text)
    return text


# Formal name indicators that signal an organization name
# When these words appear, the preceding words are likely part of an org name
FORMAL_NAME_INDICATORS = {
    # Corporate suffixes
    "corporation", "incorporated", "inc", "inc.", "llc", "ltd", "ltd.",
    "limited", "company", "co", "co.", "corp", "corp.",
    # Organization types
    "association", "consortium", "foundation", "institute", "organization",
    "authority", "commission", "agency", "board", "council", "committee",
    "alliance", "coalition", "federation", "union", "society",
    # Grid/energy specific
    "operator", "interconnection", "pool",
    # Program/project indicators
    "program", "project", "initiative",
}

# Words that should NOT be capitalized in organization names (articles, prepositions)
LOWERCASE_WORDS = {"the", "a", "an", "of", "for", "and", "or", "in", "on", "at", "to", "by"}


def _protect_organization_names(text: str) -> str:
    """
    Re-capitalize organization names that may have been lowercased.

    Uses heuristics to detect organization names:
    - When text ends with formal name indicators (Corporation, Inc., etc.),
      title-case the preceding words as they're likely part of the org name.
    - Stops at boundary words (the, a, is, about, etc.) that aren't part of names.

    Examples:
    - "north american electric reliability corporation" →
      "North American Electric Reliability Corporation"
    - "federal energy regulatory commission" →
      "Federal Energy Regulatory Commission"
    - "this is about the north american..." →
      "this is about the North American..." (only org name capitalized)
    """
    if not text:
        return text

    # Boundary words that typically precede (not part of) organization names
    BOUNDARY_WORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "about", "with", "from", "into", "through", "during", "before",
        "after", "above", "below", "between", "under", "over",
        "this", "that", "these", "those", "it", "its", "their", "our",
        "called", "named", "known", "as", "by", "to", "at", "in", "on",
    }

    words = text.split()
    result_words = words.copy()

    i = 0
    while i < len(words):
        word_lower = words[i].lower().rstrip('.,;:')

        # Check if this word is a formal name indicator
        if word_lower in FORMAL_NAME_INDICATORS:
            # Look backwards to find the start of the organization name
            # Stop at boundary words or sentence boundaries
            j = i
            org_start = i  # Track where the org name starts

            while j >= 0:
                current = words[j]
                current_lower = current.lower().rstrip('.,;:')

                # Stop at sentence boundaries
                if j > 0 and words[j-1].endswith(('.', '!', '?', ':')):
                    org_start = j
                    break

                # Stop at boundary words (but include "the" at the start of org names)
                if current_lower in BOUNDARY_WORDS and current_lower != "the":
                    org_start = j + 1
                    break

                # "the" is a boundary unless it's followed by a capitalized-looking word
                if current_lower == "the":
                    # Include "the" if it starts the org name
                    org_start = j
                    break

                org_start = j
                j -= 1

            # Capitalize words from org_start to i (inclusive)
            for k in range(org_start, i + 1):
                word = result_words[k]
                word_lower_k = word.lower()

                # Special handling for "the" at the start of org names
                if word_lower_k == "the" and k == org_start:
                    # Capitalize "the" only at the very start of text
                    if k == 0 and word and word[0].isalpha():
                        result_words[k] = word[0].upper() + word[1:]
                    continue  # Otherwise keep "the" lowercase

                # Don't capitalize articles/prepositions in the middle of names
                # but DO capitalize them if they're the indicator word
                if k == i or word_lower_k not in LOWERCASE_WORDS:
                    if word and word[0].isalpha():
                        result_words[k] = word[0].upper() + word[1:]

        i += 1

    return ' '.join(result_words)


def _fix_sentence_start_capitalization(text: str) -> str:
    """
    Ensure first letter after sentence-ending punctuation is capitalized.

    This fixes cases where Vale lowercases a term that happens to be at
    the start of a sentence. Per AP style:
    - "Virtual Power Plant" → "virtual power plant" (generic term)
    - But at sentence start: "Virtual power plant systems provide..."

    The first letter of any sentence must be capitalized.
    """
    if not text:
        return text

    # Capitalize first character of text if it's a letter
    result = []
    chars = list(text)

    # Track if we're at a sentence start
    at_sentence_start = True

    i = 0
    while i < len(chars):
        char = chars[i]

        if at_sentence_start and char.isalpha():
            # Capitalize the first letter of the sentence
            result.append(char.upper())
            at_sentence_start = False
        else:
            result.append(char)

        # Check for sentence-ending punctuation
        # Sentence ends with: . ! ? followed by space (or end of text)
        if char in '.!?':
            # Look ahead to see if this is really end of sentence
            # (not an abbreviation like "Dr." or decimal "3.14")
            j = i + 1
            # Skip any closing quotes/parens
            while j < len(chars) and chars[j] in '"\')]}':
                j += 1
            # If followed by whitespace or end, it's sentence end
            if j >= len(chars) or chars[j].isspace():
                at_sentence_start = True

        # Reset at newlines (new paragraph = new sentence)
        if char == '\n':
            at_sentence_start = True

        # If we hit non-whitespace without capitalizing, we're not at sentence start
        if not char.isspace() and char.isalpha():
            at_sentence_start = False

        i += 1

    return ''.join(result)


def apply_editops(ir: DocumentIR, ops: List[EditOp]) -> Tuple[DocumentIR, List[EditOp]]:
    # Group ops by block anchor for deterministic application
    by_anchor: Dict[str, List[EditOp]] = {}
    for op in ops:
        by_anchor.setdefault(op.target.anchor, []).append(op)

    for block in ir.blocks:
        bops = by_anchor.get(block.anchor)
        if not bops:
            continue
        # sort spans descending so offsets remain valid
        span_ops = [o for o in bops if o.op == "replace_span" and o.target.span_start is not None and o.target.span_end is not None]
        span_ops.sort(key=lambda o: (o.target.span_start or 0), reverse=True)

        text = block.text
        for op in span_ops:
            start, end = op.target.span_start, op.target.span_end
            if start is None or end is None or start < 0 or end > len(text) or start >= end:
                op.status = "failed"
                continue
            if text[start:end] != op.before:
                op.status = "rejected"
                op.verification["reason"] = "before_mismatch"
                continue
            text = text[:start] + op.after + text[end:]
            op.status = "applied"
        # Normalize whitespace (fix double spaces from source or edits)
        text = _normalize_whitespace(text)
        # Protect organization names from lowercasing (heuristic detection)
        text = _protect_organization_names(text)
        # Fix sentence-start capitalization (Vale may lowercase terms at sentence start)
        text = _fix_sentence_start_capitalization(text)
        block.text = text

        # block-level replacements (rare; future)
        for op in [o for o in bops if o.op == "replace_block"]:
            if block.text != op.before:
                op.status = "rejected"
                op.verification["reason"] = "block_before_mismatch"
            else:
                block.text = op.after
                op.status = "applied"

    return ir, ops
