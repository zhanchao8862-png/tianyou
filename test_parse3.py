# -*- coding: utf-8 -*-
"""Test new line-based parser for module_troops.py"""
import codecs, re

with codecs.open(r'G:\1_ruanjian\game\qikan\Mount&Blade Warband\Modules\Native1175\source\module_troops.py', 'r', 'utf-8', errors='replace') as f:
    lines = f.readlines()

# Strategy: parse entries using line boundaries
# 1. Find 'troops = [' line
# 2. Find matching ']' at same indent
# 3. For lines between, use heuristic: entry starts with [ + quote, 
#    all subsequent lines belong to same entry until next start

troop_start = -1
for i, line in enumerate(lines):
    if re.match(r'^\s*troops\s*=\s*\[', line):
        troop_start = i
        break

# Find array close (] at same indent as troops = [)
base_indent = len(re.match(r'^(\s*)', lines[troop_start]).group(1))
array_close = -1
for i in range(troop_start + 1, len(lines)):
    stripped = lines[i].rstrip('\r\n')
    line_indent = len(lines[i]) - len(lines[i].lstrip())
    if stripped == ']' and line_indent == base_indent:
        array_close = i
        break

print 'troops = [ at line', troop_start + 1
print 'Array ] at line', array_close + 1

# Parse entries between troop_start+1 and array_close
entries = []
current_lines = []
in_entry = False

for i in range(troop_start + 1, array_close):
    line = lines[i]
    stripped = line.lstrip()

    # Skip empty lines between entries
    if not stripped:
        continue

    # Skip comment lines (but not commented-out entries)
    if stripped.startswith('#') and not (stripped.startswith('##') and len(stripped) > 3 and stripped[2:].lstrip().startswith('[')):
        continue

    # Check if this line is an entry start: starts with [ + quote/double-quote
    is_entry_start = (stripped.startswith('[') and 
                      len(stripped) > 2 and 
                      stripped[1] in '"\'')

    if is_entry_start:
        if in_entry:
            # Close previous entry
            entries.append(''.join(current_lines))
            current_lines = []
        in_entry = True
        current_lines.append(line)
    elif in_entry:
        current_lines.append(line)

# Don't forget last entry
if current_lines:
    entries.append(''.join(current_lines))

print 'Entries parsed:', len(entries)

# Verify: parse fields and extract IDs
ids = []
for e in entries:
    stripped = e.strip()
    if stripped.startswith('[') and len(stripped) > 2 and stripped[1] in '"\'':
        # Extract first quoted string
        m2 = re.search(r'["]([^"]+)["]', stripped)
        if m2:
            ids.append(m2.group(1))

print 'Sample IDs:', ids[:5], '...', ids[-5:] if len(ids) > 5 else ''
print 'Total IDs:', len(ids)

# Check for invalid entries
for i, e in enumerate(entries[:10]):
    print '  Entry %d: %s' % (i, repr(e[:80]))

# Verify the parser catches all entries by checking line count
# Count lines that are entry starts (excluding commented-out)
entry_starts = 0
for i in range(troop_start + 1, array_close):
    stripped = lines[i].lstrip()
    if stripped.startswith('[') and len(stripped) > 2 and stripped[1] in '"\'' and not stripped.startswith('[#'):
        entry_starts += 1
print '\nEntry start lines found:', entry_starts
print 'Entries extracted:', len(entries)
print 'Match:', 'OK' if entry_starts == len(entries) else 'MISMATCH!'
