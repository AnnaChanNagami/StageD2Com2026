#!/usr/bin/env python3
"""Fix code_block sections that have literal newlines instead of escaped ones"""

with open('generate_cahier_des_charges.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all code_block sections and fix them
# The issue is that lines end with \n' which means the \n is being treated as a literal newline

import re

# Pattern to match code_block sections
# We need to find sections that have the pattern:
#   '...\n'
#   '...'
# where the \n is literal (not escaped)

# Let's use a different approach - find all lines that end with \n'
# and fix them by adding the escape

lines = content.split('\n')
fixed_lines = []

i = 0
while i < len(lines):
    line = lines[i]
    
    # Check if this line ends with \n' (literal newline before closing quote)
    # This means the string has a literal newline instead of an escaped one
    if line.rstrip().endswith("\\n'") or line.rstrip().endswith("\\n'"):
        # This line is OK - it has the escaped newline
        fixed_lines.append(line)
    elif line.rstrip().endswith("'") and i + 1 < len(lines) and lines[i + 1].strip() == "'":
        # This line ends with ' and the next line is just '
        # This means there's a literal newline that needs to be escaped
        # Add \\n before the closing quote
        new_line = line[:-1] + "\\n'"
        fixed_lines.append(new_line)
        # Skip the next line (the lone ')
        i += 2
        continue
    
    fixed_lines.append(line)
    i += 1

content = '\n'.join(fixed_lines)

with open('generate_cahier_des_charges.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed code_block sections")
