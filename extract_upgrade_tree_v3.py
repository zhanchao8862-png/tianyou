# -*- coding: utf-8 -*-
"""Extract upgrade tree - output to file"""
import sys, os, json

sys.path.insert(0, 'C:/Users/Administrator/.qclaw/workspace-tfxjjhfnjialcuju/tianyou_editor')

# Redirect stdout
sys.stdout = open('NUL', 'w')
sys.stderr = open('NUL', 'w')
import tianyou_editor
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__

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

out = []
out.append('=== Upgrade Tree Analysis ===')
out.append('Total troops: %d' % total)
out.append('With upgrades: %d' % with_upgrade)
out.append('Roots (no parent): %d' % len(roots))
out.append('Leafs (no children): %d' % len(leafs))
out.append('Branches (2 children): %d' % len(branches))
out.append('Multi-parent troops: %d' % len(multi_parent))

out.append('\n=== Sample Chains ===')
shown = 0
for tid in roots[:50]:
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
            out.append('  %s' % ' -> '.join(chain))

out.append('\n=== Branches (2 children) ===')
for tid, info in branches[:20]:
    out.append('  %s -> %s / %s  (%s)' % (tid, info['upgrade1'], info['upgrade2'], info['name']))

out.append('\n=== Multi-parent troops ===')
for tid, p in multi_parent[:20]:
    info = tree.get(tid, {})
    out.append('  %s (%s) <- [%d parents] %s...' % (tid, info.get('name','?'), len(p), ', '.join(p[:3])))

with open('upgrade_tree.json', 'w') as f:
    json.dump(tree, f, indent=2, ensure_ascii=False)

with open('upgrade_tree_report.txt', 'w') as f:
    f.write('\n'.join(out))

print 'Done. See upgrade_tree_report.txt and upgrade_tree.json'
print 'Total troops: %d, With upgrades: %d, Roots: %d, Leafs: %d' % (total, with_upgrade, len(roots), len(leafs))
