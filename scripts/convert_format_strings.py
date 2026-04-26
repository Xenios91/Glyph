#!/usr/bin/env python3
"""Convert %s/%d/%f formatting to {} in multi-line logger calls, and remove exc_info=True."""
import re
from pathlib import Path

def convert_file(filepath: str) -> int:
    """Convert formatting in logger calls. Returns number of conversions."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original = content
    conversions = 0
    
    # Convert %s, %d, %f to {} in string literals (but not %%)
    def convert_format_string(match):
        nonlocal conversions
        s = match.group(0)
        if re.search(r'%(?!%)', s):
            s = s.replace('%s', '{}').replace('%d', '{}').replace('%f', '{}')
            conversions += 1
        return s
    
    # Process double-quoted strings (including multi-line)
    content = re.sub(r'"(?:[^"\\]|\\.)*"', convert_format_string, content)
    # Process single-quoted strings
    content = re.sub(r"'(?:[^'\\]|\\.)*'", convert_format_string, content)
    
    # Remove exc_info=True (with various whitespace patterns)
    # Handle: , exc_info=True,  or  exc_info=True,  or  exc_info=True\n
    exc_info_pattern = r',?\s*exc_info\s*=\s*True\s*,?\s*\n?'
    while True:
        new_content = re.sub(exc_info_pattern, '', content)
        if new_content == content:
            break
        content = new_content
        conversions += 1
    
    # Clean up any trailing commas before closing paren
    content = re.sub(r',\s*\)', ')', content)
    
    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
    
    return conversions


if __name__ == '__main__':
    app_dir = Path('app')
    total = 0
    
    for py_file in app_dir.rglob('*.py'):
        count = convert_file(str(py_file))
        if count > 0:
            print(f"{py_file}: {count} conversions")
            total += count
    
    print(f"\nTotal: {total} conversions")
