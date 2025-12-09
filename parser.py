import re
from typing import List, Tuple, Dict
from pathlib import Path


def parse_mmd_file(mmd_path: str) -> Dict[int, List[Tuple[List[int], str]]]:
    """
    Parse .mmd file and return a dictionary mapping page numbers to 
    list of (bounding_box, text) tuples.
    
    Returns:
        Dict[int, List[Tuple[List[int], str]]]: {page_num: [(bbox, text), ...]}
    """
    with open(mmd_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by page separators
    pages = content.split('<--- Page Split --->')
    
    result = {}
    for page_num, page_content in enumerate(pages, start=1):
        lines = page_content.strip().split('\n')
        bboxes = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Look for bounding box pattern: <|det|>[[x1, y1, x2, y2]]<|/det|>
            bbox_match = re.search(r'<\|det\|>\[\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]\]<\|/det\|>', line)
            
            if bbox_match:
                x1, y1, x2, y2 = map(int, bbox_match.groups())
                bbox = [x1, y1, x2, y2]
                
                # Get the text from the next non-empty line that's not a bbox line
                text = ""
                j = i + 1
                while j < len(lines):
                    candidate = lines[j].strip()
                    if candidate and not candidate.startswith('<|'):
                        text = candidate
                        break
                    j += 1
                
                if text:
                    bboxes.append((bbox, text))
                    i = j + 1
                    continue
            
            i += 1
        
        if bboxes:
            result[page_num] = bboxes
    
    return result

