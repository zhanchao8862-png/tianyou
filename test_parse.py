# -*- coding: utf-8 -*-
import sys, os, re, codecs

source_path = r'G:\1_ruanjian\game\qikan\Mount&Blade Warband\Modules\Native1175\source'

with codecs.open(os.path.join(source_path, 'module_troops.py'), 'r', 'utf-8', errors='replace') as f:
    content = f.read()

# Find troops = [
m = re.search(r'(?:^|\n)\s*troops\s*=\s*\[', content, re.MULTILINE)
if not m:
    print 'FAIL: troops = [ not found'
    sys.exit(1)

print 'FOUND troops = [ at position', m.start()
body_start = m.end()

# Parse entries
entries = []
depth = 0
entry_start = None
in_string = False
sc = None
array_close = -1
i = body_start

while i < len(content):
    c = content[i]
    if not in_string:
        if c in ('"', "'"):
            in_string = True
            sc = c
        elif c == '#':
            while i < len(content) and content[i] not in '\r\n':
                i += 1
            i -= 1
        elif c == '[':
            if depth == 0:
                entry_start = i
            depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0 and entry_start is not None:
                entries.append(content[entry_start:i + 1])
                entry_start = None
            elif depth < 0:
                array_close = i
                break
    else:
        if c == sc and (i > 0 and content[i - 1] != '\\'):
            in_string = False
            sc = None
        elif c == '\\':
            i += 1
    i += 1

print 'Entries parsed:', len(entries)
print 'Array close at:', array_close

if entries:
    print 'First entry[:150]:', repr(entries[0][:150])
    print 'Last entry[:150]:', repr(entries[-1][:150])

# Extract IDs
ids = []
for e in entries:
    s = e.strip()
    if s.startswith('[') and len(s) > 2:
        m2 = re.search(r'"([^"]+)"', s[1:])
        if m2:
            ids.append(m2.group(1))

print 'Sample IDs:', ids[:5], '...', ids[-3:] if len(ids) > 3 else ''
print 'Total troops:', len(ids)

# Also test items
with codecs.open(os.path.join(source_path, 'module_items.py'), 'r', 'utf-8', errors='replace') as f:
    icontent = f.read()

im = re.search(r'(?:^|\n)\s*items\s*=\s*\[', icontent, re.MULTILINE)
if im:
    body_start = im.end()
    ientries = []
    depth = 0
    entry_start = None
    in_string = False
    sc = None
    i = body_start
    
    while i < len(icontent):
        c = icontent[i]
        if not in_string:
            if c in ('"', "'"):
                in_string = True
                sc = c
            elif c == '#':
                while i < len(icontent) and icontent[i] not in '\r\n':
                    i += 1
                i -= 1
            elif c == '[':
                if depth == 0:
                    entry_start = i
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0 and entry_start is not None:
                    ientries.append(icontent[entry_start:i + 1])
                    entry_start = None
                elif depth < 0:
                    break
        else:
            if c == sc and (i > 0 and icontent[i - 1] != '\\'):
                in_string = False
                sc = None
            elif c == '\\':
                i += 1
        i += 1
    
    print '\nItems parsed:', len(ientries)
else:
    print '\nFAIL: items = [ not found'
