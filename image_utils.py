"""
Image processing utility functions.
"""
import io
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import config


def load_pdf_page_as_image(pdf_path, page_number, target_dpi=None, offset_x=None, offset_y=None):
    """
    Load a specific page from a PDF file and convert it to a PIL Image.
    
    Args:
        pdf_path: Path to the PDF file
        page_number: Page number (1-indexed)
        target_dpi: Target DPI for rendering (defaults to config.TARGET_DPI)
        offset_x: X offset for coordinate adjustment (defaults to config.OFFSET_X)
        offset_y: Y offset for coordinate adjustment (defaults to config.OFFSET_Y)
    
    Returns:
        tuple: (PIL Image, dict with metadata including img_width, img_height, 
                rendered_width, rendered_height, page_width_pt, page_height_pt,
                actual_scale_x, actual_scale_y)
    """
    if target_dpi is None:
        target_dpi = config.TARGET_DPI
    if offset_x is None:
        offset_x = config.OFFSET_X
    if offset_y is None:
        offset_y = config.OFFSET_Y
    
    pdf_doc = fitz.open(str(pdf_path))
    if page_number > len(pdf_doc):
        raise ValueError(f"Page {page_number} not found in PDF")
    
    page = pdf_doc[page_number - 1]  # PDF pages are 0-indexed
    page_rect = page.rect
    
    # Get the page dimensions in points
    page_width_pt = page_rect.width
    page_height_pt = page_rect.height
    
    # Calculate scale factor based on target DPI
    # PyMuPDF default is 72 DPI, so scale_factor = target_dpi / 72
    # Match the exact processing method: zoom = dpi / 72.0
    zoom = target_dpi / float(config.DEFAULT_DPI)
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
    
    metadata = {
        'img_width': img_width,
        'img_height': img_height,
        'rendered_width': rendered_width,
        'rendered_height': rendered_height,
        'page_width_pt': page_width_pt,
        'page_height_pt': page_height_pt,
        'actual_scale_x': actual_scale_x,
        'actual_scale_y': actual_scale_y,
        'offset_x': offset_x,
        'offset_y': offset_y,
    }
    
    return img, metadata


def crop_and_highlight_bbox(img, bbox, img_metadata):
    """
    Crop image to show only the selected bounding box with highlighting.
    
    Args:
        img: PIL Image
        bbox: Tuple of (x1, y1, x2, y2) coordinates
        img_metadata: Dictionary with image metadata from load_pdf_page_as_image
    
    Returns:
        PIL Image: Cropped and highlighted image
    """
    x1, y1, x2, y2 = bbox
    img_width = img_metadata['img_width']
    img_height = img_metadata['img_height']
    offset_x = img_metadata['offset_x']
    offset_y = img_metadata['offset_y']
    rendered_width = img_metadata['rendered_width']
    rendered_height = img_metadata['rendered_height']
    page_width_pt = img_metadata['page_width_pt']
    page_height_pt = img_metadata['page_height_pt']
    
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
    padding = config.CROP_PADDING
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
    draw_overlay.rectangle([box_x1, box_y1, box_x2, box_y2], 
                          fill=config.BBOX_OVERLAY_COLOR, outline=None)
    
    # Composite the overlay onto the cropped image
    cropped_img = Image.alpha_composite(cropped_img.convert('RGBA'), overlay).convert('RGB')
    
    return cropped_img

