import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import io
import base64
from parser import parse_mmd_file
from database import init_db, insert_error, get_errors, delete_error

# Initialize database
init_db()

# Page config
st.set_page_config(page_title="OCR Annotation Tool", layout="wide")

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

