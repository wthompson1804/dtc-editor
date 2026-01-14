from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Dict, Any
import threading
import os
from pathlib import Path


class DTCEditorGUI:
    """Main GUI application for DTC Editorial Engine."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("DTC Editorial Engine")
        self.root.geometry("850x750")
        self.root.minsize(700, 600)

        # State
        self.input_file: Optional[str] = None
        self.output_dir: str = "./dtc_out"
        self.google_credentials: Optional[str] = None
        self.processing: bool = False
        self.result: Optional[Dict[str, Any]] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the main UI layout."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        row = 0

        # --- Header ---
        header = ttk.Label(main_frame, text="DTC Editorial Engine", font=("TkDefaultFont", 16, "bold"))
        header.grid(row=row, column=0, columnspan=3, pady=(0, 15))
        row += 1

        # --- Input File Section ---
        ttk.Label(main_frame, text="Input DOCX:").grid(row=row, column=0, sticky="w", pady=5)
        self.input_entry = ttk.Entry(main_frame, width=60)
        self.input_entry.grid(row=row, column=1, sticky="ew", padx=5)
        ttk.Button(main_frame, text="Browse...", command=self._browse_input).grid(row=row, column=2)
        row += 1

        # --- Output Directory ---
        ttk.Label(main_frame, text="Output Directory:").grid(row=row, column=0, sticky="w", pady=5)
        self.output_entry = ttk.Entry(main_frame, width=60)
        self.output_entry.insert(0, self.output_dir)
        self.output_entry.grid(row=row, column=1, sticky="ew", padx=5)
        ttk.Button(main_frame, text="Browse...", command=self._browse_output).grid(row=row, column=2)
        row += 1

        # --- Options Frame ---
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        options_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        options_frame.columnconfigure(1, weight=1)
        options_frame.columnconfigure(3, weight=1)
        row += 1

        # Mode dropdown
        ttk.Label(options_frame, text="Mode:").grid(row=0, column=0, sticky="w")
        self.mode_var = tk.StringVar(value="safe")
        mode_combo = ttk.Combobox(
            options_frame,
            textvariable=self.mode_var,
            values=["safe", "rewrite"],
            state="readonly",
            width=15
        )
        mode_combo.grid(row=0, column=1, sticky="w", padx=5)

        # Author field
        ttk.Label(options_frame, text="Author:").grid(row=0, column=2, sticky="w", padx=(20, 0))
        self.author_entry = ttk.Entry(options_frame, width=25)
        self.author_entry.insert(0, "DTC Editorial Engine")
        self.author_entry.grid(row=0, column=3, sticky="w", padx=5)

        # --- LLM Options Frame ---
        llm_frame = ttk.LabelFrame(main_frame, text="LLM Options (Claude API)", padding="10")
        llm_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        llm_frame.columnconfigure(1, weight=1)
        row += 1

        self.use_llm_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            llm_frame,
            text="Enable LLM prose rewrites (requires rewrite mode)",
            variable=self.use_llm_var
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        ttk.Label(llm_frame, text="API Key:").grid(row=1, column=0, sticky="w", pady=5)
        self.api_key_entry = ttk.Entry(llm_frame, width=50, show="*")
        # Pre-fill from environment if available
        env_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if env_key:
            self.api_key_entry.insert(0, env_key)
        self.api_key_entry.grid(row=1, column=1, sticky="ew", padx=5)

        ttk.Label(llm_frame, text="Model:").grid(row=2, column=0, sticky="w", pady=5)
        self.model_entry = ttk.Entry(llm_frame, width=50)
        self.model_entry.insert(0, "claude-sonnet-4-20250514")
        self.model_entry.grid(row=2, column=1, sticky="ew", padx=5)

        # --- Google Export Frame ---
        google_frame = ttk.LabelFrame(main_frame, text="Google Docs Export", padding="10")
        google_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        google_frame.columnconfigure(1, weight=1)
        row += 1

        self.export_google_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            google_frame,
            text="Export to Google Docs",
            variable=self.export_google_var
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(google_frame, text="Credentials JSON:").grid(row=1, column=0, sticky="w", pady=5)
        self.google_creds_entry = ttk.Entry(google_frame, width=50)
        self.google_creds_entry.grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Button(google_frame, text="Browse...", command=self._browse_google_creds).grid(row=1, column=2)

        ttk.Label(google_frame, text="Folder ID (optional):").grid(row=2, column=0, sticky="w", pady=5)
        self.folder_id_entry = ttk.Entry(google_frame, width=50)
        self.folder_id_entry.grid(row=2, column=1, sticky="ew", padx=5)

        # --- Run Button ---
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=3, pady=15)
        row += 1

        self.run_button = ttk.Button(
            button_frame,
            text="Run Pipeline",
            command=self._run_pipeline,
            width=20
        )
        self.run_button.pack()

        # --- Progress Section ---
        progress_frame = ttk.Frame(main_frame)
        progress_frame.grid(row=row, column=0, columnspan=3, sticky="ew")
        progress_frame.columnconfigure(0, weight=1)
        row += 1

        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.progress_var).grid(row=0, column=0, sticky="w")

        self.progress_bar = ttk.Progressbar(progress_frame, mode="indeterminate")
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=5)

        # --- Results Section ---
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding="10")
        results_frame.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=10)
        main_frame.rowconfigure(row, weight=1)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        self.results_text = tk.Text(results_frame, height=15, wrap="word", state="disabled")
        scrollbar = ttk.Scrollbar(results_frame, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        self.results_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def _browse_input(self) -> None:
        """Open file dialog for input DOCX."""
        path = filedialog.askopenfilename(
            title="Select Input DOCX",
            filetypes=[("Word Documents", "*.docx"), ("All Files", "*.*")]
        )
        if path:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, path)

    def _browse_output(self) -> None:
        """Open directory dialog for output."""
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    def _browse_google_creds(self) -> None:
        """Open file dialog for Google credentials."""
        path = filedialog.askopenfilename(
            title="Select Google Credentials JSON",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if path:
            self.google_creds_entry.delete(0, tk.END)
            self.google_creds_entry.insert(0, path)

    def _run_pipeline(self) -> None:
        """Execute the pipeline in a background thread."""
        if self.processing:
            return

        # Validate input
        input_path = self.input_entry.get().strip()
        if not input_path:
            messagebox.showerror("Error", "Please select an input DOCX file.")
            return

        if not Path(input_path).exists():
            messagebox.showerror("Error", f"Input file not found: {input_path}")
            return

        # Gather parameters
        params: Dict[str, Any] = {
            "input_docx": input_path,
            "out_dir": self.output_entry.get().strip() or "./dtc_out",
            "mode": self.mode_var.get(),
            "author": self.author_entry.get().strip() or "DTC Editorial Engine",
        }

        # LLM options
        if self.use_llm_var.get():
            api_key = self.api_key_entry.get().strip()
            if not api_key:
                messagebox.showerror("Error", "LLM enabled but no API key provided.")
                return
            if self.mode_var.get() != "rewrite":
                messagebox.showwarning(
                    "Warning",
                    "LLM rewrites only work in 'rewrite' mode. Switching to rewrite mode."
                )
                self.mode_var.set("rewrite")
                params["mode"] = "rewrite"

            params["use_llm"] = True
            params["anthropic_api_key"] = api_key
            params["llm_model"] = self.model_entry.get().strip() or "claude-sonnet-4-20250514"

        # Google export options
        if self.export_google_var.get():
            creds = self.google_creds_entry.get().strip()
            if not creds:
                messagebox.showerror("Error", "Google export enabled but no credentials file provided.")
                return
            if not Path(creds).exists():
                messagebox.showerror("Error", f"Credentials file not found: {creds}")
                return

            params["export_google_docs"] = True
            params["google_credentials"] = creds
            folder_id = self.folder_id_entry.get().strip()
            if folder_id:
                params["google_folder_id"] = folder_id

        # Start processing
        self.processing = True
        self.run_button.configure(state="disabled")
        self.progress_bar.start(10)
        self.progress_var.set("Processing...")

        # Clear previous results
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", tk.END)
        self.results_text.configure(state="disabled")

        # Run in background thread
        thread = threading.Thread(target=self._execute_pipeline, args=(params,))
        thread.daemon = True
        thread.start()

    def _execute_pipeline(self, params: Dict[str, Any]) -> None:
        """Execute pipeline in background thread."""
        try:
            from dtc_editor.pipeline import run_pipeline
            result = run_pipeline(**params)
            self.root.after(0, lambda: self._on_success(result))
        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"
            self.root.after(0, lambda: self._on_error(error_msg))

    def _on_success(self, result: Dict[str, Any]) -> None:
        """Handle successful pipeline completion."""
        self.processing = False
        self.run_button.configure(state="normal")
        self.progress_bar.stop()
        self.progress_var.set("Complete!")
        self.result = result
        self._display_results(result)

    def _on_error(self, error: str) -> None:
        """Handle pipeline error."""
        self.processing = False
        self.run_button.configure(state="normal")
        self.progress_bar.stop()
        self.progress_var.set("Error")
        messagebox.showerror("Pipeline Error", error[:500])  # Truncate long errors

        # Show error in results area too
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", tk.END)
        self.results_text.insert("1.0", f"ERROR:\n{error}")
        self.results_text.configure(state="disabled")

    def _display_results(self, result: Dict[str, Any]) -> None:
        """Display pipeline results in the results text area."""
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", tk.END)

        lines = []
        lines.append(f"Timestamp: {result.get('timestamp_utc', 'N/A')}")
        lines.append(f"Mode: {result.get('mode', 'N/A')}")
        lines.append("")

        # Stats
        stats = result.get("stats", {})
        lines.append("=== Statistics ===")
        lines.append(f"EditOps Total: {stats.get('editops_total', 0)}")
        lines.append(f"EditOps Applied: {stats.get('editops_applied', 0)}")
        lines.append(f"EditOps Rejected: {stats.get('editops_rejected', 0)}")
        lines.append(f"EditOps LLM: {stats.get('editops_llm', 0)}")
        lines.append(f"Findings Total: {stats.get('findings_total', 0)}")
        lines.append("")

        # LLM stats
        llm = result.get("llm", {})
        if llm and llm.get("enabled"):
            lines.append("=== LLM ===")
            lines.append(f"Model: {llm.get('model', 'N/A')}")
            lines.append(f"Prose Candidates: {llm.get('prose_candidates_attempted', 0)}")
            lines.append(f"EditOps Generated: {llm.get('editops_generated', 0)}")
            lines.append("")

        # Artifacts
        artifacts = result.get("artifacts", {})
        lines.append("=== Artifacts ===")
        lines.append(f"Clean DOCX: {artifacts.get('clean_docx', 'N/A')}")
        lines.append(f"Redline DOCX: {artifacts.get('redline_docx', 'N/A')}")
        if artifacts.get("google_doc_url"):
            lines.append(f"Google Doc: {artifacts.get('google_doc_url')}")
        lines.append("")

        # Redline status
        redline = result.get("redline_engine", {})
        lines.append("=== Redline ===")
        lines.append(f"Backend: {redline.get('backend', 'N/A')}")
        lines.append(f"Status: {redline.get('status', 'N/A')}")
        if redline.get("message"):
            lines.append(f"Message: {redline.get('message')}")
        lines.append("")

        # Google export
        google = result.get("google_export")
        if google:
            lines.append("=== Google Export ===")
            lines.append(f"Status: {google.get('status', 'N/A')}")
            if google.get("web_view_link"):
                lines.append(f"URL: {google.get('web_view_link')}")
            if google.get("message"):
                lines.append(f"Message: {google.get('message')}")
            lines.append("")

        # Findings summary
        findings = result.get("findings", [])
        if findings:
            lines.append(f"=== Findings ({len(findings)}) ===")
            for f in findings[:25]:
                sev = f.get('severity', '').upper()
                rule = f.get('rule_id', '')
                msg = f.get('message', '')
                lines.append(f"[{sev}] {rule}: {msg}")
            if len(findings) > 25:
                lines.append(f"... and {len(findings) - 25} more")
            lines.append("")

        # EditOps summary
        editops = result.get("editops", [])
        applied_ops = [o for o in editops if o.get("status") == "applied"]
        if applied_ops:
            lines.append(f"=== Applied EditOps ({len(applied_ops)}) ===")
            for op in applied_ops[:15]:
                intent = op.get('intent', '')
                before = (op.get('before', '')[:40] + '...') if len(op.get('before', '')) > 40 else op.get('before', '')
                after = (op.get('after', '')[:40] + '...') if len(op.get('after', '')) > 40 else op.get('after', '')
                engine = op.get('engine', '')
                lines.append(f"[{intent}] ({engine})")
                lines.append(f"  Before: {before}")
                lines.append(f"  After:  {after}")
            if len(applied_ops) > 15:
                lines.append(f"... and {len(applied_ops) - 15} more")

        self.results_text.insert("1.0", "\n".join(lines))
        self.results_text.configure(state="disabled")


def launch_gui() -> None:
    """Launch the GUI application."""
    root = tk.Tk()
    DTCEditorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
