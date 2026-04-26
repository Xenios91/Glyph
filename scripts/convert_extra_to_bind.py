#!/usr/bin/env python3
"""Script to convert extra={"extra_data": {...}} pattern to logger.bind() for loguru."""
import re
import sys
from pathlib import Path

def convert_file(filepath: str) -> int:
    """Convert extra pattern in a file. Returns number of conversions."""
    with open(filepath, 'r') as f:
        content = f.read()

    original = content
    conversions = 0

    # Pattern 1: extra={"extra_data": variable_name}
    # Convert: logger.info("msg %s", arg, extra={"extra_data": log_data},)
    # To:      logger.bind(**log_data).info("msg {}", arg,)
    pattern1 = r'(logger\.\w+\()\s*(".*?")\s*,\s*extra=\{"extra_data":\s*(\w+)\}'
    def replace1(m):
        nonlocal conversions
        conversions += 1
        method_call_start = m.group(1)  # logger.info(
        message = m.group(2)  # "msg %s"
        var_name = m.group(3)  # log_data
        # Convert %s/%d/%f to {}
        new_message = message.replace('%s', '{}').replace('%d', '{}').replace('%f', '{}')
        return f'logger.bind(**{var_name}).{method_call_start[len("logger."):]}"{new_message}"'
    # This is too complex for simple regex. Let me use a different approach.

    # Actually, let me use a line-by-line approach that's more reliable
    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if this line contains extra={"extra_data":
        if 'extra={"extra_data":' in line:
            # Find the logger call - might span multiple lines
            # Look backwards to find the logger.XXX( start
            call_start = i
            while call_start >= 0 and 'logger.' not in lines[call_start]:
                call_start -= 1
            
            if call_start >= 0:
                # Collect the full multi-line call
                call_end = i
                brace_count = 0
                paren_count = 0
                started = False
                for j in range(call_start, len(lines)):
                    for ch in lines[j]:
                        if ch == '(':
                            paren_count += 1
                            started = True
                        elif ch == ')':
                            paren_count -= 1
                        elif ch == '{':
                            brace_count += 1
                        elif ch == '}':
                            brace_count -= 1
                    if started and paren_count <= 0:
                        call_end = j
                        break
                
                # Get the full call
                full_call = '\n'.join(lines[call_start:call_end + 1])
                
                # Convert the call
                converted = convert_logger_call(full_call)
                if converted != full_call:
                    conversions += 1
                    # Replace lines
                    new_lines.extend(converted.split('\n'))
                    i = call_end + 1
                    continue
        
        new_lines.append(line)
        i += 1
    
    new_content = '\n'.join(new_lines)
    if new_content != original:
        with open(filepath, 'w') as f:
            f.write(new_content)
    
    return conversions


def convert_logger_call(call: str) -> str:
    """Convert a logger call from extra= pattern to bind() pattern."""
    # Strategy: 
    # 1. Extract the logger method (logger.info, logger.warning, etc.)
    # 2. Extract the extra={"extra_data": ...} part
    # 3. Remove the extra= part
    # 4. Convert %s/%d to {} in the message
    # 5. Prepend logger.bind(**var) or logger.bind(key=val)
    
    # Match logger.METHOD(
    method_match = re.search(r'(logger)\.(\w+)\(', call)
    if not method_match:
        return call
    
    logger_part = method_match.group(1)
    method = method_match.group(2)
    
    # Find extra={"extra_data": ...}
    extra_match = re.search(r'extra=\{"extra_data":\s*(\w+)\}', call)
    if not extra_match:
        # Try inline dict: extra={"extra_data": {...}}
        extra_match = re.search(r'extra=\{"extra_data":\s*\{[^}]*\}\}', call)
    
    if not extra_match:
        return call
    
    extra_content = extra_match.group(0)
    
    # Determine if it's a variable or inline dict
    var_match = re.search(r'extra=\{"extra_data":\s*(\w+)\}', call)
    if var_match:
        var_name = var_match.group(1)
        bind_call = f'logger.bind(**{var_name})'
    else:
        # Inline dict - extract key-value pairs
        dict_match = re.search(r'extra=\{"extra_data":\s*\{([^}]*)\}\}', call)
        if dict_match:
            dict_content = dict_match.group(1)
            # Parse key-value pairs like "key1": "val1", "key2": "val2"
            pairs = re.findall(r'"([^"]+)":\s*"([^"]*)"', dict_content)
            if pairs:
                bind_args = ', '.join(f'{k}="{v}"' for k, v in pairs)
                bind_call = f'logger.bind({bind_args})'
            else:
                return call
        else:
            return call
    
    # Remove the extra= part from the call
    new_call = call.replace(extra_content, '').strip()
    # Clean up trailing commas before closing paren
    new_call = re.sub(r',\s*\)', ')', new_call)
    
    # Replace logger.METHOD with bind_call.METHOD
    new_call = new_call.replace(f'logger.{method}(', f'{bind_call}.{method}(')
    
    # Convert %s, %d, %f to {} in string literals
    def convert_format(m):
        s = m.group(0)
        s = s.replace('%s', '{}').replace('%d', '{}').replace('%f', '{}')
        return s
    
    new_call = re.sub(r'"[^"]*%[sd][^"]*"', convert_format, new_call)
    
    return new_call


if __name__ == '__main__':
    files = [
        'app/api/v1/endpoints/config.py',
        'app/api/v1/endpoints/binaries.py',
        'app/api/v1/endpoints/status.py',
        'app/config/settings.py',
        'app/auth/security_logger.py',
        'app/auth/dependencies.py',
        'app/processing/task_management.py',
        'app/processing/pipeline.py',
        'app/core/request_tracing.py',
        'app/database/sql_service.py',
        'app/database/session_handler.py',
        'app/utils/performance_logger.py',
        'app/services/task_service.py',
    ]
    
    total = 0
    for f in files:
        if Path(f).exists():
            count = convert_file(f)
            print(f"{f}: {count} conversions")
            total += count
        else:
            print(f"{f}: FILE NOT FOUND")
    
    print(f"\nTotal: {total} conversions")
