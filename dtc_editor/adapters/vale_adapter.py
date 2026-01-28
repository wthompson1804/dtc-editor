from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path
import subprocess
import tempfile
import json
import logging
import os
import re

from dtc_editor.ir import DocumentIR, TextBlock, BlockRef, Finding
from dtc_editor.editops import EditOp, Target

logger = logging.getLogger(__name__)


@dataclass
class ValeConfig:
    """Configuration for Vale linter."""
    vale_binary: str = "vale"  # Path to vale binary
    styles_path: Optional[str] = None  # Path to .vale.ini or styles directory
    min_alert_level: str = "suggestion"  # suggestion, warning, error
    pipeline_mode: str = "surgical"  # "surgical" or "holistic" - selects which rules to enable


@dataclass
class ValeResult:
    """Result of Vale linting."""
    status: str  # "ok" | "failed" | "skipped"
    findings: List[Finding]
    editops: List[EditOp]
    message: str = ""


def _find_vale_binary() -> Optional[str]:
    """Find Vale binary in common locations."""
    # Check common locations (use absolute paths)
    project_root = Path(__file__).parent.parent.parent
    locations = [
        str(project_root / "vale"),  # Project root
        "/usr/local/bin/vale",
        "/opt/homebrew/bin/vale",
        os.path.expanduser("~/vale"),
        "./vale",  # Current directory (last resort)
    ]

    for loc in locations:
        path = Path(loc)
        if path.exists() and os.access(str(path), os.X_OK):
            return str(path.absolute())

    # Try PATH
    try:
        result = subprocess.run(["which", "vale"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return None


def _extract_text_with_mapping(ir: DocumentIR) -> tuple[str, Dict[int, BlockRef]]:
    """
    Extract plain text from IR with line-to-block mapping.

    Returns:
        Tuple of (text, line_to_block_mapping)
    """
    lines = []
    line_to_block: Dict[int, BlockRef] = {}
    current_line = 1

    for block in ir.blocks:
        if block.text.strip():
            # Split block text into lines
            block_lines = block.text.split('\n')
            for line in block_lines:
                lines.append(line)
                line_to_block[current_line] = block.ref
                current_line += 1
            # Add blank line between blocks
            lines.append("")
            current_line += 1

    return '\n'.join(lines), line_to_block


def _find_block_by_ref(ir: DocumentIR, ref: BlockRef) -> Optional[TextBlock]:
    """Find block in IR matching the given BlockRef."""
    for block in ir.blocks:
        if (block.ref.block_type == ref.block_type
                and block.ref.doc_index == ref.doc_index):
            return block
    return None


def _extract_replacement_from_message(message: str) -> Optional[str]:
    """
    Extract replacement text from Vale message.
    Vale messages like "Use DTC preferred term: 'to'." contain the replacement in quotes.
    """
    # Look for quoted replacement: "Use ... 'replacement'."
    match = re.search(r"['\"]([^'\"]+)['\"]\.?$", message)
    if match:
        return match.group(1)
    return None


def _parse_vale_output(
    vale_output: Dict[str, List[Dict]],
    ir: DocumentIR,
    line_to_block: Dict[int, BlockRef],
) -> tuple[List[Finding], List[EditOp]]:
    """
    Parse Vale JSON output into Findings and EditOps.
    """
    findings: List[Finding] = []
    editops: List[EditOp] = []

    for filepath, alerts in vale_output.items():
        for alert in alerts:
            line_num = alert.get("Line", 1)
            severity = alert.get("Severity", "warning").lower()
            message = alert.get("Message", "")
            check = alert.get("Check", "vale.unknown")
            match_text = alert.get("Match", "")
            action = alert.get("Action", {})

            # Map line to block
            block_ref = line_to_block.get(line_num)

            # Map Vale severity to our severity
            if severity == "error":
                sev = "critical"
            elif severity == "warning":
                sev = "warning"
            else:
                sev = "info"

            # Create Finding
            finding = Finding(
                rule_id=f"vale.{check}",
                severity=sev,
                category="vale",
                message=message,
                ref=block_ref,
                before=match_text if match_text else None,
                risk_tier="low" if sev == "info" else "medium",
                details={"vale_check": check, "line": str(line_num)},
            )
            findings.append(finding)

            # Try to create EditOp from Vale suggestion
            replacement = None

            # First try Action.Params (standard Vale format)
            if action and action.get("Name") == "replace":
                params = action.get("Params", [])
                if params:
                    replacement = params[0] if isinstance(params, list) else str(params)

            # Fall back to parsing replacement from message
            if not replacement and message:
                replacement = _extract_replacement_from_message(message)

            # Create EditOp if we have a replacement
            if replacement and match_text and block_ref:
                block = _find_block_by_ref(ir, block_ref)
                if block:
                    # Find the match in the block text
                    span_start = block.text.find(match_text)
                    if span_start >= 0:
                        import hashlib
                        op_id = "vale_" + hashlib.sha1(
                            f"{check}|{block.anchor}|{span_start}|{match_text}".encode()
                        ).hexdigest()[:12]

                        editops.append(EditOp(
                            id=op_id,
                            op="replace_span",
                            target=Target(
                                anchor=block.anchor,
                                doc_index=block.ref.doc_index,
                                block_type=block.ref.block_type,
                                span_start=span_start,
                                span_end=span_start + len(match_text),
                            ),
                            intent="vale_style",
                            engine="vale",
                            rule_id=f"vale.{check}",
                            rationale=message,
                            before=match_text,
                            after=replacement,
                            confidence=1.0,
                            requires_review=False,
                            risk_tier="low",
                        ))

    return findings, editops


def run_vale(
    ir: DocumentIR,
    config: ValeConfig,
) -> ValeResult:
    """
    Run Vale linter on document IR.

    Args:
        ir: Document intermediate representation
        config: Vale configuration

    Returns:
        ValeResult with findings and editops
    """
    # Find Vale binary
    vale_bin = config.vale_binary
    if vale_bin == "vale":
        vale_bin = _find_vale_binary()

    if not vale_bin or not Path(vale_bin).exists():
        return ValeResult(
            status="skipped",
            findings=[],
            editops=[],
            message="Vale binary not found. Install Vale or specify path.",
        )

    # Extract text with line mapping
    text, line_to_block = _extract_text_with_mapping(ir)

    if not text.strip():
        return ValeResult(
            status="skipped",
            findings=[],
            editops=[],
            message="No text content to lint.",
        )

    # Write text to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(text)
        temp_path = f.name

    try:
        # Build Vale command
        cmd = [vale_bin, "--output=JSON"]

        # Add config path if specified
        vale_dir = None
        if config.styles_path:
            config_path = Path(config.styles_path)
            if config_path.is_file() and config_path.suffix == ".ini":
                cmd.extend(["--config", str(config_path)])
                vale_dir = str(config_path.parent)
            elif config_path.is_dir():
                # Select config based on pipeline mode
                if config.pipeline_mode == "holistic":
                    vale_ini = config_path / ".vale.holistic.ini"
                else:
                    vale_ini = config_path / ".vale.surgical.ini"
                # Fall back to default .vale.ini if mode-specific doesn't exist
                if not vale_ini.exists():
                    vale_ini = config_path / ".vale.ini"
                if vale_ini.exists():
                    cmd.extend(["--config", str(vale_ini)])
                    vale_dir = str(config_path)
        else:
            # Try to find config in project based on pipeline mode
            project_root = Path(__file__).parent.parent.parent
            vale_path = project_root / "rules" / "vale"

            # Select config based on pipeline mode
            if config.pipeline_mode == "holistic":
                default_ini = vale_path / ".vale.holistic.ini"
            else:
                default_ini = vale_path / ".vale.surgical.ini"

            # Fall back to default .vale.ini if mode-specific doesn't exist
            if not default_ini.exists():
                default_ini = vale_path / ".vale.ini"

            if default_ini.exists():
                cmd.extend(["--config", str(default_ini)])
                vale_dir = str(default_ini.parent)
                logger.info(f"Using Vale config: {default_ini} (pipeline_mode={config.pipeline_mode})")

        cmd.append(temp_path)

        logger.info(f"Running Vale: {' '.join(cmd)}")

        # Run Vale from the vale config directory so StylesPath resolves correctly
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=vale_dir or str(Path(__file__).parent.parent.parent),
        )

        # Parse output (Vale returns non-zero if it finds issues)
        if result.stdout.strip():
            try:
                vale_output = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Vale output: {e}")
                return ValeResult(
                    status="failed",
                    findings=[],
                    editops=[],
                    message=f"Failed to parse Vale output: {e}",
                )
        else:
            vale_output = {}

        # Parse findings and editops
        findings, editops = _parse_vale_output(vale_output, ir, line_to_block)

        logger.info(f"Vale found {len(findings)} issues, generated {len(editops)} EditOps")

        return ValeResult(
            status="ok",
            findings=findings,
            editops=editops,
            message=f"Vale completed: {len(findings)} findings, {len(editops)} auto-fixable",
        )

    except subprocess.TimeoutExpired:
        return ValeResult(
            status="failed",
            findings=[],
            editops=[],
            message="Vale timed out after 60 seconds",
        )
    except Exception as e:
        logger.error(f"Vale failed: {type(e).__name__}: {e}")
        return ValeResult(
            status="failed",
            findings=[],
            editops=[],
            message=f"Vale failed: {type(e).__name__}: {e}",
        )
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_path)
        except Exception:
            pass
