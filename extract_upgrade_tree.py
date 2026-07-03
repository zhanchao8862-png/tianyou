# -*- coding: utf-8 -*-
"""Extract upgrade tree - standalone, no tianyou_editor import"""
import re, sys

src_path = 'G:/1_ruanjian/game/qikan/Mount&Blade Warband/Modules/Ahao/Module_system 1.171/module_troops.py'
with open(src_path, 'r') as f:
    content = f.read()

# Simple regex to extract troops array entries
# Each entry: ["id","name","plural", ...]
entries = re.findall(r'^\s*\["([^"]+)",\s*"([^"]*)",\s*"([^"]*)",\s*(.*?)\]', content, re.DOTALL | re.MULTILINE)

# For upgrade, the fields are typically at positions 14 and 15 after splitting
# Let's use the existing line-based approach: find the troops array first
lines = content.split('\n')

# Find troops = [ ... ]
in_troops = False
depth = 0
troop_lines = []
for line in lines:
    stripped = line.strip()
    if 'troops' in stripped and ('=[' in stripped or '= [' in stripped):
        in_troops = True
    if in_troops:
        depth += stripped.count('[') - stripped.count(']')
        troop_lines.append(line)
        if depth == 0 and len(troop_lines) > 1:
            break

# Now parse each troop entry from these lines
import json
# Re-join and try to parse
raw = '\n'.join(troop_lines)
# Find the array start
idx = raw.index('[')
raw = raw[idx:]

# Use ast.literal_eval or manual parsing
# Manual: find each ['...' pattern
tree = {}
pattern = re.compile(
    r'\s*\[\s*"([^"]+)"\s*,\s*"([^"]*)"\s*,[^,]*,\s*[^,]*,\s*[^,]*,\s*[^,]*,\s*[^,]*,\s*[^,]*,\s*[^,]*,\s*[^,]*,\s*[^,]*,\s*[^,]*,\s*'
    r'(?:[^,]*),\s*([^,\]]*)\s*,\s*([^,\]]*)\s*\]',
    re.DOTALL
)

# Actually let's just parse line by line smarter
# Each troop entry starts with '  ["'
entries_raw = re.findall(r'\s*\["([^"]+)"', raw)
print 'Found %d troop entries by ID pattern' % len(entries_raw)

# Use regex to extract full entries with upgrade fields
entry_pattern = re.compile(
    r'\["([^"]+)",\s*"([^"]*)",\s*"([^"]*)",\s*(.*?)\]\s*,?\s*(?=\n\s*\["|$)',
    re.DOTALL
)
matches = entry_pattern.findall(raw)
print 'Parsed %d full entries' % len(matches)

# For each entry, extract upgrade1 (F14) and upgrade2 (F15) from field 3
tree = {}
for m in matches:
    tid = m[0]
    name = m[1]
    body = m[3]  # everything after plural
    # Split by commas, but respect brackets
    fields = []
    current = ''
    depth = 0
    for ch in body:
        if ch == '[':
            depth += 1
            current += ch
        elif ch == ']':
            depth -= 1
            current += ch
        elif ch == ',' and depth == 0:
            fields.append(current.strip())
            current = ''
        else:
            current += ch
    if current.strip():
        fields.append(current.strip())
    
    # upgrades are typically at index 11(F14) and 12(F15) after name/plural
    # But due to variable field counts, find from end: 
    # F15=upgrade1 is 2nd from end, F14=upgrade2 is 3rd from end
    up1 = '0'
    up2 = '0'
    if len(fields) >= 2:
        up1 = fields[-2].strip().strip('"\'')
        up2 = fields[-3].strip().strip('"\'')
    
    tree[tid] = {
        'name': name,
        'upgrade1': up1,
        'upgrade2': up2
    }

# Summary
total = len(tree)
with_upgrade = sum(1 for v in tree.values() if v['upgrade1'] != '0' or v['upgrade2'] != '0')
print '\nTotal troops: %d' % total
print 'With upgrades: %d' % with_upgrade

# Parents map
parents = {}
for tid, info in tree.items():
    for target in [info['upgrade1'], info['upgrade2']]:
        if target and target != '0':
            parents.setdefault(target, []).append(tid)

roots = [tid for tid in tree if tid not in parents]
leafs = [tid for tid, info in tree.items() 
         if info['upgrade1'] == '0' and info['upgrade2'] == '0']

print 'Roots (no parent): %d' % len(roots)
print 'Leafs (no children): %d' % len(leafs)

# Show chains
print '\n=== Sample Chains ==='
shown = 0
for tid in roots[:20]:
    chain = []
    cur = tid
    visited = set()
    while cur and cur != '0' and cur not in visited:
        visited.add(cur)
        chain.append(cur)
        info = tree.get(cur, {})
        up1 = info.get('upgrade1', '0')
        up2 = info.get('upgrade2', '0')
        nxt = up2 if up2 != '0' else (up1 if up1 != '0' else None)
        cur = nxt
        if len(chain) > 15:
            break
    if len(chain) > 1:
        shown += 1
        if shown <= 15:
            print '  %s' % ' -> '.join(chain)

# Branches
branches = [(tid, info) for tid, info in tree.items() 
            if info['upgrade1'] != '0' and info['upgrade2'] != '0']
print '\nBranches (2 children): %d' % len(branches)
for tid, info in branches[:5]:
    print '  %s -> %s / %s' % (tid, info['upgrade1'], info['upgrade2'])

# Multi-parent
multi_parent = [(tid, p) for tid, p in parents.items() if len(p) > 1]
print '\nMulti-parent troops: %d' % len(multi_parent)
for tid, p in multi_parent[:10]:
    print '  %s <- %s' % (tid, ', '.join(p))

# Save full tree to JSON for reference
with open('upgrade_tree.json', 'w') as f:
    json.dump(tree, f, indent=2, ensure_ascii=False)
print '\nSaved upgrade_tree.json'
print 'Sample entries:'
for tid, info in list(tree.items())[:5]:
    print '  %s: up1=%s up2=%s name=%s' % (tid, info['upgrade1'], info['upgrade2'], info['name'])
