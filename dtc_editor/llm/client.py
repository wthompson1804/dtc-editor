from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Tuple, TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import logging

from dtc_editor.llm.prompts import (
    SYSTEM_PROMPT,
    RUNON_PROMPT_TEMPLATE,
    THROAT_CLEARING_PROMPT_TEMPLATE,
    ROOT_REPETITION_PROMPT_TEMPLATE,
    WEAK_LANGUAGE_PROMPT_TEMPLATE,
    JARGON_PROMPT_TEMPLATE,
    PASSIVE_VOICE_PROMPT_TEMPLATE,
    ORWELL_PROMPT_TEMPLATE,
    NOMINALIZATION_PROMPT_TEMPLATE,
    NOUN_STACK_PROMPT_TEMPLATE,
    STATIC_SENTENCE_PROMPT_TEMPLATE,
    ABSTRACT_START_PROMPT_TEMPLATE,
    VIGOR_PROMPT_TEMPLATE,
)

if TYPE_CHECKING:
    import anthropic

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Configuration for Claude API client."""
    api_key: str
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024
    temperature: float = 0.3  # Low temp for consistent rewrites
    max_concurrent: int = 4  # Max parallel API calls (stay under 50/min rate limit)
    max_retries: int = 3  # Max retries for rate limit errors
    min_request_interval: float = 0.3  # Min seconds between requests per worker


@dataclass
class RewriteRequest:
    """A single rewrite request."""
    id: str
    sentence: str
    context: str
    issue_type: str


@dataclass
class RewriteResult:
    """Result of a rewrite request."""
    id: str
    original: str
    rewritten: str
    success: bool
    error: Optional[str] = None


class ClaudeClient:
    """Thin wrapper around Anthropic's Claude API for prose rewrites."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client: Optional["anthropic.Anthropic"] = None

    @property
    def client(self) -> "anthropic.Anthropic":
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.config.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic library not installed. "
                    "Run: pip install anthropic"
                )
        return self._client

    def _build_prompt(self, sentence: str, context: str, issue_type: str) -> str:
        """Build the appropriate prompt for the issue type."""
        prompt_map = {
            "runon": RUNON_PROMPT_TEMPLATE,
            "throat_clearing": THROAT_CLEARING_PROMPT_TEMPLATE,
            "root_repetition": ROOT_REPETITION_PROMPT_TEMPLATE,
            "weak_language": WEAK_LANGUAGE_PROMPT_TEMPLATE,
            "jargon": JARGON_PROMPT_TEMPLATE,
            "passive_voice": PASSIVE_VOICE_PROMPT_TEMPLATE,
            "orwell": ORWELL_PROMPT_TEMPLATE,
            # Vigor-related issue types with dedicated prompts
            "nominalization": NOMINALIZATION_PROMPT_TEMPLATE,
            "abstract_start": ABSTRACT_START_PROMPT_TEMPLATE,
            "noun_stack": NOUN_STACK_PROMPT_TEMPLATE,
            "static_sentence": STATIC_SENTENCE_PROMPT_TEMPLATE,
            "vigor": VIGOR_PROMPT_TEMPLATE,
        }

        template = prompt_map.get(issue_type, RUNON_PROMPT_TEMPLATE)

        # Some prompts don't need context
        if issue_type in ("throat_clearing", "abstract_start"):
            return template.format(sentence=sentence)
        else:
            return template.format(
                context=context[:500],
                sentence=sentence,
            )

    def _single_rewrite(self, request: RewriteRequest) -> RewriteResult:
        """Execute a single rewrite request with retry logic for rate limits."""
        user_prompt = self._build_prompt(
            request.sentence,
            request.context,
            request.issue_type,
        )

        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                # Add minimum interval between requests to smooth out rate
                time.sleep(self.config.min_request_interval)

                message = self.client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                )

                result = ""
                for block in message.content:
                    if hasattr(block, "text"):
                        result += block.text

                result = result.strip()

                return RewriteResult(
                    id=request.id,
                    original=request.sentence,
                    rewritten=result,
                    success=True,
                )

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for rate limit errors (429)
                is_rate_limit = (
                    "rate" in error_str or
                    "429" in error_str or
                    "too many requests" in error_str or
                    "overloaded" in error_str
                )

                if is_rate_limit and attempt < self.config.max_retries:
                    # Exponential backoff: 2s, 4s, 8s
                    backoff = 2 ** (attempt + 1)
                    logger.warning(f"Rate limit hit for {request.id}, retry {attempt+1}/{self.config.max_retries} in {backoff}s")
                    time.sleep(backoff)
                    continue
                elif not is_rate_limit:
                    # Non-rate-limit error, don't retry
                    break

        # All retries exhausted or non-retryable error
        logger.warning(f"Rewrite failed for {request.id}: {type(last_error).__name__}: {last_error}")
        return RewriteResult(
            id=request.id,
            original=request.sentence,
            rewritten=request.sentence,  # Return original on failure
            success=False,
            error=str(last_error),
        )

    def rewrite_prose(
        self,
        sentence: str,
        context: str,
        issue_type: str,
    ) -> str:
        """
        Request a single prose rewrite from Claude.
        For batch processing, use rewrite_batch() instead.
        """
        request = RewriteRequest(
            id="single",
            sentence=sentence,
            context=context,
            issue_type=issue_type,
        )
        result = self._single_rewrite(request)
        return result.rewritten

    def rewrite_batch(
        self,
        requests: List[RewriteRequest],
        progress_callback=None,
    ) -> List[RewriteResult]:
        """
        Execute multiple rewrite requests in parallel.

        Args:
            requests: List of RewriteRequest objects
            progress_callback: Optional callable(completed, total) for progress updates

        Returns:
            List of RewriteResult objects in same order as requests
        """
        if not requests:
            return []

        total = len(requests)
        results: List[RewriteResult] = [None] * total  # Pre-allocate for ordering
        request_to_idx = {req.id: i for i, req in enumerate(requests)}
        completed = 0

        logger.info(f"Starting parallel rewrite of {total} sentences with {self.config.max_concurrent} workers")
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.config.max_concurrent) as executor:
            # Submit all requests
            future_to_request = {
                executor.submit(self._single_rewrite, req): req
                for req in requests
            }

            # Collect results as they complete
            for future in as_completed(future_to_request):
                result = future.result()
                idx = request_to_idx[result.id]
                results[idx] = result
                completed += 1

                if progress_callback:
                    progress_callback(completed, total)

                if completed % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    logger.info(f"Progress: {completed}/{total} ({rate:.1f}/sec)")

        elapsed = time.time() - start_time
        successful = sum(1 for r in results if r.success)
        logger.info(f"Completed {total} rewrites in {elapsed:.1f}s ({successful} successful, {total-successful} failed)")

        return results
