# Surgical Pipeline Enhancement Proposal

## Executive Summary

Based on analysis of:
- DTC Template document (formatting requirements)
- 3 test documents with varying conformance levels
- Existing rule implementations

This document proposes enhancements to make the surgical pipeline more robust.

---

## Test Document Analysis

| Document | Conformance Level | Key Issues |
|----------|-------------------|------------|
| **VPP Paper Will Edits** | HIGH (80%) | Wrong heading hierarchy (H5 instead of H3), some unexpanded acronyms, 9x "Digital Twin" should be lowercase |
| **Interoperable Digital Twins** | MEDIUM (60%) | Caption format uses dots not hyphens (Figure 1.2-1), Abstract as H1 instead of body text, 36x "Digital Twin" capitalization |
| **MEC White Paper** | LOW (20%) | NO headings, NO figure captions (24 figures, 0 captions), NO table captions, NO TOC/TOF/TOT |

---

## Comprehensive Rule Comparison

### A. DOCUMENT STRUCTURE

| Rule | Template Requirement | Existing Implementation | Gap | Recommendation |
|------|---------------------|------------------------|-----|----------------|
| **A1. Abstract/Intro First** | "Start with one or more paragraphs of text, not a Chapter header" | `DocumentStart.yml` - placeholder only, doesn't actually validate | **CRITICAL GAP** - Rule exists but doesn't work | Implement structural check: first non-title paragraph must NOT be a heading |
| **A2. Chapter Numbering** | Chapters numbered (1, 2, 3...) flowing with TOC | None | **CRITICAL GAP** | New rule: detect unnumbered H1 headings, insert chapter numbers |
| **A3. Heading Hierarchy** | Proper nesting (H1→H2→H3, not H1→H5) | None | **GAP** | New rule: validate heading levels don't skip (H1→H5 is wrong) |
| **A4. TOC Presence** | Must have Table of Contents | None | **GAP** | New check: detect TOC presence, flag if missing |
| **A5. TOF/TOT Presence** | Must have Table of Figures and Tables | None | **GAP** | New check: if figures/tables exist, TOF/TOT required |

### B. FIGURES & TABLES

| Rule | Template Requirement | Existing Implementation | Gap | Recommendation |
|------|---------------------|------------------------|-----|----------------|
| **B1. Caption Presence** | Every figure/table must have caption | `figure_captions.py` detects missing | **PARTIAL** - detects but placeholder text wrong | Update placeholder: "INSERT EXPLANATION OF FIGURE OR TABLE. Source: DTC INSERT NAME Working Group." |
| **B2. Caption Format** | `Figure X-Y: Description.` (Chapter-Sequence) | `FigureCaptionFormat.yml` detects malformed | **PARTIAL** - detects but doesn't fix | Enhance to AUTO-CORRECT format, not just flag |
| **B3. Source Attribution** | "Figures & Tables from outside source must be attributed" | None | **CRITICAL GAP** | New rule: captions must end with "Source: ..." line |
| **B4. Caption Style** | Sentence case, ends with period, Calibri 11, no italics | `CaptionPeriod.yml`, `CaptionSentenceCase.yml` | **PARTIAL** | Combine into single caption validator with auto-fix |
| **B5. Cross-References** | Every figure/table must be referenced in text | `CrossReference.yml` exists | OK but detect-only | Enhance to flag unreferenced figures |
| **B6. Numbering Consistency** | Caption numbers must match TOF/TOT and in-text refs | None | **CRITICAL GAP** | New: renumber all figures/tables, update TOF/TOT, fix in-text references |

### C. CAPITALIZATION

| Rule | Template Requirement | Existing Implementation | Gap | Recommendation |
|------|---------------------|------------------------|-----|----------------|
| **C1. "digital twin" lowercase** | Lowercase except in "Digital Twin Consortium" | `DigitalTwinCapitalization.yml` | OK - works correctly | No change needed |
| **C2. Technical terms** | Ambiguous - when is "Edge Computing" a proper noun? | None | **GAP** | New: LLM-assisted disambiguation with confidence scoring |
| **C3. Title case in headings** | Not specified but implied formal style | None | **GAP** | New: validate heading capitalization |

### D. ACRONYMS

| Rule | Template Requirement | Existing Implementation | Gap | Recommendation |
|------|---------------------|------------------------|-----|----------------|
| **D1. First-use expansion** | Acronyms must be spelled out on first use | `holistic/acronyms.py` - 80+ hardcoded | **PARTIAL** - only in holistic mode, limited dictionary | Port to surgical pipeline, expand dictionary |
| **D2. Unknown acronym lookup** | Need to find definitions for domain-specific terms | None | **CRITICAL GAP** | New: LLM lookup with confidence scoring, web search fallback |
| **D3. Organization acronyms** | Some don't need expansion (ETSI, IEEE, DTC) | `ORGANIZATION_ACRONYMS` set exists | OK | Expand the set |

### E. REFERENCES

| Rule | Template Requirement | Existing Implementation | Gap | Recommendation |
|------|---------------------|------------------------|-----|----------------|
| **E1. APA Format** | References must be APA format | `APAReference.yml` | OK - detects issues | No change needed |
| **E2. DOI/URL Required** | Include DOI or URL for all references | `ReferenceURL.yml` | OK | No change needed |
| **E3. Hyperlinks** | All external references must be hyperlinked | None | **GAP** | New: detect URLs without hyperlinks |

### F. PROSE QUALITY

| Rule | Template Requirement | Existing Implementation | Gap | Recommendation |
|------|---------------------|------------------------|-----|----------------|
| **F1. Wordy phrases** | General clarity | `Wordiness.yml`, `prose_rules.yml` | OK | No change needed |
| **F2. Passive voice** | Prefer active | `PassiveVoice.yml` | OK | No change needed |
| **F3. Hedging** | Avoid weak language | `Hedging.yml`, `WeakLanguage.yml` | OK | No change needed |

---

## Priority Ranking

### P0 - CRITICAL (Blocking issues in test documents)

1. **B1+B6: Figure/Table Caption System** - MEC paper has 24 figures with 0 captions
   - Detect all figures/tables
   - Generate proper Chapter-Sequence numbers
   - Insert placeholder captions with source line
   - Update TOF/TOT
   - Fix in-text references

2. **A2: Chapter Numbering** - MEC paper has no heading structure
   - Detect headings without numbers
   - Insert sequential chapter numbers
   - Regenerate TOC

3. **D1+D2: Acronym Expansion** - All papers have unexpanded acronyms
   - Port acronym tracking to surgical pipeline
   - Add LLM lookup for unknown acronyms
   - Expand on first use

### P1 - HIGH (Frequent issues)

4. **C1: "Digital Twin" Capitalization** - Already works but needs AUTO-FIX
   - Currently detects but may not fix in surgical mode
   - Ensure deterministic replacement happens

5. **A1: Abstract/Intro Validation** - Transportation paper has Abstract as H1
   - Detect if first content is heading
   - Flag for human review or generate intro via LLM

6. **B3: Source Attribution** - VPP paper has it, others don't
   - Detect captions without "Source:" line
   - Insert placeholder

### P2 - MEDIUM (Quality improvements)

7. **A3: Heading Hierarchy** - VPP paper uses H5 instead of H3
   - Validate heading levels
   - Suggest corrections

8. **C2: Technical Term Capitalization** - Ambiguous cases
   - LLM-assisted with confidence
   - Web search only for low-confidence cases

---

## Recommended Implementation Order

### Phase 1: Figure/Table Caption System (P0)
```
Input: Document with figures/tables
Steps:
1. Detect all figures (w:drawing elements) and tables
2. Detect existing captions (text starting with "Figure X" or "Table X")
3. Build chapter→figure/table mapping from heading structure
4. For missing captions:
   - Generate: "Figure X-Y: INSERT EXPLANATION. Source: DTC INSERT NAME Working Group."
5. For malformed captions:
   - Correct format to "Figure X-Y: [existing text]. Source: [add if missing]"
6. Regenerate TOF/TOT with new numbers
7. Find and fix in-text references (e.g., "see Figure 3" → "see Figure 2-1")
Output: All captions correct, TOF/TOT updated, references fixed
```

### Phase 2: Chapter Numbering (P0)
```
Input: Document with unnumbered headings
Steps:
1. Find all H1 headings
2. Detect if numbered (starts with digit) or not
3. For unnumbered: insert chapter number (1, 2, 3...)
4. Handle special cases: "Abstract", "References", "Authors" don't get numbers
5. Regenerate TOC
Output: All chapters numbered, TOC accurate
```

### Phase 3: Acronym Expansion (P0)
```
Input: Document text
Steps:
1. Scan for acronyms (2-5 uppercase letters)
2. Filter out known organization acronyms (ETSI, IEEE, etc.)
3. Check if already expanded earlier in document
4. For unexpanded:
   a. Check hardcoded dictionary (80+ common acronyms)
   b. If not found: LLM lookup with confidence score
   c. If confidence < 0.8: flag for review (don't auto-expand)
   d. If confidence >= 0.8: expand on first use
5. Track which were expanded for subsequent occurrences
Output: All acronyms expanded on first use (or flagged)
```

### Phase 4: Capitalization Fixes (P1)
```
Input: Document text
Steps:
1. Apply "Digital Twin" → "digital twin" substitution
2. For ambiguous terms:
   a. LLM assesses: is this a proper noun or common noun?
   b. Confidence < 0.8: flag for review
   c. Confidence >= 0.8: apply fix
Output: Correct capitalization with flagged ambiguities
```

### Phase 5: Document Structure Validation (P1)
```
Input: Document structure
Steps:
1. Check first non-title paragraph is body text (not heading)
2. If heading first: flag for LLM abstract generation
3. Validate heading hierarchy (no skipping levels)
4. Validate TOC/TOF/TOT presence
Output: Structure validated with flags for fixes
```

---

## Existing Rules: What NOT to Change

These rules work correctly and should be preserved:

| Rule File | Purpose | Status |
|-----------|---------|--------|
| `DigitalTwinCapitalization.yml` | Lowercase "digital twin" | KEEP |
| `APAReference.yml` | APA format validation | KEEP |
| `Wordiness.yml` | Wordy phrase detection | KEEP |
| `PassiveVoice.yml` | Passive voice detection | KEEP |
| `Hedging.yml` | Weak language detection | KEEP |
| `prose_rules.yml` replacement rules | "in order to" → "to", etc. | KEEP |
| `protected_terms.yml` | Terms not to modify | KEEP |

---

## New Modules Required

1. **`dtc_editor/surgical/figure_table_processor.py`**
   - Detect figures/tables
   - Generate/correct captions
   - Update TOF/TOT
   - Fix in-text references

2. **`dtc_editor/surgical/chapter_numberer.py`**
   - Detect unnumbered chapters
   - Insert numbers
   - Regenerate TOC

3. **`dtc_editor/surgical/acronym_expander.py`**
   - Port from holistic/acronyms.py
   - Add LLM lookup
   - Add confidence scoring
   - Web search fallback (rate-limited)

4. **`dtc_editor/surgical/structure_validator.py`**
   - Validate document structure
   - Detect missing abstract
   - Validate heading hierarchy

---

## Confidence Scoring for LLM-Assisted Fixes

For ambiguous cases (acronym meanings, capitalization decisions):

| Confidence | Action |
|------------|--------|
| >= 0.9 | Auto-apply fix |
| 0.8 - 0.9 | Apply with "REVIEW:" comment in changelog |
| 0.6 - 0.8 | Flag for human review, don't apply |
| < 0.6 | Skip, add to review report |

Web search triggered only when:
- LLM confidence < 0.7 for acronym meaning
- Term appears to be a formal program/standard name
- Maximum 5 web searches per document (latency budget)

---

## Approval Request

Please review this proposal and confirm:

1. **Priority order** - Is P0/P1/P2 ranking correct?
2. **Scope** - Any requirements missing or misunderstood?
3. **Confidence thresholds** - Are 0.8/0.9 thresholds appropriate?
4. **Web search limits** - Is 5 per document reasonable?
5. **Placeholder text** - Is "INSERT EXPLANATION OF FIGURE OR TABLE. Source: DTC INSERT NAME Working Group." correct?

Once approved, I will implement in the order specified.
