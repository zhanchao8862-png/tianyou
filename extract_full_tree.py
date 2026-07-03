# -*- coding: utf-8 -*-
"""Extract upgrade tree - parse both inline fields AND upgrade()/upgrade2() calls"""
import sys, io, re, json

_real = sys.stdout
sys.stdout = io.StringIO()
sys.path.insert(0, 'C:/Users/Administrator/.qclaw/workspace-tfxjjhfnjialcuju/tianyou_editor')
import tianyou_editor
sys.stdout = _real

src = 'G:/1_ruanjian/game/qikan/Mount&Blade Warband/Modules/Ahao/Module_system 1.171/module_troops.py'

# 1. Parse troops array
header, entries, footer = tianyou_editor.parse_array_by_lines(src, 'troops')
fields_list = [tianyou_editor.parse_fields_in_entry(e) for e in entries]

# Build base tree from inline fields
tree = {}
for i, flds in enumerate(fields_list):
    if len(flds) >= 1:
        tid = flds[0].strip(chr(34)+chr(39))
        name = flds[1].strip(chr(34)+chr(39)) if len(flds) > 1 else ''
        up1 = flds[14].strip(chr(34)+chr(39)) if len(flds) > 14 else '0'
        up2 = flds[15].strip(chr(34)+chr(39)) if len(flds) > 15 else '0'
        tree[tid] = {'name': name, 'upgrade1': up1, 'upgrade2': up2, 'index': i,
                     'fields': len(flds), 'inline_up': (up1, up2)}

# 2. Parse upgrade() / upgrade2() function calls from footer
upgrade_re = re.compile(r'upgrade2?\s*\(\s*troops\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"(?:\s*,\s*"([^"]+)")?\s*\)')

# Also parse commented-out upgrade calls (## upgrade(troops,...))
commented_re = re.compile(r'##\s*upgrade2?\s*\(\s*troops\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"(?:\s*,\s*"([^"]+)")?\s*\)')

# Parse the full file for upgrade calls
with open(src, 'r') as f:
    full_content = f.read()

all_calls = []

# Active upgrade calls
for m in upgrade_re.finditer(full_content):
    call_type = 'upgrade2' if 'upgrade2' in m.group(0) else 'upgrade'
    from_id = m.group(1)
    to1 = m.group(2)
    to2 = m.group(3) if m.lastindex and m.lastindex >= 3 else None
    all_calls.append(('active', call_type, from_id, to1, to2))

# Commented upgrade calls  
for m in commented_re.finditer(full_content):
    call_type = 'upgrade2' if 'upgrade2' in m.group(0) else 'upgrade'
    from_id = m.group(1)
    to1 = m.group(2)
    to2 = m.group(3) if m.lastindex and m.lastindex >= 3 else None
    # Skip if already captured as active
    already = any(c[2] == from_id and c[3] == to1 for c in all_calls)
    if not already:
        all_calls.append(('commented', call_type, from_id, to1, to2))

print 'Found %d upgrade calls (active + commented)' % len(all_calls)

# 3. Apply function calls to tree (override inline values if present)
# Function calls take precedence since they're more explicit
for status, ctype, from_id, to1, to2 in all_calls:
    if from_id in tree:
        info = tree[from_id]
        if ctype == 'upgrade':
            # Find which slot (upgrade1 or upgrade2) to set
            if info['upgrade1'] == '0':
                info['upgrade1'] = to1
            elif info['upgrade2'] == '0':
                info['upgrade2'] = to1
        else:  # upgrade2
            info['upgrade1'] = to1
            info['upgrade2'] = to2
    else:
        # Troop from function call but not in array (might be commented out troop)
        pass

# Add troops referenced only in upgrade calls but not in tree
for status, ctype, from_id, to1, to2 in all_calls:
    if from_id not in tree:
        tree[from_id] = {'name': '?', 'upgrade1': '0', 'upgrade2': '0', 'index': -1,
                         'fields': 0, 'inline_up': ('0','0'), '_from_call': True}

# 4. Statistics
total = len(tree)
inline_up = sum(1 for v in tree.values() if v['inline_up'][0] != '0' or v['inline_up'][1] != '0')
call_up = sum(1 for v in tree.values() if v.get('_from_call'))
with_upgrade = sum(1 for v in tree.values() if v['upgrade1'] != '0' or v['upgrade2'] != '0')

parents = {}
for tid, info in tree.items():
    for target in [info['upgrade1'], info['upgrade2']]:
        if target and target != '0':
            parents.setdefault(target, []).append(tid)

roots = [tid for tid in tree if tid not in parents]
leafs = [tid for tid, info in tree.items() 
         if info['upgrade1'] == '0' and info['upgrade2'] == '0']
branches = [(tid, info) for tid, info in tree.items() 
            if info['upgrade1'] != '0' and info['upgrade2'] != '0']
multi_parent = [(tid, p) for tid, p in parents.items() if len(p) > 1]

print 'Total troops: %d' % total
print 'Inline upgrades: %d' % inline_up
print 'From function calls: %d' % call_up
print 'Total with upgrades: %d' % with_upgrade
print 'Roots (no parent): %d' % len(roots)
print 'Leafs (no children): %d' % len(leafs)
print 'Branches (2 children): %d' % len(branches)
print 'Multi-parent troops: %d' % len(multi_parent)

# 5. Sample chains
print '\n--- Sample Chains ---'
shown = 0
for tid in roots[:80]:
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
        if len(chain) > 20:
            break
    if len(chain) > 1:
        shown += 1
        if shown <= 20:
            print '  %s' % ' -> '.join(chain)

# 6. Branches
print '\n--- Branches (2 children) ---'
for tid, info in branches[:15]:
    print '  %s -> %s / %s  (%s)' % (tid, info['upgrade1'], info['upgrade2'], info['name'])

# 7. Multi-parent
print '\n--- Multi-parent (top 15) ---'
sorted_mp = sorted(multi_parent, key=lambda x: -len(x[1]))
for tid, p in sorted_mp[:15]:
    info = tree.get(tid, {})
    print '  %s (%s) <- [%d] %s...' % (tid, info.get('name','?'), len(p), ', '.join(p[:3]))

# Save
with open('upgrade_tree.json', 'w') as f:
    json.dump(tree, f, indent=2, ensure_ascii=False)

# Save report
out = []
out.append('Total troops: %d' % total)
out.append('Inline upgrades: %d' % inline_up)
out.append('From function calls: %d' % call_up)
out.append('Total with upgrades: %d' % with_upgrade)
out.append('Roots: %d  Leafs: %d  Branches: %d  Multi-parent: %d' % (len(roots), len(leafs), len(branches), len(multi_parent)))

with open('upgrade_tree_report.txt', 'w') as f:
    f.write('\n'.join(out))

print '\nSaved upgrade_tree.json + upgrade_tree_report.txt'
