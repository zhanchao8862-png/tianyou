# -*- coding: utf-8 -*-
import codecs, re

with codecs.open(r'G:\1_ruanjian\game\qikan\Mount&Blade Warband\Modules\Native1175\source\module_troops.py', 'r', 'utf-8', errors='replace') as f:
    lines = f.readlines()

# Find all lines that look like they start an entry (2-4 space indent, start with [)
entries_start = []
for i, line in enumerate(lines):
    stripped = line.lstrip()
    if stripped.startswith('[') and len(stripped) > 2 and stripped[1] in '"\'':
        indent = len(line) - len(stripped)
        if indent < 8:  # only top-level entries
            entries_start.append(i)

print 'Potential entry start lines:', len(entries_start)
print 'First few:', entries_start[:10]
print 'Last few:', entries_start[-5:]

# Skip commented lines (##)
real_starts = [e for e in entries_start if not lines[e].lstrip().startswith('[#')]
commented = len(entries_start) - len(real_starts)
print 'Real entries:', len(real_starts), '(commented out:', commented, ')'

# Show some entries starting at line 243
print '\n--- Lines around troops = [ ---'
for i in range(242, 255):
    marker = ' <-- ENTRY' if i in entries_start else ''
    print '%04d: %s%s' % (i+1, lines[i].rstrip('\r\n'), marker)

# Show the array close
print '\n--- Looking for closing ] ---'
for i in range(2620, 2640):
    line = lines[i].rstrip('\r\n')
    if ']' in line:
        print '%04d: %s' % (i+1, line)
