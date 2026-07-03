# -*- coding: utf-8 -*-
"""Extract upgrade tree from module_troops.py"""
import sys, os, json

sys.path.insert(0, 'C:/Users/Administrator/.qclaw/workspace-tfxjjhfnjialcuju/tianyou_editor')

# Suppress import prints
import io
_real_stdout = sys.stdout
sys.stdout = io.StringIO()
import tianyou_editor
sys.stdout = _real_stdout

src = 'G:/1_ruanjian/game/qikan/Mount&Blade Warband/Modules/Ahao/Module_system 1.171/module_troops.py'

# parse_array_by_lines takes filepath, returns (header, entries, footer)
header, entries, footer = tianyou_editor.parse_array_by_lines(src, 'troops')
fields_list = [tianyou_editor.parse_fields_in_entry(e) for e in entries]

tree = {}
for i, flds in enumerate(fields_list):
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
out.append('========== Upgrade Tree Analysis ==========')
out.append('Total troops: %d' % total)
out.append('With upgrades: %d' % with_upgrade)
out.append('Roots (no parent): %d' % len(roots))
out.append('Leafs (no children): %d' % len(leafs))
out.append('Branches (2 children): %d' % len(branches))
out.append('Multi-parent troops: %d' % len(multi_parent))

# Sample chains
out.append('\n--- Sample Upgrade Chains ---')
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
    if len(chain) > 2:
        shown += 1
        if shown <= 25:
            out.append('  %s' % ' -> '.join(chain))

# Branches
out.append('\n--- Branches (2 children) ---')
for tid, info in branches[:25]:
    out.append('  %s -> %s / %s  (%s)' % (tid, info['upgrade1'], info['upgrade2'], info['name']))

# Multi-parent
out.append('\n--- Multi-parent troops ---')
for tid, p in multi_parent[:20]:
    info = tree.get(tid, {})
    out.append('  %s (%s) <- [%d] %s...' % (tid, info.get('name','?'), len(p), ', '.join(p[:3])))

# Save JSON
with open('upgrade_tree.json', 'w') as f:
    json.dump(tree, f, indent=2, ensure_ascii=False)

# Save report
with open('upgrade_tree_report.txt', 'w') as f:
    f.write('\n'.join(out))

print 'Done.'
print 'Total: %d  Upgraded: %d  Roots: %d  Leafs: %d  Branches: %d  Multi-parent: %d' % (
    total, with_upgrade, len(roots), len(leafs), len(branches), len(multi_parent))
print 'Saved upgrade_tree.json + upgrade_tree_report.txt'
