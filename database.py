import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict


DB_PATH = 'annotations.db'


def init_db():
    """Initialize the SQLite database with errors table."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_name TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            bbox_number INTEGER NOT NULL,
            text_with_error TEXT NOT NULL,
            ground_truth TEXT NOT NULL,
            error_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()


def insert_error(document_name: str, page_number: int, bbox_number: int, 
                 text_with_error: str, ground_truth: str, error_type: str):
    """Insert an error annotation into the database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO errors (document_name, page_number, bbox_number, 
                          text_with_error, ground_truth, error_type)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (document_name, page_number, bbox_number, text_with_error, 
          ground_truth, error_type))
    
    conn.commit()
    conn.close()


def get_errors(document_name: str = None) -> List[Dict]:
    """Get all errors, optionally filtered by document name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if document_name:
        c.execute('''
            SELECT * FROM errors 
            WHERE document_name = ?
            ORDER BY page_number, bbox_number
        ''', (document_name,))
    else:
        c.execute('''
            SELECT * FROM errors 
            ORDER BY document_name, page_number, bbox_number
        ''')
    
    rows = c.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def delete_error(error_id: int):
    """Delete an error annotation by ID."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('DELETE FROM errors WHERE id = ?', (error_id,))
    
    conn.commit()
    conn.close()


def get_ground_truth(document_name: str, page_number: int, bbox_number: int) -> str:
    """Get ground truth for a specific bbox, if it exists."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('''
        SELECT ground_truth FROM errors 
        WHERE document_name = ? AND page_number = ? AND bbox_number = ?
        ORDER BY created_at DESC
        LIMIT 1
    ''', (document_name, page_number, bbox_number))
    
    row = c.fetchone()
    conn.close()
    
    return row['ground_truth'] if row else ""

