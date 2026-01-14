from __future__ import annotations

SYSTEM_PROMPT = """You are a technical editor for the Digital Twin Consortium.
Your task is to rewrite sentences to improve clarity while STRICTLY preserving:
- All numbers, measurements, and units exactly as written
- All citations (e.g., [1], (2024), et al.)
- All normative keywords (SHALL, MUST, MAY, SHOULD, REQUIRED, RECOMMENDED)
- All proper nouns and technical terms
- The original meaning and intent

Rules:
1. Output ONLY the rewritten sentence(s), nothing else
2. Do not add explanations or commentary
3. Keep technical accuracy paramount
4. Maintain the same level of formality"""

RUNON_PROMPT_TEMPLATE = """Rewrite this run-on or overly complex sentence into clearer, shorter sentences.
Preserve all technical content exactly.

Context (surrounding paragraph):
{context}

Sentence to rewrite:
{sentence}

Rewritten sentence(s):"""

THROAT_CLEARING_PROMPT_TEMPLATE = """Remove the throat-clearing opening from this sentence while preserving its meaning.
Keep all technical content intact. Remove phrases like "It is important to note that", "As has been", etc.

Sentence:
{sentence}

Rewritten sentence:"""

ROOT_REPETITION_PROMPT_TEMPLATE = """This sentence contains word root repetition (e.g., "expansion...expand", "implement...implementation").
Rewrite to eliminate the repetition while preserving the meaning and all technical content.

Context (surrounding paragraph):
{context}

Sentence with repetition:
{sentence}

Rewritten sentence(s):"""

WEAK_LANGUAGE_PROMPT_TEMPLATE = """This sentence contains weak or vague language. Rewrite to be more direct and specific.
Preserve all technical content exactly.

Context (surrounding paragraph):
{context}

Sentence to strengthen:
{sentence}

Rewritten sentence:"""

JARGON_PROMPT_TEMPLATE = """This sentence contains unnecessary business jargon. Rewrite using clearer, more direct language.
Preserve all technical terms that have specific meanings in the domain.

Context (surrounding paragraph):
{context}

Sentence with jargon:
{sentence}

Rewritten sentence:"""

PASSIVE_VOICE_PROMPT_TEMPLATE = """This sentence uses passive voice that obscures the actor or adds unnecessary wordiness.
Rewrite using active voice where it improves clarity. Keep passive voice if it's appropriate for technical writing.

Context (surrounding paragraph):
{context}

Sentence to revise:
{sentence}

Rewritten sentence:"""

ORWELL_PROMPT_TEMPLATE = """This sentence contains dead metaphors, clichés, or empty phrases.
Rewrite to be more concrete and direct while preserving the meaning.

Context (surrounding paragraph):
{context}

Sentence to improve:
{sentence}

Rewritten sentence:"""

NOMINALIZATION_PROMPT_TEMPLATE = """This sentence uses nominalizations (verbs turned into nouns) that make the prose static.
Convert nominalizations back to active verbs. For example:
- "the implementation of X" → "implementing X" or "we implemented X"
- "make a decision" → "decide"
- "perform an analysis" → "analyze"

Preserve all technical content. Make the prose more vigorous and direct.

Context (surrounding paragraph):
{context}

Sentence with nominalizations:
{sentence}

Rewritten sentence:"""

NOUN_STACK_PROMPT_TEMPLATE = """This sentence contains dense noun stacks (multiple nouns piled together) that are hard to parse.
Unpack the noun stack using prepositions or by splitting into shorter phrases. For example:
- "edge computing infrastructure management system" → "system for managing edge computing infrastructure"
- "digital twin capability implementation strategy" → "strategy for implementing digital twin capabilities"

Preserve all technical meaning while making the structure clearer.

Context (surrounding paragraph):
{context}

Sentence with noun stacks:
{sentence}

Rewritten sentence:"""

STATIC_SENTENCE_PROMPT_TEMPLATE = """This sentence relies on weak "to be" verbs (is, are, was, were) instead of active verbs.
Rewrite using stronger, more active verbs. For example:
- "The system is capable of processing" → "The system processes"
- "This is supportive of scaling" → "This supports scaling"
- "The architecture is designed to handle" → "The architecture handles"

Preserve technical accuracy while making the prose more dynamic.

Context (surrounding paragraph):
{context}

Sentence to activate:
{sentence}

Rewritten sentence:"""

ABSTRACT_START_PROMPT_TEMPLATE = """This sentence starts with an abstract or empty subject (It is, There are, This is).
Rewrite to lead with the real subject and actor. For example:
- "It is important that teams coordinate" → "Teams must coordinate"
- "There are many factors that influence" → "Many factors influence"
- "This is a system that processes" → "This system processes"

Make the prose more direct and engaging.

Sentence:
{sentence}

Rewritten sentence:"""

VIGOR_PROMPT_TEMPLATE = """This sentence has multiple issues that make it feel bureaucratic and lifeless:
- Possible nominalizations (verbs as nouns)
- Weak verbs (is, are, was, were)
- Abstract subjects
- Dense noun phrases

Rewrite to be more vigorous and direct while preserving all technical content.
Use active verbs, concrete subjects, and clearer structure.

Context (surrounding paragraph):
{context}

Sentence to energize:
{sentence}

Rewritten sentence:"""
