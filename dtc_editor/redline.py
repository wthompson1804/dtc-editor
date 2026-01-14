from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
import os

@dataclass
class RedlineResult:
    backend: str
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None

def create_redline(original_docx: str, clean_docx: str, redline_docx: str, author: str = "DTC Editorial Engine", prefer_backend: Optional[str] = None) -> RedlineResult:
    backends = [prefer_backend] if prefer_backend else ["aspose", "word_com"]
    last_err = None
    for be in backends:
        if not be:
            continue
        be = be.lower().strip()
        try:
            if be == "aspose":
                return _aspose_compare(original_docx, clean_docx, redline_docx, author)
            if be == "word_com":
                return _word_com_compare(original_docx, clean_docx, redline_docx, author)
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            continue
    return RedlineResult(backend="none", status="skipped", message=("No compare backend available. " + (f"Last error: {last_err}" if last_err else "")))

def _aspose_compare(original_docx: str, clean_docx: str, redline_docx: str, author: str) -> RedlineResult:
    try:
        import aspose.words as aw  # type: ignore
    except Exception as e:
        raise RuntimeError("Aspose.Words not available.") from e
    base = aw.Document(original_docx)
    revised = aw.Document(clean_docx)
    base.compare(revised, author, datetime.utcnow())
    base.save(redline_docx)
    return RedlineResult(backend="aspose", status="ok", message="Redline created via Aspose compare().")

def _word_com_compare(original_docx: str, clean_docx: str, redline_docx: str, author: str) -> RedlineResult:
    if os.name != "nt":
        raise RuntimeError("Word COM requires Windows.")
    try:
        import win32com.client  # type: ignore
    except Exception as e:
        raise RuntimeError("pywin32 not available.") from e
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        base = word.Documents.Open(os.path.abspath(original_docx), ReadOnly=False)
        revised = word.Documents.Open(os.path.abspath(clean_docx), ReadOnly=True)
        compared = base.Compare(Name=revised.FullName, AuthorName=author)
        compared.SaveAs2(os.path.abspath(redline_docx))
        revised.Close(False); base.Close(False); compared.Close(False)
        return RedlineResult(backend="word_com", status="ok", message="Redline created via Word COM Compare.")
    finally:
        try: word.Quit()
        except Exception: pass
