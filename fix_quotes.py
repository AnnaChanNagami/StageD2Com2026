#!/usr/bin/env python3
"""Fix apostrophe issues in generate_cahier_des_charges.py"""

with open('generate_cahier_des_charges.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace problematic single-quoted strings that contain apostrophes
# with double-quoted strings

# Find all lines that are string continuations (start with spaces and a quote)
lines = content.split('\n')
fixed_lines = []

for i, line in enumerate(lines):
    stripped = line.strip()
    
    # If it's a string line starting with ' and the content has an apostrophe
    # that would break the string
    if stripped.startswith("'") and not stripped.startswith("'''") and not stripped.startswith('"""'):
        # Check if there's an unescaped apostrophe inside
        inner = stripped[1:]  # Remove opening quote
        if inner.endswith("'"):
            inner = inner[:-1]  # Remove closing quote
        
        # Count unescaped apostrophes in inner content
        count = 0
        for j, char in enumerate(inner):
            if char == "'" and (j == 0 or inner[j-1] != '\\'):
                count += 1
        
        # If there are apostrophes, this string might be broken
        # Try to fix by using double quotes
        if count > 0:
            # Replace outer quotes with double quotes
            indent = line[:len(line) - len(stripped)]
            new_line = indent + '"' + stripped[1:-1] + '"'
            fixed_lines.append(new_line)
            continue
    
    fixed_lines.append(line)

content = '\n'.join(fixed_lines)

with open('generate_cahier_des_charges.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed apostrophe issues")
