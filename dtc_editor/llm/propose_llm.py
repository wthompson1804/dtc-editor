from __future__ import annotations
from typing import List, Set, Optional, Dict
import hashlib
import logging
import re

from dtc_editor.ir import DocumentIR, TextBlock, BlockRef, Finding
from dtc_editor.editops import EditOp, Target
from dtc_editor.llm.client import ClaudeClient, RewriteRequest

logger = logging.getLogger(__name__)

# Mapping of Vale rule patterns to issue types for prompt selection
VALE_ISSUE_TYPES = {
    # Original rules
    "RootRepetition": "root_repetition",
    "WeakLanguage": "weak_language",
    "Jargon": "jargon",
    "PassiveVoice": "passive_voice",
    "Orwell": "orwell",
    "Hedging": "weak_language",
    # New vigor rules
    "Nominalization": "nominalization",
    "AbstractStart": "abstract_start",
    "NounStack": "noun_stack",
    "StaticSentence": "static_sentence",
    "Vigor": "vigor",
}


def _mk_llm_id(seed: str) -> str:
    """Generate unique ID for LLM-proposed EditOp."""
    return "llm_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _find_block_by_ref(ir: DocumentIR, ref: BlockRef) -> Optional[TextBlock]:
    """Find block in IR matching the given BlockRef."""
    for block in ir.blocks:
        if (block.ref.block_type == ref.block_type
                and block.ref.doc_index == ref.doc_index):
            return block
    return None


def _find_block_by_anchor(ir: DocumentIR, anchor: str) -> Optional[TextBlock]:
    """Find block in IR matching the given anchor."""
    for block in ir.blocks:
        if block.anchor == anchor:
            return block
    return None


def _get_issue_type_from_rule(rule_id: str) -> Optional[str]:
    """Determine issue type from Vale rule ID."""
    for pattern, issue_type in VALE_ISSUE_TYPES.items():
        if pattern in rule_id:
            return issue_type
    return None


def _find_sentence_containing(text: str, fragment: str) -> Optional[str]:
    """Find the complete sentence containing the given fragment."""
    if not fragment or fragment not in text:
        return None

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)

    for sentence in sentences:
        if fragment in sentence:
            return sentence.strip()

    # If not found in sentence split, return a window around the fragment
    idx = text.find(fragment)
    if idx >= 0:
        start = max(0, text.rfind('.', 0, idx) + 1)
        end = text.find('.', idx + len(fragment))
        if end < 0:
            end = len(text)
        else:
            end += 1
        return text[start:end].strip()

    return None


def propose_from_llm(
    ir: DocumentIR,
    findings: List[Finding],
    client: ClaudeClient,
    protected_terms: Set[str],
) -> List[EditOp]:
    """
    Generate LLM-based EditOps for prose candidates and Vale detection findings.
    Uses parallel batch processing for speed.

    Args:
        ir: Document intermediate representation
        findings: Findings from lint and Vale
        client: Configured Claude API client
        protected_terms: Terms that must not be altered

    Returns:
        List of EditOps with engine="llm_proposal"
    """
    # Collect all rewrite requests
    requests: List[RewriteRequest] = []
    request_metadata: Dict[str, dict] = {}  # Store metadata for EditOp creation
    processed_sentences = set()  # Avoid processing the same sentence twice

    # Process prose quality findings (run-on sentences, throat clearing)
    prose_findings = [
        f for f in findings
        if f.category == "prose_quality"
        and f.rule_id in ("prose.runon_or_complex", "prose.throat_clearing_opening")
    ]

    # Process Vale detection findings that don't have auto-fixes
    vale_detection_findings = [
        f for f in findings
        if f.category == "vale"
        and _get_issue_type_from_rule(f.rule_id) is not None
        and f.before  # Must have matched text
    ]

    # Process Vale detection findings FIRST (more specific issues)
    all_findings = vale_detection_findings + prose_findings
    logger.info(f"Collecting {len(vale_detection_findings)} Vale + {len(prose_findings)} prose candidates for LLM rewrite")

    for finding in all_findings:
        if not finding.ref:
            continue

        # Get the block
        block = _find_block_by_ref(ir, finding.ref)
        if not block:
            anchor = finding.details.get("anchor")
            if anchor:
                block = _find_block_by_anchor(ir, anchor)

        if not block:
            logger.debug(f"Block not found for finding {finding.rule_id}")
            continue

        # Determine what text to rewrite
        if finding.before:
            if finding.category == "vale":
                sentence = _find_sentence_containing(block.text, finding.before)
                if not sentence:
                    logger.debug(f"Could not find sentence for Vale match: {finding.before[:50]}...")
                    continue
            else:
                sentence = finding.before
        else:
            continue

        # Skip if we've already processed this sentence
        sentence_key = f"{block.anchor}:{sentence[:50]}"
        if sentence_key in processed_sentences:
            continue
        processed_sentences.add(sentence_key)

        # Determine issue type
        if finding.category == "prose_quality":
            issue_type = "runon" if "runon" in finding.rule_id else "throat_clearing"
        else:
            issue_type = _get_issue_type_from_rule(finding.rule_id)
            if not issue_type:
                continue

        # Create rewrite request
        request_id = _mk_llm_id(f"{finding.rule_id}|{block.anchor}|{sentence[:50]}")

        requests.append(RewriteRequest(
            id=request_id,
            sentence=sentence,
            context=block.text,
            issue_type=issue_type,
        ))

        # Store metadata for later EditOp creation
        request_metadata[request_id] = {
            "block": block,
            "finding": finding,
            "sentence": sentence,
            "issue_type": issue_type,
        }

    if not requests:
        logger.info("No candidates for LLM rewrite")
        return []

    logger.info(f"Sending {len(requests)} sentences for parallel LLM rewrite")

    # Execute batch rewrite
    results = client.rewrite_batch(requests)

    # Convert results to EditOps
    ops: List[EditOp] = []
    for result in results:
        if not result.success:
            continue

        # Skip if unchanged
        if result.rewritten.strip() == result.original.strip():
            logger.debug(f"Unchanged rewrite for: {result.original[:50]}...")
            continue

        # Skip if empty
        if not result.rewritten.strip():
            logger.debug(f"Empty rewrite for: {result.original[:50]}...")
            continue

        meta = request_metadata.get(result.id)
        if not meta:
            continue

        block = meta["block"]
        finding = meta["finding"]
        sentence = meta["sentence"]

        # Find span in block text
        span_start = block.text.find(sentence)
        if span_start == -1:
            logger.warning(f"Could not locate sentence in block: {sentence[:50]}...")
            continue

        span_end = span_start + len(sentence)

        ops.append(EditOp(
            id=result.id,
            op="replace_span",
            target=Target(
                anchor=block.anchor,
                doc_index=block.ref.doc_index,
                block_type=block.ref.block_type,
                span_start=span_start,
                span_end=span_end,
            ),
            intent="prose_rewrite",
            engine="llm_proposal",
            rule_id=f"llm.{finding.rule_id}",
            rationale=f"LLM rewrite: {finding.message}",
            before=sentence,
            after=result.rewritten,
            confidence=0.85,
            requires_review=True,
            risk_tier="high",
        ))

    logger.info(f"Generated {len(ops)} LLM EditOps from {len(requests)} candidates")
    return ops
