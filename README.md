# OCR Annotation Tool

A Streamlit-based UI for annotators to find and submit errors in transcribed OCR text.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the app:
```bash
streamlit run app.py
```

## Usage

1. Select a document from the sidebar
2. Select a page number
3. View the PDF page with numbered bounding boxes
4. Review the text table on the right
5. Submit errors using the form at the bottom
6. Errors are stored in `annotations.db` SQLite database

## Database

Errors are stored in SQLite database (`annotations.db`) with the following schema:
- document_name: Name of the document directory
- page_number: Page number in the document
- bbox_number: Bounding box number on the page
- text_with_error: The text containing the error
- ground_truth: The correct text
- error_type: "minor" or "major"
- created_at: Timestamp of submission

