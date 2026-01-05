"""
Text processing utility functions.
"""
import re as regex_module


def is_table(text):
    """Check if the text contains a table (HTML format)."""
    if not text:
        return False
    return text.strip().startswith('<table>')


def count_words(text):
    """Count words in text, handling tables and regular text."""
    if not text:
        return 0
    # Check if it's a table (HTML format)
    if is_table(text):
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
    if is_table(obtained_text) and is_table(ground_truth):
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

