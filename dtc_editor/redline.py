from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
import os
import shutil
import subprocess
import tempfile

@dataclass
class RedlineResult:
    backend: str
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None


def _find_libreoffice() -> Optional[str]:
    """Find LibreOffice executable on the system."""
    # Common installation paths
    lo_paths = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",  # macOS
        "/usr/bin/libreoffice",  # Linux
        "/usr/bin/soffice",  # Linux alternative
        "C:\\Program Files\\LibreOffice\\program\\soffice.exe",  # Windows
        "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe",  # Windows x86
    ]

    for path in lo_paths:
        if os.path.exists(path):
            return path

    # Try system PATH
    return shutil.which("soffice") or shutil.which("libreoffice")


def create_redline(original_docx: str, clean_docx: str, redline_docx: str, author: str = "DTC Editorial Engine", prefer_backend: Optional[str] = None) -> RedlineResult:
    # LibreOffice first (cross-platform, real track changes), then fallbacks
    backends = [prefer_backend] if prefer_backend else ["libreoffice", "aspose", "word_com"]
    last_err = None
    for be in backends:
        if not be:
            continue
        be = be.lower().strip()
        try:
            if be == "libreoffice":
                return _libreoffice_compare(original_docx, clean_docx, redline_docx, author)
            if be == "aspose":
                return _aspose_compare(original_docx, clean_docx, redline_docx, author)
            if be == "word_com":
                return _word_com_compare(original_docx, clean_docx, redline_docx, author)
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            continue
    return RedlineResult(backend="none", status="skipped", message=("No compare backend available. " + (f"Last error: {last_err}" if last_err else "")))


def _libreoffice_compare(original_docx: str, clean_docx: str, redline_docx: str, author: str) -> RedlineResult:
    """Generate redline using LibreOffice document comparison.

    LibreOffice can compare two documents and produce a result with proper
    OOXML track changes that are compatible with Microsoft Word.
    """
    soffice = _find_libreoffice()
    if not soffice:
        raise RuntimeError("LibreOffice not found. Install with: brew install --cask libreoffice")

    # Convert to absolute paths
    orig_abs = os.path.abspath(original_docx)
    clean_abs = os.path.abspath(clean_docx)
    redline_abs = os.path.abspath(redline_docx)

    # Create a Python script that uses LibreOffice's UNO API
    uno_script = f'''
import uno
from com.sun.star.beans import PropertyValue

def main():
    localContext = uno.getComponentContext()
    desktop = localContext.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop", localContext)

    # Load original document (hidden)
    load_props = (
        PropertyValue("Hidden", 0, True, 0),
        PropertyValue("ReadOnly", 0, False, 0),
    )
    original_url = "file://{orig_abs.replace(os.sep, '/').replace(' ', '%20')}"
    doc = desktop.loadComponentFromURL(original_url, "_blank", 0, load_props)

    if doc is None:
        raise Exception("Failed to load original document")

    # Compare with revised document
    revised_url = "file://{clean_abs.replace(os.sep, '/').replace(' ', '%20')}"
    compare_props = (
        PropertyValue("URL", 0, revised_url, 0),
    )

    # Use dispatcher to run CompareDocuments
    dispatcher = localContext.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.DispatchHelper", localContext)

    frame = doc.getCurrentController().getFrame()
    dispatcher.executeDispatch(frame, ".uno:CompareDocuments", "", 0, compare_props)

    # Save as DOCX with track changes
    output_url = "file://{redline_abs.replace(os.sep, '/').replace(' ', '%20')}"
    save_props = (
        PropertyValue("FilterName", 0, "MS Word 2007 XML", 0),
        PropertyValue("Overwrite", 0, True, 0),
    )
    doc.storeToURL(output_url, save_props)
    doc.close(True)

if __name__ == "__main__":
    main()
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(uno_script)
        script_path = f.name

    try:
        # Run LibreOffice with the Python script
        result = subprocess.run(
            [soffice, "--headless", "--invisible", "--nofirststartwizard",
             f"macro:///Standard.Module1.Main"],
            capture_output=True,
            timeout=120,
            text=True
        )

        # Alternative approach: use LibreOffice's Python interpreter directly
        # This is more reliable across platforms
        lo_python = os.path.join(os.path.dirname(soffice), "python")
        if not os.path.exists(lo_python):
            # macOS bundle structure
            lo_python = soffice.replace("MacOS/soffice", "Resources/python")

        if os.path.exists(lo_python):
            result = subprocess.run(
                [lo_python, script_path],
                capture_output=True,
                timeout=120,
                text=True
            )
            if result.returncode != 0:
                raise RuntimeError(f"LibreOffice Python failed: {result.stderr}")
        else:
            # Fallback: use soffice directly with a macro
            # First we need to write a simpler approach using command line
            _libreoffice_compare_cmdline(orig_abs, clean_abs, redline_abs, soffice)

        if os.path.exists(redline_abs):
            return RedlineResult(
                backend="libreoffice",
                status="ok",
                message="Redline created via LibreOffice compare."
            )
        else:
            raise RuntimeError("Redline document was not created")

    finally:
        try:
            os.unlink(script_path)
        except Exception:
            pass


def _libreoffice_compare_cmdline(original: str, revised: str, output: str, soffice: str) -> None:
    """Fallback: Use LibreOffice command line to compare documents.

    This approach creates a Basic macro on-the-fly and executes it.
    """
    # Create a temporary macro file
    macro_content = f'''
Sub CompareAndSave
    Dim oDoc As Object
    Dim oDispatcher As Object
    Dim args(0) As New com.sun.star.beans.PropertyValue

    oDoc = StarDesktop.loadComponentFromURL("file://{original.replace(os.sep, '/').replace(' ', '%20')}", "_blank", 0, Array())

    args(0).Name = "URL"
    args(0).Value = "file://{revised.replace(os.sep, '/').replace(' ', '%20')}"

    oDispatcher = createUnoService("com.sun.star.frame.DispatchHelper")
    oDispatcher.executeDispatch(oDoc.CurrentController.Frame, ".uno:CompareDocuments", "", 0, args())

    Dim saveArgs(1) As New com.sun.star.beans.PropertyValue
    saveArgs(0).Name = "FilterName"
    saveArgs(0).Value = "MS Word 2007 XML"
    saveArgs(1).Name = "Overwrite"
    saveArgs(1).Value = True

    oDoc.storeToURL("file://{output.replace(os.sep, '/').replace(' ', '%20')}", saveArgs())
    oDoc.close(True)
End Sub
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.bas', delete=False) as f:
        f.write(macro_content)
        macro_path = f.name

    try:
        # Execute using soffice
        result = subprocess.run(
            [soffice, "--headless", "--invisible",
             f"macro:///Standard.Module1.CompareAndSave"],
            capture_output=True,
            timeout=120
        )
    finally:
        try:
            os.unlink(macro_path)
        except Exception:
            pass


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
