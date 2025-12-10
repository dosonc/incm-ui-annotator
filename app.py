import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import pandas as pd
import re as regex_module
from parser import parse_mmd_file
from database import init_db, insert_error, get_errors, delete_error

# Initialize database
init_db()

# Page config
st.set_page_config(page_title="OCR Annotation Tool", layout="wide")

# Helper functions for word counting and comparison
def count_words(text):
    """Count words in text, handling tables and regular text."""
    if not text:
        return 0
    # Check if it's a table (HTML format)
    if text.strip().startswith('<table>'):
        # For tables, extract text from cells and count words
        cell_texts = regex_module.findall(r'<td>(.*?)</td>', text, regex_module.DOTALL)
        all_text = ' '.join(cell_texts)
        # Remove HTML entities and normalize
        all_text = all_text.strip()
    else:
        all_text = text.strip()
    
    # Split into words (handle punctuation as word boundaries)
    # Use \w+ which matches word characters (letters, digits, underscore)
    words = regex_module.findall(r'\b\w+\b', all_text)
    return len(words)

def count_differing_words(obtained_text, ground_truth):
    """Count the number of words that differ between obtained text and ground truth."""
    if not obtained_text or not ground_truth:
        return 0
    
    # Handle tables - if both are tables, we need to compare cell by cell
    if obtained_text.strip().startswith('<table>') and ground_truth.strip().startswith('<table>'):
        # Extract cells from both tables
        obtained_cells = regex_module.findall(r'<td>(.*?)</td>', obtained_text, regex_module.DOTALL)
        ground_truth_cells = regex_module.findall(r'<td>(.*?)</td>', ground_truth, regex_module.DOTALL)
        
        # Compare corresponding cells
        differing_words = 0
        max_len = max(len(obtained_cells), len(ground_truth_cells))
        for i in range(max_len):
            obtained_cell = obtained_cells[i].strip() if i < len(obtained_cells) else ""
            truth_cell = ground_truth_cells[i].strip() if i < len(ground_truth_cells) else ""
            
            # Get words from each cell
            obtained_words = regex_module.findall(r'\b\w+\b', obtained_cell)
            truth_words = regex_module.findall(r'\b\w+\b', truth_cell)
            
            # Count words that differ (using simple alignment)
            differing_words += abs(len(obtained_words) - len(truth_words))
            # Also check word-by-word differences (simplified - just count different lengths or positions)
            min_len = min(len(obtained_words), len(truth_words))
            for j in range(min_len):
                if obtained_words[j].lower() != truth_words[j].lower():
                    differing_words += 1
        
        return differing_words
    else:
        # Regular text comparison
        obtained_words = regex_module.findall(r'\b\w+\b', obtained_text)
        truth_words = regex_module.findall(r'\b\w+\b', ground_truth)
        
        # Count differing words using sequence alignment approach
        # Simple approach: count words in the shorter sequence that don't match
        differing_words = 0
        min_len = min(len(obtained_words), len(truth_words))
        
        for i in range(min_len):
            if obtained_words[i].lower() != truth_words[i].lower():
                differing_words += 1
        
        # Add difference in length as additional differing words
        differing_words += abs(len(obtained_words) - len(truth_words))
        
        return differing_words

# Get all document directories
parsed_docs_dir = Path("parsed_docs")
doc_dirs = sorted([d for d in parsed_docs_dir.iterdir() if d.is_dir()])

if not doc_dirs:
    st.error("No document directories found in parsed_docs/")
    st.stop()

# Sidebar for document selection
st.sidebar.title("Document Selection")
selected_dir = st.sidebar.selectbox(
    "Select Document",
    options=doc_dirs,
    format_func=lambda x: x.name
)

# Create tabs for Annotation and Statistics
tab1, tab2 = st.tabs(["📝 Annotation", "📊 Statistics"])

# Find PDF and MMD files
# Use the regular PDF (not the layouts PDF which has boxes drawn on it)
pdf_files = [f for f in selected_dir.glob("DR_*.pdf") if "_layouts" not in f.name]
mmd_files = list(selected_dir.glob("DR_*_det.mmd"))

if not pdf_files or not mmd_files:
    st.error(f"Missing PDF or MMD files in {selected_dir.name}")
    st.stop()

pdf_path = pdf_files[0]
mmd_path = mmd_files[0]
document_name = selected_dir.name

# Parse MMD file
if 'parsed_data' not in st.session_state or st.session_state.get('current_doc') != document_name:
    with st.spinner("Parsing MMD file..."):
        st.session_state.parsed_data = parse_mmd_file(str(mmd_path))
        st.session_state.current_doc = document_name

parsed_data = st.session_state.parsed_data

# Page selection
pages = sorted(parsed_data.keys())
if not pages:
    st.error("No pages found in MMD file")
    st.stop()

selected_page = st.sidebar.selectbox("Select Page", options=pages, index=0)

# Fixed settings to match OCR processing (144 DPI)
target_dpi = 144
offset_x = 0
offset_y = 0

# Get bounding boxes for selected page
bboxes_data = parsed_data[selected_page]

# Load PDF page as image
try:
    pdf_doc = fitz.open(str(pdf_path))
    if selected_page > len(pdf_doc):
        st.error(f"Page {selected_page} not found in PDF")
        st.stop()
    
    page = pdf_doc[selected_page - 1]  # PDF pages are 0-indexed
    page_rect = page.rect
    
    # Get the page dimensions in points
    page_width_pt = page_rect.width
    page_height_pt = page_rect.height
    
    # Calculate scale factor based on target DPI
    # PyMuPDF default is 72 DPI, so scale_factor = target_dpi / 72
    # Match the exact processing method: zoom = dpi / 72.0
    zoom = target_dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    # Use alpha=False to match the original processing
    pix = page.get_pixmap(matrix=mat, alpha=False)
    
    # Get actual rendered dimensions
    rendered_width = pix.width
    rendered_height = pix.height
    
    # Calculate the actual scale factor based on rendered vs PDF dimensions
    # This accounts for any DPI differences
    actual_scale_x = rendered_width / page_width_pt
    actual_scale_y = rendered_height / page_height_pt
    
    img_data = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_data))
    
    # Get image dimensions
    img_width, img_height = img.size
    
    pdf_doc.close()
    
except Exception as e:
    st.error(f"Error loading PDF: {e}")
    st.stop()

# Initialize bbox_num in session state if not exists
if 'bbox_num' not in st.session_state:
    st.session_state.bbox_num = 1

# Get the current bounding box coordinates
current_bbox_num = st.session_state.bbox_num
current_bbox, _ = bboxes_data[current_bbox_num - 1] if current_bbox_num <= len(bboxes_data) else (None, None)

# Crop image to show only the selected bounding box
if current_bbox:
    x1, y1, x2, y2 = current_bbox
    
    # Check if coordinates are normalized (0-999 range) or already in pixels
    max_coord = max(x1, y1, x2, y2)
    
    if max_coord <= 999:
        # Coordinates are normalized to 0-999, scale to image dimensions
        x1_scaled = int(x1 / 999 * img_width) + offset_x
        y1_scaled = int(y1 / 999 * img_height) + offset_y
        x2_scaled = int(x2 / 999 * img_width) + offset_x
        y2_scaled = int(y2 / 999 * img_height) + offset_y
    else:
        # Coordinates are already in pixel space
        actual_scale_x = rendered_width / page_width_pt
        actual_scale_y = rendered_height / page_height_pt
        x1_scaled = int(x1 * actual_scale_x) + offset_x
        y1_scaled = int(y1 * actual_scale_y) + offset_y
        x2_scaled = int(x2 * actual_scale_x) + offset_x
        y2_scaled = int(y2 * actual_scale_y) + offset_y
    
    # Ensure coordinates are within image bounds
    x1_scaled = max(0, min(x1_scaled, img_width))
    y1_scaled = max(0, min(y1_scaled, img_height))
    x2_scaled = max(0, min(x2_scaled, img_width))
    y2_scaled = max(0, min(y2_scaled, img_height))
    
    # Crop the image to the bounding box with some padding
    padding = 20
    crop_x1 = max(0, x1_scaled - padding)
    crop_y1 = max(0, y1_scaled - padding)
    crop_x2 = min(img_width, x2_scaled + padding)
    crop_y2 = min(img_height, y2_scaled + padding)
    
    # Crop the image
    cropped_img = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
    
    # Adjust coordinates relative to crop
    box_x1 = x1_scaled - crop_x1
    box_y1 = y1_scaled - crop_y1
    box_x2 = x2_scaled - crop_x1
    box_y2 = y2_scaled - crop_y1
    
    # Create a transparent overlay for the bounding box
    overlay = Image.new('RGBA', cropped_img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    
    # Draw semi-transparent light blue rectangle
    # Light blue with transparency: (173, 216, 230, 100) - light blue with ~40% opacity
    draw_overlay.rectangle([box_x1, box_y1, box_x2, box_y2], 
                          fill=(173, 216, 230, 100), outline=None)
    
    # Composite the overlay onto the cropped image
    cropped_img = Image.alpha_composite(cropped_img.convert('RGBA'), overlay).convert('RGB')
    
    display_img = cropped_img
else:
    display_img = img

# Annotation tab
with tab1:
    # Main layout - PDF on left, form on right
    col1, col2 = st.columns([1, 1])

with col1:
    st.subheader(f"Page {selected_page} - Bounding Box {current_bbox_num}")
    st.image(display_img, use_container_width=True)

with col2:
    st.subheader("Submit Error")
    
    # Bounding box number selection with custom +/- buttons
    st.write("**Bounding Box Number**")
    bbox_col1, bbox_col2, bbox_col3 = st.columns([1, 3, 1])
    
    with bbox_col1:
        decrement_clicked = st.button("◄", key="decrement_bbox", use_container_width=True)
        if decrement_clicked:
            if st.session_state.bbox_num > 1:
                st.session_state.bbox_num -= 1
            st.rerun()
    
    with bbox_col2:
        bbox_num = st.number_input(
            "",
            min_value=1,
            max_value=len(bboxes_data),
            value=st.session_state.bbox_num,
            step=1,
            key="bbox_input",
            label_visibility="collapsed"
        )
        # Update session state when user changes the input
        if bbox_num != st.session_state.bbox_num:
            st.session_state.bbox_num = bbox_num
            st.rerun()
    
    with bbox_col3:
        increment_clicked = st.button("►", key="increment_bbox", use_container_width=True)
        if increment_clicked:
            if st.session_state.bbox_num < len(bboxes_data):
                st.session_state.bbox_num += 1
            st.rerun()
    
    # Get the text for selected bounding box - use current session state value
    current_bbox_num = st.session_state.bbox_num
    selected_bbox_text = bboxes_data[current_bbox_num - 1][1] if current_bbox_num <= len(bboxes_data) else ""
    
    # Form for error submission
    with st.form("error_form", clear_on_submit=True):
        # Obtained text (non-editable) - use the current bbox text
        st.text_area(
            "Obtained text",
            value=selected_bbox_text,
            height=150,
            disabled=True,
            key=f"obtained_text_{current_bbox_num}"
        )
        
        # Ground truth (editable)
        ground_truth = st.text_area(
            "Ground Truth",
            height=150,
            key="ground_truth"
        )
        
        # Error type
        error_type = st.selectbox(
            "Error Type",
            options=["minor", "major"],
            key="error_type"
        )
        
        submitted = st.form_submit_button("Submit Error", type="primary")
        
        if submitted:
            if not ground_truth.strip():
                st.error("Please provide the ground truth text")
            else:
                insert_error(
                    document_name=document_name,
                    page_number=selected_page,
                    bbox_number=st.session_state.bbox_num,
                    text_with_error=selected_bbox_text,
                    ground_truth=ground_truth,
                    error_type=error_type
                )
                st.success("Error submitted successfully!")
                st.rerun()

# Show existing errors for this document/page
st.divider()
st.subheader("Existing Errors")

errors = get_errors(document_name)
page_errors = [e for e in errors if e['page_number'] == selected_page]

if page_errors:
    # Display errors with delete buttons
    for idx, err in enumerate(page_errors):
        col1, col2 = st.columns([10, 1])
        
        with col1:
            st.markdown(f"**Box #{err['bbox_number']}** - {err['error_type']}")
            st.markdown(f"**Text with Error:** {err['text_with_error'][:100]}{'...' if len(err['text_with_error']) > 100 else ''}")
            st.markdown(f"**Ground Truth:** {err['ground_truth'][:100]}{'...' if len(err['ground_truth']) > 100 else ''}")
        
        with col2:
            if st.button("🗑️", key=f"delete_{err['id']}", help="Delete this error"):
                delete_error(err['id'])
                st.success("Error deleted!")
                st.rerun()
        
        if idx < len(page_errors) - 1:
            st.divider()
    else:
        st.info("No errors submitted for this page yet.")

# Statistics tab
with tab2:
    st.header("Annotation Statistics")
    
    # Get all errors
    all_errors = get_errors()
    
    if not all_errors:
        st.info("No annotations recorded yet.")
    else:
        # Overall statistics
        col1, col2, col3, col4 = st.columns(4)
        
        total_errors = len(all_errors)
        minor_errors = len([e for e in all_errors if e['error_type'] == 'minor'])
        major_errors = len([e for e in all_errors if e['error_type'] == 'major'])
        unique_documents = len(set(e['document_name'] for e in all_errors))
        
        with col1:
            st.metric("Total Errors", total_errors)
        with col2:
            st.metric("Minor Errors", minor_errors)
        with col3:
            st.metric("Major Errors", major_errors)
        with col4:
            st.metric("Documents", unique_documents)
        
        # Calculate word error statistics
        with st.spinner("Calculating word error statistics..."):
            # Get unique document names that have errors
            documents_with_errors = set(error['document_name'] for error in all_errors)
            
            # Count total OCR words only from documents with errors
            total_ocr_words = 0
            for doc_name in documents_with_errors:
                doc_dir = parsed_docs_dir / doc_name
                if doc_dir.exists() and doc_dir.is_dir():
                    mmd_file_list = list(doc_dir.glob("DR_*_det.mmd"))
                    if mmd_file_list:
                        try:
                            parsed_doc_data = parse_mmd_file(str(mmd_file_list[0]))
                            for page_num, bboxes in parsed_doc_data.items():
                                for bbox, text in bboxes:
                                    total_ocr_words += count_words(text)
                        except Exception as e:
                            st.warning(f"Could not parse {doc_name}: {e}")
            
            # Count error words
            minor_error_words = 0
            major_error_words = 0
            total_error_words = 0
            
            for error in all_errors:
                error_word_count = count_differing_words(
                    error['text_with_error'], 
                    error['ground_truth']
                )
                total_error_words += error_word_count
                if error['error_type'] == 'minor':
                    minor_error_words += error_word_count
                else:
                    major_error_words += error_word_count
            
            # Calculate percentages
            minor_error_pct = (minor_error_words / total_ocr_words * 100) if total_ocr_words > 0 else 0
            major_error_pct = (major_error_words / total_ocr_words * 100) if total_ocr_words > 0 else 0
            total_error_pct = (total_error_words / total_ocr_words * 100) if total_ocr_words > 0 else 0
        
        # Word error statistics section
        st.subheader("Word Error Statistics")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total OCR Words", f"{total_ocr_words:,}")
        with col2:
            st.metric("Total Error Words", f"{total_error_words:,}", f"{total_error_pct:.3f}%")
        with col3:
            st.metric("Minor Error Words", f"{minor_error_words:,}", f"{minor_error_pct:.3f}%")
        with col4:
            st.metric("Major Error Words", f"{major_error_words:,}", f"{major_error_pct:.3f}%")
        with col5:
            accuracy = (1 - total_error_pct / 100) * 100 if total_ocr_words > 0 else 100
            st.metric("Accuracy", f"{accuracy:.3f}%")
        
        st.divider()
        
        # Errors by document
        st.subheader("Errors by Document")
        doc_stats = {}
        for error in all_errors:
            doc_name = error['document_name']
            if doc_name not in doc_stats:
                doc_stats[doc_name] = {'total': 0, 'minor': 0, 'major': 0}
            doc_stats[doc_name]['total'] += 1
            doc_stats[doc_name][error['error_type']] += 1
        
        # Display as table
        doc_df = pd.DataFrame([
            {
                'Document': doc,
                'Total': stats['total'],
                'Minor': stats['minor'],
                'Major': stats['major']
            }
            for doc, stats in sorted(doc_stats.items())
        ])
        st.dataframe(doc_df, use_container_width=True, hide_index=True)
        
        st.divider()
        
        # Errors per page for selected document
        st.subheader(f"Errors per Page - {selected_dir.name}")
        doc_errors = [e for e in all_errors if e['document_name'] == selected_dir.name]
        
        if doc_errors:
            page_stats = {}
            for error in doc_errors:
                page_num = error['page_number']
                if page_num not in page_stats:
                    page_stats[page_num] = {'total': 0, 'minor': 0, 'major': 0}
                page_stats[page_num]['total'] += 1
                page_stats[page_num][error['error_type']] += 1
            
            page_df = pd.DataFrame([
                {
                    'Page': page,
                    'Total': stats['total'],
                    'Minor': stats['minor'],
                    'Major': stats['major']
                }
                for page, stats in sorted(page_stats.items())
            ])
            st.dataframe(page_df, use_container_width=True, hide_index=True)
            
            # Bar chart of errors per page
            if len(page_df) > 0:
                st.subheader("Errors per Page (Chart)")
                st.bar_chart(page_df.set_index('Page')[['Minor', 'Major']], height=400)
        else:
            st.info(f"No errors recorded for document {selected_dir.name} yet.")
        
        st.divider()
        
        # Recent errors
        st.subheader("Recent Errors")
        recent_errors = sorted(all_errors, key=lambda x: x['created_at'], reverse=True)[:10]
        
        for error in recent_errors:
            with st.expander(f"{error['document_name']} - Page {error['page_number']}, Box {error['bbox_number']} ({error['error_type']})"):
                st.write(f"**Text with Error:** {error['text_with_error'][:200]}{'...' if len(error['text_with_error']) > 200 else ''}")
                st.write(f"**Ground Truth:** {error['ground_truth'][:200]}{'...' if len(error['ground_truth']) > 200 else ''}")
                st.caption(f"Submitted: {error['created_at']}")

