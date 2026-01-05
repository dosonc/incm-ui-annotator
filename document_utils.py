"""
Document parsing and processing utility functions.
"""
from pathlib import Path
import json
import re
import config


def parse_doc_name(filename):
    """Parse document name DR_DD_MM_YYYY to extract date components."""
    # Remove .pdf extension if present
    name = filename.replace('.pdf', '').replace('_det.mmd', '').replace('.mmd', '')
    parts = name.split('_')
    if len(parts) >= 4 and parts[0] == 'DR':
        try:
            day = int(parts[1])
            month = int(parts[2])
            year = int(parts[3])
            return day, month, year
        except ValueError:
            return None, None, None
    return None, None, None


def extract_date_from_json(json_path):
    """
    Extract date information from the first page JSON file.
    Looks for date patterns in page headers.
    Returns (day, month, year) or (None, None, None) if not found.
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            page_data = json.load(f)
        
        # Look for date information in page headers
        for item in page_data:
            if item.get('category') == 'Page-header':
                text = item.get('text', '')
                
                # Try to extract date from text like "Segunda feira 20 de Maio"
                # Portuguese month names
                month_map = {
                    'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
                    'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
                    'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
                }
                
                # Pattern: day number followed by "de" and month name
                date_pattern = r'(\d+)\s+de\s+(\w+)'
                match = re.search(date_pattern, text, re.IGNORECASE)
                if match:
                    day = int(match.group(1))
                    month_name = match.group(2).lower()
                    month = month_map.get(month_name)
                    if month:
                        # Extract year from folder name or from text
                        year_match = re.search(r'Ano\s+(\d{4})', text, re.IGNORECASE)
                        if year_match:
                            year = int(year_match.group(1))
                            return day, month, year
                        # If no year in text, try to get from parent folder
                        parent = Path(json_path).parent.parent
                        try:
                            year = int(parent.name)
                            return day, month, year
                        except ValueError:
                            pass
        
        # If no date found in headers, try to get year from folder structure
        parent = Path(json_path).parent.parent
        try:
            year = int(parent.name)
            # Return with day/month as None - will create a year-only document
            return None, None, year
        except ValueError:
            return None, None, None
            
    except (json.JSONDecodeError, FileNotFoundError, KeyError):
        return None, None, None


def get_documents_data():
    """Extract all documents from year folders and return as list of document data."""
    parsed_docs_dir = config.PARSED_DOCS_DIR
    year_dirs = sorted([d for d in parsed_docs_dir.iterdir() if d.is_dir()])
    
    documents_data = []
    for year_dir in year_dirs:
        # Find PDF files in this year folder
        pdf_files = [f for f in year_dir.glob("DR_*.pdf") if "_layouts" not in f.name]
        for pdf_file in pdf_files:
            day, month, year = parse_doc_name(pdf_file.name)
            if day is not None:
                documents_data.append({
                    'path': year_dir,  # The year folder path
                    'name': pdf_file.stem,  # Document name without extension (DR_DD_MM_YYYY)
                    'day': day,
                    'month': month,
                    'year': year
                })
    
    return documents_data

