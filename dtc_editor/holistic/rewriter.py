"""
Holistic Rewriter

LLM-powered paragraph rewriter that transforms prose holistically
rather than fixing individual issues.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Set, Optional, Callable, TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import logging

from dtc_editor.holistic.chunker import Chunk
from dtc_editor.holistic.prompts import (
    HOLISTIC_SYSTEM_PROMPT,
    HOLISTIC_USER_TEMPLATE,
    HOLISTIC_USER_TEMPLATE_MINIMAL,
)

if TYPE_CHECKING:
    import anthropic

logger = logging.getLogger(__name__)


@dataclass
class RewriteConfig:
    """Configuration for the holistic rewriter."""
    api_key: str
    model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.4      # Slightly creative but controlled
    max_tokens: int = 4096
    max_concurrent: int = 2       # Reduced for rate limit safety
    max_retries: int = 3
    min_request_interval: float = 1.5  # 1.5s between requests per worker


@dataclass
class RewriteResult:
    """Result of rewriting a single chunk."""
    chunk_id: str
    original: str
    rewritten: str
    success: bool
    error: Optional[str] = None
    latency_ms: float = 0


class HolisticRewriter:
    """
    Rewrites document chunks holistically using LLM.

    Unlike the surgical approach (fix specific issues), this rewrites
    entire paragraphs for overall clarity and vigor.
    """

    def __init__(self, config: RewriteConfig, protected_terms: Set[str]):
        self.config = config
        self.protected_terms = protected_terms
        self._client: Optional["anthropic.Anthropic"] = None

    @property
    def client(self) -> "anthropic.Anthropic":
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.config.api_key)
            except ImportError:
                raise ImportError("anthropic library required: pip install anthropic")
        return self._client

    def _build_prompt(self, chunk: Chunk) -> str:
        """Build the rewrite prompt for a chunk."""
        # Format protected terms
        terms_in_chunk = [t for t in self.protected_terms if t.lower() in chunk.text.lower()]
        terms_str = ", ".join(terms_in_chunk) if terms_in_chunk else "(none detected)"

        # Use full template if we have context, minimal otherwise
        if chunk.context_before or chunk.context_after:
            return HOLISTIC_USER_TEMPLATE.format(
                section_title=chunk.section_title,
                context_before=chunk.context_before or "(start of document)",
                text=chunk.text,
                context_after=chunk.context_after or "(end of section)",
                protected_terms=terms_str,
            )
        else:
            return HOLISTIC_USER_TEMPLATE_MINIMAL.format(text=chunk.text)

    def _rewrite_single(self, chunk: Chunk) -> RewriteResult:
        """Rewrite a single chunk with retry logic."""
        if not chunk.is_rewritable:
            # Return unchanged for non-rewritable chunks
            return RewriteResult(
                chunk_id=chunk.id,
                original=chunk.text,
                rewritten=chunk.text,
                success=True,
            )

        user_prompt = self._build_prompt(chunk)
        last_error = None
        start_time = time.time()

        for attempt in range(self.config.max_retries + 1):
            try:
                time.sleep(self.config.min_request_interval)

                message = self.client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    system=HOLISTIC_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                )

                rewritten = ""
                for block in message.content:
                    if hasattr(block, "text"):
                        rewritten += block.text
                rewritten = rewritten.strip()

                latency = (time.time() - start_time) * 1000

                return RewriteResult(
                    chunk_id=chunk.id,
                    original=chunk.text,
                    rewritten=rewritten,
                    success=True,
                    latency_ms=latency,
                )

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                is_rate_limit = (
                    "rate" in error_str or
                    "429" in error_str or
                    "too many requests" in error_str
                )

                if is_rate_limit and attempt < self.config.max_retries:
                    backoff = 2 ** (attempt + 1)
                    logger.warning(f"Rate limit for {chunk.id}, retry in {backoff}s")
                    time.sleep(backoff)
                    continue
                elif not is_rate_limit:
                    break

        latency = (time.time() - start_time) * 1000
        logger.error(f"Rewrite failed for {chunk.id}: {last_error}")

        return RewriteResult(
            chunk_id=chunk.id,
            original=chunk.text,
            rewritten=chunk.text,  # Return original on failure
            success=False,
            error=str(last_error),
            latency_ms=latency,
        )

    def rewrite_chunks(
        self,
        chunks: List[Chunk],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[RewriteResult]:
        """
        Rewrite multiple chunks in parallel.

        Args:
            chunks: List of chunks to rewrite
            progress_callback: Optional callback(completed, total)

        Returns:
            List of RewriteResult in same order as input chunks
        """
        # Filter to only rewritable chunks for LLM processing
        rewritable = [(i, c) for i, c in enumerate(chunks) if c.is_rewritable]
        non_rewritable = [(i, c) for i, c in enumerate(chunks) if not c.is_rewritable]

        # Pre-populate results for non-rewritable
        results: List[Optional[RewriteResult]] = [None] * len(chunks)
        for i, chunk in non_rewritable:
            results[i] = RewriteResult(
                chunk_id=chunk.id,
                original=chunk.text,
                rewritten=chunk.text,
                success=True,
            )

        if not rewritable:
            return results

        total = len(rewritable)
        completed = 0

        logger.info(f"Starting holistic rewrite of {total} chunks with {self.config.max_concurrent} workers")
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.config.max_concurrent) as executor:
            future_to_idx = {
                executor.submit(self._rewrite_single, chunk): idx
                for idx, chunk in rewritable
            }

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                result = future.result()
                results[idx] = result
                completed += 1

                if progress_callback:
                    progress_callback(completed, total)

                if completed % 5 == 0:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    logger.info(f"Progress: {completed}/{total} ({rate:.1f} chunks/sec)")

        elapsed = time.time() - start_time
        successful = sum(1 for r in results if r and r.success)
        logger.info(f"Completed {total} rewrites in {elapsed:.1f}s ({successful} successful)")

        return results
