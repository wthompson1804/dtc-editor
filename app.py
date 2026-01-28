"""
DTC Editor - Streamlit GUI

Drag-and-drop interface for the editorial pipeline with multiple editing modes.
Run with: streamlit run app.py
"""
import streamlit as st
import tempfile
import os
import shutil
from pathlib import Path
import time

st.set_page_config(
    page_title="DTC Editor",
    page_icon="📝",
    layout="centered",
)

st.title("📝 DTC Editorial Engine")
st.markdown("Transform technical documents with AI-powered editing.")

# API Key input
api_key = st.text_input(
    "Anthropic API Key",
    type="password",
    help="Your Anthropic API key for Claude",
    value=os.environ.get("ANTHROPIC_API_KEY", ""),
)

# File uploader with drag-and-drop
uploaded_file = st.file_uploader(
    "Drop your Word document here",
    type=["docx"],
    help="Drag and drop a .docx file or click to browse",
)

# Mode selection with explanations
st.markdown("---")
st.markdown("### Editing Mode")

mode = st.radio(
    "Choose how you want your document edited:",
    options=["style_only", "readability", "combined"],
    format_func=lambda x: {
        "style_only": "Style Conformance Only",
        "readability": "Readability Rewrite",
        "combined": "Readability + Style Polish (Recommended)",
    }[x],
    index=2,  # Default to combined
    help="Select the type of editing to apply",
)

# Mode explanations
with st.expander("What do these modes do?", expanded=False):
    st.markdown("""
    **Style Conformance Only**
    - Applies DTC/AP style guidelines (capitalization, formatting)
    - Fixes common wordy phrases ("in order to" → "to")
    - Minimal changes - preserves your writing voice
    - Best for: Final polish before publication

    **Readability Rewrite**
    - AI rewrites paragraphs for clarity and conciseness
    - Follows Orwell-inspired principles (active voice, cut filler)
    - Makes substantive changes while preserving content
    - Best for: Dense technical prose needing improvement

    **Readability + Style Polish (Recommended)**
    - First: AI rewrites for readability
    - Then: Applies style conformance to the result
    - Ensures the AI output follows DTC/AP guidelines
    - Best for: Comprehensive document improvement
    """)

# Additional options based on mode
if mode == "readability" or mode == "combined":
    with st.expander("Advanced Options", expanded=False):
        chunk_strategy = st.selectbox(
            "Chunking Strategy",
            options=["paragraph", "section", "adaptive"],
            index=0,
            help="How to divide the document for rewriting. 'paragraph' is safest."
        )
        auto_accept = st.checkbox(
            "Auto-accept all rewrites",
            value=True,
            help="Automatically accept passing validations without flagging for review"
        )
else:
    chunk_strategy = "paragraph"
    auto_accept = True

# Process button
if uploaded_file and api_key:
    if st.button("✨ Process Document", type="primary", use_container_width=True):

        # Create temp directory for processing
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save uploaded file
            input_path = Path(tmpdir) / uploaded_file.name
            with open(input_path, "wb") as f:
                f.write(uploaded_file.getvalue())

            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            # Progress display
            progress_bar = st.progress(0, text="Starting pipeline...")
            status_text = st.empty()

            try:
                # Import adapters
                from dtc_editor.adapters.docx_adapter import extract_ir_and_inventory, emit_clean_docx

                status_text.text("Loading document...")
                progress_bar.progress(10, text="Loading document...")

                ir, inventory = extract_ir_and_inventory(str(input_path))

                # Find vale config
                vale_config = str(Path(__file__).parent / "rules" / "vale" / ".vale.ini")
                if not Path(vale_config).exists():
                    vale_config = None

                if mode == "style_only":
                    # Run the new style-only pipeline (Layer 1 + Layer 2)
                    status_text.text("Running style conformance checks...")
                    progress_bar.progress(20, text="Running structural fixes...")

                    from dtc_editor.surgical import (
                        run_style_only_pipeline,
                        StyleOnlyConfig,
                        StructuralFixesConfig,
                    )

                    # Configure the style-only pipeline
                    style_config = StyleOnlyConfig(
                        structural=StructuralFixesConfig(),
                        enable_vale=vale_config is not None,
                        vale_config_path=vale_config,
                        create_redline=False,  # We'll create redline ourselves
                    )

                    progress_bar.progress(40, text="Running Vale linting...")

                    # Run the pipeline
                    result = run_style_only_pipeline(
                        input_path=str(input_path),
                        output_dir=str(output_dir),
                        config=style_config,
                    )

                    progress_bar.progress(80, text="Generating outputs...")

                    # The pipeline creates a timestamped bundle; find the clean file
                    doc_stem = Path(uploaded_file.name).stem
                    final_clean = Path(result.clean_path)

                    # Copy to our expected location
                    expected_clean = output_dir / f"{doc_stem}.clean.docx"
                    if str(final_clean) != str(expected_clean):
                        shutil.copy2(final_clean, expected_clean)
                        final_clean = expected_clean

                    # Generate review content
                    structural = result.structural
                    vale = result.vale

                    review_content = f"""# Style Conformance Report

## Summary
| Metric | Value |
|--------|-------|
| Structural Changes | {structural.total_changes} |
| Vale Edits Applied | {vale.editops_applied} |
| Vale Findings | {vale.findings_count} |

## Layer 1: Structural Fixes (python-docx)
| Processor | Result |
|-----------|--------|
| Chapters | {structural.chapter_result.chapters_numbered if structural.chapter_result else 0} numbered |
| Figures/Tables | {structural.figure_table_result.captions_added if structural.figure_table_result else 0} captions |
| Acronyms | {structural.acronym_result.expansions_made if structural.acronym_result else 0} expanded |

## Layer 2: Vale Linting
Status: {vale.status}
{vale.message}

## Mode
Style conformance only (surgical pipeline - no LLM rewriting)
"""
                    stats = {
                        'words_before': inventory.word_count,
                        'words_after': inventory.word_count,  # Minimal change expected
                        'chunks': structural.total_changes + vale.editops_applied,
                        'reduction': 0,
                        'mode': 'style_only',
                        'structural_changes': structural.total_changes,
                        'vale_edits': vale.editops_applied,
                    }

                else:
                    # Run holistic pipeline (readability or combined)
                    from dtc_editor.holistic import run_holistic_pipeline, HolisticConfig, generate_review_report

                    # Configure pipeline
                    config = HolisticConfig(
                        api_key=api_key,
                        model="claude-sonnet-4-20250514",
                        chunk_strategy=chunk_strategy,
                        max_concurrent=1,  # Reduced to avoid rate limits
                        vale_config=vale_config,
                        auto_accept=auto_accept,
                        style_polish=(mode == "combined"),  # Enable style polish for combined mode
                    )

                    status_text.text("Rewriting with AI...")
                    progress_bar.progress(20, text="Rewriting with AI...")

                    def progress_callback(stage, completed, total):
                        pct = 20 + int(60 * (completed / max(total, 1)))
                        status_text.text(f"{stage}: {completed}/{total}")
                        progress_bar.progress(min(pct, 80), text=f"{stage}...")

                    result = run_holistic_pipeline(ir, config, progress_callback=progress_callback)

                    progress_bar.progress(80, text="Generating outputs...")
                    status_text.text("Generating clean document...")

                    # Generate outputs
                    doc_stem = Path(uploaded_file.name).stem
                    final_clean = output_dir / f"{doc_stem}.clean.docx"

                    # Emit clean document
                    emit_clean_docx(
                        str(input_path),
                        result.final_ir,
                        str(final_clean),
                    )

                    # Generate review report
                    review_content = generate_review_report(result)

                    stats = {
                        'words_before': result.stats.total_words_original,
                        'words_after': result.stats.total_words_final,
                        'chunks': result.stats.rewritable_chunks,
                        'reduction': (1 - result.stats.total_words_final / result.stats.total_words_original) * 100,
                        'mode': mode,
                    }

                    # Add style polish stats if applicable
                    if result.stats.style_polish.enabled:
                        stats['style_polish'] = {
                            'findings': result.stats.style_polish.findings_count,
                            'edits_applied': result.stats.style_polish.editops_applied,
                        }

                # Save review report
                review_path = output_dir / f"{doc_stem}.review.md"
                with open(review_path, "w") as f:
                    f.write(review_content)

                # Generate redline
                status_text.text("Generating redline...")
                redline_path = output_dir / f"{doc_stem}.redline.docx"

                from dtc_editor.redline import create_redline
                create_redline(
                    str(input_path),
                    str(final_clean),
                    str(redline_path),
                    author="DTC Editor",
                )

                progress_bar.progress(100, text="Complete!")
                status_text.text("")

                # Read file contents into memory before temp dir is cleaned up
                with open(final_clean, "rb") as f:
                    clean_data = f.read()
                with open(redline_path, "rb") as f:
                    redline_data = f.read()
                with open(review_path, "rb") as f:
                    review_data = f.read()

                # Store in session state so they persist across re-runs
                st.session_state['clean_data'] = clean_data
                st.session_state['redline_data'] = redline_data
                st.session_state['review_data'] = review_data
                st.session_state['doc_stem'] = doc_stem
                st.session_state['stats'] = stats

            except Exception as e:
                st.error(f"Error: {str(e)}")
                import traceback
                st.code(traceback.format_exc())

# Show results if we have them in session state
if 'clean_data' in st.session_state:
    stats = st.session_state['stats']
    doc_stem = st.session_state['doc_stem']

    # Success message based on mode
    mode_name = {
        'style_only': 'Style Conformance',
        'readability': 'Readability Rewrite',
        'combined': 'Readability + Style Polish',
    }.get(stats.get('mode', 'combined'), 'Processing')

    if stats['reduction'] > 0:
        st.success(f"**{mode_name} Complete!** Reduced word count by {stats['reduction']:.1f}%")
    else:
        st.success(f"**{mode_name} Complete!**")

    # Stats
    col1, col2, col3 = st.columns(3)
    col1.metric("Words Before", f"{stats['words_before']:,}")
    col2.metric("Words After", f"{stats['words_after']:,}")
    col3.metric("Chunks Processed", stats['chunks'])

    # Style polish stats if present
    if 'style_polish' in stats:
        st.info(f"Style Polish: {stats['style_polish']['edits_applied']} style fixes applied")

    # Download buttons
    st.markdown("### Downloads")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.download_button(
            "📄 Clean Document",
            st.session_state['clean_data'],
            file_name=f"{doc_stem}.clean.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    with col2:
        st.download_button(
            "📝 Redline",
            st.session_state['redline_data'],
            file_name=f"{doc_stem}.redline.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    with col3:
        st.download_button(
            "📋 Change Log",
            st.session_state['review_data'],
            file_name=f"{doc_stem}.review.md",
            mime="text/markdown",
        )

    # Clear results button
    if st.button("Process Another Document"):
        for key in ['clean_data', 'redline_data', 'review_data', 'doc_stem', 'stats']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

elif uploaded_file and not api_key:
    st.warning("Please enter your Anthropic API key to process the document.")
elif not uploaded_file:
    st.info("Upload a Word document (.docx) to get started.")

# Footer
st.markdown("---")
st.markdown("""
*Powered by Claude AI*

**Modes:**
- **Style Conformance**: Quick fixes for DTC/AP guidelines
- **Readability Rewrite**: AI-powered prose improvement
- **Combined**: Best of both - improved readability that follows style guidelines
""")
