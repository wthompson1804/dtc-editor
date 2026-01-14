"""
Document Chunker

Breaks document into rewritable units with surrounding context.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Set, Literal, Optional
from dtc_editor.ir import DocumentIR, TextBlock

ChunkStrategy = Literal["paragraph", "section", "adaptive"]

# Minimum words to consider a paragraph worth rewriting
MIN_WORDS_FOR_REWRITE = 20

# Maximum words per chunk (for adaptive strategy)
MAX_WORDS_PER_CHUNK = 200

# Context window (words before/after to include)
CONTEXT_WORDS = 100


@dataclass
class Chunk:
    """A rewritable unit of the document."""
    id: str
    block_indices: List[int]         # Indices into ir.blocks
    text: str                        # Combined text of blocks
    context_before: str              # Previous text for context
    context_after: str               # Following text for context
    section_title: str               # Current section heading
    word_count: int
    is_rewritable: bool = True       # False for headings, short blocks


@dataclass
class ChunkingResult:
    """Result of chunking a document."""
    chunks: List[Chunk]
    total_rewritable_words: int
    total_chunks: int
    strategy_used: ChunkStrategy


def _get_section_title(blocks: List[TextBlock], current_idx: int) -> str:
    """Find the most recent heading before this block."""
    for i in range(current_idx - 1, -1, -1):
        if blocks[i].ref.block_type == "heading":
            return blocks[i].text
    return "Introduction"


def _get_context(blocks: List[TextBlock], start_idx: int, end_idx: int, direction: str) -> str:
    """Get context text before or after the chunk."""
    context_parts = []
    word_count = 0

    if direction == "before":
        indices = range(start_idx - 1, -1, -1)
    else:  # after
        indices = range(end_idx, len(blocks))

    for i in indices:
        block = blocks[i]
        if block.ref.block_type == "heading":
            # Include heading but stop there
            context_parts.append(f"[{block.text}]")
            break
        words = block.text.split()
        if word_count + len(words) > CONTEXT_WORDS:
            # Take partial
            remaining = CONTEXT_WORDS - word_count
            if direction == "before":
                context_parts.append(" ".join(words[-remaining:]))
            else:
                context_parts.append(" ".join(words[:remaining]))
            break
        context_parts.append(block.text)
        word_count += len(words)

    if direction == "before":
        context_parts.reverse()

    return " ".join(context_parts)


def chunk_by_paragraph(ir: DocumentIR) -> List[Chunk]:
    """
    Chunk document into individual paragraphs.

    Most granular strategy - safest for validation,
    but may lose some cross-paragraph coherence.
    """
    chunks = []
    blocks = ir.blocks

    for i, block in enumerate(blocks):
        word_count = len(block.text.split())

        # Skip headings and very short blocks
        is_rewritable = (
            block.ref.block_type == "paragraph" and
            word_count >= MIN_WORDS_FOR_REWRITE
        )

        chunk = Chunk(
            id=f"chunk_{i:04d}",
            block_indices=[i],
            text=block.text,
            context_before=_get_context(blocks, i, i + 1, "before"),
            context_after=_get_context(blocks, i, i + 1, "after"),
            section_title=_get_section_title(blocks, i),
            word_count=word_count,
            is_rewritable=is_rewritable,
        )
        chunks.append(chunk)

    return chunks


def chunk_by_section(ir: DocumentIR) -> List[Chunk]:
    """
    Chunk document by sections (heading to heading).

    Better coherence within sections, but higher risk
    if LLM makes mistakes - affects more content.
    """
    chunks = []
    blocks = ir.blocks

    current_section_start = 0
    current_section_title = "Introduction"
    current_block_indices = []

    for i, block in enumerate(blocks):
        if block.ref.block_type == "heading":
            # Emit previous section as chunk
            if current_block_indices:
                section_text = " ".join(blocks[j].text for j in current_block_indices)
                word_count = len(section_text.split())

                chunk = Chunk(
                    id=f"section_{len(chunks):04d}",
                    block_indices=current_block_indices.copy(),
                    text=section_text,
                    context_before=_get_context(blocks, current_block_indices[0], current_block_indices[-1] + 1, "before"),
                    context_after=_get_context(blocks, current_block_indices[0], current_block_indices[-1] + 1, "after"),
                    section_title=current_section_title,
                    word_count=word_count,
                    is_rewritable=word_count >= MIN_WORDS_FOR_REWRITE,
                )
                chunks.append(chunk)

            # Start new section
            current_section_title = block.text
            current_section_start = i
            current_block_indices = []
        else:
            current_block_indices.append(i)

    # Don't forget last section
    if current_block_indices:
        section_text = " ".join(blocks[j].text for j in current_block_indices)
        word_count = len(section_text.split())
        chunk = Chunk(
            id=f"section_{len(chunks):04d}",
            block_indices=current_block_indices,
            text=section_text,
            context_before=_get_context(blocks, current_block_indices[0], current_block_indices[-1] + 1, "before"),
            context_after="",
            section_title=current_section_title,
            word_count=word_count,
            is_rewritable=word_count >= MIN_WORDS_FOR_REWRITE,
        )
        chunks.append(chunk)

    return chunks


def chunk_adaptive(ir: DocumentIR) -> List[Chunk]:
    """
    Adaptive chunking: group small paragraphs, split large ones.

    Aims for chunks of roughly MAX_WORDS_PER_CHUNK words.
    Best balance of coherence and safety.
    """
    chunks = []
    blocks = ir.blocks

    current_indices = []
    current_words = 0
    current_section = "Introduction"

    def emit_chunk():
        nonlocal current_indices, current_words
        if not current_indices:
            return

        chunk_text = " ".join(blocks[j].text for j in current_indices)

        chunk = Chunk(
            id=f"adaptive_{len(chunks):04d}",
            block_indices=current_indices.copy(),
            text=chunk_text,
            context_before=_get_context(blocks, current_indices[0], current_indices[-1] + 1, "before"),
            context_after=_get_context(blocks, current_indices[0], current_indices[-1] + 1, "after"),
            section_title=current_section,
            word_count=current_words,
            is_rewritable=current_words >= MIN_WORDS_FOR_REWRITE,
        )
        chunks.append(chunk)
        current_indices = []
        current_words = 0

    for i, block in enumerate(blocks):
        word_count = len(block.text.split())

        # Headings always break chunks
        if block.ref.block_type == "heading":
            emit_chunk()
            current_section = block.text
            # Add heading as non-rewritable chunk
            chunks.append(Chunk(
                id=f"heading_{len(chunks):04d}",
                block_indices=[i],
                text=block.text,
                context_before="",
                context_after="",
                section_title=block.text,
                word_count=word_count,
                is_rewritable=False,
            ))
            continue

        # Would this block push us over the limit?
        if current_words + word_count > MAX_WORDS_PER_CHUNK and current_indices:
            emit_chunk()

        current_indices.append(i)
        current_words += word_count

    # Emit final chunk
    emit_chunk()

    return chunks


def chunk_document(ir: DocumentIR, strategy: ChunkStrategy = "paragraph") -> ChunkingResult:
    """
    Chunk a document using the specified strategy.

    Args:
        ir: Document intermediate representation
        strategy: One of "paragraph", "section", or "adaptive"

    Returns:
        ChunkingResult with list of chunks and stats
    """
    if strategy == "paragraph":
        chunks = chunk_by_paragraph(ir)
    elif strategy == "section":
        chunks = chunk_by_section(ir)
    elif strategy == "adaptive":
        chunks = chunk_adaptive(ir)
    else:
        raise ValueError(f"Unknown chunk strategy: {strategy}")

    rewritable_words = sum(c.word_count for c in chunks if c.is_rewritable)

    return ChunkingResult(
        chunks=chunks,
        total_rewritable_words=rewritable_words,
        total_chunks=len(chunks),
        strategy_used=strategy,
    )
