#!/usr/bin/env python3
"""
Script to extract code blocks from files and save them to separate files.
Non-code content is saved to a file prefixed with "notes_".
Only processes files that are detected as code files.
"""

import os
import re
import sys
import argparse
from pygments.lexers import guess_lexer, get_lexer_for_filename, get_lexer_by_name, TextLexer
from pygments.lexers.markup import MarkdownLexer
from pygments.util import ClassNotFound

# Define custom extensions mapping
CUSTOM_MAPPING = {
    ".inc": "php",      # Treat .inc files as PHP
    ".rules": "python", # Treat .rules files as Python
    ".myext": "c++",    # Treat .myext files as C++
    ".logcfg": "json",  # Treat .logcfg files as JSON
    ".prompt": "text",  # Treat prompt files as text
    ".chatdsl": "dsl"   # chatdsl domain language
}

def is_code_file(file_path):
    """
    Determine if a file is a code file using Pygments.

    Args:
        file_path (str): Path to the file to analyze.

    Returns:
        bool: True if the file is code, False otherwise.
    """
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()

    lexer = None

    # 1. Check Custom Mapping First
    if ext in CUSTOM_MAPPING:
        try:
            lexer = get_lexer_by_name(CUSTOM_MAPPING[ext])
        except ClassNotFound:
            pass

    # 2. Identify by standard extension if no custom mapping found
    if not lexer:
        try:
            lexer = get_lexer_for_filename(filename)
        except ClassNotFound:
            lexer = None

    # 3. Read content for analysis
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(10000)

        if not content.strip():
            return False

        # 4. If still no lexer, guess by content
        if not lexer:
            try:
                lexer = guess_lexer(content)
            except ClassNotFound:
                return False

        # 5. Final Classification Logic
        non_code_types = ['Text only', 'Markdown', 'ChaiScript', 'Gettext catalog']

        if isinstance(lexer, (MarkdownLexer, TextLexer)) or lexer.name in non_code_types:
            return False

        return True

    except Exception:
        return False

def extract_code_blocks(file_path):
    """
    Extract code blocks from a file and return them along with non-code content.

    Args:
        file_path (str): Path to the file to process.

    Returns:
        tuple: (code_blocks, non_code_content)
    """
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
        content = file.read()

    # Pattern to match code blocks (e.g., ```cpp ... ```)
    code_block_pattern = re.compile(r'```\w*\n([\s\S]*?)```', re.MULTILINE)
    code_blocks = code_block_pattern.findall(content)

    # Remove code blocks from the content to get non-code content
    non_code_content = code_block_pattern.sub('', content)

    return code_blocks, non_code_content

def process_file(file_path):
    """
    Process a file to extract code blocks and save them to separate files.
    Only processes files that are detected as code files.

    Args:
        file_path (str): Path to the file to process.
    """
    # First check if the file is a code file
    if not is_code_file(file_path):
        print(f"Skipping non-code file: {file_path}")
        return

    code_blocks, non_code_content = extract_code_blocks(file_path)

    if not code_blocks:
        print(f"No code blocks found in {file_path}")
        return

    # Save the first code block to the original file
    code_block = code_blocks[0]
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(code_block)

    # Save non-code content to a notes file
    base_name = os.path.basename(file_path)
    notes_file_path = os.path.join(os.path.dirname(file_path), f"notes_{base_name}")
    with open(notes_file_path, 'w', encoding='utf-8') as file:
        file.write(non_code_content)

    print(f"Processed {file_path} -> {notes_file_path}")

def main(directory):
    """
    Main function to process all files in a directory.

    Args:
        directory (str): Directory to process.
    """
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            process_file(file_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract code blocks from files.")
    parser.add_argument("directory", help="Directory to process")
    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: {args.directory} is not a valid directory.")
        sys.exit(1)

    main(args.directory)
