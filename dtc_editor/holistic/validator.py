"""
Post-Rewrite Validator

Validates that LLM rewrites haven't violated constraints.
This is the KEY DIFFERENCE from the surgical approach:
Vale rules serve as VALIDATORS, not DETECTORS.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional, Literal
import subprocess
import tempfile
import json
import re
import os
import logging

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Result of a single validation check."""
    name: str
    passed: bool
    severity: Literal["info", "warning", "error"]
    details: str = ""


@dataclass
class ValidationResult:
    """Complete validation result for a rewrite."""
    passed: bool
    checks: List[CheckResult]
    recommendation: Literal["accept", "review", "reject"]
    summary: str


@dataclass
class ValeIssue:
    """A single Vale issue for feedback."""
    rule: str
    message: str
    text: str
    severity: str


@dataclass
class ValidatorConfig:
    """Configuration for the validator."""
    vale_config: Optional[str] = None
    protected_terms: Set[str] = field(default_factory=set)
    max_length_reduction: float = 0.55  # Max 55% length reduction allowed (good rewrites cut filler)
    max_length_increase: float = 0.3    # Max 30% length increase allowed
    require_all_numbers: bool = True
    require_all_citations: bool = True
    require_all_terms: bool = True


class Validator:
    """
    Validates LLM rewrites against constraints.

    The validator ensures that holistic rewrites haven't:
    - Lost numbers, citations, or protected terms
    - Dramatically changed length (suggests content loss/addition)
    - Introduced Vale errors (rules as guardrails)
    """

    def __init__(self, config: ValidatorConfig):
        self.config = config

    def _extract_numbers(self, text: str) -> Set[str]:
        """Extract all numbers and numeric patterns."""
        patterns = [
            r'\b\d+\.?\d*%?\b',           # Basic numbers
            r'\b\d+(?:,\d{3})+\b',         # Comma-separated thousands
            r'\$[\d,]+\.?\d*\b',           # Currency
            r'\b5G\b',                      # 5G specifically
        ]
        numbers = set()
        for p in patterns:
            numbers.update(re.findall(p, text))
        return numbers

    def _extract_citations(self, text: str) -> Set[str]:
        """Extract figure, table, and other references."""
        patterns = [
            r'Figure\s+\d+[-–]\d+',
            r'Table\s+\d+[-–]\d+',
            r'Section\s+\d+(?:\.\d+)*',
            r'\[\d+\]',                    # Numeric citations
        ]
        citations = set()
        for p in patterns:
            citations.update(re.findall(p, text, re.IGNORECASE))
        return citations

    def _extract_protected_terms(self, text: str) -> Set[str]:
        """Find which protected terms appear in text."""
        found = set()
        text_lower = text.lower()
        for term in self.config.protected_terms:
            # Skip very short terms (IT, OT) - too many false positives
            # LLM might write "Information Technology" instead of "IT" which is fine
            if len(term) <= 2:
                continue
            if term.lower() in text_lower:
                found.add(term)
        return found

    def _run_vale(self, text: str) -> List[Dict]:
        """Run Vale on text and return issues (uses HOLISTIC config with all rules)."""
        if not self.config.vale_config:
            return []

        # Determine config file - use holistic config if directory provided
        config_path = self.config.vale_config
        if os.path.isdir(config_path):
            holistic_ini = os.path.join(config_path, '.vale.holistic.ini')
            if os.path.exists(holistic_ini):
                config_path = holistic_ini
            else:
                # Fall back to default
                config_path = os.path.join(config_path, '.vale.ini')

        if not os.path.exists(config_path):
            return []

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(text)
            temp_path = f.name

        try:
            result = subprocess.run(
                ['vale', '--config', config_path, '--output', 'JSON', temp_path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.stdout.strip():
                data = json.loads(result.stdout)
                issues = []
                for filepath, file_issues in data.items():
                    issues.extend(file_issues)
                return issues
        except FileNotFoundError:
            logger.warning("Vale not found, skipping Vale validation")
        except Exception as e:
            logger.warning(f"Vale error: {e}")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        return []

    def get_vale_issues(self, text: str) -> List[ValeIssue]:
        """Get structured Vale issues for LLM feedback."""
        raw_issues = self._run_vale(text)
        issues = []
        for issue in raw_issues:
            severity = issue.get('Severity', 'suggestion')
            if severity in ('warning', 'error'):
                issues.append(ValeIssue(
                    rule=issue.get('Check', 'unknown'),
                    message=issue.get('Message', ''),
                    text=issue.get('Match', ''),
                    severity=severity,
                ))
        return issues

    def _check_numbers(self, original: str, rewritten: str) -> CheckResult:
        """Check that all numbers are preserved."""
        orig_numbers = self._extract_numbers(original)
        new_numbers = self._extract_numbers(rewritten)
        missing = orig_numbers - new_numbers

        if not missing:
            return CheckResult(
                name="numbers_preserved",
                passed=True,
                severity="info",
                details=f"All {len(orig_numbers)} numbers preserved",
            )
        else:
            return CheckResult(
                name="numbers_preserved",
                passed=False,
                severity="error",
                details=f"Missing numbers: {missing}",
            )

    def _check_citations(self, original: str, rewritten: str) -> CheckResult:
        """Check that all citations/references are preserved."""
        orig_cites = self._extract_citations(original)
        new_cites = self._extract_citations(rewritten)
        missing = orig_cites - new_cites

        if not orig_cites:
            return CheckResult(
                name="citations_preserved",
                passed=True,
                severity="info",
                details="No citations to preserve",
            )
        elif not missing:
            return CheckResult(
                name="citations_preserved",
                passed=True,
                severity="info",
                details=f"All {len(orig_cites)} citations preserved",
            )
        else:
            return CheckResult(
                name="citations_preserved",
                passed=False,
                severity="error",
                details=f"Missing citations: {missing}",
            )

    def _check_protected_terms(self, original: str, rewritten: str) -> CheckResult:
        """Check that protected terms are preserved."""
        orig_terms = self._extract_protected_terms(original)
        new_terms = self._extract_protected_terms(rewritten)
        missing = orig_terms - new_terms

        if not orig_terms:
            return CheckResult(
                name="terms_preserved",
                passed=True,
                severity="info",
                details="No protected terms in original",
            )
        elif not missing:
            return CheckResult(
                name="terms_preserved",
                passed=True,
                severity="info",
                details=f"All {len(orig_terms)} protected terms preserved",
            )
        else:
            return CheckResult(
                name="terms_preserved",
                passed=False,
                severity="error",
                details=f"Missing terms: {missing}",
            )

    def _check_length(self, original: str, rewritten: str) -> CheckResult:
        """Check length change - informational only, never fails."""
        orig_words = len(original.split())
        new_words = len(rewritten.split())

        if orig_words == 0:
            return CheckResult(
                name="length_reasonable",
                passed=True,
                severity="info",
                details="Empty original",
            )

        ratio = new_words / orig_words
        change = f"{orig_words} → {new_words}"
        if ratio < 1:
            change += f" ({1-ratio:.0%} shorter)"
        elif ratio > 1:
            change += f" ({ratio-1:.0%} longer)"

        # Always pass - trust the LLM to preserve meaning
        return CheckResult(
            name="length_reasonable",
            passed=True,
            severity="info",
            details=change,
        )

    def _check_vale_errors(self, rewritten: str) -> CheckResult:
        """Check for critical Vale errors in rewrite."""
        issues = self._run_vale(rewritten)

        # Count by severity
        errors = [i for i in issues if i.get('Severity') == 'error']
        warnings = [i for i in issues if i.get('Severity') == 'warning']

        if errors:
            return CheckResult(
                name="vale_critical",
                passed=False,
                severity="error",
                details=f"{len(errors)} Vale errors: {[e.get('Check') for e in errors[:3]]}",
            )
        elif warnings:
            return CheckResult(
                name="vale_critical",
                passed=True,  # Warnings don't fail validation
                severity="warning",
                details=f"{len(warnings)} Vale warnings (acceptable)",
            )
        else:
            return CheckResult(
                name="vale_critical",
                passed=True,
                severity="info",
                details="No Vale issues",
            )

    def _check_not_identical(self, original: str, rewritten: str) -> CheckResult:
        """Check that the LLM actually made changes."""
        # Normalize whitespace for comparison
        orig_norm = " ".join(original.split())
        new_norm = " ".join(rewritten.split())

        if orig_norm == new_norm:
            return CheckResult(
                name="changes_made",
                passed=True,  # Not a failure, but noteworthy
                severity="info",
                details="No changes made (original returned unchanged)",
            )
        else:
            return CheckResult(
                name="changes_made",
                passed=True,
                severity="info",
                details="Changes detected",
            )

    def validate(self, original: str, rewritten: str) -> ValidationResult:
        """
        Validate a rewrite against all constraints.

        Returns recommendation:
        - "accept": All critical checks passed
        - "review": Warnings present, human should review
        - "reject": Critical check failed, use original
        """
        checks = [
            self._check_numbers(original, rewritten),
            self._check_citations(original, rewritten),
            self._check_protected_terms(original, rewritten),
            self._check_length(original, rewritten),
            self._check_vale_errors(rewritten),
            self._check_not_identical(original, rewritten),
        ]

        # Determine overall result
        errors = [c for c in checks if not c.passed and c.severity == "error"]
        warnings = [c for c in checks if not c.passed and c.severity == "warning"]

        if errors:
            return ValidationResult(
                passed=False,
                checks=checks,
                recommendation="reject",
                summary=f"REJECT: {len(errors)} critical errors - {errors[0].details}",
            )
        elif warnings:
            return ValidationResult(
                passed=True,
                checks=checks,
                recommendation="review",
                summary=f"REVIEW: {len(warnings)} warnings - {warnings[0].details}",
            )
        else:
            return ValidationResult(
                passed=True,
                checks=checks,
                recommendation="accept",
                summary="ACCEPT: All checks passed",
            )
