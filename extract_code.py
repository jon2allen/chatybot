#!/usr/bin/env python3
"""
Script to extract code blocks from files and save them to separate files.
Non-code content is saved to a file prefixed with "notes_".
"""

import os
import re
import sys

def extract_code_blocks(file_path):
    """
    Extract code blocks from a file and return them along with non-code content.
    
    Args:
        file_path (str): Path to the file to process.
    
    Returns:
        tuple: (code_blocks, non_code_content)
    """
    with open(file_path, 'r') as file:
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
    
    Args:
        file_path (str): Path to the file to process.
    """
    code_blocks, non_code_content = extract_code_blocks(file_path)
    
    if not code_blocks:
        print(f"No code blocks found in {file_path}")
        return
    
    # Save the first code block to the original file
    code_block = code_blocks[0]
    with open(file_path, 'w') as file:
        file.write(code_block)
    
    # Save non-code content to a notes file
    base_name = os.path.basename(file_path)
    notes_file_path = os.path.join(os.path.dirname(file_path), f"notes_{base_name}")
    with open(notes_file_path, 'w') as file:
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
    if len(sys.argv) != 2:
        print("Usage: python extract_code.py <directory>")
        sys.exit(1)
    
    directory = sys.argv[1]
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a valid directory.")
        sys.exit(1)
    
    main(directory)
