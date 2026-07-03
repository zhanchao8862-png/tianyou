# -*- coding: utf-8 -*-
"""Extract upgrade tree using the editor's parser"""
import sys, os, json, io

# Suppress any prints during import
_old_stdout = sys.stdout
sys.stdout = io.StringIO()

sys.path.insert(0, 'C:/Users/Administrator/.qclaw/workspace-tfxjjhfnjialcuju/tianyou_editor')
import tianyou_editor

sys.stdout = _old_stdout

src_path = 'G:/1_ruanjian/game/qikan/Mount&Blade Warband/Modules/Ahao/Module_system 1.171/module_troops.py'
with open(src_path, 'r') as f:
    content = f.read()

entries, fields = tianyou_editor.parse_array_by_lines(content, 'troops')

tree = {}
for i, flds in enumerate(fields):
    if len(flds) >= 1:
        tid = flds[0].strip('"\'')
        up1 = flds[14].strip('"\'') if len(flds) > 14 else '0'
        up2 = flds[15].strip('"\'') if len(flds) > 15 else '0'
        name = flds[1].strip('"\'') if len(flds) > 1 else ''
        tree[tid] = {'name': name, 'upgrade1': up1, 'upgrade2': up2, 'index': i}

total = len(tree)
with_upgrade = sum(1 for v in tree.values() if v['upgrade1'] != '0' or v['upgrade2'] != '0')

# Parents map
parents = {}
for tid, info in tree.items():
    for target in [info['upgrade1'], info['upgrade2']]:
        if target and target != '0':
            parents.setdefault(target, []).append(tid)

roots = [tid for tid in tree if tid not in parents]
leafs = [tid for tid, info in tree.items() 
         if info['upgrade1'] == '0' and info['upgrade2'] == '0']

print 'Total troops: %d' % total
print 'With upgrades: %d' % with_upgrade
print 'Roots (no parent): %d' % len(roots)
print 'Leafs (no children): %d' % len(leafs)

# Show sample chains
print '\n=== Sample Chains ==='
shown = 0
for tid in roots[:30]:
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
        if shown <= 15:
            print '  %s' % ' -> '.join(chain)

# Branches (2 children)
branches = [(tid, info) for tid, info in tree.items() 
            if info['upgrade1'] != '0' and info['upgrade2'] != '0']
print '\nBranches (2 children): %d' % len(branches)
for tid, info in branches[:10]:
    print '  %s -> %s / %s  (%s)' % (tid, info['upgrade1'], info['upgrade2'], info['name'])

# Multi-parent
multi_parent = [(tid, p) for tid, p in parents.items() if len(p) > 1]
print '\nMulti-parent troops: %d' % len(multi_parent)
for tid, p in multi_parent[:10]:
    info = tree.get(tid, {})
    print '  %s (%s) <- [%d parents] %s' % (tid, info.get('name','?'), len(p), ', '.join(p[:4]))

# Save tree
with open('upgrade_tree.json', 'w') as f:
    json.dump(tree, f, indent=2, ensure_ascii=False)
print '\nSaved upgrade_tree.json (%d entries)' % len(tree)

# Stats by faction
print '\n=== Roots by first few ==='
for tid in roots[:20]:
    info = tree.get(tid, {})
    print '  %s (%s)' % (tid, info.get('name', '?'))
