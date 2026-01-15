"""
DTC Editor - Streamlit GUI

Simple drag-and-drop interface for the holistic editorial pipeline.
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
)

# File uploader with drag-and-drop
uploaded_file = st.file_uploader(
    "Drop your Word document here",
    type=["docx"],
    help="Drag and drop a .docx file or click to browse",
)

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
                # Import and run pipeline
                from dtc_editor.adapters.docx_adapter import extract_ir_and_inventory, emit_clean_docx
                from dtc_editor.holistic import run_holistic_pipeline, HolisticConfig, generate_review_report

                status_text.text("Loading document...")
                progress_bar.progress(10, text="Loading document...")

                ir, inventory = extract_ir_and_inventory(str(input_path))

                # Configure pipeline
                config = HolisticConfig(
                    api_key=api_key,
                    model="claude-sonnet-4-20250514",
                    chunk_strategy="paragraph",
                    max_concurrent=1,  # Reduced to avoid rate limits
                    vale_config=str(Path(__file__).parent / "rules" / "vale" / ".vale.ini"),
                    auto_accept=True,
                )

                status_text.text("Rewriting with AI...")
                progress_bar.progress(20, text="Rewriting with AI (this takes a few minutes)...")

                # Run pipeline
                result = run_holistic_pipeline(ir, config)

                progress_bar.progress(80, text="Generating outputs...")
                status_text.text("Generating clean document...")

                # Generate outputs
                doc_stem = Path(uploaded_file.name).stem
                clean_path = output_dir / f"{doc_stem}.clean.docx"
                review_path = output_dir / f"{doc_stem}.review.md"

                # Emit clean document
                emit_clean_docx(
                    str(input_path),
                    result.final_ir,
                    str(clean_path),
                )

                # Generate review report
                review_content = generate_review_report(result)
                with open(review_path, "w") as f:
                    f.write(review_content)

                # Generate redline
                status_text.text("Generating redline...")
                redline_path = output_dir / f"{doc_stem}.redline.docx"

                from dtc_editor.redline import create_redline
                create_redline(
                    str(input_path),
                    str(clean_path),
                    str(redline_path),
                    author="DTC Editor",
                )

                progress_bar.progress(100, text="Complete!")
                status_text.text("")

                # Read file contents into memory before temp dir is cleaned up
                with open(clean_path, "rb") as f:
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
                st.session_state['stats'] = {
                    'words_before': result.stats.total_words_original,
                    'words_after': result.stats.total_words_final,
                    'chunks': result.stats.rewritable_chunks,
                    'reduction': (1 - result.stats.total_words_final / result.stats.total_words_original) * 100
                }

            except Exception as e:
                st.error(f"Error: {str(e)}")
                raise e

# Show results if we have them in session state
if 'clean_data' in st.session_state:
    stats = st.session_state['stats']
    doc_stem = st.session_state['doc_stem']

    # Success message
    st.success(f"**Done!** Reduced word count by {stats['reduction']:.1f}%")

    # Stats
    col1, col2, col3 = st.columns(3)
    col1.metric("Words Before", f"{stats['words_before']:,}")
    col2.metric("Words After", f"{stats['words_after']:,}")
    col3.metric("Chunks Processed", stats['chunks'])

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
st.markdown("*Powered by Claude AI*")
