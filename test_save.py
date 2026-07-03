# -*- coding: utf-8 -*-
"""Dry-run save test"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tianyou_editor import parse_array_by_lines, parse_fields_in_entry

tp = r'G:\1_ruanjian\game\qikan\Mount&Blade Warband\Modules\Native1175\source\module_troops.py'
header, entries, footer = parse_array_by_lines(tp, 'troops')

print 'Entries:', len(entries)

# Reconstruct
parts = [header]
for i, e in enumerate(entries):
    if i < len(entries) - 1:
        parts.append(e + ',\n')
    else:
        parts.append(e + '\n')
parts.append(footer)
output = ''.join(parts)

lines = output.split('\n')
print 'Output lines:', len(lines)

# Find 'troops = [' and show surrounding lines
for i, line in enumerate(lines):
    if 'troops = [' in line:
        print '\n--- Entries section start (line %d) ---' % (i+1)
        for j in range(i, min(i+10, len(lines))):
            print '%4d: %s' % (j+1, lines[j][:100])
        break

# Show last lines
print '\n--- Last entries ---'
for j in range(max(0, len(lines)-10), len(lines)):
    print '%4d: %s' % (j+1, lines[j][:100])

# Count entries by counting lines that start with '  ["'
count = 0
for line in lines:
    if line.strip().startswith('["') or line.strip().startswith("['"):
        count += 1
print '\nEntry starts found:', count
print 'Expected:', len(entries)
print 'Match:', 'OK' if count == len(entries) else 'MISMATCH!'
