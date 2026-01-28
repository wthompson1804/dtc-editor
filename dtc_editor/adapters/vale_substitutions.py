"""
Vale Substitution Registry

Vale 3.x doesn't populate Action.Params for substitution rules.
This module parses the Vale YAML rule files directly and provides
a lookup function to get replacements.

Usage:
    registry = SubstitutionRegistry.load_from_path("rules/vale/dtc")
    replacement = registry.get_replacement("dtc.Wordiness", "in order to")
    # Returns "to"
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, Set
from pathlib import Path
import yaml
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class SubstitutionRule:
    """A single substitution rule with all its swaps."""
    rule_id: str
    swaps: Dict[str, str]  # match → replacement (case-sensitive keys)
    ignorecase: bool = True
    regex_swaps: Dict[str, tuple] = field(default_factory=dict)  # pattern → (compiled_regex, replacement)

    def __post_init__(self):
        """Compile regex patterns from swaps that contain regex metacharacters."""
        self.regex_swaps = {}
        for pattern, replacement in self.swaps.items():
            # Check if pattern contains regex metacharacters
            if any(c in pattern for c in ['(', ')', '?', '+', '*', '[', ']', '|', '^', '$', '\\']):
                try:
                    flags = re.IGNORECASE if self.ignorecase else 0
                    compiled = re.compile(pattern, flags)
                    self.regex_swaps[pattern] = (compiled, replacement)
                except re.error:
                    # Not a valid regex, treat as literal
                    pass

    def get_replacement(self, match_text: str) -> Optional[str]:
        """
        Get replacement for a match.

        Note: We use the EXACT replacement from the rule file. The 'ignorecase'
        setting only affects matching, not the output. If a rule says
        "Digital Twin" -> "digital twin", we return "digital twin" regardless
        of whether the input was "DIGITAL TWIN" or "digital twin".
        """
        # 1. Try exact match first
        if match_text in self.swaps:
            return self.swaps[match_text]

        # 2. Try case-insensitive matching (if ignorecase=True)
        if self.ignorecase:
            match_lower = match_text.lower()
            for key, value in self.swaps.items():
                # Skip regex patterns for plain string matching
                if key in self.regex_swaps:
                    continue
                if key.lower() == match_lower:
                    # Return exact replacement from rule, not case-preserved
                    return value

        # 3. Try regex pattern matching
        for pattern, (compiled, replacement) in self.regex_swaps.items():
            if compiled.fullmatch(match_text):
                # Return exact replacement from rule
                return replacement

        return None

    def _preserve_case(self, original: str, replacement: str) -> str:
        """Try to preserve the case pattern from original in replacement."""
        if original.isupper():
            return replacement.upper()
        if original.istitle():
            return replacement.title()
        if original.islower():
            return replacement.lower()
        return replacement


class SubstitutionRegistry:
    """Registry of all substitution rules for quick lookup."""

    def __init__(self):
        self.rules: Dict[str, SubstitutionRule] = {}
        self._loaded = False

    def load_from_path(self, styles_path: str) -> "SubstitutionRegistry":
        """Load all substitution rules from a Vale styles directory."""
        path = Path(styles_path)

        # Handle both directory and specific file
        if path.is_file():
            # Single file, get parent directory
            styles_dir = path.parent
        else:
            styles_dir = path

        # Find all YAML files in the dtc subdirectory
        dtc_path = styles_dir / "dtc"
        if not dtc_path.exists():
            # Maybe we're already in the dtc directory
            dtc_path = styles_dir

        for yml_file in dtc_path.glob("*.yml"):
            self._load_rule_file(yml_file)

        self._loaded = True
        logger.info(f"Loaded {len(self.rules)} substitution rules from {styles_dir}")
        return self

    def _load_rule_file(self, yml_path: Path) -> None:
        """Load a single Vale YAML rule file."""
        try:
            with open(yml_path) as f:
                data = yaml.safe_load(f)

            if not data:
                return

            # Only process substitution rules
            if data.get("extends") != "substitution":
                return

            swaps = data.get("swap", {})
            if not swaps:
                return

            # Build rule ID: dtc.RuleName
            rule_name = yml_path.stem
            rule_id = f"dtc.{rule_name}"

            ignorecase = data.get("ignorecase", True)

            self.rules[rule_id] = SubstitutionRule(
                rule_id=rule_id,
                swaps=swaps,
                ignorecase=ignorecase,
            )

            logger.debug(f"Loaded substitution rule {rule_id}: {len(swaps)} swaps")

        except Exception as e:
            logger.warning(f"Failed to load rule {yml_path}: {e}")

    def get_replacement(self, rule_id: str, match_text: str) -> Optional[str]:
        """
        Get replacement for a match from a specific rule.

        Args:
            rule_id: Vale rule ID (e.g., "dtc.Wordiness" or "vale.dtc.Wordiness")
            match_text: The text that was matched

        Returns:
            Replacement text or None if not found
        """
        # Normalize rule ID
        if rule_id.startswith("vale."):
            rule_id = rule_id[5:]  # Remove "vale." prefix

        rule = self.rules.get(rule_id)
        if rule:
            return rule.get_replacement(match_text)

        return None

    def is_substitution_rule(self, rule_id: str) -> bool:
        """Check if a rule ID is a substitution rule."""
        if rule_id.startswith("vale."):
            rule_id = rule_id[5:]
        return rule_id in self.rules


# Global registry instance (lazy-loaded)
_global_registry: Optional[SubstitutionRegistry] = None


def get_registry(styles_path: Optional[str] = None) -> SubstitutionRegistry:
    """Get the global substitution registry, loading if necessary."""
    global _global_registry

    if _global_registry is None or styles_path:
        _global_registry = SubstitutionRegistry()

        # Default to project rules directory
        if styles_path is None:
            project_root = Path(__file__).parent.parent.parent
            styles_path = str(project_root / "rules" / "vale")

        _global_registry.load_from_path(styles_path)

    return _global_registry


def get_replacement(rule_id: str, match_text: str, styles_path: Optional[str] = None) -> Optional[str]:
    """
    Convenience function to get a replacement from the global registry.

    Args:
        rule_id: Vale rule ID (e.g., "vale.dtc.Wordiness")
        match_text: The text that was matched
        styles_path: Optional path to Vale styles directory

    Returns:
        Replacement text or None
    """
    registry = get_registry(styles_path)
    return registry.get_replacement(rule_id, match_text)
