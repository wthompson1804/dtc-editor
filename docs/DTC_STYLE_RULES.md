# DTC Style Guide Vale Rules

This document describes the Vale rules extracted from the DTC Technical Document Template and style guide.

## DTC-Specific Rules (from Style Guide)

### Capitalization & Terminology

| Rule | File | Description |
|------|------|-------------|
| Digital Twin Capitalization | `DigitalTwinCapitalization.yml` | "digital twin" lowercase as common noun; capitalized only in "Digital Twin Consortium" |
| DTC Trademarks | `DTCTrademarks.yml` | Proper formatting of "Digital Twin Consortium" and "DTC" |

### Figures & Tables

| Rule | File | Description |
|------|------|-------------|
| Figure Caption Format | `FigureCaptionFormat.yml` | Must use "Figure X-Y: Caption." format (chapter-item numbering) |
| Table Caption Format | `TableCaptionFormat.yml` | Must use "Table X-Y: Caption." format (chapter-item numbering) |
| Caption Sentence Case | `CaptionSentenceCase.yml` | Captions should use sentence case, not title case |
| Caption Period | `CaptionPeriod.yml` | All captions must end with a period |
| Cross Reference | `CrossReference.yml` | Every figure/table needs in-text cross-reference |
| Attribution | `Attribution.yml` | External sources must be attributed |

### References

| Rule | File | Description |
|------|------|-------------|
| APA Reference | `APAReference.yml` | References must follow APA format |
| Reference URL | `ReferenceURL.yml` | All references should include DOI or URL |
| Bibliography vs References | `BibliographyVsReferences.yml` | Use "References" if cited in text, "Bibliography" otherwise |

### Document Structure

| Rule | File | Description |
|------|------|-------------|
| Title Length | `TitleLength.yml` | Document titles should be less than 7 words |
| Document Start | `DocumentStart.yml` | Start with text (abstract/intro), not chapter heading |

## Prose Quality Rules (Orwell-inspired)

### Clarity & Vigor

| Rule | File | Description |
|------|------|-------------|
| Nominalization | `Nominalization.yml` | Flag verbs turned into nouns ("implementation of" → "implement") |
| Noun Stack | `NounStack.yml` | Flag dense noun phrases that need unpacking |
| Static Sentence | `StaticSentence.yml` | Flag overuse of be-verbs (is, are, was, were) |
| Abstract Start | `AbstractStart.yml` | Flag sentences starting with "It is", "There are" |
| Vigor | `Vigor.yml` | Flag bureaucratic/lifeless constructions |
| Passive Voice | `PassiveVoice.yml` | Flag passive constructions |

### Word Choice

| Rule | File | Description |
|------|------|-------------|
| Wordiness | `Wordiness.yml` | Suggest concise alternatives ("in order to" → "to") |
| Redundancy | `Redundancy.yml` | Flag redundant phrases ("future plans" → "plans") |
| Weak Language | `WeakLanguage.yml` | Flag hedging words ("somewhat", "fairly") |
| Hedging | `Hedging.yml` | Flag excessive qualification |
| Jargon | `Jargon.yml` | Suggest plain language alternatives |
| Terms | `Terms.yml` | Enforce consistent terminology |

### Repetition

| Rule | File | Description |
|------|------|-------------|
| Root Repetition | `RootRepetition.yml` | Flag word root repetition ("expansion...expand") |
| Orwell | `Orwell.yml` | Comprehensive Orwellian style checks |

## Usage

These rules are automatically applied:
1. **Holistic mode**: LLM rewrites first, then Vale validates
2. **Surgical mode**: Vale detects issues, then LLM fixes them

```bash
# Run with Vale validation
python3 -m dtc_editor.cli document.docx --mode holistic --use-vale ...
```

## Adding New Rules

Create a new `.yml` file in `rules/vale/dtc/` following the Vale rule format:

```yaml
extends: existence|substitution|occurrence|...
message: "Description of the issue: '%s'"
level: error|warning|suggestion
scope: paragraph|heading|sentence|...
tokens:
  - 'regex pattern to match'
```

## References

- DTC Technical Document Template (2026)
- George Orwell's "Politics and the English Language" (1946)
- Vale documentation: https://vale.sh/docs/
